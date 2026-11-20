"""Try the agent on any CRAG question: retrieve, read, decide, and show why."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np

from wk import crag, llm
from wk.baseline_agent import grade
from wk.semantic_agent import passages, score_question

DATA = ROOT / "data" / "crag_task_1_and_2_dev_v5.jsonl.bz2"


def pick(questions, needle):
    if needle.isdigit():
        return questions[int(needle)]
    low = needle.lower()
    for q in questions:
        if low in q.text.lower():
            return q
    raise SystemExit(f"no question contains {needle!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("needle", help="a word from the question, or its index")
    ap.add_argument("--pages", type=int, default=6)
    ap.add_argument("--fifty", action="store_true",
                    help="use the fifty-page corpus for this question")
    args = ap.parse_args()

    qs = crag.load_crag(DATA)
    q = pick(qs, args.needle)
    print(f"question : {q.text}")
    print(f"domain {q.domain} · recency {q.dynamism} · type {q.question_type}\n")

    if args.fifty:
        import bz2
        import json as _json
        raw = {}
        with bz2.open(ROOT / "data" / "task3" / "task3_matched.jsonl.bz2",
                      "rt") as fh:
            for line in fh:
                item = _json.loads(line)
                raw[str(item.get("interaction_id") or "")] = item
        if q.qid not in raw:
            raise SystemExit("this question is not among the 738 fifty-page pairs")
        web = crag.CragWebSource(raw=raw)
    else:
        web = crag.CragWebSource()
    ev = web.retrieve(q)
    cands = passages(ev)
    member = web.contains_answer(q, ev)
    scored = score_question(q.text, cands)
    order = np.argsort(scored["ce"])[::-1][:args.pages]
    top = [cands[int(scored["idx"][int(i)])] for i in order]

    print(f"evidence : {len(ev.items)} saved pages → {len(cands)} spans, "
          f"reader sees the top {len(top)}")
    print(f"corpus holds the answer: {member}\n")

    llm.start()
    out = llm.read(q.text, top, n_evidence=len(top))
    p_true = llm.p_true(q.text, out["answer"]) if out["answer"] else 0.0
    llm.stop()

    said = out["answer"] or "(abstained)"
    decision = "answers" if out["answer"] and p_true >= 0.5 else "abstains"
    print(f"agent says : {said}")
    print(f"P(True)    : {p_true:.3f}  → the agent {decision}")
    print(f"gold       : {q.answer}")
    if out["answer"]:
        print(f"graded     : {'correct' if grade(out['answer'], crag.gold_answers(q), q.text) else 'wrong'}")
    print(f"\nbest span the reader saw:\n  {top[0][:240]}")


if __name__ == "__main__":
    main()
