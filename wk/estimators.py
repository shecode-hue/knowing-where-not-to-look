"""Contingency cells and bootstrapped r, g and lambda estimates for each source."""
from __future__ import annotations

import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from wk.contract import DYNAMISM, POPULARITY, Record

CELLS = ("covered", "rare", "ghost_abstained", "ghost_answered")
QUANTITIES = ("r", "g", "lambda")

_CELL_INDEX = {name: i for i, name in enumerate(CELLS)}
_NUMERATOR = {
    "r": ("covered",),
    "g": ("ghost_abstained", "ghost_answered"),
    "lambda": ("rare",),
}
_DENOMINATOR = {
    "r": ("covered", "rare"),
    "g": CELLS,
    "lambda": CELLS,
}
_NAN = float("nan")
_MAX_DRAW = 2_000_000


@dataclass(frozen=True)
class Estimate:
    value: float
    lo: float
    hi: float
    n: int


def usable_records(records: Sequence[Record], source: str) -> list[Record]:
    return [rec for rec in records if source in rec.runs]


def _cell_counts(records: Sequence[Record], source: str) -> tuple[dict[str, int], int]:
    counts = dict.fromkeys(CELLS, 0)
    impossible = 0
    for rec in records:
        run = rec.runs.get(source)
        if run is None:
            continue
        if rec.membership.get(source, False):
            counts["covered" if run.majority_correct else "rare"] += 1
        else:
            counts["ghost_abstained" if run.abstained else "ghost_answered"] += 1
            if run.majority_correct:
                impossible += 1
    return counts, impossible


def two_by_two(records: Sequence[Record], source: str) -> dict[str, int]:
    counts, impossible = _cell_counts(records, source)
    if impossible:
        warnings.warn(
            f"{impossible} impossible cell(s) for source {source}: membership "
            "labels may be wrong, the source may have leaked, or the grader "
            "scored a lucky guess as correct",
            stacklevel=2,
        )
    return {
        "covered": counts["covered"],
        "rare": counts["rare"],
        "ghost_abstained": counts["ghost_abstained"],
        "ghost_answered": counts["ghost_answered"],
        "impossible": impossible,
    }


def _ratio(counts: dict[str, int], quantity: str) -> tuple[float, int]:
    den = sum(counts[cell] for cell in _DENOMINATOR[quantity])
    if den == 0:
        return _NAN, 0
    num = sum(counts[cell] for cell in _NUMERATOR[quantity])
    return num / den, den


def r_point(records: Sequence[Record], source: str) -> float:
    return _ratio(_cell_counts(records, source)[0], "r")[0]


def g_point(records: Sequence[Record], source: str) -> float:
    return _ratio(_cell_counts(records, source)[0], "g")[0]


def lambda_point(records: Sequence[Record], source: str) -> float:
    return _ratio(_cell_counts(records, source)[0], "lambda")[0]


_POINT_OF = {"r": r_point, "g": g_point, "lambda": lambda_point}
_QUANTITY_OF = {fn: quantity for quantity, fn in _POINT_OF.items()}


def _codes(records: Sequence[Record], source: str) -> np.ndarray:
    out = np.empty(len(records), dtype=np.int64)
    for i, rec in enumerate(records):
        run = rec.runs[source]
        if rec.membership.get(source, False):
            out[i] = 0 if run.majority_correct else 1
        else:
            out[i] = 2 if run.abstained else 3
    return out


def _ratio_replicates(
    codes: np.ndarray, quantity: str, n_boot: int, rng: np.random.Generator
) -> np.ndarray:
    n = int(codes.size)
    width = len(CELLS)
    num_idx = [_CELL_INDEX[cell] for cell in _NUMERATOR[quantity]]
    den_idx = [_CELL_INDEX[cell] for cell in _DENOMINATOR[quantity]]
    block = max(1, _MAX_DRAW // max(n, 1))
    out = np.empty(n_boot, dtype=float)
    done = 0
    while done < n_boot:
        size = min(block, n_boot - done)
        idx = rng.integers(0, n, size=(size, n))
        shifted = codes[idx] + width * np.arange(size, dtype=np.int64)[:, None]
        tally = np.bincount(shifted.ravel(), minlength=width * size)
        tally = tally.reshape(size, width).astype(float)
        den = tally[:, den_idx].sum(axis=1)
        num = tally[:, num_idx].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[done:done + size] = num / np.where(den > 0, den, _NAN)
        done += size
    return out


def _as_float(value: Any) -> float:
    if isinstance(value, Estimate):
        value = value.value
    try:
        return float(value)
    except (TypeError, ValueError):
        return _NAN


def _call_stat(stat_fn: Callable, sample: list[Record], source: str) -> Any:
    try:
        return stat_fn(sample, source)
    except TypeError:
        return stat_fn(sample)


def _generic_replicates(
    records: Sequence[Record],
    source: str,
    stat_fn: Callable,
    n_boot: int,
    rng: np.random.Generator,
) -> np.ndarray:
    n = len(records)
    out = np.empty(n_boot, dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for b in range(n_boot):
            idx = rng.integers(0, n, size=n)
            sample = [records[i] for i in idx]
            try:
                out[b] = _as_float(_call_stat(stat_fn, sample, source))
            except Exception:
                out[b] = _NAN
    return out


def bootstrap_ci(
    records: Sequence[Record],
    source: str,
    stat_fn: Callable,
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    recs = usable_records(records, source)
    if not recs or n_boot <= 0 or not 0.0 < alpha < 1.0:
        return _NAN, _NAN
    rng = np.random.default_rng(seed)
    quantity = _QUANTITY_OF.get(stat_fn)
    if quantity is None:
        draws = _generic_replicates(recs, source, stat_fn, int(n_boot), rng)
    else:
        draws = _ratio_replicates(_codes(recs, source), quantity, int(n_boot), rng)
    draws = draws[np.isfinite(draws)]
    if draws.size == 0:
        return _NAN, _NAN
    lo, hi = np.percentile(draws, [100.0 * alpha / 2.0, 100.0 * (1.0 - alpha / 2.0)])
    return float(lo), float(hi)


def _estimate(
    records: Sequence[Record],
    source: str,
    quantity: str,
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 0,
) -> Estimate:
    recs = usable_records(records, source)
    value, n = _ratio(_cell_counts(recs, source)[0], quantity)
    if n == 0:
        return Estimate(_NAN, _NAN, _NAN, 0)
    lo, hi = bootstrap_ci(recs, source, _POINT_OF[quantity], n_boot, alpha, seed)
    return Estimate(float(value), lo, hi, int(n))


def estimate_r(
    records: Sequence[Record],
    source: str,
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 0,
) -> Estimate:
    return _estimate(records, source, "r", n_boot, alpha, seed)


def estimate_g(
    records: Sequence[Record],
    source: str,
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 0,
) -> Estimate:
    return _estimate(records, source, "g", n_boot, alpha, seed)


def estimate_lambda(
    records: Sequence[Record],
    source: str,
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 0,
) -> Estimate:
    return _estimate(records, source, "lambda", n_boot, alpha, seed)


def _canonical_order(key: str) -> tuple[str, ...]:
    if key == "dynamism":
        return DYNAMISM
    if key == "popularity":
        return POPULARITY
    return ()


def _grouped(records: Sequence[Record], key: str) -> dict[str, list[Record]]:
    groups: dict[str, list[Record]] = {}
    for rec in records:
        label = str(getattr(rec.question, key, "unknown"))
        groups.setdefault(label, []).append(rec)
    order = _canonical_order(key)
    known = [g for g in order if g in groups]
    rest = sorted(g for g in groups if g not in known)
    return {g: groups[g] for g in known + rest}


def by_stratum(
    records: Sequence[Record],
    source: str,
    key: str,
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict[str, dict[str, Estimate]]:
    out: dict[str, dict[str, Estimate]] = {}
    for label, group in _grouped(records, key).items():
        out[label] = {
            quantity: _estimate(group, source, quantity, n_boot, alpha, seed)
            for quantity in QUANTITIES
        }
    return out


def summary_table(
    records: Sequence[Record],
    sources: Sequence[str] = ("W", "K"),
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 0,
) -> pd.DataFrame:
    rows = []
    for source in sources:
        for quantity in QUANTITIES:
            est = _estimate(records, source, quantity, n_boot, alpha, seed)
            rows.append({
                "source": source,
                "quantity": quantity,
                "value": est.value,
                "lo": est.lo,
                "hi": est.hi,
                "n": est.n,
            })
    return pd.DataFrame(rows, columns=["source", "quantity", "value", "lo", "hi", "n"])
