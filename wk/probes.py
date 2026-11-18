"""Stage-one cheap probes yielding rho_W and rho_K before any answer is generated."""
from __future__ import annotations

import math
import unicodedata
from datetime import date, datetime
from itertools import combinations
from typing import Any, Sequence

import numpy as np

try:
    from wk.contract import Evidence, Question, Record
except ImportError:
    from contract import Evidence, Question, Record

RELEVANCE_THRESHOLD: float = 0.35
CONTRADICTION_THRESHOLD: float = 0.2
TOP_N: int = 10
SECONDS_PER_DAY: float = 86400.0

WEB_FEATURES: tuple[str, ...] = (
    "n_hits", "agreement_at_10", "contradiction_rate", "recency_spread_days")
KB_FEATURES: tuple[str, ...] = (
    "entity_resolved", "relation_present", "node_degree", "type_coverage")

SPAN_KEYS: tuple[str, ...] = ("span", "snippet", "text", "title")
TIME_KEYS: tuple[str, ...] = (
    "timestamp", "ts", "time", "date", "published", "published_at")
RELATION_KEYS: tuple[str, ...] = ("relation", "target_relation", "query_relation")

ARTICLES: frozenset[str] = frozenset({"a", "an", "the"})
TRUE_WORDS: frozenset[str] = frozenset(
    {"1", "true", "t", "yes", "y", "resolved", "present", "linked"})

__all__ = [
    "RELEVANCE_THRESHOLD", "CONTRADICTION_THRESHOLD", "TOP_N",
    "WEB_FEATURES", "KB_FEATURES", "normalise", "token_set",
    "agreement_kernel", "candidate_span", "top_items", "probe_web",
    "probe_kb", "feature_matrix", "impute_nan"]


def _field(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _unit(value: float) -> float:
    return min(1.0, max(0.0, value))


def _truthy(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, str):
        return 1.0 if value.strip().lower() in TRUE_WORDS else 0.0
    if isinstance(value, (bool, int, float)):
        return 1.0 if _as_float(value) > 0.0 else 0.0
    return 1.0 if value else 0.0


def normalise(text: Any) -> str:
    if text is None:
        return ""
    if isinstance(text, (list, tuple, set, frozenset)):
        text = " ".join(str(part) for part in text)
    decomposed = unicodedata.normalize("NFKD", str(text))
    folded = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    plain = "".join(ch.lower() if ch.isalnum() else " " for ch in folded)
    return " ".join(plain.split())


def token_set(text: Any) -> set[str]:
    return {tok for tok in normalise(text).split() if tok not in ARTICLES}


def agreement_kernel(a: Any, b: Any) -> float:
    left, right = token_set(a), token_set(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def candidate_span(item: Any) -> str:
    for key in SPAN_KEYS:
        span = normalise(_field(item, key))
        if span:
            return span
    return ""


def _items(ev: Evidence) -> list[Any]:
    return list(getattr(ev, "items", None) or [])


def _meta(ev: Evidence) -> dict[str, Any]:
    meta = getattr(ev, "meta", None)
    return dict(meta) if isinstance(meta, dict) else {}


def _scored(items: Sequence[Any]) -> bool:
    return any(_field(item, "score") is not None for item in items)


def top_items(ev: Evidence, limit: int = TOP_N) -> list[Any]:
    items = _items(ev)
    if not _scored(items):
        return items[:limit]
    ranked = sorted(items, key=lambda it: _as_float(_field(it, "score")),
                    reverse=True)
    return ranked[:limit]


def _rescale_epoch(seconds: float) -> float | None:
    if not math.isfinite(seconds):
        return None
    return seconds / 1000.0 if abs(seconds) > 1e11 else seconds


def _epoch_seconds(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day).timestamp()
    if isinstance(value, (int, float)):
        return _rescale_epoch(float(value))
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        pass
    try:
        return _rescale_epoch(float(text))
    except ValueError:
        return None


def _item_time(item: Any) -> float | None:
    for key in TIME_KEYS:
        stamp = _epoch_seconds(_field(item, key))
        if stamp is not None:
            return stamp
    return None


def probe_web(q: Question, ev: Evidence) -> dict[str, float]:
    items = _items(ev)
    if _scored(items):
        n_hits = sum(1 for item in items
                     if _as_float(_field(item, "score")) > RELEVANCE_THRESHOLD)
    else:
        n_hits = len(items)
    spans = [span for span in (candidate_span(it) for it in top_items(ev)) if span]
    sims = [agreement_kernel(a, b) for a, b in combinations(spans, 2)]
    agreement = float(np.mean(sims)) if sims else 0.0
    contradiction = (
        float(np.mean([1.0 if s < CONTRADICTION_THRESHOLD else 0.0 for s in sims]))
        if sims else 0.0)
    stamps = [t for t in (_item_time(it) for it in items) if t is not None]
    spread = (max(stamps) - min(stamps)) / SECONDS_PER_DAY if len(stamps) > 1 else 0.0
    return {"n_hits": float(n_hits),
            "agreement_at_10": _unit(agreement),
            "contradiction_rate": _unit(contradiction),
            "recency_spread_days": float(abs(spread))}


def _target_relation(ev: Evidence) -> str:
    meta = _meta(ev)
    for key in RELATION_KEYS:
        relation = normalise(meta.get(key))
        if relation:
            return relation
    return ""


def _has_relation(item: Any, relation: str) -> bool:
    value = _field(item, "value")
    empty = isinstance(value, (str, list, tuple, dict, set)) and len(value) == 0
    if value is None or empty:
        return False
    if not relation:
        return True
    return normalise(_field(item, "relation")) == relation


def _lookup(table: Any, key: Any) -> Any:
    if not isinstance(table, dict) or key is None:
        return None
    if isinstance(key, str) and not key.strip():
        return None
    if key in table:
        return table[key]
    wanted = normalise(key)
    if not wanted:
        return None
    for name, value in table.items():
        if normalise(name) == wanted:
            return value
    return None


def _type_coverage(meta: dict[str, Any], relation: str) -> float:
    if "type_coverage" in meta:
        return _unit(_as_float(meta.get("type_coverage")))
    entry = _lookup(meta.get("type_coverage_table"), meta.get("entity_type"))
    if entry is None:
        return 0.0
    if isinstance(entry, dict):
        chosen = _lookup(entry, relation)
        if chosen is None:
            shares = [_as_float(v) for v in entry.values()]
            return _unit(float(np.mean(shares))) if shares else 0.0
        entry = chosen
    return _unit(_as_float(entry))


def probe_kb(q: Question, ev: Evidence) -> dict[str, float]:
    meta = _meta(ev)
    items = _items(ev)
    relation = _target_relation(ev)
    if "entity_resolved" in meta:
        resolved = _truthy(meta.get("entity_resolved"))
    else:
        resolved = 1.0 if any(_field(it, "entity") for it in items) else 0.0
    if "relation_present" in meta:
        present = _truthy(meta.get("relation_present"))
    else:
        present = 1.0 if any(_has_relation(it, relation) for it in items) else 0.0
    if "node_degree" in meta:
        degree = max(_as_float(meta.get("node_degree")), 0.0)
    else:
        degree = float(len(items))
    if resolved <= 0.0:
        degree = 0.0
    return {"entity_resolved": resolved,
            "relation_present": present,
            "node_degree": float(degree),
            "type_coverage": _type_coverage(meta, relation)}


def feature_matrix(records: Sequence[Record],
                   source: str) -> tuple[np.ndarray, list[str]]:
    rows: list[dict[str, Any]] = []
    for rec in records:
        rho = getattr(rec, "rho", None) or {}
        block = rho.get(source) if isinstance(rho, dict) else None
        rows.append(dict(block) if isinstance(block, dict) else {})
    names = sorted({key for row in rows for key in row})
    X = np.full((len(rows), len(names)), np.nan, dtype=float)
    for i, row in enumerate(rows):
        for j, name in enumerate(names):
            if name in row:
                X[i, j] = _as_float(row[name], default=np.nan)
    return X, names


def impute_nan(X: np.ndarray) -> np.ndarray:
    out = np.array(X, dtype=float, copy=True)
    if out.size == 0:
        return out
    view = out.reshape(-1, 1) if out.ndim == 1 else out
    for column in view.T:
        missing = ~np.isfinite(column)
        if not missing.any():
            continue
        known = column[~missing]
        column[missing] = float(np.median(known)) if known.size else 0.0
    return out
