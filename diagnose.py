"""Find where present answers are lost: span pool, prefilter, or final ranking."""
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np

from experiment import window
from wk.baseline_agent import grade

rows = pickle.load(open(ROOT / "results" / "spans_cache.pkl", "rb"))
ranks = pickle.load(open(ROOT / "results" / "ranked.pkl", "rb"))["ranks"]

pool = pre = top5 = top1 = n = 0
short = {"n": 0, "pool": 0, "top1": 0}
long_ = {"n": 0, "pool": 0, "top1": 0}
for row, rk in zip(rows[:1200], ranks[:1200]):
    if not row["member"] or "cos" not in rk:
        continue
    n += 1
    q, golds, spans = row["q"].text, row["golds"], row["spans"]
    ok = lambda s: grade(s, golds, q)
    in_pool = any(ok(window(spans, i)) for i in range(len(spans)))
    idx = rk["idx"]
    order = np.argsort(-rk["cos"])
    in_pre = any(ok(window(spans, int(i))) for i in idx)
    in5 = any(ok(window(spans, int(idx[j]))) for j in order[:5])
    in1 = ok(window(spans, int(idx[order[0]])))
    pool += in_pool; pre += in_pre; top5 += in5; top1 += in1
    bucket = short if len(golds[0].split()) <= 3 else long_
    bucket["n"] += 1; bucket["pool"] += in_pool; bucket["top1"] += in1

print(f"present answers examined: {n}")
print(f"  some single passage holds it   {pool / n:.3f}")
print(f"  survives BM25 top-40 filter    {pre / n:.3f}")
print(f"  in embedding top 5             {top5 / n:.3f}")
print(f"  embedding top 1                {top1 / n:.3f}")
for name, b in (("short answers (<=3 words)", short), ("long answers", long_)):
    print(f"{name}: n={b['n']}  in pool {b['pool'] / b['n']:.3f}  "
          f"top1 {b['top1'] / b['n']:.3f}")
