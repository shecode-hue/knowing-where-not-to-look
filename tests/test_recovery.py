"""Recovery tests: the estimators must return the simulator's known r, g and lambda."""
from __future__ import annotations

import copy
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wk.contract import DYNAMISM, Record, class_of
from wk.estimators import (
    by_stratum,
    estimate_g,
    estimate_lambda,
    estimate_r,
    two_by_two,
)
from wk.simulate import STALENESS, make_synthetic

N_RECORDS = 4000
SEED = 0
N_BOOT = 4000
TOLERANCE = 0.04
FLAT_BAND = 0.05
MIN_KB_SEPARATION = 0.30
GHOST_CONFIDENT = 0.6

TRUTH: dict[str, dict[str, float]] = {
    "W": {"r": 0.72, "g": 0.12},
    "K": {"r": 0.93, "g": 0.45},
}
SOURCES = tuple(TRUTH)
POINT_CASES = [(s, q) for s in SOURCES for q in ("r", "g")]
ESTIMATORS = {"r": estimate_r, "g": estimate_g, "lambda": estimate_lambda}


@pytest.fixture(scope="module")
def records() -> list[Record]:
    return make_synthetic(
        N_RECORDS,
        seed=SEED,
        r_W=TRUTH["W"]["r"],
        g_W=TRUTH["W"]["g"],
        r_K=TRUTH["K"]["r"],
        g_K=TRUTH["K"]["g"],
    )


@pytest.fixture(scope="module")
def estimates(records: list[Record]) -> dict[tuple[str, str], object]:
    return {
        (source, quantity): fn(records, source, n_boot=N_BOOT, seed=SEED)
        for source in SOURCES
        for quantity, fn in ESTIMATORS.items()
    }


@pytest.fixture(scope="module")
def ghost_by_dynamism(records: list[Record]) -> dict[str, dict[str, object]]:
    return {
        source: {
            label: strata["g"]
            for label, strata in by_stratum(
                records, source, "dynamism", n_boot=N_BOOT, seed=SEED
            ).items()
        }
        for source in SOURCES
    }


def _declared(records: list[Record], quantity: str, source: str) -> float:
    return float(np.mean([rec.truth[f"{quantity}_{source}"] for rec in records]))


def test_simulator_declares_the_requested_truth(records: list[Record]) -> None:
    assert len(records) == N_RECORDS
    for source in SOURCES:
        assert _declared(records, "r", source) == pytest.approx(
            TRUTH[source]["r"])
        assert _declared(records, "g", source) == pytest.approx(
            TRUTH[source]["g"], abs=TOLERANCE / 2.0)
    assert {rec.truth["g_W"] for rec in records} == {TRUTH["W"]["g"]}
    for rec in records:
        expected = TRUTH["K"]["g"] * STALENESS[rec.question.dynamism]
        assert rec.truth["g_K"] == pytest.approx(expected, abs=1e-9)


def test_staleness_preserves_the_marginal_ghost_mass() -> None:
    multipliers = [STALENESS[label] for label in DYNAMISM]
    assert len(multipliers) == len(STALENESS)
    assert float(np.mean(multipliers)) == pytest.approx(1.0)
    assert max(multipliers) * TRUTH["K"]["g"] < 0.95


@pytest.mark.parametrize(("source", "quantity"), POINT_CASES)
def test_point_estimate_recovers_truth(
    estimates: dict, source: str, quantity: str
) -> None:
    est = estimates[(source, quantity)]
    true = TRUTH[source][quantity]
    assert est.n > 0
    assert abs(est.value - true) < TOLERANCE, (
        f"{quantity}_{source} estimated at {est.value:.4f}, truth {true:.4f}")


@pytest.mark.parametrize(("source", "quantity"), POINT_CASES)
def test_bootstrap_interval_covers_truth(
    estimates: dict, source: str, quantity: str
) -> None:
    est = estimates[(source, quantity)]
    true = TRUTH[source][quantity]
    assert est.lo < est.hi
    assert est.lo <= true <= est.hi, (
        f"{quantity}_{source} interval [{est.lo:.4f}, {est.hi:.4f}] misses "
        f"truth {true:.4f}")


@pytest.mark.parametrize("source", SOURCES)
def test_lambda_recovers_the_rare_passage_mass(
    records: list[Record], estimates: dict, source: str
) -> None:
    est = estimates[(source, "lambda")]
    true = _declared(records, "lambda", source)
    assert est.lo <= true <= est.hi, (
        f"lambda_{source} interval [{est.lo:.4f}, {est.hi:.4f}] misses "
        f"truth {true:.4f}")
    assert abs(est.value - true) < TOLERANCE


@pytest.mark.parametrize("source", SOURCES)
def test_class_masses_partition_the_questions(
    estimates: dict, source: str
) -> None:
    r = estimates[(source, "r")].value
    g = estimates[(source, "g")].value
    lam = estimates[(source, "lambda")].value
    assert (1.0 - g) * r + lam + g == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("source", SOURCES)
def test_no_impossible_cells_on_clean_data(
    records: list[Record], source: str
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        cells = two_by_two(records, source)
    assert cells["impossible"] == 0
    assert sum(v for k, v in cells.items() if k != "impossible") == N_RECORDS


@pytest.mark.parametrize("source", SOURCES)
def test_ghost_cell_split_recovers_the_confident_ghost_rate(
    records: list[Record], source: str
) -> None:
    cells = two_by_two(records, source)
    ghost = cells["ghost_abstained"] + cells["ghost_answered"]
    assert ghost > 0
    assert abs(cells["ghost_answered"] / ghost - GHOST_CONFIDENT) < TOLERANCE


def test_impossible_cell_is_detected_when_membership_is_wrong() -> None:
    spoiled = copy.deepcopy(make_synthetic(200, seed=5))
    covered = next(rec for rec in spoiled if class_of(rec, "W") == "covered")
    covered.membership["W"] = False
    with pytest.warns(UserWarning, match="impossible cell"):
        cells = two_by_two(spoiled, "W")
    assert cells["impossible"] == 1


def test_kb_ghost_mass_rises_with_dynamism(ghost_by_dynamism: dict) -> None:
    kb = ghost_by_dynamism["K"]
    values = [kb[label].value for label in DYNAMISM]
    assert values == sorted(values)
    assert kb["realtime"].value > kb["static"].value
    assert kb["realtime"].value - kb["static"].value > MIN_KB_SEPARATION
    assert kb["realtime"].lo > kb["static"].hi


def test_web_ghost_mass_is_flat_across_dynamism(ghost_by_dynamism: dict) -> None:
    web = ghost_by_dynamism["W"]
    values = [web[label].value for label in DYNAMISM]
    assert max(values) - min(values) < FLAT_BAND
    assert abs(web["realtime"].value - web["static"].value) < FLAT_BAND
    assert web["realtime"].lo <= web["static"].hi
    assert web["static"].lo <= web["realtime"].hi


def test_only_the_kb_separates_on_dynamism(ghost_by_dynamism: dict) -> None:
    kb, web = ghost_by_dynamism["K"], ghost_by_dynamism["W"]
    kb_gap = kb["realtime"].value - kb["static"].value
    web_gap = abs(web["realtime"].value - web["static"].value)
    assert kb_gap > MIN_KB_SEPARATION > web_gap


def test_make_synthetic_is_deterministic() -> None:
    assert make_synthetic(200, seed=11) == make_synthetic(200, seed=11)


def test_make_synthetic_serialises_identically_under_one_seed() -> None:
    left = [rec.to_json() for rec in make_synthetic(200, seed=11)]
    right = [rec.to_json() for rec in make_synthetic(200, seed=11)]
    assert left == right


def test_make_synthetic_depends_on_the_seed() -> None:
    left = [rec.question.text for rec in make_synthetic(200, seed=11)]
    right = [rec.question.text for rec in make_synthetic(200, seed=12)]
    assert left != right
