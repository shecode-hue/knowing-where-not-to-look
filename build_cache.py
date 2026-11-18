"""Cache per-page spans, membership and gold answers for every CRAG question."""
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from wk import crag
from wk.baseline_agent import candidate_spans, gold_answers
from wk.contract import Evidence

DATA = ROOT / "data" / "crag_task_1_and_2_dev_v5.jsonl.bz2"
OUT = ROOT / "results" / "spans_cache.pkl"
PER_PAGE = 120

t0 = time.time()
questions = crag.load_crag(DATA)
source = crag.CragWebSource()
rows = []
for i, q in enumerate(questions):
    ev = source.retrieve(q)
    spans, seen = [], set()
    for p, item in enumerate(ev.items):
        one = Evidence(source="W", items=[item], meta=ev.meta)
        for s in candidate_spans(one, max_spans=PER_PAGE):
            key = crag.normalise(s)
            if key not in seen:
                seen.add(key)
                spans.append((p, s))
    rows.append({"q": q, "spans": spans, "n_pages": len(ev.items),
                 "member": source.contains_answer(q, ev),
                 "golds": gold_answers(q)})
    if i % 500 == 0:
        print(i, f"{time.time() - t0:.0f}s", flush=True)

pickle.dump(rows, open(OUT, "wb"))
print(f"cached {len(rows)} questions, "
      f"{sum(len(r['spans']) for r in rows)} spans -> {OUT}")
