"""Four views of uncertainty in the project, drawn from the real W results."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from wk import classmodel, probes, simulate
from wk.contract import class_of

recs = simulate.read_jsonl(ROOT / "results" / "real_W.jsonl")
cls = np.array([class_of(r, "W") for r in recs])
agree = np.array([r.runs["W"].agreement for r in recs])
answered = np.array([not r.runs["W"].abstained for r in recs])
member = np.array([r.membership["W"] for r in recs])
n = len(recs)

GREEN, AMBER, RED, BLUE, GREY = "#2a7a4a", "#c47a1a", "#b5304a", "#2f5d8a", "#999"
fig, ax = plt.subplots(2, 2, figsize=(14, 9.6))
fig.patch.set_facecolor("white")

a = ax[0, 0]
shares = [(cls == "covered").mean(), (cls == "rare").mean(),
          (cls == "ghost").mean()]
left = 0
for s, c, lab in zip(shares, (GREEN, AMBER, RED),
                     ("found", "there, but missed", "not there at all")):
    a.barh(0, s, left=left, color=c, height=0.5)
    if s < 0.1:
        a.text(left + s / 2, 0.33, f"{lab} {s:.1%}", ha="left", va="bottom",
               color=c, fontsize=10.5, weight="bold")
    else:
        a.text(left + s / 2, 0, f"{lab}\n{s:.1%}", ha="center", va="center",
               color="white", fontsize=10.5, weight="bold")
    left += s
a.set_xlim(0, 1); a.set_ylim(-0.6, 0.6); a.set_yticks([])
a.set_xlabel("share of 2,706 real questions")
a.set_title("1. Where the agent's uncertainty comes from", weight="bold")

a = ax[0, 1]
groups = [("found", (cls == "covered"), GREEN),
          ("there,\nbut missed", (cls == "rare") & answered, AMBER),
          ("not there,\nanswered anyway", (cls == "ghost") & answered, RED)]
for i, (lab, mask, c) in enumerate(groups):
    vals = agree[mask]
    a.bar(i, vals.mean(), color=c, width=0.6)
    a.text(i, vals.mean() + 0.02, f"{vals.mean():.2f}\n(n={mask.sum()})",
           ha="center", fontsize=10)
a.set_xticks(range(3), [g[0] for g in groups])
a.set_ylim(0, 1)
a.set_ylabel("mean agreement across 10 runs")
a.set_title("2. Agreement does not tell right from wrong", weight="bold")

a = ax[1, 0]
rng = np.random.default_rng(0)
boot = np.array([(~member[rng.integers(0, n, n)]).mean() for _ in range(5000)])
lo, hi = np.percentile(boot, [2.5, 97.5])
a.hist(boot, bins=50, color=BLUE, alpha=0.8)
for v in (lo, hi):
    a.axvline(v, color="k", ls="--", lw=1.2)
a.axvline((~member).mean(), color=RED, lw=2)
a.set_xlabel("ghost mass g for W")
a.set_yticks([])
a.set_title(f"3. How sure we are of g: {(~member).mean():.3f}, "
            f"95% interval {lo:.3f} to {hi:.3f}", weight="bold")

a = ax[1, 1]
X, _ = probes.feature_matrix(recs, "W")
X = probes.impute_nan(X)
real = classmodel.cross_val_auroc(X, cls)["macro"]
null = [classmodel.cross_val_auroc(X, rng.permutation(cls))["macro"]
        for _ in range(60)]
a.hist(null, bins=15, color=GREY, alpha=0.9, label="shuffled labels (chance)")
a.axvline(real, color=RED, lw=2.5, label=f"real probes: {real:.3f}")
a.axvline(0.6, color="k", ls="--", lw=1.2, label="H2 needs 0.6")
a.set_xlabel("macro AUROC")
a.set_yticks([])
a.legend(frameon=False, fontsize=9.5)
a.set_title("4. Is the prediction better than chance?", weight="bold")

for row in ax:
    for a in row:
        for s in ("top", "right", "left"):
            a.spines[s].set_visible(False)

fig.suptitle("Uncertainty in the project, on real CRAG data (source W, "
             "keyword agent)", fontsize=14.5, weight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.96])
out = ROOT / "results" / "uncertainty_explained.png"
fig.savefig(out, dpi=140, facecolor="white")
print("written", out)
for lab, mask, _ in groups:
    print(f"agreement {lab!r}: mean {agree[mask].mean():.3f} n {mask.sum()}")
print(f"shares {shares}; g {(~member).mean():.3f} [{lo:.3f}, {hi:.3f}]; "
      f"auroc {real:.3f} null {np.mean(null):.3f}")
