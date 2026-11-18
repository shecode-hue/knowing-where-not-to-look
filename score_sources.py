"""Score every question with the semantic ranker and cache the result."""
import argparse
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np

from wk import crag
from wk.baseline_agent import gold_answers
from wk.semantic_agent import RERANK, features, passages, score_question

DATA = ROOT / "data" / "crag_task_1_and_2_dev_v5.jsonl.bz2"
OUT = ROOT / "results"


def build(source_name, questions, retrieve, contains):
    rows, t0 = [], time.time()
    for i, q in enumerate(questions):
        ev = retrieve(q)
        cands = passages(ev)
        scored = score_question(q.text, cands)
        keep = scored["idx"]
        rows.append({
            "qid": q.qid, "q": q,
            "member": contains(q, ev),
            "golds": gold_answers(q),
            "texts": [cands[int(j)] for j in keep],
            "ce": scored["ce"], "cos": scored["cos"],
            "feat": features(scored),
            "n_items": len(ev.items), "n_cands": len(cands),
        })
        if i % 200 == 0:
            rate = (i + 1) / max(time.time() - t0, 1e-9)
            print(f"  {source_name} {i}/{len(questions)}  "
                  f"{rate:.1f} q/s  {time.time() - t0:.0f}s", flush=True)
    path = OUT / f"scored_{source_name}.pkl"
    pickle.dump(rows, open(path, "wb"))
    print(f"{source_name}: {len(rows)} questions -> {path} "
          f"({time.time() - t0:.0f}s)")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="W,K")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    which = args.sources.split(",")

    questions = crag.load_crag(DATA, limit=args.limit)
    print(f"{len(questions)} questions loaded")

    if "W" in which:
        web = crag.CragWebSource()
        build("W", questions, web.retrieve, web.contains_answer)

    if "K" in which:
        from wk.kg_source import DOMAINS, KBSource
        kb = KBSource()
        kq = [q for q in questions if q.domain in DOMAINS]
        print(f"K covers {len(kq)} questions in {DOMAINS}")
        build("K", kq, kb.retrieve, kb.contains_answer)


if __name__ == "__main__":
    main()
