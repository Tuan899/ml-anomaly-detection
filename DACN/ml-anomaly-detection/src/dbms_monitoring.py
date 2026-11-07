"""Chronological multivariate MySQL activity monitoring with auditable alerts.

The four original estimators remain unchanged. A separate, optional operational
noise gate requires a raw model anomaly AND a material metric deviation. Both
sets of predictions and evaluation results are retained for fair comparison.
The tolerance defaults are demonstration policies, not MySQL service objectives.
QPS is a rate; connections is a gauge; slow_queries and connection_errors are
event counts over each sampling interval, never cumulative server counters.
"""
from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from .contracts import DetectionRun
from .data_prep import read_csv_frame
from .models import MODEL_NAMES, build_feature_matrix, evaluate_predictions, fit_models


MYSQL_METRICS = (
    "queries_per_second", "connections", "response_time_ms",
    "slow_queries", "connection_errors",
)
MINIMUM_TOLERANCES = {
    "queries_per_second": 2.0, "connections": 2.0,
    "response_time_ms": 5.0, "slow_queries": 1.0, "connection_errors": 0.0,
}
RELATIVE_TOLERANCE = 0.05


def load_mysql_metrics(source, timestamp_col="timestamp", label_col=None) -> pd.DataFrame:
    """Validate every required metric strictly; never silently discard rows.

    Metrics are nonnegative, finite, real numbers. Labels, when explicitly
    selected, use 1=normal and -1=anomaly. Timestamps are unique, converted to
    UTC without a timezone suffix, then sorted before the chronological split.
    Additional CSV columns are retained as context but never become features.
    """
    if not isinstance(timestamp_col, str) or not timestamp_col:
        raise ValueError("timestamp_col must be a non-empty column name")
    if label_col is not None and (not isinstance(label_col, str) or not label_col):
        raise ValueError("label_col must be a non-empty column name or None")
    if timestamp_col in MYSQL_METRICS or label_col in MYSQL_METRICS or timestamp_col == label_col:
        raise ValueError("Timestamp, metric and label columns must be distinct")
    frame = read_csv_frame(source)
    required = [timestamp_col, *MYSQL_METRICS]
    missing = [column for column in required if column not in frame]
    if missing:
        raise ValueError("Missing MySQL activity columns: " + ", ".join(missing))
    raw_time = frame[timestamp_col]
    if pd.api.types.is_numeric_dtype(raw_time) or raw_time.map(lambda x: isinstance(x, (bool, np.bool_))).any():
        raise ValueError("Column " + timestamp_col + " contains invalid timestamps; use datetime strings")
    timestamps = pd.to_datetime(raw_time, errors="coerce", utc=True)
    if timestamps.isna().any():
        raise ValueError(f"Column {timestamp_col} contains invalid timestamps")
    if timestamps.duplicated().any():
        raise ValueError("Duplicate timestamps are not supported; aggregate samples first")
    frame[timestamp_col] = timestamps.dt.tz_convert(None)
    for column in MYSQL_METRICS:
        raw = frame[column]
        if raw.map(lambda x: isinstance(x, (bool, np.bool_, complex, np.complexfloating))).any():
            raise ValueError(f"MySQL metric {column} must contain real numeric values, not booleans")
        numbers = pd.to_numeric(raw, errors="coerce")
        try:
            values = numbers.to_numpy(dtype=float, na_value=np.nan)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"MySQL metric {column} must contain finite nonnegative numeric values") from exc
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError(f"MySQL metric {column} must contain finite nonnegative numeric values; no rows were dropped")
        frame[column] = values
    if label_col:
        if label_col not in frame:
            raise ValueError(f"Missing label column: {label_col}")
        raw = frame[label_col]
        labels = pd.to_numeric(raw, errors="coerce")
        if raw.map(lambda x: isinstance(x, (bool, np.bool_, complex, np.complexfloating))).any() or not labels.isin([-1, 1]).all():
            raise ValueError("Labels must be explicit -1 (anomaly) or 1 (normal), without missing values")
        frame[label_col] = labels.astype(int)
    frame = frame.sort_values(timestamp_col, kind="stable").reset_index(drop=True)
    frame.attrs["cleaning"] = {"input_rows": len(frame), "output_rows": len(frame),
                               "dropped_rows": 0, "reason": "strict validation; no rows dropped"}
    return frame


def _fit_baselines(train: pd.DataFrame, threshold: float) -> dict:
    baselines = {}
    for metric in MYSQL_METRICS:
        values = train[metric].to_numpy(dtype=float)
        with np.errstate(over="ignore", invalid="ignore"):
            median = float(np.median(values))
            mad = float(np.median(np.abs(values - median)))
            q25, q75 = np.quantile(values, [.25, .75])
            # The IQR fallback handles discrete metrics whose MAD is zero.
            sigma = max(1.4826 * mad, float((q75 - q25) / 1.349))
            floor = max(MINIMUM_TOLERANCES[metric], RELATIVE_TOLERANCE * abs(median))
            tolerance = max(threshold * sigma, floor)
        if not np.isfinite([median, mad, sigma, tolerance]).all():
            raise ValueError("Metric magnitude is too large for finite training baseline statistics")
        baselines[metric] = {
            "median": median, "mad": mad, "robust_sigma": sigma,
            "minimum_absolute_tolerance": MINIMUM_TOLERANCES[metric],
            "relative_tolerance": RELATIVE_TOLERANCE,
            "allowed_deviation": tolerance,
            "lower_bound": max(0.0, median - tolerance),
            "upper_bound": median + tolerance,
        }
        if not np.isfinite(baselines[metric]["upper_bound"]):
            raise ValueError("Metric magnitude is too large for a finite tolerance interval")
    return baselines


def _add_indicators(predictions: pd.DataFrame, baselines: dict, threshold: float) -> np.ndarray:
    deviations = []
    score_matrix = []
    for metric in MYSQL_METRICS:
        baseline = baselines[metric]
        delta = predictions[metric].to_numpy() - baseline["median"]
        # Positive score means a rise; negative means a fall. A zero training
        # spread uses the documented tolerance floor, never test statistics.
        # Zero tolerance is possible for errors at a zero training baseline.
        # Use one count as the reporting resolution: one event receives the
        # threshold score. This score is policy-scaled, not a robust z-score;
        # the independent gate still tests abs(delta) > allowed_deviation.
        effective_sigma = baseline["allowed_deviation"] / threshold if baseline["allowed_deviation"] else 1.0 / threshold
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            scores = delta / effective_sigma
        scores = np.nan_to_num(scores, posinf=np.finfo(float).max / 4, neginf=-np.finfo(float).max / 4)
        predictions[f"{metric}_deviation"] = delta
        predictions[f"{metric}_deviation_score"] = scores
        deviations.append(np.abs(delta) > baseline["allowed_deviation"])
        score_matrix.append(np.abs(scores))
    material = np.column_stack(deviations)
    predictions["activity_deviation"] = material.any(axis=1)
    predictions["max_deviation_score"] = np.column_stack(score_matrix).max(axis=1)
    explanations = []
    for index, row in predictions.iterrows():
        evidence = []
        for column_index, metric in enumerate(MYSQL_METRICS):
            if material[index, column_index]:
                baseline = baselines[metric]
                evidence.append(
                    f"{metric}: actual={row[metric]:.6g}, train_median={baseline['median']:.6g}, "
                    f"delta={row[f'{metric}_deviation']:+.6g}, allowed_deviation={baseline['allowed_deviation']:.6g}"
                )
        explanations.append("; ".join(evidence) if evidence else "No metric exceeds the documented training tolerance.")
    predictions["suspected_indicators"] = explanations
    return material.any(axis=1)


def run_dbms_detection(source, timestamp_col="timestamp", value_col="queries_per_second", label_col=None,
                       train_fraction=.7, contamination=.01, model_names=None,
                       include_time=False, split_index=None, noise_guard=True,
                       deviation_threshold=3.5) -> DetectionRun:
    """Train four existing models on five metrics, evaluate subsequent samples.

    ``value_col`` selects the chart metric only; all five metrics always enter
    every model. A guarded alert is a raw anomaly intersected with a metric
    exceeding its training-only tolerance. Raw scores/predictions are preserved.
    A 50->51 change falls inside the default 5% floor; errors rising from zero
    have a zero floor and can qualify. This is explicit policy, not causality.
    """
    try:
        names = list(MODEL_NAMES if model_names is None else [model_names] if isinstance(model_names, str) else model_names)
    except TypeError as exc:
        raise ValueError("Select unique algorithms from: " + ", ".join(MODEL_NAMES)) from exc
    if not names or any(not isinstance(name, str) or name not in MODEL_NAMES for name in names) or len(set(names)) != len(names):
        raise ValueError("Select unique algorithms from: " + ", ".join(MODEL_NAMES))
    numeric_types = (int, float, np.integer, np.floating)
    for name, value, upper in (("train_fraction", train_fraction, 1), ("contamination", contamination, .5)):
        if isinstance(value, bool) or not isinstance(value, numeric_types) or not np.isfinite(value) or value <= 0 or value > upper or (name == "train_fraction" and value == 1):
            raise ValueError(f"{name} must be finite and in (0, {upper}{')' if name == 'train_fraction' else ']'}")
    if isinstance(deviation_threshold, bool) or not isinstance(deviation_threshold, numeric_types) or not np.isfinite(deviation_threshold) or deviation_threshold <= 0:
        raise ValueError("deviation_threshold must be a positive finite number")
    if not isinstance(noise_guard, (bool, np.bool_)) or not isinstance(include_time, (bool, np.bool_)):
        raise ValueError("noise_guard and include_time must be booleans")
    if value_col not in MYSQL_METRICS:
        raise ValueError("value_col must select one of the five MySQL activity metrics")
    reserved = {"activity_deviation", "max_deviation_score", "suspected_indicators"}
    reserved |= {f"{name}_{suffix}" for name in MODEL_NAMES for suffix in ("prediction", "raw_prediction", "score")}
    reserved |= {f"{metric}_{suffix}" for metric in MYSQL_METRICS for suffix in ("deviation", "deviation_score")}
    if timestamp_col in reserved or label_col in reserved:
        raise ValueError("Selected input columns conflict with generated monitoring columns; rename them first")
    frame = load_mysql_metrics(source, timestamp_col=timestamp_col, label_col=label_col)
    if split_index is not None and (isinstance(split_index, bool) or not isinstance(split_index, (int, np.integer))):
        raise ValueError("split_index must be an integer")
    # Decimal text avoids 1440 * .7 == 1007.9999999999999 truncating a
    # mathematically integral 70% split to 1007 rows.
    split = int(Decimal(len(frame)) * Decimal(str(train_fraction))) if split_index is None else int(split_index)
    if split < 3 or split >= len(frame):
        raise ValueError("Need at least 3 training rows and 1 test row; adjust split or provide more data")
    features = build_feature_matrix(frame, MYSQL_METRICS, timestamp_col, include_time=include_time)
    results = fit_models(features.iloc[:split], features.iloc[split:], contamination=contamination,
                         random_state=42, model_names=names)
    cols = [timestamp_col, *MYSQL_METRICS] + ([label_col] if label_col else [])
    if "scenario" in frame and "scenario" not in cols and "scenario" != timestamp_col:
        cols.append("scenario")
    predictions = frame.iloc[split:][cols].copy().reset_index(drop=True)
    baselines = _fit_baselines(frame.iloc[:split], float(deviation_threshold))
    material_deviation = _add_indicators(predictions, baselines, float(deviation_threshold))
    metrics, raw_metrics, matrices, raw_matrices = {}, {}, {}, {}
    anomaly_counts, raw_anomaly_counts = {}, {}
    for name, result in results.items():
        raw = result.predictions
        alerts = np.where((raw == -1) & material_deviation, -1, 1) if noise_guard else raw.copy()
        predictions[f"{name}_raw_prediction"] = raw
        predictions[f"{name}_prediction"] = alerts
        predictions[f"{name}_score"] = result.scores
        anomaly_counts[name] = int((alerts == -1).sum())
        raw_anomaly_counts[name] = int((raw == -1).sum())
        if label_col:
            truth = predictions[label_col]
            metrics[name] = evaluate_predictions(truth, alerts)
            raw_metrics[name] = evaluate_predictions(truth, raw)
            matrices[name] = confusion_matrix(truth, alerts, labels=[1, -1]).astype(int).tolist()
            raw_matrices[name] = confusion_matrix(truth, raw, labels=[1, -1]).astype(int).tolist()
    warnings = [
        "Suspected indicators describe observed deviations from the training baseline; they do not establish root cause.",
        "Tolerance floors are explicit demonstration defaults, not calibrated MySQL capacity limits or an SLA.",
    ]
    if noise_guard:
        warnings.append("Operational alerts require both a raw model anomaly and a metric deviation. This may suppress subtle multivariate anomalies; compare raw predictions and metrics as well.")
    if len(frame) < 100:
        warnings.append("Small dataset: this run verifies functionality and cannot establish general detection quality.")
    if not label_col:
        warnings.append("No ground-truth labels selected: precision, recall, F1 and confusion matrices are not computed.")
    elif not (predictions[label_col] == -1).any():
        warnings.append("Test labels contain no anomalies: recall/F1 cannot support a detection-quality conclusion; inspect false positives.")
    if label_col and (frame.iloc[:split][label_col] == -1).any():
        warnings.append("Training labels contain anomalies. Models remain unsupervised and do not filter rows using labels; a contaminated reference can reduce sensitivity.")
    if include_time:
        warnings.append("Calendar features are enabled for all models; guarded alerts still require a deviation in a MySQL activity metric.")
    metadata = {
        "analysis_mode": "dbms", "rows": len(frame), "train_rows": split, "test_rows": len(frame) - split,
        "split_index": split, "train_fraction": split / len(frame), "timestamp_col": timestamp_col,
        "value_col": value_col, "label_col": label_col, "model_names": names,
        "metric_cols": list(MYSQL_METRICS), "features": list(features.columns),
        "contamination": float(contamination), "random_state": 42, "warnings": warnings,
        "cleaning": frame.attrs["cleaning"], "train_baselines": baselines,
        "parameters": {name: result.parameters for name, result in results.items()},
        "timings": {name: {"train_seconds": result.train_seconds, "predict_seconds": result.predict_seconds}
                    for name, result in results.items()},
        "noise_guard": {
            "enabled": bool(noise_guard), "deviation_threshold": float(deviation_threshold),
            "minimum_absolute_tolerances": dict(MINIMUM_TOLERANCES), "relative_tolerance": RELATIVE_TOLERANCE,
            "description": "alert = raw anomaly AND any absolute metric deviation > max(threshold * max(1.4826*MAD, IQR/1.349), absolute floor, 5% of train median); training statistics only",
            "score_policy": "Model decision scores are unchanged raw margins; larger means more normal. Indicator deviation scores are policy-scaled deviations, not robust z-scores.",
            "score_definition": "signed deviation / (allowed_deviation / threshold); when allowed_deviation is zero, signed deviation * threshold using one event as the count resolution",
            "zero_tolerance_score": {"count_resolution": 1.0, "one_event_score": float(deviation_threshold),
                                     "gate": "abs(deviation) > 0 remains independent of the reporting score"},
        },
        "anomaly_counts": anomaly_counts, "raw_anomaly_counts": raw_anomaly_counts,
        "raw_metrics": raw_metrics, "confusion_matrices": matrices, "raw_confusion_matrices": raw_matrices,
        "confusion_matrix_order": {"rows": ["normal", "anomaly"], "columns": ["normal", "anomaly"], "layout": [["TN", "FP"], ["FN", "TP"]]},
        "label_policy": "explicit held-out point labels (-1 anomaly, 1 normal)" if label_col else "unlabeled",
        "scope": "Chronological multivariate analysis of MySQL activity samples from CSV or a read-only collector; held-out predictions only.",
    }
    return DetectionRun(frame, predictions, metrics, metadata)
