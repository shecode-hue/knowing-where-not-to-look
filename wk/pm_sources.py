"""The P source (the model's own knowledge) and the M source (its memory)."""
import json
import math
from dataclasses import replace
from pathlib import Path

from wk import crag, llm
from wk.contract import Evidence, Question, SourceRun

ROOT = Path(__file__).resolve().parent.parent
MEMORY = ROOT / "results" / "memory.json"
KEEP_ABOVE = -0.7


class ParametricSource:
    name = "P"

    def retrieve(self, q: Question) -> Evidence:
        return Evidence(source="P", items=[], meta={"n_hits": 0.0})

    def probe(self, q: Question, ev: Evidence) -> dict[str, float]:
        out = llm.recall(q.text)
        ev.meta["said"] = out["raw"]
        ev.meta["abstained"] = float(out["abstained"])
        ev.meta["mean_logprob"] = out["mean_logprob"]
        return {"p_abstained": float(out["abstained"]),
                "p_logprob": out["mean_logprob"]}

    def contains_answer(self, q: Question, ev: Evidence) -> bool:
        said = ev.meta.get("said")
        if said is None:
            said = llm.recall(q.text)["raw"]
            ev.meta["said"] = said
        from wk.baseline_agent import grade
        return grade(said, crag.gold_answers(q), q.text)

    def run(self, q: Question, ev: Evidence, n: int = 1) -> SourceRun:
        from wk.baseline_agent import grade
        golds = crag.gold_answers(q)
        answers, correct = [], []
        for i in range(n):
            out = llm.recall(q.text, seed=i,
                             temperature=0.0 if n == 1 else 0.7)
            answers.append(out["answer"])
            correct.append(grade(out["answer"], golds, q.text))
            ev.meta.setdefault("logprobs", []).append(out["mean_logprob"])
        return SourceRun(qid=q.qid, source="P", answers=answers,
                         correct=correct)


class MemorySource:
    name = "M"

    def __init__(self, path: Path = MEMORY, store: dict | None = None):
        self.path = path
        if store is not None:
            self.store = store
        elif path.exists():
            self.store = json.loads(path.read_text())
        else:
            self.store = {}

    def _keys(self, q: Question) -> list[str]:
        toks = [t for t in crag._tokens(q.text) if t not in crag.STOPWORDS]
        out = []
        for size in range(min(5, len(toks)), 1, -1):
            for i in range(len(toks) - size + 1):
                out.append(" ".join(toks[i:i + size]))
        return out

    def remember(self, q: Question, answer: str, logprob: float) -> None:
        if not answer or (logprob is not None and not math.isnan(logprob)
                          and logprob < KEEP_ABOVE):
            return
        for key in self._keys(q)[:3]:
            self.store.setdefault(key, []).append(
                {"q": q.text, "a": answer, "lp": logprob})

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.store))

    def retrieve(self, q: Question) -> Evidence:
        hits = []
        for key in self._keys(q):
            for rec in self.store.get(key, []):
                if rec["q"] != q.text:
                    hits.append({"entity": key,
                                 "text": f"{rec['q']} {rec['a']}."})
        seen, items = set(), []
        for h in hits:
            if h["text"] not in seen:
                seen.add(h["text"])
                items.append(h)
        return Evidence(source="M", items=items[:20],
                        meta={"n_hits": float(len(items)),
                              "n_keys": float(len(self.store))})

    def probe(self, q: Question, ev: Evidence) -> dict[str, float]:
        return {"m_hits": ev.meta["n_hits"],
                "m_empty": 1.0 if not ev.items else 0.0}

    def contains_answer(self, q: Question, ev: Evidence) -> bool:
        hay = []
        for item in ev.items:
            hay.extend(crag._tokens(item["text"]))
        return any(crag.answer_present(g, q.text, hay)
                   for g in crag.gold_answers(q))

    def run(self, q: Question, ev: Evidence, n: int = 1) -> SourceRun:
        if not ev.items:
            return SourceRun(qid=q.qid, source="M", answers=[None] * n,
                             correct=[False] * n)
        from wk.baseline_agent import run_extractive
        return replace(run_extractive(q, ev, n=n), source="M")
