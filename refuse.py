"""Re-fuse the cached four-source run with per-question r and g, no LLM calls."""
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
from wk.fuse import decide, fuse

RESULTS = ROOT / "results"
PROBE = ("ce_top", "ce_margin", "ce_mean", "cos_top", "n_cand")
SOURCES = ("W", "K", "P", "M")


def cache(source):
    path = RESULTS / f"scored_{source}.pkl"
    if not path.exists():
        return {}
    return {r["qid"]: r for r in pickle.load(open(path, "rb"))}


def features(recs, source, caches):
    if source in ("W", "K"):
        return np.array([[caches[source][r["qid"]]["feat"][f] for f in PROBE]
                         for r in recs])
    return np.array([[r["per"][source]["lp"] or -9.0,
                      float(r["per"][source]["answer"] is None)]
                     for r in recs])


def fit(train, source, caches, target):
    y = np.array([target(r, source) for r in train], dtype=int)
    if y.min() == y.max():
        return None, float(y.mean())
    model = make_pipeline(StandardScaler(),
                          LogisticRegression(max_iter=2000))
    model.fit(features(train, source, caches), y)
    return model, float(y.mean())


def predict(model, marginal, recs, source, caches):
    if model is None:
        return np.full(len(recs), marginal)
    return model.predict_proba(features(recs, source, caches))[:, 1]


def crag_score(answered, correct):
    answered, correct = np.asarray(answered), np.asarray(correct)
    return float((correct.sum() - (answered & ~correct).sum()) / len(answered))


def line(name, answered, correct, member):
    answered = np.asarray(answered)
    correct = np.asarray(correct)
    member = np.asarray(member)
    return {"version": name,
            "r": float(correct[member].mean()) if member.any() else float("nan"),
            "precision": float(correct[answered].mean()) if answered.any()
            else float("nan"),
            "g": float((~member).mean()),
            "answered": float(answered.mean()),
            "bluff": float((answered & ~member).sum() / max((~member).sum(), 1)),
            "crag": crag_score(answered, correct)}


def main():
    rows = pickle.load(open(RESULTS / "four_source.pkl", "rb"))
    train = [r for r in rows if r["phase"] == "train"]
    test = [r for r in rows if r["phase"] == "test"]
    caches = {"W": cache("W"), "K": cache("K"), "P": {}, "M": {}}
    print(f"{len(train)} train / {len(test)} test questions")

    ghost, rely = {}, {}
    for s in SOURCES:
        ghost[s] = fit(train, s, caches, lambda r, s: r["per"][s]["member"])
        members = [r for r in train if r["per"][s]["member"]]
        rely[s] = (fit(members, s, caches, lambda r, s: r["per"][s]["correct"])
                   if len(members) >= 30 else (None, 0.5))

    g_hat = {s: 1.0 - predict(*ghost[s], test, s, caches) for s in SOURCES}
    r_hat = {s: predict(*rely[s], test, s, caches) for s in SOURCES}

    conf, cut = {}, {}
    for s in SOURCES:
        model, marginal = fit(train, s, caches,
                              lambda r, s: r["per"][s]["correct"])
        p_tr = predict(model, marginal, train, s, caches)
        ok_tr = np.array([r["per"][s]["correct"] for r in train], dtype=bool)
        said_tr = np.array([bool(r["per"][s]["answer"]) for r in train])
        best_t, best_s = 1.1, -9e9
        for cand in np.linspace(0.02, 0.98, 97):
            take = said_tr & (p_tr >= cand)
            score = crag_score(take, ok_tr & take)
            if score > best_s:
                best_t, best_s = float(cand), score
        conf[s] = predict(model, marginal, test, s, caches)
        cut[s] = best_t

    log = []
    for s in SOURCES:
        answered = np.array([bool(r["per"][s]["answer"]) for r in test])
        correct = np.array([r["per"][s]["correct"] for r in test])
        member = np.array([r["per"][s]["member"] for r in test])
        log.append(line(f"{s} alone", answered, correct, member))

    for s in SOURCES:
        said = np.array([bool(r["per"][s]["answer"]) for r in test])
        answered = said & (conf[s] >= cut[s])
        correct = np.array([r["per"][s]["correct"] for r in test]) & answered
        member = np.array([r["per"][s]["member"] for r in test])
        log.append(line(f"{s} + fitted threshold", answered, correct, member))

    for label, subset, conditional in (
            ("W+K marginal", ("W", "K"), False),
            ("W+K conditional", ("W", "K"), True),
            ("W+K+P conditional", ("W", "K", "P"), True),
            ("W+K+P+M conditional", ("W", "K", "P", "M"), True)):
        marg = {s: {"r": float(np.mean([r["per"][s]["correct"] for r in train
                                        if r["per"][s]["member"]] or [0.5])),
                    "g": float(np.mean([not r["per"][s]["member"]
                                        for r in train]))}
                for s in subset}
        answered, correct, member = [], [], []
        for i, r in enumerate(test):
            props = [(s, r["per"][s]["answer"]
                      if conf[s][i] >= cut[s] else None, None)
                     for s in subset]
            if conditional:
                w = {s: {"r": float(r_hat[s][i]), "g": float(g_hat[s][i])}
                     for s in subset}
            else:
                w = marg
            res = fuse(props, w)
            act, ans = decide(res)
            answered.append(act == "answer")
            correct.append(grade(ans, r["golds"], r["q"].text))
            member.append(any(r["per"][s]["member"] for s in subset))
        log.append(line(f"{label} fused", answered, correct, member))

    head = f"{'version':<26}{'r':>7}{'prec':>7}{'g':>7}{'ans':>7}{'bluff':>7}{'CRAG':>8}"
    print(f"\n{head}")
    for row in log:
        print(f"{row['version']:<26}{row['r']:>7.3f}{row['precision']:>7.3f}"
              f"{row['g']:>7.3f}{row['answered']:>7.3f}{row['bluff']:>7.3f}"
              f"{row['crag']:>8.3f}")
    json.dump(log, open(RESULTS / "refused.json", "w"), indent=2)
    print(f"\nwritten {RESULTS / 'refused.json'}")


if __name__ == "__main__":
    main()
