"""Print one real question whose membership flipped when the corpus grew."""
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from wk import crag

RESULTS = ROOT / "results"

five = {r["qid"]: r for r in pickle.load(open(RESULTS / "scored_W.pkl", "rb"))}
fifty = pickle.load(open(RESULTS / "scored_W50.pkl", "rb"))

for r in fifty:
    old = five.get(r["qid"])
    if old is None or old["member"] or not r["member"]:
        continue
    q = r["q"]
    gold = q.answer
    print(f"interaction_id : {q.qid}")
    print(f"question       : {q.text}")
    print(f"gold answer    : {gold}")
    print(f"domain {q.domain} · dynamism {q.dynamism} · type {q.question_type}")
    print(f"5-page corpus  : member = {old['member']}  "
          f"({old['n_items']} pages, {old['n_cands']} spans)")
    print(f"50-page corpus : member = {r['member']}  "
          f"({r['n_items']} pages, {r['n_cands']} spans capped)")
    toks = crag.answer_tokens(gold, q.text)
    print(f"gold content tokens sought: {sorted(toks)[:12]}")
    hit = next((t for t in r["texts"]
                if crag.answer_present(gold, q.text, crag._tokens(t))), None)
    if hit:
        print(f"a 50-page span containing it:\n  {hit[:260]}")
    print(); SHOWN = globals().setdefault("N",0)+1; globals()["N"]=SHOWN
    if SHOWN >= 4: break
