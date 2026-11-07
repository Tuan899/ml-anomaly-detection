"""Compare two held-out MySQL timelines against one normal training reference.

Only the chronological prefix of the normal source fits the existing estimators,
StandardScaler and operational baselines. The anomalous source is never fitted.
Both held-outs are scored in one feature batch, then restored to their own
observations. Timestamps may overlap across sources; observations are not merged.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from .contracts import DetectionRun
from .dbms_monitoring import (
    MINIMUM_TOLERANCES, MYSQL_METRICS, RELATIVE_TOLERANCE,
    _add_indicators, _fit_baselines, load_mysql_metrics,
)
from .models import MODEL_NAMES, build_feature_matrix, evaluate_predictions, fit_models


def _validate_options(timestamp_col, value_col, label_col, train_fraction,
                      contamination, model_names, include_time, split_index,
                      noise_guard, deviation_threshold):
    """Apply the single-run DBMS contract without fitting a throwaway model."""
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
    if split_index is not None and (isinstance(split_index, bool) or not isinstance(split_index, (int, np.integer))):
        raise ValueError("split_index must be an integer")
    reserved = {"activity_deviation", "max_deviation_score", "suspected_indicators"}
    reserved |= {f"{name}_{suffix}" for name in MODEL_NAMES for suffix in ("prediction", "raw_prediction", "score")}
    reserved |= {f"{metric}_{suffix}" for metric in MYSQL_METRICS for suffix in ("deviation", "deviation_score")}
    if timestamp_col in reserved or label_col in reserved:
        raise ValueError("Selected input columns conflict with generated monitoring columns; rename them first")
    return names


def _split(frame, train_fraction, split_index):
    split = int(Decimal(len(frame)) * Decimal(str(train_fraction))) if split_index is None else int(split_index)
    if split < 3 or split >= len(frame):
        raise ValueError("Need at least 3 training rows and 1 test row in each source; adjust split or provide more data")
    return split


def compare_dbms_datasets(normal_source, anomalous_source, timestamp_col="timestamp",
                          value_col="queries_per_second", label_col=None,
                          train_fraction=.7, contamination=.01, model_names=None,
                          include_time=False, split_index=None, noise_guard=True,
                          deviation_threshold=3.5) -> dict[str, DetectionRun]:
    """Return normal/anomalous runs scored by the same fitted reference.

    Each source uses its own chronological split and retains every original
    observation. ``train_rows`` describes that source's excluded prefix for
    compatibility with DetectionRun; ``comparison.reference_train_rows`` records
    the actual fit size, which always comes from the normal source. Labels are
    opt-in, validated in both sources, and never enter features or fitting.
    """
    names = _validate_options(timestamp_col, value_col, label_col, train_fraction,
                              contamination, model_names, include_time, split_index,
                              noise_guard, deviation_threshold)
    frames = {
        "normal": load_mysql_metrics(normal_source, timestamp_col, label_col),
        "anomalous": load_mysql_metrics(anomalous_source, timestamp_col, label_col),
    }
    splits = {role: _split(frame, train_fraction, split_index) for role, frame in frames.items()}
    features = {role: build_feature_matrix(frame, MYSQL_METRICS, timestamp_col, include_time)
                for role, frame in frames.items()}
    reference = frames["normal"].iloc[:splits["normal"]]
    # Concatenate features, never timestamps: each source can have identical
    # timestamps or a different sampling cadence without ambiguous restoration.
    held_out = pd.concat([features[role].iloc[splits[role]:] for role in frames], ignore_index=True)
    fitted = fit_models(features["normal"].iloc[:splits["normal"]], held_out,
                        contamination=contamination, random_state=42, model_names=names)
    baselines = _fit_baselines(reference, float(deviation_threshold))
    comparison = {
        "reference_source": "normal", "reference_train_rows": len(reference),
        "reference_start": reference[timestamp_col].iloc[0].isoformat(),
        "reference_end": reference[timestamp_col].iloc[-1].isoformat(),
        "shared_model_fit_calls": 1, "shared_scaler_fit_calls": 1,
        "prediction_batch_rows": len(held_out), "same_model_parameters": True,
        "normalization": "one StandardScaler fitted only on the normal training prefix",
        "evaluation_scope": "each source's own chronological held-out observations",
        "timing_scope": "shared training and combined prediction; do not sum the two runs",
        "prefix_policy": "normal prefix trains the reference; anomalous prefix is excluded and never fitted",
    }
    runs, offset = {}, 0
    for role, frame in frames.items():
        split = splits[role]
        columns = [timestamp_col, *MYSQL_METRICS] + ([label_col] if label_col else [])
        if "scenario" in frame and "scenario" not in columns:
            columns.append("scenario")
        predictions = frame.iloc[split:][columns].copy().reset_index(drop=True)
        material = _add_indicators(predictions, baselines, float(deviation_threshold))
        stop = offset + len(predictions)
        metrics, raw_metrics, matrices, raw_matrices, counts, raw_counts = {}, {}, {}, {}, {}, {}
        for name, result in fitted.items():
            raw = result.predictions[offset:stop].copy()
            alerts = np.where((raw == -1) & material, -1, 1) if noise_guard else raw.copy()
            predictions[f"{name}_raw_prediction"] = raw
            predictions[f"{name}_prediction"] = alerts
            predictions[f"{name}_score"] = result.scores[offset:stop].copy()
            counts[name], raw_counts[name] = int((alerts == -1).sum()), int((raw == -1).sum())
            if label_col:
                truth = predictions[label_col]
                metrics[name], raw_metrics[name] = evaluate_predictions(truth, alerts), evaluate_predictions(truth, raw)
                matrices[name] = confusion_matrix(truth, alerts, labels=[1, -1]).astype(int).tolist()
                raw_matrices[name] = confusion_matrix(truth, raw, labels=[1, -1]).astype(int).tolist()
        warnings = [
            "Suspected indicators describe observed deviations from the training baseline; they do not establish root cause.",
            "Tolerance floors are explicit demonstration defaults, not calibrated MySQL capacity limits or an SLA.",
            "Comparison uses the normal source training prefix for both datasets; the anomalous source prefix is excluded, not fitted.",
            "The normal source is a user-designated reference, not verified normal ground truth.",
        ]
        if noise_guard:
            warnings.append("Operational alerts require both a raw model anomaly and a metric deviation. This may suppress subtle multivariate anomalies; compare raw predictions and metrics as well.")
        if len(frame) < 100:
            warnings.append("Small dataset: this run verifies functionality and cannot establish general detection quality.")
        if not label_col:
            warnings.append("No ground-truth labels selected: precision, recall, F1 and confusion matrices are not computed.")
        elif not (predictions[label_col] == -1).any():
            warnings.append("Test labels contain no anomalies: recall/F1 cannot support a detection-quality conclusion; inspect false positives.")
        if label_col and (reference[label_col] == -1).any():
            warnings.append("Training labels contain anomalies. Models remain unsupervised and do not filter rows using labels; a contaminated reference can reduce sensitivity.")
        if include_time:
            warnings.append("Calendar features are enabled for all models; guarded alerts still require a deviation in a MySQL activity metric.")
        metadata = {
            "analysis_mode": "dbms", "rows": len(frame), "train_rows": split,
            "test_rows": len(frame) - split, "split_index": split, "train_fraction": split / len(frame),
            "timestamp_col": timestamp_col, "value_col": value_col, "label_col": label_col,
            "model_names": list(names), "metric_cols": list(MYSQL_METRICS),
            "features": list(features[role].columns), "contamination": float(contamination),
            "random_state": 42, "warnings": warnings, "cleaning": deepcopy(frame.attrs["cleaning"]),
            "train_baselines": deepcopy(baselines),
            "parameters": {name: deepcopy(result.parameters) for name, result in fitted.items()},
            "timings": {name: {"train_seconds": result.train_seconds, "predict_seconds": result.predict_seconds}
                        for name, result in fitted.items()},
            "comparison": {**deepcopy(comparison), "role": role, "local_excluded_prefix_rows": split},
            "noise_guard": {
                "enabled": bool(noise_guard), "deviation_threshold": float(deviation_threshold),
                "minimum_absolute_tolerances": dict(MINIMUM_TOLERANCES), "relative_tolerance": RELATIVE_TOLERANCE,
                "description": "alert = raw anomaly AND any absolute metric deviation > max(threshold * max(1.4826*MAD, IQR/1.349), absolute floor, 5% of train median); training statistics only",
                "score_policy": "Model decision scores are unchanged raw margins; larger means more normal. Indicator deviation scores are policy-scaled deviations, not robust z-scores.",
                "score_definition": "signed deviation / (allowed_deviation / threshold); when allowed_deviation is zero, signed deviation * threshold using one event as the count resolution",
                "zero_tolerance_score": {"count_resolution": 1.0, "one_event_score": float(deviation_threshold),
                                         "gate": "abs(deviation) > 0 remains independent of the reporting score"},
            },
            "anomaly_counts": counts, "raw_anomaly_counts": raw_counts, "raw_metrics": raw_metrics,
            "confusion_matrices": matrices, "raw_confusion_matrices": raw_matrices,
            "confusion_matrix_order": {"rows": ["normal", "anomaly"], "columns": ["normal", "anomaly"], "layout": [["TN", "FP"], ["FN", "TP"]]},
            "label_policy": "explicit held-out point labels (-1 anomaly, 1 normal)" if label_col else "unlabeled",
            "scope": "Two MySQL held-out datasets scored by the same normal-reference fitted estimators, scaler and operational baselines.",
        }
        runs[role] = DetectionRun(frame, predictions, metrics, metadata)
        offset = stop
    return runs
