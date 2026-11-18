"""Run the K pipeline on real CRAG movie and open questions and compare with W."""
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np

from wk import classmodel, crag, estimators, probes, simulate
from wk.contract import Record
from wk.kg_source import DOMAINS, KBSource

DATA = ROOT / "data" / "crag_task_1_and_2_dev_v5.jsonl.bz2"


def line(tag, recs, src):
    r, g = estimators.estimate_r(recs, src), estimators.estimate_g(recs, src)
    return (f"{tag:<12}n={len(recs):4d}  g {g.value:.3f} [{g.lo:.2f},{g.hi:.2f}]"
            f"  r {r.value:.3f} [{r.lo:.2f},{r.hi:.2f}]")


t0 = time.time()
questions = [q for q in crag.load_crag(DATA) if q.domain in DOMAINS]
print(f"REAL CRAG, domains {DOMAINS}: {len(questions)} questions")
source = KBSource()
print(f"knowledge graph loaded in {time.time() - t0:.0f}s: "
      f"{len(source.kb.movies)} movies, {len(source.kb.persons)} people, "
      f"{len(source.kb.open.kg)} open entities")

recs = []
for q in questions:
    ev = source.retrieve(q)
    rec = Record(question=q)
    rec.rho["K"] = source.probe(q, ev)
    rec.membership["K"] = source.contains_answer(q, ev)
    rec.runs["K"] = source.run(q, ev)
    recs.append(rec)
print(f"{len(recs)} records in {time.time() - t0:.0f}s")

resolved = np.array([r.rho["K"]["entity_resolved"] for r in recs])
print(f"\nentity found in the graph: {resolved.mean():.3f}")
print("2x2:", estimators.two_by_two(recs, "K"))
print(line("ALL", recs, "K"))
lam = estimators.estimate_lambda(recs, "K")
print(f"lambda {lam.value:.3f} [{lam.lo:.3f}, {lam.hi:.3f}]")
for key in ("domain", "dynamism", "question_type"):
    print(f"\nby {key}")
    for grp in sorted({getattr(r.question, key) for r in recs}):
        sub = [r for r in recs if getattr(r.question, key) == grp]
        print("  " + line(grp[:12], sub, "K"))

member = np.array([r.membership["K"] for r in recs])
print("\nghost mass split by whether the entity was found")
print(f"  entity not found: {(resolved == 0).mean():.3f} of questions, "
      f"all ghosts by construction")
print(f"  entity found but answer absent: "
      f"{((resolved == 1) & ~member).mean():.3f} of questions")

X, names = probes.feature_matrix(recs, "K")
X = probes.impute_nan(X)
y = classmodel.labels(recs, "K")
print(f"\nclass counts {dict(Counter(y))}; probes {names}")
try:
    auc = classmodel.cross_val_auroc(X, y)
    perm = classmodel.permutation_baseline(X, y, n_perm=100)
    print(f"H2 on K: macro AUROC {auc['macro']:.3f}  null {perm['mean']:.3f}"
          f"  p {perm.get('p_value', float('nan')):.4f}  "
          f"refuted={auc['refuted']}")
    print("  per class:", {c: round(auc[c], 3) for c in
                           ("covered", "rare", "ghost") if c in auc})
    yb = np.where(y == "ghost", "ghost", "present")
    ab = classmodel.cross_val_auroc(X, yb)
    print(f"  ghost vs present only: AUROC {ab['macro']:.3f}")
except ValueError as exc:
    print("H2 not testable:", exc)

simulate.write_jsonl(recs, ROOT / "results" / "real_K.jsonl")

w = {r.question.qid: r for r in
     simulate.read_jsonl(ROOT / "results" / "real_W.jsonl")}
both = [(r, w[r.question.qid]) for r in recs if r.question.qid in w]
k_in = np.array([a.membership["K"] for a, _ in both])
w_in = np.array([b.membership["W"] for _, b in both])
print(f"\nSAME {len(both)} QUESTIONS, where is the answer?")
print(f"  in both W and K   {(k_in & w_in).mean():.3f}")
print(f"  only in W         {(~k_in & w_in).mean():.3f}")
print(f"  only in K         {(k_in & ~w_in).mean():.3f}")
print(f"  in neither        {(~k_in & ~w_in).mean():.3f}")
print("  " + line("W same set", [b for _, b in both], "W"))
print("  " + line("K same set", [a for a, _ in both], "K"))
print(f"\nwritten results/real_K.jsonl  ({time.time() - t0:.0f}s)")
