"""Decompose the estimator inversion by abstention, and test the conditioning fix."""
import json
import pickle
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

import numpy as np
from sklearn.metrics import roc_auc_score

from wk.baseline_agent import grade

RESULTS = ROOT / "results"
SEED = 0
ARMS = ("closed_book", "concat_rag", "w_only", "k_only")


def estimators(arms):
    from lm_polygraph.estimators import (LexicalSimilarity,
                                         MaximumSequenceProbability,
                                         MeanTokenEntropy,
                                         MonteCarloSequenceEntropy)
    stats = {
        "greedy_log_likelihoods": [a["greedy_log_likelihoods"] for a in arms],
        "entropy": [a["entropy"] for a in arms],
        "sample_texts": [a["sample_texts"] for a in arms],
        "sample_log_probs": [a["sample_log_probs"] for a in arms],
    }
    out = {}
    for name, est in (("MeanTokenEntropy", MeanTokenEntropy()),
                      ("MonteCarloSequenceEntropy",
                       MonteCarloSequenceEntropy()),
                      ("LexicalSimilarity", LexicalSimilarity()),
                      ("MaximumSequenceProbability",
                       MaximumSequenceProbability())):
        vals = np.asarray(est(stats), dtype=float)
        out[name] = np.nan_to_num(vals, nan=float(np.nanmax(vals))
                                  if np.isfinite(vals).any() else 0.0)
    out["PTrue"] = -np.array([a["p_true"] for a in arms])
    return out


def auroc(y, score):
    y = np.asarray(y, dtype=int)
    if y.min() == y.max():
        return float("nan")
    return float(roc_auc_score(y, score))


def main():
    path = RESULTS / "baselines_raw_1.5b.pkl"
    rows = pickle.load(open(path, "rb"))
    for r in rows:
        for arm in ARMS:
            a = r["arms"][arm]
            a["correct"] = grade(a["answer"], r["golds"], r["q"].text)
            a["abstained_flag"] = a["answer"] is None
    test = [r for r in rows if r["split"] in ("test", "dev")]
    print(f"{len(test)} questions (test + dev), model 1.5B\n")

    report = {}
    for arm in ARMS:
        arms = [r["arms"][arm] for r in test]
        est = estimators(arms)
        abstained = np.array([a["abstained_flag"] for a in arms])
        correct = np.array([a["correct"] for a in arms], dtype=bool)
        if correct.sum() < 5 or abstained.mean() in (0.0, 1.0):
            print(f"=== {arm}: degenerate ===\n")
            continue
        ans = ~abstained
        print(f"=== {arm} ===  abstained {abstained.mean():.2f}, "
              f"accuracy {correct.mean():.3f}, "
              f"accuracy|answered {correct[ans].mean():.3f}")
        print(f"  {'estimator':<28}{'all':>7}{'answered':>10}"
              f"{'conditioned':>13}   mean score: abst / wrong / right")
        report[arm] = {}
        for name, raw in est.items():
            conf = -raw
            a_all = auroc(correct, conf)
            a_ans = auroc(correct[ans], conf[ans])
            floor = conf.min() - 1.0
            conditioned = np.where(abstained, floor, conf)
            a_cond = auroc(correct, conditioned)
            m_abst = float(raw[abstained].mean())
            m_wrong = float(raw[ans & ~correct].mean())
            m_right = float(raw[ans & correct].mean()) if (ans & correct).any() \
                else float("nan")
            print(f"  {name:<28}{a_all:>7.3f}{a_ans:>10.3f}{a_cond:>13.3f}"
                  f"   {m_abst:>7.2f} / {m_wrong:>6.2f} / {m_right:>6.2f}")
            report[arm][name] = {
                "auroc_all": a_all, "auroc_answered": a_ans,
                "auroc_conditioned": a_cond,
                "mean_raw_abstained": m_abst,
                "mean_raw_answered_wrong": m_wrong,
                "mean_raw_answered_right": m_right,
                "abstention_rate": float(abstained.mean())}
        print()

    json.dump(report, open(RESULTS / "inversion.json", "w"), indent=2)
    print(f"written {RESULTS / 'inversion.json'}")


if __name__ == "__main__":
    main()
