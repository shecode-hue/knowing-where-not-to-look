"""The second half of the independence experiment: same agent, tenfold corpus."""
import bz2
import json
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np

from wk import crag
from wk.baseline_agent import gold_answers, grade
from wk.semantic_agent import features, passages, score_question

RESULTS = ROOT / "results"
DATA = ROOT / "data" / "crag_task_1_and_2_dev_v5.jsonl.bz2"
MATCHED = ROOT / "data" / "task3" / "task3_matched.jsonl.bz2"
SEED = 0


def load_raw():
    raw = {}
    with bz2.open(MATCHED, "rt") as fh:
        for line in fh:
            item = json.loads(line)
            raw[str(item.get("interaction_id") or "")] = item
    return raw


def window_member(q, cands, item):
    hay = []
    for c in cands:
        hay.extend(crag._tokens(c))
    golds = [q.answer, *crag._alt_answers(item)]
    return any(crag.answer_present(g, q.text, hay) for g in golds)


def build(questions, source):
    rows, t0 = [], time.time()
    for i, q in enumerate(questions):
        ev = source.retrieve(q)
        cands = passages(ev)
        scored = score_question(q.text, cands)
        keep = scored["idx"]
        rows.append({
            "qid": q.qid, "q": q,
            "member": source.contains_answer(q, ev),
            "member_window": window_member(q, cands, source.item(q)),
            "golds": gold_answers(q),
            "texts": [cands[int(j)] for j in keep],
            "ce": scored["ce"], "cos": scored["cos"],
            "feat": features(scored),
            "n_items": len(ev.items), "n_cands": len(cands)})
        if i % 50 == 0:
            print(f"  W50 {i}/{len(questions)}  {time.time() - t0:.0f}s",
                  flush=True)
    pickle.dump(rows, open(RESULTS / "scored_W50.pkl", "wb"))
    print(f"W50: {len(rows)} -> scored_W50.pkl ({time.time() - t0:.0f}s)",
          flush=True)
    return rows


def correct_of(row):
    if not row["texts"]:
        return False
    top = row["texts"][int(np.argmax(row["ce"]))]
    return grade(top, row["golds"], row["q"].text)


def boot_delta(a, b, reps=5000):
    rng = np.random.default_rng(SEED)
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    n = len(a)
    d = [a[i].mean() - b[i].mean()
         for i in (rng.integers(0, n, n) for _ in range(reps))]
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def main():
    raw = load_raw()
    print(f"{len(raw)} fifty-page questions loaded", flush=True)
    questions = [q for q in crag.load_crag(DATA) if q.qid in raw]
    source = crag.CragWebSource(raw=raw)
    rows50 = build(questions, source)

    five = {r["qid"]: r for r in
            pickle.load(open(RESULTS / "scored_W.pkl", "rb"))}
    pairs = [(five[r["qid"]], r) for r in rows50 if r["qid"] in five]
    print(f"\n{len(pairs)} paired questions, identical agent throughout")

    m5 = np.array([p[0]["member"] for p in pairs], dtype=bool)
    m50 = np.array([p[1]["member"] for p in pairs], dtype=bool)
    c5 = np.array([correct_of(p[0]) for p in pairs], dtype=bool)
    c50 = np.array([correct_of(p[1]) for p in pairs], dtype=bool)
    w50 = np.array([p[1]["member_window"] for p in pairs], dtype=bool)

    g5, g50 = float((~m5).mean()), float((~m50).mean())
    lo_g, hi_g = boot_delta(~m50, ~m5)
    r5 = float(c5[m5].mean()) if m5.any() else float("nan")
    r50 = float(c50[m50].mean()) if m50.any() else float("nan")
    r50w = float(c50[w50].mean()) if w50.any() else float("nan")
    gained = int((m50 & ~m5).sum())
    lost = int((m5 & ~m50).sum())

    print(f"\n{'':<26}{'5 pages':>9}{'50 pages':>10}")
    print(f"{'ghost mass g':<26}{g5:>9.3f}{g50:>10.3f}   "
          f"delta {g50 - g5:+.3f}  [{lo_g:+.3f}, {hi_g:+.3f}]")
    print(f"{'reliability r (member)':<26}{r5:>9.3f}{r50:>10.3f}")
    print(f"{'r within agent window':<26}{'':>9}{r50w:>10.3f}   "
          f"(window holds {w50.mean():.2f} of questions)")
    print(f"membership flips: gained {gained}, lost {lost} of {len(pairs)}")

    print(f"\nby dynamism:")
    print(f"{'':<10}{'n':>5}{'g5':>8}{'g50':>8}{'delta':>8}")
    by_dyn = {}
    for dyn in ("static", "slow", "fast", "realtime"):
        idx = np.array([p[0]["q"].dynamism == dyn for p in pairs])
        if idx.sum() < 10:
            continue
        d5, d50 = float((~m5[idx]).mean()), float((~m50[idx]).mean())
        print(f"{dyn:<10}{int(idx.sum()):>5}{d5:>8.3f}{d50:>8.3f}"
              f"{d50 - d5:>+8.3f}")
        by_dyn[dyn] = {"n": int(idx.sum()), "g5": d5, "g50": d50}

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    feats = ("ce_top", "ce_margin", "ce_mean", "cos_top", "n_cand")
    X = np.array([[p[1]["feat"][f] for f in feats] + [p[1]["n_cands"]]
                  for p in pairs])
    y = m50.astype(int)
    rng = np.random.default_rng(SEED)
    idx = rng.permutation(len(pairs))
    half = len(pairs) // 2
    model = make_pipeline(StandardScaler(),
                          LogisticRegression(max_iter=2000))
    model.fit(X[idx[:half]], y[idx[:half]])
    p_hat = model.predict_proba(X[idx[half:]])[:, 1]
    auc = roc_auc_score(y[idx[half:]], p_hat)
    shuf = roc_auc_score(rng.permutation(y[idx[half:]]), p_hat)
    print(f"\nH2 on W with a varying corpus: membership predictable at "
          f"AUROC {auc:.3f} (shuffled {shuf:.3f})")

    json.dump({"n_pairs": len(pairs), "g5": g5, "g50": g50,
               "delta_ci": [lo_g, hi_g], "r5": r5, "r50": r50,
               "r50_window": r50w, "gained": gained, "lost": lost,
               "by_dynamism": by_dyn,
               "h2_w50_auroc": float(auc), "h2_shuffled": float(shuf)},
              open(RESULTS / "independence.json", "w"), indent=2)
    print(f"\nwritten {RESULTS / 'independence.json'}")


if __name__ == "__main__":
    main()
