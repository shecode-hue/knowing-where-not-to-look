"""H4: marginal split conformal against per-KAP-cell (Mondrian) conformal."""
import json
import pickle
import sys
import warnings
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

import numpy as np
from sklearn.isotonic import IsotonicRegression

from wk.baseline_agent import grade

RESULTS = ROOT / "results"
SEED = 0
ALPHA = 0.10
ARMS = ("closed_book", "concat_rag", "w_only", "k_only")
SCORE = "PTrue"


def kap_cell(q):
    recency = "moving" if q.dynamism in ("fast", "realtime") else "settled"
    popularity = "tail" if q.popularity in ("tail", "torso") else "head"
    hops = "multi" if (q.n_hops or 1) > 1 else "single"
    return f"{recency}/{popularity}/{hops}"


def confidence(rows, arm):
    return np.array([r["arms"][arm]["p_true"] for r in rows], dtype=float)


def nonconformity(conf):
    return 1.0 - np.asarray(conf, dtype=float)


def marginal_threshold(scores, alpha=ALPHA):
    n = len(scores)
    if n == 0:
        return 1.0
    k = int(np.ceil((n + 1) * (1 - alpha)))
    k = min(max(k, 1), n)
    return float(np.sort(scores)[k - 1])


def coverage_and_size(scores, correct, threshold):
    inside = scores <= threshold
    covered = np.mean(inside[correct]) if correct.any() else float("nan")
    return float(covered), float(np.mean(inside))


def main():
    rows = pickle.load(open(RESULTS / "baselines_raw.pkl", "rb"))
    for r in rows:
        r["cell"] = kap_cell(r["q"])
        for arm in ARMS:
            r["arms"][arm]["correct"] = grade(r["arms"][arm]["answer"],
                                              r["golds"], r["q"].text)
    cal = [r for r in rows if r["split"] == "calibration"]
    test = [r for r in rows if r["split"] == "test"]
    print(f"{len(cal)} calibration, {len(test)} test, target coverage "
          f"{1 - ALPHA:.0%}, score = {SCORE}\n")

    report = {}
    for arm in ARMS:
        y_cal = np.array([r["arms"][arm]["correct"] for r in cal], dtype=bool)
        y_test = np.array([r["arms"][arm]["correct"] for r in test],
                          dtype=bool)
        if y_cal.sum() < 10 or y_test.sum() < 5:
            print(f"=== {arm}: too few correct answers to calibrate ===\n")
            continue

        iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
        iso.fit(confidence(cal, arm), y_cal)
        s_cal = nonconformity(iso.predict(confidence(cal, arm)))
        s_test = nonconformity(iso.predict(confidence(test, arm)))

        t_marg = marginal_threshold(s_cal[y_cal])
        cells = sorted({r["cell"] for r in rows})
        t_cell = {}
        for c in cells:
            mask = np.array([r["cell"] == c for r in cal]) & y_cal
            t_cell[c] = (marginal_threshold(s_cal[mask]) if mask.sum() >= 10
                         else t_marg)

        print(f"=== {arm} ===")
        print(f"{'KAP cell':<24}{'n':>5}{'marginal cov':>14}{'size':>7}"
              f"{'per-cell cov':>14}{'size':>7}")
        report[arm] = {"marginal_threshold": t_marg, "cells": {}}
        rows_m, rows_c = [], []
        for c in cells:
            idx = np.array([r["cell"] == c for r in test])
            if idx.sum() < 8:
                continue
            ok = y_test[idx]
            if not ok.any():
                continue
            cov_m, size_m = coverage_and_size(s_test[idx], ok, t_marg)
            cov_c, size_c = coverage_and_size(s_test[idx], ok, t_cell[c])
            miss_m = cov_m < (1 - ALPHA)
            flag = "  <- misses" if miss_m else ""
            print(f"{c:<24}{int(idx.sum()):>5}{cov_m:>14.3f}{size_m:>7.3f}"
                  f"{cov_c:>14.3f}{size_c:>7.3f}{flag}")
            report[arm]["cells"][c] = {
                "n": int(idx.sum()), "marginal_coverage": cov_m,
                "marginal_size": size_m, "percell_coverage": cov_c,
                "percell_size": size_c}
            rows_m.append(cov_m)
            rows_c.append(cov_c)

        cov_all, size_all = coverage_and_size(s_test, y_test, t_marg)
        print(f"{'overall':<24}{len(test):>5}{cov_all:>14.3f}{size_all:>7.3f}")
        if rows_m:
            worst_m, worst_c = min(rows_m), min(rows_c)
            n_miss_m = sum(c < (1 - ALPHA) for c in rows_m)
            n_miss_c = sum(c < (1 - ALPHA) for c in rows_c)
            print(f"  worst cell: marginal {worst_m:.3f}, "
                  f"per-cell {worst_c:.3f}")
            print(f"  cells below target: marginal {n_miss_m}/{len(rows_m)}, "
                  f"per-cell {n_miss_c}/{len(rows_c)}")
            report[arm]["summary"] = {
                "overall_coverage": cov_all, "worst_marginal": worst_m,
                "worst_percell": worst_c, "cells_missed_marginal": n_miss_m,
                "cells_missed_percell": n_miss_c, "n_cells": len(rows_m)}
        print()

    json.dump(report, open(RESULTS / "conformal.json", "w"), indent=2)
    print(f"written {RESULTS / 'conformal.json'}")


if __name__ == "__main__":
    main()
