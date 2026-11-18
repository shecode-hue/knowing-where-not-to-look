"""Run the W pipeline on real CRAG questions and report r, g, lambda and H2."""
import argparse
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from wk import classmodel, crag, estimators, probes, simulate
from wk.baseline_agent import impossible_cell
from wk.contract import Record

DATA = ROOT / "data" / "crag_task_1_and_2_dev_v5.jsonl.bz2"
SOURCES = {"W": crag.CragWebSource()}


def build(questions, source, n_traces):
    records = []
    for q in questions:
        ev = source.retrieve(q)
        rec = Record(question=q)
        rec.rho[source.name] = source.probe(q, ev)
        rec.membership[source.name] = source.contains_answer(q, ev)
        rec.runs[source.name] = source.run(q, ev, n=n_traces)
        records.append(rec)
    return records


def table(title, rows):
    print(f"\n{title}")
    for row in rows:
        print("  " + row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1500)
    ap.add_argument("--traces", type=int, default=10)
    args = ap.parse_args()

    t0 = time.time()
    questions = crag.load_crag(DATA, limit=args.limit)
    print(f"REAL CRAG: {len(questions)} questions from {DATA.name}")
    for key in ("domain", "dynamism", "question_type"):
        c = Counter(getattr(q, key) for q in questions)
        print(f"  {key:<14}{dict(c.most_common())}")

    out = {}
    for name, source in SOURCES.items():
        recs = build(questions, source, args.traces)
        out[name] = recs
        print(f"\n=== source {name}: {len(recs)} records in "
              f"{time.time() - t0:.0f}s ===")

        cells = estimators.two_by_two(recs, name)
        table("2x2", [f"{k:<16}{v:6d}" for k, v in cells.items()])
        bad = impossible_cell(recs, name)
        if bad:
            print(f"  impossible cell examples: {bad[:5]}")

        rows = []
        for qn, fn in (("r", estimators.estimate_r),
                       ("g", estimators.estimate_g),
                       ("lambda", estimators.estimate_lambda)):
            e = fn(recs, name)
            rows.append(f"{qn:<8}{e.value:7.3f}  [{e.lo:.3f}, {e.hi:.3f}]  "
                        f"n={e.n}")
        table("estimates, 95% bootstrap", rows)

        for key in ("dynamism", "domain"):
            rows = []
            groups = sorted({getattr(r.question, key) for r in recs})
            for grp in groups:
                sub = [r for r in recs if getattr(r.question, key) == grp]
                g = estimators.estimate_g(sub, name)
                r = estimators.estimate_r(sub, name)
                rows.append(f"{grp:<12}n={len(sub):5d}  "
                            f"g {g.value:.3f} [{g.lo:.2f},{g.hi:.2f}]  "
                            f"r {r.value:.3f} [{r.lo:.2f},{r.hi:.2f}]")
            table(f"by {key}", rows)

        X, names = probes.feature_matrix(recs, name)
        X = probes.impute_nan(X)
        y = classmodel.labels(recs, name)
        counts = Counter(y)
        print(f"\nclass counts {dict(counts)}")
        auc = perm = None
        try:
            auc = classmodel.cross_val_auroc(X, y)
            perm = classmodel.permutation_baseline(X, y, n_perm=100)
            print(f"H2 macro AUROC {auc['macro']:.3f}  "
                  f"null {perm['mean']:.3f}  p {perm.get('p_value', np.nan):.4f}"
                  f"  refuted={auc['refuted']}")
            for cls in ("covered", "rare", "ghost"):
                if cls in auc:
                    print(f"  {cls:<9}{auc[cls]:.3f}")
        except ValueError as exc:
            print(f"H2 not testable: {exc}")

        simulate.write_jsonl(recs, ROOT / "results" / f"real_{name}.jsonl")

        fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
        keys = ["covered", "rare", "ghost_abstained", "ghost_answered",
                "impossible"]
        ax[0].bar(range(5), [cells[k] for k in keys],
                  color=["#2a7a4a", "#c47a1a", "#888", "#b5304a", "#000"])
        ax[0].set_xticks(range(5), ["covered", "rare", "ghost\nabst.",
                                    "ghost\nanswered", "impossible"])
        ax[0].set_title(f"{name}: the 2×2 on real CRAG")
        dyn = [d for d in ("static", "slow", "fast", "realtime")
               if any(r.question.dynamism == d for r in recs)]
        gs = [estimators.estimate_g([r for r in recs
                                     if r.question.dynamism == d], name)
              for d in dyn]
        ax[1].errorbar(range(len(dyn)), [e.value for e in gs],
                       yerr=[[e.value - e.lo for e in gs],
                             [e.hi - e.value for e in gs]],
                       fmt="o-", color="#2f5d8a", capsize=4)
        ax[1].set_xticks(range(len(dyn)), dyn)
        ax[1].set_ylim(0, 1)
        ax[1].set_title(f"g_{name} by dynamism")
        if auc and perm:
            ax[2].bar([0, 1], [perm["mean"], auc["macro"]],
                      color=["#bbb", "#2f5d8a"])
            ax[2].axhline(0.6, ls="--", color="#b5304a", lw=1)
            ax[2].set_xticks([0, 1], ["shuffled null", "real probes"])
            ax[2].set_ylim(0, 1)
            ax[2].set_title("H2: macro AUROC")
        for a in ax:
            for s in ("top", "right"):
                a.spines[s].set_visible(False)
        fig.tight_layout()
        fig.savefig(ROOT / "results" / f"real_{name}.png", dpi=140)
        print(f"\nwritten results/real_{name}.jsonl and results/real_{name}.png")


if __name__ == "__main__":
    main()
