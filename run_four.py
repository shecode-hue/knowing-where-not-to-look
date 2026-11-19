"""Run all four sources with an LLM reader, fuse them, and score the result."""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from wk import crag, llm
from wk.baseline_agent import grade
from wk.fuse import decide, fuse
from wk.kg_source import KBSource
from wk.pm_sources import MemorySource, ParametricSource

RESULTS = ROOT / "results"
DATA = ROOT / "data" / "crag_task_1_and_2_dev_v5.jsonl.bz2"
SEED = 0


def ranked_passages(row, k=6):
    order = np.argsort(row["ce"])[::-1][:k]
    return [row["texts"][i] for i in order]


def cached(source):
    path = RESULTS / f"scored_{source}.pkl"
    if not path.exists():
        return {}
    return {r["qid"]: r for r in pickle.load(open(path, "rb"))}


PROBE = ("ce_top", "ce_margin", "ce_mean", "cos_top", "n_cand")


def probe_matrix(recs, source, cache):
    if source in ("W", "K"):
        return np.array([[cache[r["qid"]]["feat"][f] for f in PROBE]
                         for r in recs])
    lp = np.array([[r["per"][source]["lp"] or -9.0,
                    float(r["per"][source]["answer"] is None)]
                   for r in recs])
    return lp


def fit_ghost(train, source, cache):
    y = np.array([r["per"][source]["member"] for r in train], dtype=int)
    if y.min() == y.max():
        return None, float(1.0 - y.mean())
    model = make_pipeline(StandardScaler(),
                          LogisticRegression(max_iter=2000))
    model.fit(probe_matrix(train, source, cache), y)
    return model, float(1.0 - y.mean())


def weights_from(rows):
    out = {}
    for source, recs in rows.items():
        member = np.array([r["member"] for r in recs], dtype=bool)
        correct = np.array([r["correct"] for r in recs], dtype=bool)
        out[source] = {
            "r": float(correct[member].mean()) if member.any() else 0.5,
            "g": float((~member).mean())}
    return out


def crag_score(answered, correct):
    answered, correct = np.asarray(answered), np.asarray(correct)
    return float((correct.sum() - (answered & ~correct).sum()) / len(answered))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--passes", type=int, default=2)
    ap.add_argument("--threshold", type=float, default=0.5)
    args = ap.parse_args()

    llm.start()
    print(f"model {llm.model_path().name}", flush=True)

    qs = crag.load_crag(DATA)
    w_cache, k_cache = cached("W"), cached("K")
    shared = [q for q in qs if q.qid in w_cache and q.qid in k_cache]
    rng = np.random.default_rng(SEED)
    rng.shuffle(shared)
    sample = shared[:args.n]
    half = len(sample) // 2
    train, test = sample[:half], sample[half:]
    print(f"{len(sample)} questions in both caches, "
          f"{len(train)} train / {len(test)} test", flush=True)

    kb = KBSource()
    para = ParametricSource()
    mem = MemorySource(store={})
    rows = []
    t0 = time.time()

    for phase, qset in (("train", train), ("test", test)):
        for i, q in enumerate(qset):
            golds = crag.gold_answers(q)
            per = {}

            for source, cache in (("W", w_cache), ("K", k_cache)):
                row = cache[q.qid]
                passages = ranked_passages(row)
                out = llm.read(q.text, passages)
                per[source] = {
                    "answer": out["answer"], "lp": out["mean_logprob"],
                    "member": bool(row["member"]),
                    "correct": grade(out["answer"], golds, q.text)}

            pout = llm.recall(q.text)
            knows = grade(pout["raw"], golds, q.text)
            if not knows:
                for s in range(1, 5):
                    alt = llm.recall(q.text, seed=s, temperature=0.8)
                    if grade(alt["raw"], golds, q.text):
                        knows = True
                        break
            per["P"] = {
                "answer": pout["answer"], "lp": pout["mean_logprob"],
                "member": knows,
                "correct": grade(pout["answer"], golds, q.text)}

            mev = mem.retrieve(q)
            mrun = mem.run(q, mev)
            m_answer = next((a for a in mrun.answers if a), None)
            per["M"] = {
                "answer": m_answer, "lp": None,
                "member": mem.contains_answer(q, mev),
                "correct": any(mrun.correct)}

            rows.append({"qid": q.qid, "q": q, "phase": phase, "per": per,
                         "golds": golds})

            best = max(("W", "K", "P"),
                       key=lambda s: per[s]["lp"] if per[s]["answer"]
                       and per[s]["lp"] is not None else -9e9)
            if per[best]["answer"]:
                mem.remember(q, per[best]["answer"], per[best]["lp"])

            if (i + 1) % 25 == 0:
                print(f"  {phase} {i + 1}/{len(qset)}  "
                      f"{time.time() - t0:.0f}s", flush=True)

    llm.stop()
    mem.flush()
    pickle.dump(rows, open(RESULTS / "four_source.pkl", "wb"))

    by_phase = {"train": [r for r in rows if r["phase"] == "train"],
                "test": [r for r in rows if r["phase"] == "test"]}
    per_source_train = {s: [{"member": r["per"][s]["member"],
                             "correct": r["per"][s]["correct"]}
                            for r in by_phase["train"]]
                        for s in ("W", "K", "P", "M")}
    weights = weights_from(per_source_train)
    caches = {"W": w_cache, "K": k_cache, "P": {}, "M": {}}
    ghost_models = {}
    for s in ("W", "K", "P"):
        ghost_models[s] = fit_ghost(by_phase["train"], s, caches[s])

    log = []
    for s in ("W", "K", "P", "M"):
        recs = by_phase["test"]
        member = np.array([r["per"][s]["member"] for r in recs], dtype=bool)
        correct = np.array([r["per"][s]["correct"] for r in recs], dtype=bool)
        answered = np.array([bool(r["per"][s]["answer"]) for r in recs])
        log.append({
            "version": f"{s} alone, LLM reader",
            "r": round(float(correct[member].mean()) if member.any()
                       else float("nan"), 4),
            "g": round(float((~member).mean()), 4),
            "answered": round(float(answered.mean()), 4),
            "bluff_rate": round(float((answered & ~member).sum()
                                      / max((~member).sum(), 1)), 4),
            "crag_score": round(crag_score(answered, correct & answered), 4)})

    for label, subset in (("W+K", ("W", "K")),
                          ("W+K+P", ("W", "K", "P")),
                          ("W+K+P+M", ("W", "K", "P", "M"))):
        answered, correct, member = [], [], []
        g_hat = {}
        for s in subset:
            model, marginal = ghost_models.get(s, (None, None)) or (None, None)
            if model is None:
                g_hat[s] = np.full(len(by_phase["test"]),
                                   marginal if marginal is not None
                                   else weights[s]["g"])
            else:
                p_member = model.predict_proba(
                    probe_matrix(by_phase["test"], s, caches[s]))[:, 1]
                g_hat[s] = 1.0 - p_member
        for idx, r in enumerate(by_phase["test"]):
            props = [(s, r["per"][s]["answer"],
                      float(np.exp(r["per"][s]["lp"]))
                      if r["per"][s]["lp"] is not None else 0.5)
                     for s in subset]
            local = {s: {"r": weights[s]["r"], "g": float(g_hat[s][idx])}
                     for s in subset}
            res = fuse(props, local)
            act, ans = decide(res, args.threshold)
            ok = grade(ans, r["golds"], r["q"].text)
            answered.append(act == "answer")
            correct.append(ok)
            member.append(any(r["per"][s]["member"] for s in subset))
        answered = np.array(answered)
        correct = np.array(correct)
        member = np.array(member)
        log.append({
            "version": f"{label} fused",
            "r": round(float(correct[member].mean()) if member.any()
                       else float("nan"), 4),
            "g": round(float((~member).mean()), 4),
            "answered": round(float(answered.mean()), 4),
            "bluff_rate": round(float((answered & ~member).sum()
                                      / max((~member).sum(), 1)), 4),
            "crag_score": round(crag_score(answered, correct), 4)})

    print(f"\n{'version':<30}{'r':>7}{'g':>7}{'ans':>7}{'bluff':>7}{'CRAG':>8}")
    for row in log:
        print(f"{row['version']:<30}{row['r']:>7.3f}{row['g']:>7.3f}"
              f"{row['answered']:>7.3f}{row['bluff_rate']:>7.3f}"
              f"{row['crag_score']:>8.3f}")
    json.dump({"weights": weights, "versions": log},
              open(RESULTS / "four_source.json", "w"), indent=2)
    print(f"\nwritten {RESULTS / 'four_source.json'}")


if __name__ == "__main__":
    main()
