"""Adversarial check that the H2 class model recovers injected signal honestly."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wk.classmodel import (REFUTATION_THRESHOLD, cross_val_auroc,
                           feature_importance, fit_class_model, labels,
                           permutation_baseline)
from wk.contract import CLASSES, Question, Record
from wk.probes import KB_FEATURES, WEB_FEATURES, feature_matrix
from wk.simulate import SOURCES, make_synthetic

N_RECORDS = 3000
SEED = 11
N_SPLITS = 5
N_PERM = 200
DECLARED: dict[str, tuple[str, ...]] = {"W": WEB_FEATURES, "K": KB_FEATURES}


@pytest.fixture(scope="module")
def records() -> list[Record]:
    return make_synthetic(N_RECORDS, seed=SEED)


@pytest.fixture(scope="module")
def designs(records: list[Record]) -> dict[str, tuple]:
    built = {}
    for source in SOURCES:
        X, names = feature_matrix(records, source)
        built[source] = (X, names, labels(records, source))
    return built


@pytest.fixture(scope="module")
def scores(designs: dict[str, tuple]) -> dict[str, dict]:
    return {
        source: cross_val_auroc(X, y, n_splits=N_SPLITS, seed=0)
        for source, (X, _, y) in designs.items()
    }


def _marginal_auroc(X: np.ndarray, y: np.ndarray,
                    names: list[str]) -> dict[str, tuple[float, str]]:
    best: dict[str, tuple[float, str]] = {}
    for cls in np.unique(y):
        target = (y == cls).astype(int)
        ranked = []
        for j, name in enumerate(names):
            one = float(roc_auc_score(target, X[:, j]))
            ranked.append((max(one, 1.0 - one), name))
        best[str(cls)] = max(ranked)
    return best


def _blame(source: str, macro: float,
           marginal: dict[str, tuple[float, str]]) -> str:
    strongest, feature = max(marginal.values())
    head = (f"{source}: macro AUROC {macro:.4f} does not clear "
            f"{REFUTATION_THRESHOLD} on the simulator. ")
    if strongest < 0.60:
        return head + (
            f"The strongest single rho feature, {feature}, only reaches "
            f"{strongest:.4f} on its own, so no class signal was injected: "
            "wk.simulate is at fault, not the class model.")
    return head + (
        f"Yet rho feature {feature} alone reaches {strongest:.4f}, so the "
        "signal is present in the records and is being lost downstream: "
        "wk.probes.feature_matrix or wk.classmodel is at fault, not the "
        "simulator.")


def test_design_matrix_matches_the_probe_contract(designs):
    for source, (X, names, y) in designs.items():
        assert X.shape == (N_RECORDS, len(DECLARED[source]))
        assert names == sorted(DECLARED[source])
        assert np.isfinite(X).all()
        found, counts = np.unique(y, return_counts=True)
        assert set(str(c) for c in found) == set(CLASSES)
        assert int(counts.min()) >= N_SPLITS


def test_labels_match_the_simulator_truth(records, designs):
    for source, (_, _, y) in designs.items():
        truth = np.asarray([rec.truth[f"class_{source}"] for rec in records])
        assert (y == truth).all()


def test_no_single_probe_feature_is_a_label_proxy(designs):
    for source, (X, names, y) in designs.items():
        marginal = _marginal_auroc(X, y, names)
        for cls, (value, feature) in marginal.items():
            assert value < 0.99, (
                f"{source}: rho feature {feature} separates {cls} at "
                f"{value:.4f} on its own, which means the label has leaked "
                "into stage one")


def test_fitted_model_covers_every_class_and_names_its_features(designs):
    for _, (X, names, y) in designs.items():
        model = fit_class_model(X, y, seed=0)
        assert [str(c) for c in model[-1].classes_] == sorted(CLASSES)
        proba = model.predict_proba(X)
        assert proba.shape == (N_RECORDS, len(CLASSES))
        assert np.allclose(proba.sum(axis=1), 1.0)
        frame = feature_importance(model, names)
        assert len(frame) == len(CLASSES) * len(names)
        assert set(frame["feature"]) == set(names)
        assert float(frame["abs_coefficient"].max()) > 0.0


def test_cross_val_auroc_clears_the_refutation_threshold(designs, scores):
    for source, (X, names, y) in designs.items():
        score = scores[source]
        macro = score["macro"]
        assert macro > REFUTATION_THRESHOLD, _blame(
            source, macro, _marginal_auroc(X, y, names))
        assert score["refuted"] is False
        assert score["n"] == N_RECORDS
        assert score["n_splits"] == N_SPLITS
        for cls in CLASSES:
            assert 0.0 <= score[cls] <= 1.0


def test_permutation_null_is_centred_and_the_observed_score_significant(
        designs, scores):
    for source, (X, _, y) in designs.items():
        null = permutation_baseline(X, y, n_perm=N_PERM, seed=0,
                                    n_splits=N_SPLITS)
        assert null["observed"] == pytest.approx(scores[source]["macro"])
        assert abs(null["mean"] - 0.5) < 0.02
        assert null["std"] < 0.05
        assert null["p_value"] < 0.01
        assert null["observed"] > null["p95"]
        assert float(np.max(null["null"])) < null["observed"]


def test_cross_validation_is_out_of_fold_not_in_sample():
    rng = np.random.default_rng(4)
    X = rng.normal(size=(300, 60))
    y = np.asarray(CLASSES)[rng.integers(0, len(CLASSES), X.shape[0])]
    out_of_fold = cross_val_auroc(X, y, n_splits=N_SPLITS, seed=0)["macro"]
    model = fit_class_model(X, y, seed=0)
    proba = model.predict_proba(X)
    in_sample = float(np.mean([
        roc_auc_score((y == cls).astype(int), proba[:, i])
        for i, cls in enumerate(model[-1].classes_)]))
    assert out_of_fold < 0.60
    assert in_sample > out_of_fold + 0.10


def test_per_class_columns_stay_aligned():
    rng = np.random.default_rng(5)
    pool = np.asarray(["zebra", "alpha", "middle"])
    y = pool[rng.integers(0, pool.size, 600)]
    X = np.zeros((y.size, 2))
    X[y == "zebra"] = (12.0, 0.0)
    X[y == "alpha"] = (-12.0, 0.0)
    X[y == "middle"] = (0.0, 12.0)
    X = X + rng.normal(0.0, 0.01, size=X.shape)
    score = cross_val_auroc(X, y, n_splits=N_SPLITS, seed=0)
    for cls in pool:
        assert score[str(cls)] == pytest.approx(1.0, abs=1e-9)


def test_nan_input_is_rejected():
    holed = make_synthetic(400, seed=5)
    y = labels(holed, "W")
    holed[7].rho.pop("W")
    X, _ = feature_matrix(holed, "W")
    assert not np.isfinite(X).all()
    with pytest.raises(ValueError, match="NaN or infinite"):
        cross_val_auroc(X, y, n_splits=N_SPLITS)
    with pytest.raises(ValueError, match="NaN or infinite"):
        fit_class_model(X, y)
    with pytest.raises(ValueError, match="NaN or infinite"):
        permutation_baseline(X, y, n_perm=4, n_splits=N_SPLITS)
    spiked, _ = feature_matrix(make_synthetic(400, seed=5), "W")
    spiked[3, 1] = np.inf
    with pytest.raises(ValueError, match="NaN or infinite"):
        cross_val_auroc(spiked, y, n_splits=N_SPLITS)


def test_single_class_target_is_rejected(designs):
    X, _, y = designs["W"]
    only = np.asarray([CLASSES[0]] * y.size)
    with pytest.raises(ValueError, match="at least two classes"):
        cross_val_auroc(X, only, n_splits=N_SPLITS)
    with pytest.raises(ValueError, match="at least two classes"):
        fit_class_model(X, only)
    with pytest.raises(ValueError, match="at least two classes"):
        permutation_baseline(X, only, n_perm=4, n_splits=N_SPLITS)


def test_labels_refuse_a_member_question_carrying_no_run():
    question = Question(qid="q0001", text="Who funds the array?",
                        answer="Meridian Foundation")
    with pytest.raises(ValueError, match="carries no run"):
        labels([Record(question=question, membership={"K": True})], "K")
    outside = Record(question=question, membership={"K": False})
    assert labels([outside], "K").tolist() == ["ghost"]


def test_knowledge_base_class_is_more_predictable_than_the_open_web(scores):
    assert scores["K"]["ghost"] > scores["W"]["ghost"]
    assert scores["K"]["macro"] > scores["W"]["macro"]


def test_macro_is_the_mean_of_the_class_aurocs(scores, capsys):
    with capsys.disabled():
        print()
        for source in SOURCES:
            score = scores[source]
            parts = [score[cls] for cls in CLASSES]
            assert score["macro"] == pytest.approx(float(np.mean(parts)))
            print(f"  {source}: macro {score['macro']:.4f}  "
                  f"covered {score['covered']:.4f}  "
                  f"rare {score['rare']:.4f}  "
                  f"ghost {score['ghost']:.4f}")
