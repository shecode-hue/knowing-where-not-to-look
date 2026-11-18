"""Offline extractive agent per source, so the 2x2 can be filled without an LLM."""
from __future__ import annotations

import random
import re
from dataclasses import replace
from typing import Any, Iterable, Sequence

try:
    from wk import crag
    from wk.contract import Evidence, Question, Record, SourceRun
except ImportError:
    import crag
    from contract import Evidence, Question, Record, SourceRun

SCORE_THRESHOLD: float = 0.18
TOP_K: int = 5
MAX_SPANS: int = 400
MIN_SPAN_TOKENS: int = 3
MAX_SPAN_TOKENS: int = 60
MIN_PREDICTION_CHARS: int = 4
DIGIT_BONUS: float = 0.05

HEAD_FIELDS: tuple[str, ...] = ("snippet", "title")
BODY_FIELD: str = "text"
ARTICLES: frozenset[str] = frozenset({"a", "an", "the"})
NUMERIC_CUES: tuple[str, ...] = ("how many", "how much", "what year", "when")

_SENTENCE_BREAK = re.compile(r"(?<=[.!?;])\s+|\s*[|•·]\s*|\s{2,}")
_WEIGHT_FLOOR = 1e-9

__all__ = [
    "SCORE_THRESHOLD", "TOP_K", "MAX_SPANS", "candidate_spans", "score_span",
    "run_extractive", "grade", "gold_answers", "answer_in_evidence",
    "impossible_cell", "attach_runs"]


def _field_text(item: Any, key: str) -> str:
    if isinstance(item, dict):
        return str(item.get(key) or "")
    value = getattr(item, key, None)
    if value is None:
        return str(item) if key == BODY_FIELD else ""
    return str(value)


def _spans_from(text: str, seen: set[str], budget: int) -> list[str]:
    out: list[str] = []
    if budget <= 0 or not text:
        return out
    for piece in _SENTENCE_BREAK.split(text):
        if len(out) >= budget:
            break
        span = " ".join(piece.split())
        key = crag.normalise(span)
        size = len(key.split())
        if size < MIN_SPAN_TOKENS or size > MAX_SPAN_TOKENS or key in seen:
            continue
        seen.add(key)
        out.append(span)
    return out


def candidate_spans(ev: Evidence, max_spans: int = MAX_SPANS) -> list[str]:
    items = list(getattr(ev, "items", None) or [])
    if not items or max_spans <= 0:
        return []
    seen: set[str] = set()
    spans: list[str] = []
    for item in items:
        for key in HEAD_FIELDS:
            spans.extend(_spans_from(_field_text(item, key), seen,
                                     max_spans - len(spans)))
    quota = max(1, (max_spans - len(spans)) // len(items))
    for item in items:
        room = min(quota, max_spans - len(spans))
        spans.extend(_spans_from(_field_text(item, BODY_FIELD), seen, room))
    return spans


def _content_tokens(text: Any) -> set[str]:
    return {tok for tok in crag.normalise(text).split() if tok not in ARTICLES}


def _wants_number(question: str) -> bool:
    padded = f" {crag.normalise(question)} "
    return any(f" {cue} " in padded for cue in NUMERIC_CUES)


def score_span(question: str, span: str) -> float:
    asked = _content_tokens(question)
    found = _content_tokens(span)
    if not asked or not found:
        return 0.0
    overlap = len(asked & found) / len(asked | found)
    if _wants_number(question) and any(ch.isdigit() for ch in span):
        overlap += DIGIT_BONUS
    return min(1.0, overlap)


def _ranked_spans(question: str, spans: Sequence[str]) -> list[tuple[float, str]]:
    scored = [(score_span(question, span), span) for span in spans]
    return sorted(scored, key=lambda pair: (-pair[0], crag.normalise(pair[1])))


def gold_answers(q: Question) -> list[str]:
    item = crag.RAW_ITEMS.get(q.qid, {})
    out: list[str] = []
    for gold in [q.answer, *crag._alt_answers(item)]:
        target = crag.normalise(gold)
        if target and target not in crag.NO_ANSWER and gold not in out:
            out.append(gold)
    return out


def grade(prediction: str | None, golds: list[str], question: str = "") -> bool:
    if prediction is None:
        return False
    said = crag._tokens(prediction)
    if not said:
        return False
    return any(crag.answer_present(g, question, said) for g in golds)


def answer_in_evidence(q: Question, ev: Evidence) -> bool:
    return crag._CragSource().contains_answer(q, ev)


def run_extractive(q: Question, ev: Evidence, n: int = 10,
                   seed: int = 0) -> SourceRun:
    width = max(0, int(n))
    name = getattr(ev, "source", "") or ""
    top = _ranked_spans(q.text, candidate_spans(ev))[:TOP_K]
    if not top or top[0][0] < SCORE_THRESHOLD:
        return SourceRun(qid=q.qid, source=name, answers=[None] * width,
                         correct=[False] * width)
    rng = random.Random(f"{seed}:{q.qid}")
    answers = rng.choices([span for _, span in top],
                          weights=[max(score, _WEIGHT_FLOOR) for score, _ in top],
                          k=width) if width else []
    golds = gold_answers(q)
    correct = [grade(answer, golds, q.text) for answer in answers]
    return SourceRun(qid=q.qid, source=name, answers=list(answers),
                     correct=correct)


def impossible_cell(records: Sequence[Record], source: str) -> list[str]:
    return [rec.question.qid for rec in records
            if source in rec.runs and not rec.membership.get(source, False)
            and rec.runs[source].majority_correct]


def attach_runs(records: Iterable[Record], source: str,
                sources_map: dict[str, Any], n: int = 10,
                seed: int = 0) -> None:
    agent = sources_map.get(source)
    if agent is None:
        raise KeyError(f"no source registered under {source!r}; sources_map "
                       f"holds {sorted(sources_map)}")
    for rec in records:
        ev = agent.retrieve(rec.question)
        rec.membership.setdefault(source, answer_in_evidence(rec.question, ev))
        run = run_extractive(rec.question, ev, n=n, seed=seed)
        rec.runs[source] = replace(run, source=source)
