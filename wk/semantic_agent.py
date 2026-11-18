"""Semantic agent: BM25 shortlist, embedding rank, cross-encoder rerank."""
from __future__ import annotations

import os
from dataclasses import replace
from typing import Any, Sequence

import numpy as np

from wk import crag
from wk.baseline_agent import candidate_spans, gold_answers, grade
from wk.contract import Evidence, Question, SourceRun

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

EMBED_MODEL = "sentence-transformers/multi-qa-MiniLM-L6-cos-v1"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
SHORTLIST = 100
RERANK = 30
MAX_SPANS = 400
_MODELS: dict[str, Any] = {}


def models() -> tuple[Any, Any]:
    if "embed" not in _MODELS:
        from sentence_transformers import CrossEncoder, SentenceTransformer
        embed = SentenceTransformer(EMBED_MODEL)
        embed.max_seq_length = 128
        _MODELS["embed"] = embed
        _MODELS["rerank"] = CrossEncoder(RERANK_MODEL, max_length=192)
    return _MODELS["embed"], _MODELS["rerank"]


def content_tokens(text: Any) -> list[str]:
    return [t for t in crag._tokens(text) if t not in crag.STOPWORDS]


def passages(ev: Evidence, max_spans: int = MAX_SPANS) -> list[str]:
    spans = candidate_spans(ev, max_spans=max_spans)
    out, seen = [], set()
    for i, span in enumerate(spans):
        text = span
        if i + 1 < len(spans):
            text = f"{span} {spans[i + 1]}"
        key = crag.normalise(text)
        if key and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def shortlist(question: str, cands: Sequence[str],
              size: int = SHORTLIST) -> np.ndarray:
    from rank_bm25 import BM25Okapi
    if not cands:
        return np.zeros(0, dtype=int)
    corpus = [content_tokens(c) or ["_"] for c in cands]
    scores = BM25Okapi(corpus).get_scores(content_tokens(question) or ["_"])
    return np.argsort(-np.asarray(scores))[:size]


def score_question(question: str, cands: Sequence[str]) -> dict[str, Any]:
    keep = shortlist(question, cands)
    if keep.size == 0:
        return {"idx": keep, "ce": np.zeros(0), "cos": np.zeros(0)}
    embed, rerank = models()
    texts = [cands[i] for i in keep]
    qv = embed.encode([question], normalize_embeddings=True,
                      show_progress_bar=False)[0]
    ev = embed.encode(texts, batch_size=256, normalize_embeddings=True,
                      show_progress_bar=False)
    cos = np.asarray(ev @ qv)
    top = np.argsort(-cos)[:RERANK]
    ce = np.asarray(rerank.predict([(question, texts[j]) for j in top],
                                   batch_size=128, show_progress_bar=False))
    return {"idx": keep[top], "ce": ce, "cos": cos[top]}


def features(scored: dict[str, Any]) -> dict[str, float]:
    ce, cos = scored["ce"], scored["cos"]
    if ce.size == 0:
        return {"ce_top": -12.0, "ce_margin": 0.0, "ce_mean": -12.0,
                "cos_top": 0.0, "n_cand": 0.0}
    order = np.argsort(-ce)
    best = float(ce[order[0]])
    second = float(ce[order[1]]) if ce.size > 1 else best
    return {"ce_top": best, "ce_margin": best - second,
            "ce_mean": float(ce.mean()), "cos_top": float(cos.max()),
            "n_cand": float(ce.size)}


def run_semantic(q: Question, ev: Evidence, scored: dict[str, Any],
                 cands: Sequence[str], n: int = 10,
                 threshold: float | None = None) -> SourceRun:
    name = getattr(ev, "source", "") or ""
    ce = scored["ce"]
    if ce.size == 0:
        return SourceRun(qid=q.qid, source=name, answers=[None] * n,
                         correct=[False] * n)
    best = int(scored["idx"][int(np.argmax(ce))])
    if threshold is not None and float(ce.max()) < threshold:
        return SourceRun(qid=q.qid, source=name, answers=[None] * n,
                         correct=[False] * n)
    answer = cands[best]
    ok = grade(answer, gold_answers(q), q.text)
    return SourceRun(qid=q.qid, source=name, answers=[answer] * n,
                     correct=[ok] * n)


def attach(rec, source_name: str, ev: Evidence, scored: dict[str, Any],
           cands: Sequence[str], threshold: float | None = None) -> None:
    run = run_semantic(rec.question, ev, scored, cands, threshold=threshold)
    rec.runs[source_name] = replace(run, source=source_name)
