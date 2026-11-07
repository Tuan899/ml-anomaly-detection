"""Train-only anomaly estimators and honest validation metrics.

All models return +/-1 predictions and decision margins: larger means more normal.
StandardScaler is fitted only on training rows, including during parameter search.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import product
from time import perf_counter

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from .data_prep import LABEL_COLUMNS, add_time_features, robust_location_scale, robust_z_values

MODEL_NAMES = ("mad", "isolation_forest", "lof", "one_class_svm")


@dataclass(frozen=True)
class ModelResult:
    name: str
    predictions: np.ndarray
    scores: np.ndarray
    train_seconds: float = 0.0
    predict_seconds: float = 0.0
    parameters: dict = field(default_factory=dict)


def _validate_features(features: pd.DataFrame | np.ndarray, minimum_rows: int = 1) -> np.ndarray:
    if isinstance(features, pd.DataFrame):
        if any(str(column).lower() in LABEL_COLUMNS for column in features.columns):
            raise ValueError("Ground-truth label columns must not be model features")
        source = features.to_numpy()
    else:
        source = np.asarray(features)
    if np.iscomplexobj(source):
        raise ValueError("Features must contain real numeric values")
    try:
        values = np.asarray(source, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Features must contain finite numeric values") from exc
    if values.ndim == 1:
        values = values.reshape(-1, 1)
    if values.ndim != 2 or values.shape[0] < minimum_rows or values.shape[1] == 0:
        raise ValueError(f"Features must be a non-empty 2D array with at least {minimum_rows} rows")
    if not np.isfinite(values).all():
        raise ValueError("Features must contain only finite numbers")
    return values


def _validate_pair(train_features, test_features) -> tuple[np.ndarray, np.ndarray]:
    train = _validate_features(train_features, minimum_rows=3)
    test = _validate_features(test_features)
    if train.shape[1] != test.shape[1]:
        raise ValueError("Train and evaluation feature counts must match")
    if isinstance(train_features, pd.DataFrame) and isinstance(test_features, pd.DataFrame):
        if list(train_features.columns) != list(test_features.columns):
            raise ValueError("Train and evaluation feature columns and order must match")
    return train, test


def _validate_contamination(contamination: float) -> None:
    if not isinstance(contamination, (int, float, np.integer, np.floating)) or isinstance(contamination, bool):
        raise ValueError("contamination must be a number in (0, 0.5]")
    if not np.isfinite(contamination) or not 0 < contamination <= 0.5:
        raise ValueError("contamination must be in the interval (0, 0.5]")


def _validate_labels(labels, name: str = "labels") -> np.ndarray:
    values = np.asarray(labels)
    if values.ndim != 1 or len(values) == 0:
        raise ValueError(f"{name} must be a non-empty one-dimensional array")
    if values.dtype.kind not in "iuf" or not np.isin(values, [-1, 1]).all():
        raise ValueError(f"{name} must contain only -1 (anomaly) and 1 (normal)")
    return values.astype(int)


def _make_estimator(name: str, contamination: float, random_state: int, rows: int, parameters: dict):
    params = dict(parameters)
    if name == "isolation_forest":
        return IsolationForest(contamination=contamination, random_state=random_state, **params)
    if name == "lof":
        params.setdefault("n_neighbors", min(20, rows - 1))
        neighbors = params["n_neighbors"]
        if isinstance(neighbors, bool) or not isinstance(neighbors, (int, np.integer)) or not 1 <= neighbors < rows:
            raise ValueError("LOF n_neighbors must be an integer smaller than the training row count")
        return LocalOutlierFactor(contamination=contamination, novelty=True, **params)
    if name == "one_class_svm":
        params.setdefault("nu", contamination)
        params.setdefault("kernel", "rbf")
        params.setdefault("gamma", "scale")
        return OneClassSVM(**params)
    raise ValueError(f"Unknown model {name!r}; choose from {MODEL_NAMES}")


def _fit_result(name: str, train: np.ndarray, test: np.ndarray, contamination: float, random_state: int,
                parameters: dict | None = None, preprocessing: dict | None = None) -> ModelResult:
    params = dict(parameters or {})
    start = perf_counter()
    if name == "mad":
        threshold = params.pop("threshold", 3.5)
        if params:
            raise ValueError(f"Unsupported MAD parameters: {sorted(params)}")
        if not isinstance(threshold, (int, float)) or not np.isfinite(threshold) or threshold <= 0:
            raise ValueError("MAD threshold must be positive and finite")
        center, scale = robust_location_scale(train)
        train_seconds = perf_counter() - start
        start = perf_counter()
        scores = threshold - np.abs(robust_z_values(test, center, scale)).max(axis=1)
        predictions = np.where(scores <= 0, -1, 1)
        details = {"threshold": float(threshold), "center": center.tolist(), "mad_scale": scale.tolist(),
                   "aggregation": "maximum absolute robust z-score over selected features",
                   "zero_mad": "train-only epsilon tolerance; no test-statistic fallback"}
    else:
        model = _make_estimator(name, contamination, random_state, len(train), params)
        model.fit(train)
        train_seconds = perf_counter() - start
        start = perf_counter()
        predictions = model.predict(test).astype(int)
        scores = np.asarray(model.decision_function(test), dtype=float)
        details = model.get_params(deep=False)
    predict_seconds = perf_counter() - start
    if not np.isfinite(scores).all():
        raise ValueError(f"{name} generated non-finite scores; check metric magnitudes")
    if preprocessing is not None:
        details["preprocessing"] = dict(preprocessing)
    return ModelResult(name, np.asarray(predictions, dtype=int), np.asarray(scores, dtype=float),
                       train_seconds, predict_seconds, details)


def fit_models(
    train_features: pd.DataFrame | np.ndarray,
    test_features: pd.DataFrame | np.ndarray,
    contamination: float = 0.01,
    random_state: int = 42,
    model_names: Sequence[str] | str | None = None,
) -> dict[str, ModelResult]:
    """Fit selected estimators on train only, then predict distinct held-out rows.

    MAD uses its fixed robust-z threshold (3.5), independently of contamination.
    The other methods interpret contamination/nu according to their own APIs;
    this does not guarantee the same anomaly rate on unseen data. MAD combines
    multiple selected features using the maximum absolute robust z-score.
    """
    _validate_contamination(contamination)
    train, test = _validate_pair(train_features, test_features)
    names = list(MODEL_NAMES if model_names is None else [model_names] if isinstance(model_names, str) else model_names)
    if not names or len(set(names)) != len(names) or any(name not in MODEL_NAMES for name in names):
        raise ValueError(f"model_names must be a non-empty unique selection from {MODEL_NAMES}")
    scaler = StandardScaler()
    scaled_train = scaler.fit_transform(train)
    scaled_test = scaler.transform(test)
    if not np.isfinite(scaled_train).all() or not np.isfinite(scaled_test).all():
        raise ValueError("Feature scaling overflowed; reduce metric magnitudes")
    preprocessing = {"name": "StandardScaler", "fit_rows": len(train),
                     "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()}
    return {name: _fit_result(name, scaled_train, scaled_test, contamination, random_state,
                             preprocessing=preprocessing) for name in names}


def evaluate_predictions(y_true: pd.Series | np.ndarray, predictions: pd.Series | np.ndarray) -> dict[str, float]:
    """Compute point precision, recall, and F1 for explicit -1 anomaly labels.

    Zero denominators produce zero. These are not official NAB window scores.
    """
    truth = _validate_labels(y_true, "y_true")
    predicted = _validate_labels(predictions, "predictions")
    if len(truth) != len(predicted):
        raise ValueError("y_true and predictions must have equal length")
    return {
        "precision": float(precision_score(truth, predicted, pos_label=-1, zero_division=0)),
        "recall": float(recall_score(truth, predicted, pos_label=-1, zero_division=0)),
        "f1": float(f1_score(truth, predicted, pos_label=-1, zero_division=0)),
    }


def tune_model(
    model_name: str,
    train_features: pd.DataFrame | np.ndarray,
    validation_features: pd.DataFrame | np.ndarray,
    validation_labels: pd.Series | np.ndarray,
    param_grid: dict[str, list] | None = None,
    contamination: float = 0.01,
    random_state: int = 42,
) -> dict:
    """Select parameters on a separate chronological validation partition.

    The old API that fitted and scored the same rows is intentionally removed.
    Training, validation, and final test rows must be supplied by the caller as
    disjoint chronological partitions. Test labels must never enter this search.
    The scaler and every candidate estimator are fitted on train_features only.
    """
    _validate_contamination(contamination)
    if model_name not in MODEL_NAMES:
        raise ValueError(f"Unknown model {model_name!r}")
    train, validation = _validate_pair(train_features, validation_features)
    labels = _validate_labels(validation_labels, "validation_labels")
    if len(validation) != len(labels):
        raise ValueError("validation_features and validation_labels must have equal length")
    if not (labels == -1).any():
        raise ValueError("Validation labels contain no anomalies; F1-based tuning is not meaningful")
    defaults = {
        "mad": {"threshold": [2.5, 3.5, 4.5]},
        "isolation_forest": {"n_estimators": [100, 200], "max_samples": ["auto", 0.8]},
        "lof": {"n_neighbors": sorted(set(min(n, len(train) - 1) for n in (10, 20, 35))), "leaf_size": [20, 30]},
        "one_class_svm": {"gamma": ["scale", "auto"], "nu": [contamination]},
    }
    grid = defaults[model_name] if param_grid is None else param_grid
    if not isinstance(grid, dict) or any(not isinstance(values, (list, tuple)) or not len(values) for values in grid.values()):
        raise ValueError("param_grid must map parameter names to non-empty lists")
    scaler = StandardScaler()
    scaled_train = scaler.fit_transform(train)
    scaled_validation = scaler.transform(validation)
    keys = list(grid)
    trials = []
    best = None
    for values in product(*(grid[key] for key in keys)):
        params = dict(zip(keys, values))
        result = _fit_result(model_name, scaled_train, scaled_validation, contamination, random_state, params)
        metrics = evaluate_predictions(labels, result.predictions)
        trial = {"params": params, **metrics}
        trials.append(trial)
        if best is None or metrics["f1"] > best["f1"]:
            best = {"model": model_name, "params": params, "f1": metrics["f1"], "validation_metrics": metrics}
    if best is None:
        raise ValueError("Parameter grid produced no candidates")
    best["trials"] = trials
    best["train_rows"] = len(train)
    best["validation_rows"] = len(validation)
    best["protocol"] = "fit training rows; select by validation F1; final test remains untouched"
    return best


def build_feature_matrix(
    frame: pd.DataFrame,
    value_col: str | Sequence[str],
    timestamp_col: str = "timestamp",
    include_time: bool = False,
) -> pd.DataFrame:
    """Select activity metrics and optional deterministic cyclical time features.

    Calendar features are opt-in because dataset-specific anomalies can otherwise
    be confused with calendar boundaries. No labels may be selected as metrics.
    """
    columns = [value_col] if isinstance(value_col, str) else list(value_col)
    if not columns or len(set(columns)) != len(columns):
        raise ValueError("Select at least one unique metric column")
    if any(column == timestamp_col or str(column).lower() in LABEL_COLUMNS for column in columns):
        raise ValueError("Metric columns cannot include timestamps or ground-truth labels")
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing metric columns: {', '.join(missing)}")
    try:
        result = frame[columns].astype(float).copy()
    except (TypeError, ValueError) as exc:
        raise ValueError("Selected metrics must contain finite numeric values") from exc
    if include_time:
        # Calendar helpers must never replace a source metric with the same name.
        calendar = add_time_features(frame[[timestamp_col]], timestamp_col)
        for column in ("hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend"):
            if column not in result.columns:
                result[column] = calendar[column]
    _validate_features(result)
    return result
