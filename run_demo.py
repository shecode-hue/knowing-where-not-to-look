"""End-to-end run: build data, measure r/g/lambda, test H2, and say what it means."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from wk import classmodel, crag, estimators, probes, simulate

N = 4000
SEED = 0
TRUE = dict(r_W=0.72, g_W=0.12, r_K=0.93, g_K=0.45)


def rule(ch="="):
    print(ch * 78)


def head(text):
    print()
    rule()
    print(text)
    rule()


head("1.  WHERE THE DATA CAME FROM")
if crag.available("data/crag"):
    print("  real CRAG data found")
else:
    print("  No CRAG data on this machine, so this run uses the SIMULATOR.")
    print("  That is deliberate: the simulator has known r and g, which is the")
    print("  only way to prove the estimators are correct before real data lands.")
    print()
    print(f"  true values set by hand:  {TRUE}")

records = simulate.make_synthetic(N, seed=SEED, **TRUE)
print(f"\n  {len(records)} questions generated")

head("2.  THE 2x2, PER SOURCE")
for s in ("W", "K"):
    c = estimators.two_by_two(records, s)
    total = sum(v for k, v in c.items() if k != "impossible")
    print(f"\n  source {s}")
    print(f"    covered          {c['covered']:5d}   "
          f"answer was there and the agent got it")
    print(f"    rare             {c['rare']:5d}   "
          f"answer was there and the agent missed it")
    print(f"    ghost_abstained  {c['ghost_abstained']:5d}   "
          f"not there, and it said so")
    print(f"    ghost_answered   {c['ghost_answered']:5d}   "
          f"not there, and it answered anyway  <-- the dangerous cell")
    flag = "OK" if c["impossible"] == 0 else "*** LABELS ARE BROKEN ***"
    print(f"    impossible       {c['impossible']:5d}   {flag}")
    print(f"    total            {total:5d}")

head("3.  THE THREE NUMBERS, WITH BOOTSTRAP INTERVALS")
print(f"\n  {'source':<8}{'quantity':<10}{'estimate':>10}"
      f"{'95% interval':>22}{'truth':>9}")
print("  " + "-" * 60)
for s in ("W", "K"):
    for q, fn in (("r", estimators.estimate_r), ("g", estimators.estimate_g),
                  ("lambda", estimators.estimate_lambda)):
        e = fn(records, s)
        key = f"{q}_{s}"
        truth = TRUE.get(key)
        tx = f"{truth:.3f}" if truth is not None else "-"
        print(f"  {s:<8}{q:<10}{e.value:>10.3f}"
              f"{f'[{e.lo:.3f}, {e.hi:.3f}]':>22}{tx:>9}")

head("4.  THE CENTRAL PREDICTION: DOES K GO STALE AND W NOT?")
print("\n  ghost mass g by how fast the answer changes\n")
print(f"  {'dynamism':<12}{'g_W':>18}{'g_K':>18}")
print("  " + "-" * 48)
for d in ("static", "slow", "fast", "realtime"):
    sub = [r for r in records if r.question.dynamism == d]
    if not sub:
        continue
    gw, gk = estimators.estimate_g(sub, "W"), estimators.estimate_g(sub, "K")
    print(f"  {d:<12}{gw.value:>8.3f} [{gw.lo:.2f},{gw.hi:.2f}]"
          f"{gk.value:>8.3f} [{gk.lo:.2f},{gk.hi:.2f}]")

head("5.  H2: CAN THE QUESTION ALONE PREDICT THE CLASS?")
for s in ("W", "K"):
    X, names = probes.feature_matrix(records, s)
    X = probes.impute_nan(X)
    y = classmodel.labels(records, s)
    auc = classmodel.cross_val_auroc(X, y, seed=SEED)
    perm = classmodel.permutation_baseline(X, y, n_perm=100, seed=SEED)
    verdict = "REFUTED" if auc["refuted"] else "supported"
    print(f"\n  source {s}:  macro AUROC {auc['macro']:.3f}   -> H2 {verdict}")
    for cls in ("covered", "rare", "ghost"):
        if cls in auc:
            print(f"      {cls:<10}{auc[cls]:.3f}")
    print(f"      shuffled-label null  {perm['mean']:.3f}"
          f"   p = {perm.get('p_value', float('nan')):.4f}")

head("6.  HOW TO READ ALL THAT")
print("""
  g, ghost mass.  How often the answer is simply not in this source.
      Sampling cannot reduce it. Only reaching for another source can.
      High g means: stop asking this source, it has nothing.

  r, reliability.  When the answer WAS there, how often the agent got it.
      Low r means: your retrieval is bad. Fix the pipeline, not the source.

  lambda, rare passage.  The other half of r, 1 - r.
      It gets its own name because its remedy is different from ghost's.

  the impossible cell.  Must be zero. Non-zero means your membership
      labels are wrong, a source leaked, or the grader rewarded a guess.

  ghost_answered.  The cell that should frighten you. The answer was
      nowhere and the agent answered anyway, confidently. That is the
      failure the whole project exists to predict in advance.

  AUROC vs the shuffled null.  0.5 is chance. If the real score is not
      clearly above the shuffled-label null, your probes carry no signal
      and H2 is dead regardless of how large the number looks.
""")
rule()
print("H2 is refuted below macro AUROC", classmodel.REFUTATION_THRESHOLD)
rule()
