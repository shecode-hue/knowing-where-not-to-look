"""Fit a confidence model, calibrate abstention, and score every agent version."""
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from wk.baseline_agent import grade

RESULTS = ROOT / "results"
FEATURES = ("ce_top", "ce_margin", "ce_mean", "cos_top", "n_cand")
SEED = 0


def load(source):
    rows = pickle.load(open(RESULTS / f"scored_{source}.pkl", "rb"))
    for r in rows:
        r["correct"] = bool(r["texts"]) and grade(
            r["texts"][int(np.argmax(r["ce"]))], r["golds"], r["q"].text)
        r["top1"] = r["texts"][int(np.argmax(r["ce"]))] if r["texts"] else None
    return rows


def split(rows, frac=0.5):
    rng = np.random.default_rng(SEED)
    mask = rng.random(len(rows)) < frac
    return [r for r, m in zip(rows, mask) if m], \
           [r for r, m in zip(rows, mask) if not m]


def matrix(rows):
    return np.array([[r["feat"][f] for f in FEATURES] for r in rows])


def crag_score(answered, correct):
    answered, correct = np.asarray(answered), np.asarray(correct)
    return float((correct.sum() - (answered & ~correct).sum()) / len(answered))


def report(name, rows, answered, extra=None):
    correct = np.array([r["correct"] for r in rows]) & answered
    member = np.array([r["member"] for r in rows])
    present = member.sum()
    r_val = correct[member].mean() if present else float("nan")
    bluff = (answered & ~member).sum() / max((~member).sum(), 1)
    out = {"version": name, "n": len(rows),
           "r": round(float(r_val), 4),
           "g": round(float((~member).mean()), 4),
           "answered": round(float(answered.mean()), 4),
           "bluff_rate": round(float(bluff), 4),
           "crag_score": round(crag_score(answered, correct), 4)}
    if extra:
        out.update(extra)
    return out


def main():
    log, thresholds = [], {}
    for source in ("W", "K"):
        path = RESULTS / f"scored_{source}.pkl"
        if not path.exists():
            print(f"skipping {source}, no cache")
            continue
        rows = load(source)
        train, test = split(rows)
        always = np.ones(len(test), dtype=bool)

        log.append(report(f"{source}: semantic, always answer", test, always))

        ce = np.array([r["feat"]["ce_top"] for r in test])
        tr_ce = np.array([r["feat"]["ce_top"] for r in train])
        tr_ok = np.array([r["correct"] for r in train])
        best_t, best_s = None, -9e9
        for t in np.quantile(tr_ce, np.linspace(0, 0.98, 60)):
            s = crag_score(tr_ce >= t, tr_ok & (tr_ce >= t))
            if s > best_s:
                best_t, best_s = float(t), s
        log.append(report(f"{source}: + score threshold", test, ce >= best_t,
                          {"threshold": round(best_t, 3)}))

        model = make_pipeline(StandardScaler(),
                              LogisticRegression(max_iter=2000))
        model.fit(matrix(train), tr_ok)
        p_test = model.predict_proba(matrix(test))[:, 1]
        p_train = model.predict_proba(matrix(train))[:, 1]
        best_p, best_s = 0.5, -9e9
        for t in np.linspace(0.05, 0.95, 91):
            s = crag_score(p_train >= t, tr_ok & (p_train >= t))
            if s > best_s:
                best_p, best_s = float(t), s
        log.append(report(f"{source}: + confidence model", test,
                          p_test >= best_p, {"threshold": round(best_p, 3)}))
        thresholds[source] = best_p
        for cov in (0.10, 0.25, 0.50):
            cut = float(np.quantile(p_test, 1 - cov))
            log.append(report(f"{source}: answer top {cov:.0%} by confidence",
                              test, p_test >= cut))
        for r, p in zip(test, p_test):
            r["p"] = float(p)
        for r, p in zip(train, p_train):
            r["p"] = float(p)
        pickle.dump({"train": train, "test": test},
                    open(RESULTS / f"split_{source}.pkl", "wb"))

    wp, kp = RESULTS / "split_W.pkl", RESULTS / "split_K.pkl"
    if wp.exists() and kp.exists():
        w = {r["qid"]: r for r in pickle.load(open(wp, "rb"))["test"]}
        k = {r["qid"]: r for r in pickle.load(open(kp, "rb"))["test"]}
        both = [(w[q], k[q]) for q in w.keys() & k.keys()]
        rows, answered = [], []
        for a, b in both:
            pick = a if a["p"] >= b["p"] else b
            rows.append({"correct": pick["correct"],
                         "member": a["member"] or b["member"],
                         "feat": pick["feat"], "q": pick["q"]})
            answered.append(a["p"] >= thresholds.get("W", 0.5)
                            or b["p"] >= thresholds.get("K", 0.5))
        log.append(report("W+K: pick the more confident source", rows,
                          np.array(answered)))
        for name, src in (("W only, same questions", 0), ("K only, same", 1)):
            sub = [{"correct": p[src]["correct"],
                    "member": p[src]["member"], "feat": p[src]["feat"],
                    "q": p[src]["q"]} for p in both]
            key = "W" if src == 0 else "K"
            ans = np.array([p[src]["p"] >= thresholds.get(key, 0.5)
                            for p in both])
            log.append(report(name, sub, ans))

    print(f"\n{'version':<38}{'r':>7}{'g':>7}{'ans':>7}{'bluff':>7}{'CRAG':>8}")
    for row in log:
        print(f"{row['version']:<38}{row['r']:>7.3f}{row['g']:>7.3f}"
              f"{row['answered']:>7.3f}{row['bluff_rate']:>7.3f}"
              f"{row['crag_score']:>8.3f}")
    json.dump(log, open(RESULTS / "agent_versions.json", "w"), indent=2)
    print(f"\nwritten {RESULTS / 'agent_versions.json'}")


if __name__ == "__main__":
    main()
