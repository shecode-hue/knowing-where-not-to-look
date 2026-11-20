"""Figures for the completed results: dissociation, depth effect, inversion repair."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS = ROOT / "results"
FIGS = RESULTS / "figures"
INK = "#1a1a1c"
BLUE = "#1c4a80"
RED = "#b2303a"
GREY = "#b9b7b2"

plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK,
                     "axes.labelcolor": INK, "text.color": INK,
                     "xtick.color": INK, "ytick.color": INK})


def dissociation():
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.9), sharey=True)
    labels = ["agent improved\n(corpus fixed)", "corpus grown\n(agent fixed)"]
    r_vals = [(0.066, 0.286), (0.236, 0.228)]
    g_vals = [(0.318, 0.343), (0.322, 0.154)]
    for ax, vals, name, colour in ((axes[0], r_vals, "reliability r", BLUE),
                                   (axes[1], g_vals, "ghost mass g", RED)):
        x = np.arange(2)
        before = [v[0] for v in vals]
        after = [v[1] for v in vals]
        ax.bar(x - 0.17, before, 0.34, color=GREY, label="before")
        ax.bar(x + 0.17, after, 0.34, color=colour, label="after")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_title(name, fontsize=10)
        ax.set_ylim(0, 0.45)
        ax.legend(frameon=False, fontsize=8)
    fig.suptitle("Each manipulation moves exactly one quantity "
                 "(738 paired questions)", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGS / "dissociation.png", dpi=180)
    print(f"figure -> {FIGS / 'dissociation.png'}")


def depth():
    data = json.load(open(RESULTS / "independence.json"))["by_dynamism"]
    order = ["static", "slow", "fast", "realtime"]
    g5 = [data[d]["g5"] for d in order]
    g50 = [data[d]["g50"] for d in order]
    n = [data[d]["n"] for d in order]
    x = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(5.4, 3.0))
    ax.bar(x - 0.17, g5, 0.34, color=GREY, label="5 pages")
    ax.bar(x + 0.17, g50, 0.34, color=BLUE, label="50 pages")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{d}\nn={m}" for d, m in zip(order, n)], fontsize=8)
    ax.set_ylabel("ghost mass g")
    ax.set_title("Apparent staleness is retrieval depth: the realtime class "
                 "gains most from a deeper corpus", fontsize=9)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGS / "depth_effect.png", dpi=180)
    print(f"figure -> {FIGS / 'depth_effect.png'}")


def inversion():
    data = json.load(open(RESULTS / "inversion.json"))["k_only"]
    names = ["MeanTokenEntropy", "MonteCarloSequenceEntropy",
             "LexicalSimilarity", "MaximumSequenceProbability", "PTrue"]
    before = [data[n]["auroc_all"] for n in names]
    after = [data[n]["auroc_conditioned"] for n in names]
    y = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(6.2, 2.9))
    for i, (b, a) in enumerate(zip(before, after)):
        ax.plot([b, a], [i, i], color=GREY, lw=1.2, zorder=1)
    ax.scatter(before, y, s=34, color=RED, zorder=2, label="raw")
    ax.scatter(after, y, s=34, color=BLUE, zorder=2,
               label="abstention-conditioned")
    ax.axvline(0.5, color=GREY, lw=1, ls="--")
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("AUROC, answer-is-correct (K source, 1.5B)")
    ax.set_xlim(0, 1)
    ax.invert_yaxis()
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    ax.set_title("Conditioning on abstention repairs inverted estimators "
                 "and never hurts", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGS / "inversion_repair.png", dpi=180)
    print(f"figure -> {FIGS / 'inversion_repair.png'}")


if __name__ == "__main__":
    FIGS.mkdir(exist_ok=True)
    dissociation()
    depth()
    inversion()
