"""Reproduce the supplied NAB notebook without changing its experiment protocol.

The notebook's MAD baseline describes the entire series. Its Isolation Forest
and novelty LOF fit the first 3,550 observations and predict the final 482. The
usual result table keeps those 482 rows for all three methods, while the full
MAD baseline is carried separately with its own explicit evaluation scope.
"""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix
from sklearn.neighbors import LocalOutlierFactor

from .contracts import DetectionRun
from .data_prep import NAB_ANOMALY_TIMESTAMPS, read_csv_frame
from .models import evaluate_predictions


REFERENCE_MODELS = ("mad", "isolation_forest", "lof")
REFERENCE_ROWS = 4032
REFERENCE_SPLIT = 3550
REFERENCE_CONTAMINATION = 1 / REFERENCE_SPLIT
REFERENCE_DATA = Path(__file__).resolve().parents[1] / "data" / "ec2_cpu_utilization.csv"


def _reference_frame(source, timestamp_col: str, value_col: str) -> pd.DataFrame:
    """Accept only the notebook's complete canonical series in original order.

    Labels supplied by a caller are intentionally ignored: the known NAB point
    annotations are attached only after both timestamps and values are checked.
    """
    reserved = {"is_anomaly", "z_score"}
    reserved.update(f"{name}_{suffix}" for name in REFERENCE_MODELS for suffix in ("prediction", "score"))
    if timestamp_col == value_col or timestamp_col in reserved or value_col in reserved:
        raise ValueError("Notebook reference timestamp and value columns must be distinct and cannot use generated result names")
    raw = read_csv_frame(source)
    if timestamp_col not in raw or value_col not in raw:
        raise ValueError("Notebook reference requires the selected timestamp and value columns")
    if len(raw) != REFERENCE_ROWS:
        raise ValueError("Notebook reference requires the complete 4032-row NAB ec2_cpu_utilization_24ae8d dataset")
    timestamps = pd.to_datetime(raw[timestamp_col], errors="coerce", utc=True).dt.tz_convert(None)
    expected = pd.date_range("2014-02-14 14:30:00", periods=REFERENCE_ROWS, freq="5min")
    if timestamps.isna().any() or not np.array_equal(timestamps.to_numpy(), expected.to_numpy()):
        raise ValueError("Notebook reference requires the original 4032 timestamps in chronological 5-minute order")
    if pd.api.types.is_bool_dtype(raw[value_col]) or raw[value_col].map(lambda value: isinstance(value, (bool, np.bool_))).any():
        raise ValueError("Notebook reference requires the original finite numeric CPU values")
    values = pd.to_numeric(raw[value_col], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(values).all():
        raise ValueError("Notebook reference requires the original finite numeric CPU values without missing rows")
    if not REFERENCE_DATA.is_file():
        raise ValueError("Notebook reference data is missing; restore data/ec2_cpu_utilization.csv before running this profile")
    canonical = pd.read_csv(REFERENCE_DATA)
    if len(canonical) != REFERENCE_ROWS or "value" not in canonical:
        raise ValueError("Bundled notebook reference data is invalid; restore the canonical NAB CSV")
    canonical_values = canonical["value"].to_numpy(dtype=float)
    # CSV export/import can move a float by one ULP. This tolerance accepts that
    # harmless round trip while rejecting materially different input values.
    if not np.allclose(values, canonical_values, rtol=1e-13, atol=1e-15):
        raise ValueError("Notebook reference CPU values must match the bundled NAB ec2_cpu_utilization_24ae8d dataset")
    # Reuse canonical float representations after validation. This avoids tiny
    # CSV-round-trip changes splitting equal-value neighbor ties in novelty LOF.
    frame = pd.DataFrame({timestamp_col: timestamps.to_numpy(), value_col: canonical_values})
    frame["is_anomaly"] = np.where(frame[timestamp_col].isin(pd.to_datetime(list(NAB_ANOMALY_TIMESTAMPS))), -1, 1)
    frame.attrs["cleaning"] = {
        "input_rows": REFERENCE_ROWS, "output_rows": REFERENCE_ROWS, "dropped_rows": 0,
        "reason": "Notebook reference requires the complete unmodified series; no rows are removed",
    }
    return frame


def run_notebook_reference(source, timestamp_col: str = "timestamp", value_col: str = "value") -> DetectionRun:
    """Run the fixed notebook profile; caller-supplied labels are never used.

    Main predictions and metrics cover the common 482 test rows. MAD's fitted
    statistics still use all 4,032 observations, exactly as in the notebook, so
    its test metrics must not be described as an independent held-out result.
    """
    frame = _reference_frame(source, timestamp_col, value_col)
    values = frame[value_col].to_numpy(dtype=float)
    train = values[:REFERENCE_SPLIT].reshape(-1, 1)
    test = values[REFERENCE_SPLIT:].reshape(-1, 1)
    predictions = frame.iloc[REFERENCE_SPLIT:].copy().reset_index(drop=True)
    timings, parameters = {}, {}

    start = perf_counter()
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    timings["mad"] = {"train_seconds": perf_counter() - start}
    start = perf_counter()
    z_score = .6745 * (values - median) / mad
    mad_score = 3.5 - np.abs(z_score)
    mad_prediction = np.where(np.abs(z_score) >= 3.5, -1, 1)
    timings["mad"]["predict_seconds"] = perf_counter() - start
    predictions["mad_prediction"] = mad_prediction[REFERENCE_SPLIT:]
    predictions["mad_score"] = mad_score[REFERENCE_SPLIT:]
    parameters["mad"] = {
        "threshold": 3.5, "median": median, "mad": mad, "fit_rows": REFERENCE_ROWS,
        "z_score_factor": .6745, "two_sided": True, "preprocessing": {"name": "none"},
        "fit_scope": "full_series_descriptive",
    }

    estimators = {
        "isolation_forest": IsolationForest(contamination=REFERENCE_CONTAMINATION, random_state=42),
        "lof": LocalOutlierFactor(contamination=REFERENCE_CONTAMINATION, novelty=True),
    }
    for name, model in estimators.items():
        start = perf_counter()
        model.fit(train)
        fit_seconds = perf_counter() - start
        start = perf_counter()
        predictions[f"{name}_prediction"] = model.predict(test).astype(int)
        predictions[f"{name}_score"] = model.decision_function(test)
        timings[name] = {"train_seconds": fit_seconds, "predict_seconds": perf_counter() - start}
        parameters[name] = {**model.get_params(deep=False), "fit_rows": REFERENCE_SPLIT,
                            "preprocessing": {"name": "none"}}

    truth = predictions["is_anomaly"]
    metrics = {name: evaluate_predictions(truth, predictions[f"{name}_prediction"]) for name in REFERENCE_MODELS}
    baseline = frame.copy()
    baseline["mad_prediction"], baseline["mad_score"], baseline["z_score"] = mad_prediction, mad_score, z_score
    metadata = {
        "analysis_mode": "notebook_reference", "rows": REFERENCE_ROWS,
        "train_rows": REFERENCE_SPLIT, "test_rows": REFERENCE_ROWS - REFERENCE_SPLIT,
        "split_index": REFERENCE_SPLIT, "train_fraction": REFERENCE_SPLIT / REFERENCE_ROWS,
        "timestamp_col": timestamp_col, "value_col": value_col, "label_col": "is_anomaly",
        "model_names": list(REFERENCE_MODELS), "features": [value_col],
        "contamination": REFERENCE_CONTAMINATION, "random_state": 42,
        "cleaning": frame.attrs["cleaning"], "parameters": parameters, "timings": timings,
        "label_policy": "Official NAB combined_labels exact point timestamps (-1 anomaly, 1 normal); supplied labels ignored",
        "scope": "Offline reproduction of the supplied NAB EC2 notebook; no real-time monitoring or DBMS connection.",
        "warnings": [
            "Notebook MAD fits all 4032 rows, including test observations; it is a full-series descriptive baseline, not independent held-out detection.",
            "The separate notebook MAD baseline evaluates 4032 rows; the common comparison table evaluates only 482 test rows. These evaluation scopes must not be compared as identical experiments.",
            "The fixed 3550/482 split contains one known anomaly in training and one in test; the training series is not anomaly-free.",
            "Metrics use exact point labels and are not official NAB anomaly-window scores.",
        ],
        "reference_protocol": {
            "dataset": "realAWSCloudwatch/ec2_cpu_utilization_24ae8d.csv",
            "mad": "Fit and evaluate all 4032 raw values; abs(0.6745 * (value - median) / MAD) >= 3.5",
            "isolation_forest": "Fit first 3550 raw values; predict final 482; contamination=1/3550; random_state=42",
            "lof": "Fit first 3550 raw values; predict final 482; contamination=1/3550; novelty=True; n_neighbors=20",
            "preprocessing": "Raw value only; no StandardScaler or calendar features",
            "test_metrics": "All three methods evaluated on the same final 482 rows; MAD statistics were fitted on the full series",
            "anomaly_timestamps": list(NAB_ANOMALY_TIMESTAMPS),
            "train_anomalies": int(frame["is_anomaly"].iloc[:REFERENCE_SPLIT].eq(-1).sum()),
            "test_anomalies": int(truth.eq(-1).sum()),
        },
        "confusion_matrices": {
            name: confusion_matrix(truth, predictions[f"{name}_prediction"], labels=[1, -1]).tolist()
            for name in REFERENCE_MODELS
        },
        "reference_baseline": {
            "scope": "full_series_descriptive", "rows": REFERENCE_ROWS, "fit_rows": REFERENCE_ROWS,
            "median": median, "mad": mad, "threshold": 3.5, "z_score_factor": .6745,
            "metrics": evaluate_predictions(frame["is_anomaly"], mad_prediction),
            "confusion_matrix": confusion_matrix(frame["is_anomaly"], mad_prediction, labels=[1, -1]).tolist(),
            "labels": [1, -1],
            "predictions": json.loads(baseline.to_json(orient="records", date_format="iso", date_unit="ns", double_precision=15)),
        },
    }
    return DetectionRun(frame, predictions, metrics, metadata)
