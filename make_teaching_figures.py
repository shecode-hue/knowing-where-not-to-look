"""Three plain teaching diagrams: one record, the flip, the pipeline."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrow, Rectangle

FIGS = ROOT / "results" / "figures"
INK = "#1a1a1c"
BLUE = "#1c4a80"
RED = "#b2303a"
GREY = "#b9b7b2"
WASH = "#f4f3f1"


def box(ax, x, y, w, h, text, fc=WASH, ec=INK, size=10, tc=None):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec,
                           linewidth=1.1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=size, color=tc or INK)


def record():
    fig, ax = plt.subplots(figsize=(7.6, 3.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.text(0.2, 4.7, "one record in Meta's CRAG file  (there are 4,409 of these)",
            fontsize=11, color=INK)
    box(ax, 0.2, 3.3, 4.4, 0.9,
        'question:\n"when did air supply start performing as a band?"', size=9.5)
    box(ax, 0.2, 2.1, 4.4, 0.9, 'gold answer:  "1975"\n(written by Meta, hidden from the agent)',
        size=9.5)
    box(ax, 0.2, 0.9, 4.4, 0.9, "labels: domain = music\nrecency = static, type = simple",
        size=9.5)
    ax.text(5.2, 4.2, "five saved web pages, full HTML", fontsize=10, color=INK)
    for i in range(5):
        box(ax, 5.2 + i * 0.3, 1.1 - i * 0.12 + 1.4, 3.2, 1.5,
            "" if i < 4 else "page text\n(already fetched by\nMeta's search engine)",
            fc="white", size=9)
    fig.tight_layout(pad=0.4)
    fig.savefig(FIGS / "teach_record.png", dpi=190, bbox_inches="tight")


def flip():
    fig, ax = plt.subplots(figsize=(7.6, 3.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.text(0.2, 4.7, 'the corpus change: same question, more saved pages',
            fontsize=11, color=INK)
    box(ax, 0.4, 1.6, 2.6, 2.4, "", fc="white")
    for i in range(5):
        box(ax, 0.6, 3.5 - i * 0.42, 2.2, 0.34, f"page {i + 1}", fc=WASH, size=8)
    ax.text(1.7, 1.2, '5 pages\n"1975" appears nowhere\nmember = False',
            ha="center", fontsize=9.5, color=RED)
    ax.add_patch(FancyArrow(3.6, 2.8, 1.2, 0, width=0.06, color=INK,
                            length_includes_head=True, head_width=0.22))
    ax.text(4.2, 3.1, "add 45 more\nof Meta's pages", ha="center", fontsize=9)
    box(ax, 5.2, 1.0, 3.4, 3.0, "", fc="white")
    for i in range(10):
        col, row = divmod(i, 5)
        fc = BLUE if i == 7 else WASH
        tc = "white" if i == 7 else INK
        box(ax, 5.4 + col * 1.6, 3.5 - row * 0.52, 1.45, 0.42,
            "page 38:\n'...in 1975'" if i == 7 else f"pages", fc=fc, size=7.5,
            tc=tc)
    ax.text(6.9, 0.55, '50 pages\n"1975" is on one of them\nmember = True',
            ha="center", fontsize=9.5, color=BLUE)
    fig.tight_layout(pad=0.4)
    fig.savefig(FIGS / "teach_flip.png", dpi=190, bbox_inches="tight")


def pipeline():
    fig, ax = plt.subplots(figsize=(8.4, 2.6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3)
    ax.axis("off")
    steps = [
        "load the\n4,409\nquestions",
        "take the\nsaved pages\n(5 or 50)",
        "strip HTML,\ncut into\n2-sentence\npieces",
        "search:\nBM25 keeps\n100 pieces",
        "rank:\nembeddings\nkeep 30",
        "pick:\ncross-encoder\nchooses one",
        "label:\nis the gold\nin the corpus?\nwas it found?",
        "count:\nr and g,\nerror bars by\nbootstrap",
    ]
    w, gap = 1.32, 0.14
    for i, s in enumerate(steps):
        x = 0.2 + i * (w + gap)
        fc = WASH if i < 6 else "#e8eef6"
        box(ax, x, 0.7, w, 1.7, s, fc=fc, size=8)
        if i:
            ax.add_patch(FancyArrow(x - gap, 1.55, gap * 0.9, 0, width=0.03,
                                    color=INK, length_includes_head=True,
                                    head_width=0.12))
    ax.text(0.2, 2.65, "the pipeline, one pass over every question; each stage saves its output to disk",
            fontsize=10.5, color=INK)
    fig.tight_layout(pad=0.4)
    fig.savefig(FIGS / "teach_pipeline.png", dpi=190, bbox_inches="tight")


if __name__ == "__main__":
    record()
    flip()
    pipeline()
    print("teaching figures written")
