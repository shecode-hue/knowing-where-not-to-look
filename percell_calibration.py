"""Per-KAP-cell calibration: ECE with bootstrap intervals and reliability diagrams."""
import json
import pickle
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.isotonic import IsotonicRegression

from wk.baseline_agent import grade

RESULTS = ROOT / "results"
FIGS = RESULTS / "figures"
SEED = 0
ARM = "concat_rag"
BINS = 8

INK = "#1a1a1c"
BLUE = "#1c4a80"
GREY = "#b9b7b2"


def kap_cell(q):
    recency = "moving" if q.dynamism in ("fast", "realtime") else "settled"
    popularity = "tail" if q.popularity in ("tail", "torso") else "head"
    hops = "multi" if (q.n_hops or 1) > 1 else "single"
    return f"{recency}/{popularity}/{hops}"


def ece(conf, correct, bins=BINS):
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


def boot_ece(conf, correct, reps=3000):
    rng = np.random.default_rng(SEED)
    n = len(conf)
    vals = [ece(np.asarray(conf)[i], np.asarray(correct)[i])
            for i in (rng.integers(0, n, n) for _ in range(reps))]
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def curve(conf, correct, bins=BINS):
    edges = np.linspace(0, 1, bins + 1)
    xs, ys, ns = [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf >= lo) & (conf < hi if hi < 1 else conf <= hi)
        if m.sum():
            xs.append(float(conf[m].mean()))
            ys.append(float(np.asarray(correct, dtype=float)[m].mean()))
            ns.append(int(m.sum()))
    return xs, ys, ns


def main():
    FIGS.mkdir(exist_ok=True)
    rows = pickle.load(open(RESULTS / "baselines_raw_1.5b.pkl", "rb"))
    for r in rows:
        r["cell"] = kap_cell(r["q"])
        a = r["arms"][ARM]
        a["correct"] = grade(a["answer"], r["golds"], r["q"].text)
    cal = [r for r in rows if r["split"] == "calibration"]
    test = [r for r in rows if r["split"] != "calibration"]

    conf_raw = np.array([r["arms"][ARM]["p_true"] for r in cal])
    y_cal = np.array([r["arms"][ARM]["correct"] for r in cal], dtype=float)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
    iso.fit(conf_raw, y_cal)
    conf = iso.predict(np.array([r["arms"][ARM]["p_true"] for r in test]))
    correct = np.array([r["arms"][ARM]["correct"] for r in test], dtype=bool)
    cells = sorted({r["cell"] for r in test})

    print(f"{ARM}, PTrue calibrated on {len(cal)}, shown on {len(test)}\n")
    print(f"{'KAP cell':<24}{'n':>5}{'ECE':>8}{'95% CI':>18}{'acc':>7}")
    out = {}
    rich = []
    for c in cells + ["overall"]:
        m = (np.array([r["cell"] == c for r in test]) if c != "overall"
             else np.ones(len(test), dtype=bool))
        if m.sum() < 15:
            continue
        e = ece(conf[m], correct[m])
        lo, hi = boot_ece(conf[m], correct[m])
        print(f"{c:<24}{int(m.sum()):>5}{e:>8.3f}"
              f"{f'[{lo:.3f}, {hi:.3f}]':>18}{correct[m].mean():>7.3f}")
        out[c] = {"n": int(m.sum()), "ece": e, "ci": [lo, hi],
                  "accuracy": float(correct[m].mean())}
        if c != "overall":
            rich.append(c)

    k = len(rich)
    fig, axes = plt.subplots(1, k, figsize=(2.6 * k, 2.9), sharey=True)
    for ax, c in zip(np.atleast_1d(axes), rich):
        m = np.array([r["cell"] == c for r in test])
        xs, ys, ns = curve(conf[m], correct[m])
        ax.plot([0, 1], [0, 1], color=GREY, lw=1)
        ax.plot(xs, ys, "o-", color=BLUE, lw=1.4, ms=4)
        ax.set_title(f"{c}\nn={int(m.sum())}, ECE {out[c]['ece']:.2f}",
                     fontsize=8, color=INK)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("stated confidence", fontsize=8)
        ax.tick_params(labelsize=7)
    np.atleast_1d(axes)[0].set_ylabel("observed accuracy", fontsize=8)
    fig.suptitle("Reliability by KAP cell, P(True) on concatenation RAG, "
                 "1.5B", fontsize=9, color=INK)
    fig.tight_layout()
    path = FIGS / "reliability_by_cell.png"
    fig.savefig(path, dpi=180)
    print(f"\nfigure -> {path}")

    json.dump(out, open(RESULTS / "percell_ece.json", "w"), indent=2)
    print(f"written {RESULTS / 'percell_ece.json'}")


if __name__ == "__main__":
    main()
