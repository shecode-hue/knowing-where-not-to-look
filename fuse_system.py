"""H3 end to end: source-resolved fusion with abstention against concatenation."""
import json
import pickle
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

import numpy as np
from sklearn.isotonic import IsotonicRegression

from wk import crag
from wk.baseline_agent import grade

RESULTS = ROOT / "results"
SEED = 0
SOURCES = {"P": "closed_book", "W": "w_only", "K": "k_only"}
RIVAL = "concat_rag"


def kap_cell(q):
    recency = "moving" if q.dynamism in ("fast", "realtime") else "settled"
    popularity = "tail" if q.popularity in ("tail", "torso") else "head"
    hops = "multi" if (q.n_hops or 1) > 1 else "single"
    return f"{recency}/{popularity}/{hops}"


def crag_score(answered, correct):
    answered = np.asarray(answered, dtype=bool)
    correct = np.asarray(correct, dtype=bool)
    return float((correct.sum() - (answered & ~correct).sum()) / answered.size)


def fit_conf(cal, arm):
    x = np.array([r["arms"][arm]["p_true"] for r in cal])
    y = np.array([r["arms"][arm]["correct"] for r in cal], dtype=float)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
    iso.fit(x, y)
    return iso


def conf_of(iso, rows, arm):
    p = iso.predict(np.array([r["arms"][arm]["p_true"] for r in rows]))
    gone = np.array([r["arms"][arm]["answer"] is None for r in rows])
    return np.where(gone, 0.0, p)


def fit_threshold(conf, correct, answered):
    best_t, best_s = 1.1, -9e9
    for t in np.linspace(0.02, 0.98, 97):
        take = answered & (conf >= t)
        s = crag_score(take, correct & take)
        if s > best_s:
            best_t, best_s = float(t), s
    return best_t


def ds_fuse(entries):
    focal = {None: 1.0}
    for answer, conf in entries:
        m = {answer: conf, None: 1.0 - conf}
        combined, kappa = {}, 0.0
        for a_key, a_val in focal.items():
            for b_key, b_val in m.items():
                mass = a_val * b_val
                if a_key is not None and b_key is not None and a_key != b_key:
                    kappa += mass
                    continue
                tgt = a_key if a_key is not None else b_key
                combined[tgt] = combined.get(tgt, 0.0) + mass
        scale = 1.0 - kappa
        focal = ({k: v / scale for k, v in combined.items()}
                 if scale > 1e-12 else {None: 1.0})
    named = {k: v for k, v in focal.items() if k is not None}
    if not named:
        return None, 0.0
    best = max(named, key=named.get)
    return best, named[best]


def line(name, test, answered, correct, member=None):
    answered = np.asarray(answered, dtype=bool)
    correct = np.asarray(correct, dtype=bool) & answered
    wrong = answered & ~correct
    out = {"version": name,
           "answered": float(answered.mean()),
           "n_correct": int(correct.sum()), "n_wrong": int(wrong.sum()),
           "precision": float(correct[answered].mean())
           if answered.any() else float("nan"),
           "crag": crag_score(answered, correct)}
    if member is not None:
        member = np.asarray(member, dtype=bool)
        out["bluff"] = float((answered & ~member).sum()
                             / max((~member).sum(), 1))
    return out


def main():
    rows = pickle.load(open(RESULTS / "baselines_raw.pkl", "rb"))
    for r in rows:
        r["cell"] = kap_cell(r["q"])
        for arm in list(SOURCES.values()) + [RIVAL]:
            a = r["arms"][arm]
            a["correct"] = grade(a["answer"], r["golds"], r["q"].text)
    cal = [r for r in rows if r["split"] == "calibration"]
    test = [r for r in rows if r["split"] == "test"]
    member_w = {q["qid"]: q["member"] for q in
                pickle.load(open(RESULTS / "scored_W.pkl", "rb"))}
    member_k = {q["qid"]: q["member"] for q in
                pickle.load(open(RESULTS / "scored_K.pkl", "rb"))}
    any_member = np.array(
        [member_w.get(r["qid"], False) or member_k.get(r["qid"], False)
         or r["arms"]["closed_book"]["correct"] for r in test])
    print(f"{len(cal)} calibration, {len(test)} test\n")

    iso, cut, conf_t = {}, {}, {}
    for s, arm in list(SOURCES.items()) + [("RAG", RIVAL)]:
        iso[s] = fit_conf(cal, arm)
        c_cal = conf_of(iso[s], cal, arm)
        y_cal = np.array([r["arms"][arm]["correct"] for r in cal])
        a_cal = np.array([r["arms"][arm]["answer"] is not None for r in cal])
        cut[s] = fit_threshold(c_cal, y_cal, a_cal)
        conf_t[s] = conf_of(iso[s], test, arm)

    log = []
    oracle_ans, oracle_ok = [], []
    for r in test:
        ok = [r["arms"][arm]["correct"] for arm in SOURCES.values()]
        oracle_ans.append(any(r["arms"][arm]["answer"] is not None
                              for arm in SOURCES.values()))
        oracle_ok.append(any(ok))
    log.append(line("oracle routing over P, W, K", test,
                    oracle_ans, oracle_ok, any_member))

    for s, arm in list(SOURCES.items()) + [("RAG", RIVAL)]:
        answered = np.array([r["arms"][arm]["answer"] is not None
                             for r in test]) & (conf_t[s] >= cut[s])
        correct = np.array([r["arms"][arm]["correct"] for r in test])
        label = (f"{s} alone, calibrated threshold" if s != "RAG"
                 else "concatenation RAG, same treatment")
        log.append(line(label, test, answered, correct, any_member))

    fused_ans, fused_ok = [], []
    for i, r in enumerate(test):
        entries = []
        for s, arm in SOURCES.items():
            ans = r["arms"][arm]["answer"]
            if ans is not None and conf_t[s][i] >= cut[s]:
                entries.append((" ".join(crag._tokens(ans)),
                                float(conf_t[s][i])))
        raw_map = {" ".join(crag._tokens(r["arms"][arm]["answer"])):
                   r["arms"][arm]["answer"]
                   for arm in SOURCES.values()
                   if r["arms"][arm]["answer"]}
        best, belief = ds_fuse(entries)
        take = best is not None and belief > 0.5
        fused_ans.append(take)
        fused_ok.append(grade(raw_map.get(best), r["golds"], r["q"].text)
                        if take else False)
    log.append(line("DS fusion of gated sources", test,
                    fused_ans, fused_ok, any_member))

    head = (f"{'version':<34}{'ans':>7}{'right':>7}{'wrong':>7}"
            f"{'prec':>7}{'bluff':>7}{'CRAG':>8}")
    print(head)
    for row in log:
        print(f"{row['version']:<34}{row['answered']:>7.3f}"
              f"{row['n_correct']:>7d}{row['n_wrong']:>7d}"
              f"{row['precision']:>7.3f}{row.get('bluff', float('nan')):>7.3f}"
              f"{row['crag']:>8.3f}")

    fused_ans = np.array(fused_ans)
    fused_ok = np.array(fused_ok)
    rag_ans = (np.array([r["arms"][RIVAL]["answer"] is not None
                         for r in test]) & (conf_t["RAG"] >= cut["RAG"]))
    rag_ok = np.array([r["arms"][RIVAL]["correct"] for r in test]) & rag_ans
    print(f"\nper KAP cell, CRAG score, fusion vs concatenation:")
    cells = sorted({r["cell"] for r in test})
    per_cell = {}
    for c in cells:
        m = np.array([r["cell"] == c for r in test])
        if m.sum() < 15:
            continue
        f = crag_score(fused_ans[m], fused_ok[m])
        g = crag_score(rag_ans[m], rag_ok[m])
        per_cell[c] = {"n": int(m.sum()), "fusion": f, "concat": g}
        print(f"  {c:<24}{int(m.sum()):>4}   fusion {f:+.3f}   "
              f"concat {g:+.3f}")

    json.dump({"rows": log, "thresholds": cut, "per_cell": per_cell},
              open(RESULTS / "h3_system.json", "w"), indent=2)
    print(f"\nwritten {RESULTS / 'h3_system.json'}")


if __name__ == "__main__":
    main()
