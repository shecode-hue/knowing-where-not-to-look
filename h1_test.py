"""Test H1: agreement-based confidence is over-confident in the tail cells."""
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np

from wk import crag

RESULTS = ROOT / "results"
DATA = ROOT / "data" / "crag_task_1_and_2_dev_v5.jsonl.bz2"
SEED = 0
TAIL = {"popularity": ("tail",), "dynamism": ("fast", "realtime"),
        "n_hops": (2, 3, 4, 5)}


def boot_ci(values, reps=5000):
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(SEED)
    draws = rng.choice(arr, size=(reps, arr.size), replace=True).mean(axis=1)
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def gap(rows):
    conf = np.array([r["agreement"] for r in rows])
    acc = np.array([r["majority_correct"] for r in rows], dtype=float)
    return conf - acc


def ece(rows, bins=10):
    conf = np.array([r["agreement"] for r in rows])
    acc = np.array([r["majority_correct"] for r in rows], dtype=float)
    if conf.size == 0:
        return float("nan")
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf >= lo) & (conf < hi if hi < 1 else conf <= hi)
        if m.sum():
            total += (m.sum() / conf.size) * abs(acc[m].mean() - conf[m].mean())
    return float(total)


def confident_wrong(rows, threshold=1.0):
    wrong = [r for r in rows if not r["majority_correct"]]
    if not wrong:
        return float("nan"), 0
    unanimous = [r for r in wrong if r["agreement"] >= threshold]
    return len(unanimous) / len(wrong), len(wrong)


def main():
    rows = pickle.load(open(RESULTS / "agreement.pkl", "rb"))
    qs = {q.qid: q for q in crag.load_crag(DATA)}
    for r in rows:
        q = qs[r["qid"]]
        r["popularity"] = q.popularity
        r["dynamism"] = q.dynamism
        r["n_hops"] = q.n_hops
    print(f"{len(rows)} questions with {10} samples each\n")

    report = {}
    for axis in ("popularity", "dynamism", "n_hops"):
        groups = sorted({r[axis] for r in rows}, key=str)
        print(f"=== by {axis} ===")
        print(f"{'group':<12}{'n':>5}{'conf':>7}{'acc':>7}{'gap':>8}"
              f"{'95% CI':>18}{'ECE':>7}{'all-agree wrong':>17}")
        report[axis] = {}
        for grp in groups:
            sub = [r for r in rows if r[axis] == grp]
            if len(sub) < 8:
                continue
            g = gap(sub)
            lo, hi = boot_ci(g)
            share, n_wrong = confident_wrong(sub)
            conf = float(np.mean([r["agreement"] for r in sub]))
            acc = float(np.mean([r["majority_correct"] for r in sub]))
            tail = grp in TAIL[axis]
            mark = "  <- tail" if tail else ""
            print(f"{str(grp):<12}{len(sub):>5}{conf:>7.3f}{acc:>7.3f}"
                  f"{float(np.mean(g)):>8.3f}{f'[{lo:.3f}, {hi:.3f}]':>18}"
                  f"{ece(sub):>7.3f}{f'{share:.2f} of {n_wrong}':>17}{mark}")
            report[axis][str(grp)] = {
                "n": len(sub), "confidence": conf, "accuracy": acc,
                "gap": float(np.mean(g)), "ci": [lo, hi], "ece": ece(sub),
                "unanimous_wrong_share": share, "n_wrong": n_wrong,
                "is_tail": tail}

        tail_rows = [r for r in rows if r[axis] in TAIL[axis]]
        head_rows = [r for r in rows if r[axis] not in TAIL[axis]]
        if len(tail_rows) >= 8 and len(head_rows) >= 8:
            diff = float(np.mean(gap(tail_rows)) - np.mean(gap(head_rows)))
            rng = np.random.default_rng(SEED)
            pool = np.concatenate([gap(tail_rows), gap(head_rows)])
            n_t = len(tail_rows)
            null = []
            for _ in range(5000):
                perm = rng.permutation(pool)
                null.append(perm[:n_t].mean() - perm[n_t:].mean())
            p = float((np.abs(null) >= abs(diff)).mean())
            verdict = ("SUPPORTS H1" if diff > 0 and p < 0.05
                       else "does not support H1")
            print(f"  tail gap minus head gap: {diff:+.3f}, "
                  f"permutation p = {p:.3f}  -> {verdict}")
            report[axis]["_contrast"] = {"diff": diff, "p": p,
                                         "verdict": verdict}
        print()

    json.dump(report, open(RESULTS / "h1.json", "w"), indent=2)
    print(f"written {RESULTS / 'h1.json'}")


if __name__ == "__main__":
    main()
