"""Score the baselines with LM-Polygraph estimators and proper scoring rules."""
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
from sklearn.metrics import roc_auc_score

from wk import crag
from wk.baseline_agent import grade

RESULTS = ROOT / "results"
SEED = 0
NLI = "cross-encoder/nli-deberta-v3-small"
ARMS = ("closed_book", "concat_rag", "w_only", "k_only")


def entail_matrices(rows, arm, batch=128):
    import torch
    from transformers import (AutoModelForSequenceClassification,
                              AutoTokenizer)
    tok = AutoTokenizer.from_pretrained(NLI)
    model = AutoModelForSequenceClassification.from_pretrained(NLI).eval()
    labels = [l.lower() for l in model.config.id2label.values()]
    ent_idx = next(i for i, l in enumerate(labels) if "entail" in l)
    con_idx = next(i for i, l in enumerate(labels) if "contra" in l)

    pairs, index = [], []
    for qi, r in enumerate(rows):
        texts = r["arms"][arm]["sample_texts"]
        for a in range(len(texts)):
            for b in range(len(texts)):
                pairs.append((texts[a] or "(no answer)",
                              texts[b] or "(no answer)"))
                index.append((qi, a, b))

    n = len(rows[0]["arms"][arm]["sample_texts"])
    ent = np.zeros((len(rows), n, n))
    con = np.zeros((len(rows), n, n))
    with torch.no_grad():
        for start in range(0, len(pairs), batch):
            chunk = pairs[start:start + batch]
            enc = tok([p[0] for p in chunk], [p[1] for p in chunk],
                      return_tensors="pt", padding=True, truncation=True,
                      max_length=128)
            probs = torch.softmax(model(**enc).logits, dim=-1).numpy()
            for k, (qi, a, b) in enumerate(index[start:start + batch]):
                ent[qi, a, b] = probs[k, ent_idx]
                con[qi, a, b] = probs[k, con_idx]
    return ent, con


def estimator_scores(rows, arm, ent, con):
    from lm_polygraph.estimators import (DegMat, Eccentricity,
                                         LexicalSimilarity,
                                         MaximumSequenceProbability,
                                         MeanTokenEntropy,
                                         MonteCarloSequenceEntropy,
                                         NumSemSets)
    arms = [r["arms"][arm] for r in rows]
    stats = {
        "greedy_log_likelihoods": [a["greedy_log_likelihoods"] for a in arms],
        "entropy": [a["entropy"] for a in arms],
        "sample_texts": [a["sample_texts"] for a in arms],
        "sample_log_probs": [a["sample_log_probs"] for a in arms],
        "semantic_matrix_entail": ent,
        "semantic_matrix_contra": con,
    }
    out = {}
    for name, est in (("MaximumSequenceProbability",
                       MaximumSequenceProbability()),
                      ("MeanTokenEntropy", MeanTokenEntropy()),
                      ("MonteCarloSequenceEntropy",
                       MonteCarloSequenceEntropy()),
                      ("LexicalSimilarity", LexicalSimilarity()),
                      ("DegMat", DegMat()),
                      ("Eccentricity", Eccentricity()),
                      ("NumSemSets", NumSemSets())):
        try:
            vals = np.asarray(est(stats), dtype=float)
            out[name] = np.nan_to_num(vals, nan=float(np.nanmax(vals))
                                      if np.isfinite(vals).any() else 0.0)
        except Exception as e:
            print(f"    {name} failed: {type(e).__name__}: {e}")
    out["PTrue"] = -np.array([a["p_true"] for a in arms])
    verb = np.array([a["verbalised_confidence"] if
                     a["verbalised_confidence"] is not None else 0.5
                     for a in arms])
    out["VerbalisedConfidence"] = -verb
    return out


def murphy(conf, correct, bins=10):
    conf = np.clip(np.asarray(conf, dtype=float), 0, 1)
    correct = np.asarray(correct, dtype=float)
    base = correct.mean()
    edges = np.linspace(0, 1, bins + 1)
    rel = res = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf >= lo) & (conf < hi if hi < 1 else conf <= hi)
        if not m.sum():
            continue
        w = m.sum() / conf.size
        rel += w * (conf[m].mean() - correct[m].mean()) ** 2
        res += w * (correct[m].mean() - base) ** 2
    return {"brier": float(np.mean((conf - correct) ** 2)),
            "reliability": float(rel), "resolution": float(res),
            "uncertainty": float(base * (1 - base))}


def log_score(conf, correct, eps=1e-6):
    conf = np.clip(np.asarray(conf, dtype=float), eps, 1 - eps)
    correct = np.asarray(correct, dtype=float)
    return float(-np.mean(correct * np.log(conf)
                          + (1 - correct) * np.log(1 - conf)))


def ece(conf, correct, bins=10):
    conf = np.clip(np.asarray(conf, dtype=float), 0, 1)
    correct = np.asarray(correct, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf >= lo) & (conf < hi if hi < 1 else conf <= hi)
        if m.sum():
            total += (m.sum() / conf.size) * abs(correct[m].mean()
                                                 - conf[m].mean())
    return float(total)


def risk_coverage(conf, correct):
    order = np.argsort(-np.asarray(conf, dtype=float))
    ok = np.asarray(correct, dtype=float)[order]
    cov = np.arange(1, ok.size + 1) / ok.size
    risk = np.cumsum(1 - ok) / np.arange(1, ok.size + 1)
    return float(np.trapezoid(risk, cov))


def crag_score(answered, correct):
    answered = np.asarray(answered, dtype=bool)
    correct = np.asarray(correct, dtype=bool)
    return float((correct.sum() - (answered & ~correct).sum()) / answered.size)


def boot(fn, conf, correct, reps=2000):
    rng = np.random.default_rng(SEED)
    n = len(conf)
    vals = []
    for _ in range(reps):
        idx = rng.integers(0, n, n)
        try:
            vals.append(fn(np.asarray(conf)[idx], np.asarray(correct)[idx]))
        except Exception:
            continue
    if not vals:
        return float("nan"), float("nan")
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main():
    rows = pickle.load(open(RESULTS / "baselines_raw.pkl", "rb"))
    for r in rows:
        for arm in ARMS:
            a = r["arms"][arm]
            a["correct"] = grade(a["answer"], r["golds"], r["q"].text)
    cal = [r for r in rows if r["split"] == "calibration"]
    test = [r for r in rows if r["split"] == "test"]
    print(f"{len(rows)} questions: {len(cal)} calibration, {len(test)} test\n")

    report = {}
    for arm in ARMS:
        print(f"=== {arm} ===")
        acc = np.mean([r["arms"][arm]["correct"] for r in test])
        ans = np.mean([bool(r["arms"][arm]["answer"]) for r in test])
        print(f"  accuracy {acc:.3f}, answered {ans:.3f}")
        ent_c, con_c = entail_matrices(cal, arm)
        ent_t, con_t = entail_matrices(test, arm)
        sc_cal = estimator_scores(cal, arm, ent_c, con_c)
        sc_test = estimator_scores(test, arm, ent_t, con_t)
        y_cal = np.array([r["arms"][arm]["correct"] for r in cal], dtype=float)
        y_test = np.array([r["arms"][arm]["correct"] for r in test],
                          dtype=float)

        print(f"  {'estimator':<28}{'AUROC':>7}{'Brier':>8}{'rel':>7}"
              f"{'res':>7}{'ECE':>7}{'log':>7}{'RC-AUC':>8}")
        report[arm] = {"accuracy": float(acc), "answered": float(ans),
                       "estimators": {}}
        for name in sorted(sc_test):
            raw_cal, raw_test = sc_cal.get(name), sc_test.get(name)
            if raw_cal is None or raw_test is None:
                continue
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
            iso.fit(-raw_cal, y_cal)
            conf = iso.predict(-raw_test)
            try:
                auc = roc_auc_score(y_test, -raw_test)
            except ValueError:
                auc = float("nan")
            m = murphy(conf, y_test)
            entry = {"auroc": float(auc), **m, "ece": ece(conf, y_test),
                     "log_score": log_score(conf, y_test),
                     "rc_auc": risk_coverage(conf, y_test),
                     "crag_at_half": crag_score(conf >= 0.5,
                                                y_test.astype(bool)
                                                & (conf >= 0.5))}
            lo, hi = boot(lambda c, y: roc_auc_score(y, c)
                          if len(set(y)) > 1 else float("nan"),
                          conf, y_test)
            entry["auroc_ci"] = [lo, hi]
            report[arm]["estimators"][name] = entry
            print(f"  {name:<28}{auc:>7.3f}{m['brier']:>8.3f}"
                  f"{m['reliability']:>7.3f}{m['resolution']:>7.3f}"
                  f"{entry['ece']:>7.3f}{entry['log_score']:>7.3f}"
                  f"{entry['rc_auc']:>8.3f}")
        print()

    json.dump(report, open(RESULTS / "baseline_scores.json", "w"), indent=2)
    print(f"written {RESULTS / 'baseline_scores.json'}")


if __name__ == "__main__":
    main()
