"""H2 test: do the stage-1 rho features alone predict covered, rare or ghost?"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from wk.contract import Record, class_of

REFUTATION_THRESHOLD = 0.6


def labels(records: Sequence[Record], source: str) -> np.ndarray:
    out: list[str] = []
    for rec in records:
        if rec.membership.get(source, False) and source not in rec.runs:
            raise ValueError(
                f"question {rec.question.qid!r} is marked present in corpus "
                f"{source!r} but carries no run for it")
        out.append(class_of(rec, source))
    return np.asarray(out, dtype=str)


def _check(
    X: Any, y: Any, n_splits: int | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=str)
    if X.ndim != 2:
        raise ValueError(f"X must be two-dimensional, got shape {X.shape}")
    if y.ndim != 1:
        raise ValueError(f"y must be one-dimensional, got shape {y.shape}")
    if X.shape[0] != y.shape[0]:
        raise ValueError(
            f"X has {X.shape[0]} rows but y has {y.shape[0]} labels")
    if X.shape[0] == 0:
        raise ValueError("X is empty; nothing to fit")
    if not np.isfinite(X).all():
        bad = int(np.count_nonzero(~np.isfinite(X)))
        raise ValueError(
            f"X contains {bad} NaN or infinite value(s); the probe must emit a "
            "finite number for every feature, so impute or drop them first")
    present, counts = np.unique(y, return_counts=True)
    if present.size < 2:
        raise ValueError(
            f"need at least two classes to test H2, got only {present.tolist()}")
    if n_splits is not None:
        if n_splits < 2:
            raise ValueError(f"n_splits must be at least 2, got {n_splits}")
        thin = {str(c): int(n) for c, n in zip(present, counts) if n < n_splits}
        if thin:
            raise ValueError(
                f"classes {thin} have fewer members than n_splits={n_splits}; "
                "lower n_splits or gather more questions for those classes")
    return X, y, present


def _pipeline(seed: int = 0) -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("logit", LogisticRegression(
            class_weight="balanced",
            C=1.0,
            solver="lbfgs",
            max_iter=2000,
            random_state=seed,
        )),
    ])


def fit_class_model(X: Any, y: Any, seed: int = 0) -> Pipeline:
    X, y, _ = _check(X, y)
    return _pipeline(seed).fit(X, y)


def _out_of_fold(
    X: np.ndarray, y: np.ndarray, n_splits: int, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    classes = np.unique(y)
    oof = np.zeros((y.size, classes.size))
    folds = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for train, test in folds.split(X, y):
        model = clone(_pipeline(seed)).fit(X[train], y[train])
        cols = np.searchsorted(classes, model.classes_)
        oof[np.ix_(test, cols)] = model.predict_proba(X[test])
    return classes, oof


def cross_val_auroc(
    X: Any, y: Any, n_splits: int = 5, seed: int = 0
) -> dict[str, Any]:
    X, y, _ = _check(X, y, n_splits)
    classes, oof = _out_of_fold(X, y, n_splits, seed)
    per_class = {
        str(c): float(roc_auc_score((y == c).astype(int), oof[:, i]))
        for i, c in enumerate(classes)
    }
    macro = float(np.mean(list(per_class.values())))
    return {
        **per_class,
        "macro": macro,
        "n": int(y.size),
        "n_splits": int(n_splits),
        "threshold": REFUTATION_THRESHOLD,
        "refuted": bool(macro < REFUTATION_THRESHOLD),
    }


def permutation_baseline(
    X: Any, y: Any, n_perm: int = 200, seed: int = 0, n_splits: int = 5
) -> dict[str, Any]:
    X, y, _ = _check(X, y, n_splits)
    if n_perm < 1:
        raise ValueError(f"n_perm must be at least 1, got {n_perm}")
    observed = cross_val_auroc(X, y, n_splits=n_splits, seed=seed)["macro"]
    rng = np.random.default_rng(seed)
    null = np.array([
        cross_val_auroc(
            X, rng.permutation(y), n_splits=n_splits, seed=seed)["macro"]
        for _ in range(n_perm)
    ])
    exceed = int(np.count_nonzero(null >= observed))
    return {
        "observed": float(observed),
        "mean": float(null.mean()),
        "std": float(null.std(ddof=1)) if n_perm > 1 else 0.0,
        "p95": float(np.percentile(null, 95)),
        "p_value": float((exceed + 1) / (n_perm + 1)),
        "n_perm": int(n_perm),
        "null": null,
    }


def feature_importance(model: Any, names: Sequence[str]) -> pd.DataFrame:
    est = model[-1] if isinstance(model, Pipeline) else model
    if not hasattr(est, "coef_"):
        raise ValueError(
            "model carries no coefficients; fit it before inspecting it")
    coef = np.atleast_2d(np.asarray(est.coef_, dtype=float))
    names = [str(n) for n in names]
    if len(names) != coef.shape[1]:
        raise ValueError(
            f"got {len(names)} feature names for {coef.shape[1]} coefficients")
    classes = [str(c) for c in est.classes_]
    if coef.shape[0] == 1 and len(classes) == 2:
        coef = np.vstack([-coef[0], coef[0]])
    rows = [
        {"class": cls, "feature": name, "coefficient": float(value),
         "abs_coefficient": abs(float(value))}
        for cls, row in zip(classes, coef)
        for name, value in zip(names, row)
    ]
    frame = pd.DataFrame(
        rows, columns=["class", "feature", "coefficient", "abs_coefficient"])
    return frame.sort_values(
        ["class", "abs_coefficient"], ascending=[True, False]
    ).reset_index(drop=True)


def reliability_curve(
    y_true_binary: Any, p_pred: Any, n_bins: int = 10
) -> dict[str, Any]:
    y = np.asarray(y_true_binary, dtype=float).ravel()
    p = np.asarray(p_pred, dtype=float).ravel()
    if y.size != p.size:
        raise ValueError(
            f"y_true_binary has {y.size} entries but p_pred has {p.size}")
    if y.size == 0:
        raise ValueError("y_true_binary and p_pred are empty")
    if not (np.isfinite(y).all() and np.isfinite(p).all()):
        raise ValueError(
            "y_true_binary and p_pred must not contain NaN or infinite values")
    if not np.isin(y, (0.0, 1.0)).all():
        raise ValueError("y_true_binary must contain only 0 and 1")
    if p.min() < 0.0 or p.max() > 1.0:
        raise ValueError(
            f"p_pred must lie in [0, 1], got [{p.min():.3g}, {p.max():.3g}]")
    if n_bins < 1:
        raise ValueError(f"n_bins must be at least 1, got {n_bins}")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    centres = (edges[:-1] + edges[1:]) / 2.0
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    observed = np.full(n_bins, np.nan)
    mean_pred = np.full(n_bins, np.nan)
    count = np.zeros(n_bins, dtype=int)
    for b in range(n_bins):
        sel = idx == b
        count[b] = int(np.count_nonzero(sel))
        if count[b]:
            observed[b] = float(y[sel].mean())
            mean_pred[b] = float(p[sel].mean())
    filled = count > 0
    gap = np.abs(observed[filled] - mean_pred[filled])
    ece = float(np.sum(count[filled] * gap) / y.size)
    return {
        "centres": centres,
        "observed": observed,
        "count": count,
        "mean_pred": mean_pred,
        "ece": ece,
    }
