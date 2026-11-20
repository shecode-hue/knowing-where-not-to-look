"""Regenerate the figures as title-free plates for mounting on dark slides."""
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

plt.rcParams.update({"font.size": 12, "axes.edgecolor": INK,
                     "axes.labelcolor": INK, "text.color": INK,
                     "xtick.color": INK, "ytick.color": INK,
                     "axes.linewidth": 0.9})


def dissociation():
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.1), sharey=True)
    labels = ["agent improved\ncorpus fixed", "corpus grown\nagent fixed"]
    r_vals = [(0.066, 0.286), (0.236, 0.228)]
    g_vals = [(0.318, 0.343), (0.322, 0.154)]
    for ax, vals, name, colour in ((axes[0], r_vals, "reliability  r", BLUE),
                                   (axes[1], g_vals, "ghost mass  g", RED)):
        x = np.arange(2)
        ax.bar(x - 0.17, [v[0] for v in vals], 0.34, color=GREY)
        ax.bar(x + 0.17, [v[1] for v in vals], 0.34, color=colour)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=11)
        ax.set_title(name, fontsize=13)
        ax.set_ylim(0, 0.42)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].bar(0, 0, color=GREY, label="before")
    axes[0].bar(0, 0, color=BLUE, label="after")
    axes[0].legend(frameon=False, fontsize=10, loc="upper left")
    fig.tight_layout(pad=0.4)
    fig.savefig(FIGS / "plate_dissociation.png", dpi=200,
                bbox_inches="tight")


def depth():
    data = json.load(open(RESULTS / "independence.json"))["by_dynamism"]
    order = ["static", "slow", "fast", "realtime"]
    g5 = [data[d]["g5"] for d in order]
    g50 = [data[d]["g50"] for d in order]
    x = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(6.4, 3.1))
    ax.bar(x - 0.17, g5, 0.34, color=GREY, label="5 pages")
    ax.bar(x + 0.17, g50, 0.34, color=BLUE, label="50 pages")
    ax.set_xticks(x)
    ax.set_xticklabels(order, fontsize=12)
    ax.set_ylabel("ghost mass  g", fontsize=12)
    ax.legend(frameon=False, fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.4)
    fig.savefig(FIGS / "plate_depth.png", dpi=200, bbox_inches="tight")


def inversion():
    data = json.load(open(RESULTS / "inversion.json"))["k_only"]
    names = ["MeanTokenEntropy", "MonteCarloSequenceEntropy",
             "LexicalSimilarity", "MaximumSequenceProbability", "PTrue"]
    before = [data[n]["auroc_all"] for n in names]
    after = [data[n]["auroc_conditioned"] for n in names]
    y = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    for i, (b, a) in enumerate(zip(before, after)):
        ax.plot([b, a], [i, i], color=GREY, lw=1.4, zorder=1)
    ax.scatter(before, y, s=46, color=RED, zorder=2, label="raw")
    ax.scatter(after, y, s=46, color=BLUE, zorder=2, label="conditioned")
    ax.axvline(0.5, color=GREY, lw=1, ls="--")
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=11)
    ax.set_xlabel("AUROC, answer is correct", fontsize=12)
    ax.set_xlim(0, 1)
    ax.invert_yaxis()
    ax.legend(frameon=False, fontsize=11, loc="lower left")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.4)
    fig.savefig(FIGS / "plate_inversion.png", dpi=200, bbox_inches="tight")


if __name__ == "__main__":
    dissociation()
    depth()
    inversion()
    print("plates written")
