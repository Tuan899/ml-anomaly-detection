"""HTTP-only connection between the Streamlit dashboard and FastAPI.

There is deliberately no local model-fitting fallback: unavailable or invalid
backend responses are reported to the user instead of generating new results.
"""

from __future__ import annotations

from decimal import Decimal
import math
import json
import os
from urllib.parse import urlsplit

import httpx
import numpy as np
import pandas as pd

from frontend.helpers import error_message
from src.contracts import DetectionRun


DEFAULT_API_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = httpx.Timeout(120.0, connect=3.0, write=30.0, pool=5.0)
MODEL_NAMES = ("mad", "isolation_forest", "lof", "one_class_svm")


class BackendError(Exception):
    """A backend failure that can be shown directly in the Vietnamese UI."""


def get_backend_url() -> str:
    return os.environ.get("ANOMALY_API_URL", DEFAULT_API_URL).strip().rstrip("/")


def _read_result(payload: dict, names: list[str], timestamp_col: str,
                 value_col: str, label_col: str | None) -> DetectionRun:
    """Read backend-owned observations and predictions, checking the contract."""
    if not isinstance(payload, dict):
        raise ValueError("Expected a result object")
    metadata, metrics = payload["metadata"], payload["metrics"]
    if not isinstance(metadata, dict) or not isinstance(metrics, dict):
        raise ValueError("Invalid result metadata or metrics")
    if (metadata["model_names"] != names or metadata["timestamp_col"] != timestamp_col
            or metadata["value_col"] != value_col or metadata.get("label_col") != label_col):
        raise ValueError("Backend returned a different configuration")
    context, records = payload["context"], payload["predictions"]
    if not isinstance(context, list) or not isinstance(records, list):
        raise ValueError("Expected context and prediction records")
    frame, predictions = pd.DataFrame(context), pd.DataFrame(records)
    train_rows, test_rows, rows = (metadata[key] for key in ("train_rows", "test_rows", "rows"))
    if (any(type(count) is not int for count in (train_rows, test_rows, rows))
            or train_rows < 3 or test_rows < 1 or train_rows + test_rows != rows
            or len(frame) != rows or len(predictions) != test_rows):
        raise ValueError("Invalid chronological partition")
    columns = list(dict.fromkeys([timestamp_col, value_col] + metadata.get("metric_cols", [])))
    columns += [label_col] if label_col else []
    for data in (frame, predictions):
        if not all(column in data for column in columns):
            raise ValueError("Missing observation columns")
        data[timestamp_col] = pd.to_datetime(data[timestamp_col], errors="raise", utc=True).dt.tz_convert(None)
        data[value_col] = pd.to_numeric(data[value_col], errors="raise")
        if data[timestamp_col].isna().any() or not np.isfinite(data[value_col]).all():
            raise ValueError("Invalid observations")
        for column in metadata.get("metric_cols", []):
            data[column] = pd.to_numeric(data[column], errors="raise")
            if not np.isfinite(data[column]).all() or data[column].lt(0).any():
                raise ValueError("Invalid DBMS observations")
        if label_col:
            if not data[label_col].isin([-1, 1]).all():
                raise ValueError("Invalid ground-truth labels")
            data[label_col] = data[label_col].astype(int)
    # A held-out subset can infer int64 while the full CSV infers uint64.
    # Compare observation values, rather than requiring identical inferred dtypes.
    expected_test = frame.iloc[train_rows:][columns].reset_index(drop=True).astype(object)
    if (not frame[timestamp_col].is_monotonic_increasing
            or frame[timestamp_col].duplicated().any()
            or not expected_test.equals(predictions[columns].astype(object))):
        raise ValueError("Predictions do not match the chronological test observations")
    for name in names:
        prediction_col, score_col = f"{name}_prediction", f"{name}_score"
        if not predictions[prediction_col].isin([-1, 1]).all():
            raise ValueError("Invalid predictions")
        predictions[prediction_col] = predictions[prediction_col].astype(int)
        predictions[score_col] = pd.to_numeric(predictions[score_col], errors="raise")
        if not np.isfinite(predictions[score_col]).all():
            raise ValueError("Invalid decision scores")
    if set(metrics) != (set(names) if label_col else set()):
        raise ValueError("Metrics do not match the selected labels")
    for values in metrics.values():
        if (not isinstance(values, dict) or set(values) != {"precision", "recall", "f1"}
                or any(isinstance(value, bool) or not isinstance(value, (int, float))
                       or not math.isfinite(value) or not 0 <= value <= 1 for value in values.values())):
            raise ValueError("Invalid evaluation metrics")
    if (not isinstance(metadata.get("features"), list)
            or not all(isinstance(item, str) for item in metadata["features"])
            or not isinstance(metadata.get("warnings", []), list)
            or not all(isinstance(item, str) for item in metadata.get("warnings", []))):
        raise ValueError("Invalid feature or warning lists")
    return DetectionRun(frame=frame, predictions=predictions, metrics=metrics, metadata=metadata)


def _validate_reference_result(result: DetectionRun) -> None:
    """Validate the complete reference payload before any chart can consume it.

    This checks observations and reported counts only. The frontend never fits
    an anomaly estimator or falls back to producing predictions locally.
    """
    metadata = result.metadata
    baseline = metadata.get("reference_baseline")
    if (metadata.get("analysis_mode") != "notebook_reference"
            or metadata["rows"] != 4032 or metadata["train_rows"] != 3550
            or metadata["test_rows"] != 482 or not isinstance(baseline, dict)
            or baseline.get("scope") != "full_series_descriptive"
            or baseline.get("rows") != 4032 or baseline.get("fit_rows") != 4032):
        raise ValueError("Backend did not reproduce the requested notebook protocol")
    for key in ("median", "mad", "threshold"):
        value = baseline[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Invalid reference MAD statistics")
    if baseline["mad"] <= 0 or baseline["threshold"] != 3.5:
        raise ValueError("Invalid reference MAD statistics")

    time_col, value_col = metadata["timestamp_col"], metadata["value_col"]
    records = baseline["predictions"]
    columns = [time_col, value_col, "is_anomaly", "mad_prediction", "mad_score", "z_score"]
    if (not isinstance(records, list) or len(records) != 4032
            or any(not isinstance(row, dict) or not all(column in row for column in columns) for row in records)):
        raise ValueError("Invalid full-series reference records")
    full = pd.DataFrame(records)[columns]
    full[time_col] = pd.to_datetime(full[time_col], errors="raise", utc=True).dt.tz_convert(None)
    for column in (value_col, "mad_score", "z_score"):
        if full[column].map(lambda value: isinstance(value, bool)).any():
            raise ValueError("Invalid full-series reference values or scores")
        full[column] = pd.to_numeric(full[column], errors="raise")
        if not np.isfinite(full[column]).all():
            raise ValueError("Invalid full-series reference values or scores")
    for column in ("is_anomaly", "mad_prediction"):
        if (full[column].map(lambda value: isinstance(value, bool)).any()
                or not full[column].isin([-1, 1]).all()):
            raise ValueError("Invalid full-series reference labels or predictions")
        full[column] = full[column].astype(int)
    observed_columns = [time_col, value_col, "is_anomaly"]
    if not full[observed_columns].astype(object).equals(result.frame[observed_columns].astype(object)):
        raise ValueError("Full-series reference observations do not match backend context")
    expected_times = pd.date_range("2014-02-14 14:30:00", periods=4032, freq="5min")
    known = pd.to_datetime(["2014-02-26 22:05:00", "2014-02-27 17:15:00"])
    expected_labels = np.where(full[time_col].isin(known), -1, 1)
    if (not np.array_equal(full[time_col].to_numpy(), expected_times.to_numpy())
            or not np.array_equal(full["is_anomaly"].to_numpy(), expected_labels)
            or full[value_col].nunique() < 2):
        raise ValueError("Invalid reference timeline or official point labels")
    for column in ("mad_prediction", "mad_score"):
        if not np.array_equal(full[column].iloc[3550:].to_numpy(), result.predictions[column].to_numpy()):
            raise ValueError("Full-series MAD results do not match test predictions")

    def validate_matrix(matrix, truth, predicted, expected_rows):
        if (not isinstance(matrix, list) or len(matrix) != 2
                or any(not isinstance(row, list) or len(row) != 2 for row in matrix)
                or any(type(value) is not int or value < 0 for row in matrix for value in row)
                or sum(sum(row) for row in matrix) != expected_rows):
            raise ValueError("Invalid reference confusion matrix")
        actual = [[int(((truth == label) & (predicted == prediction)).sum())
                   for prediction in (1, -1)] for label in (1, -1)]
        if matrix != actual:
            raise ValueError("Reference confusion matrix does not match prediction records")

    metrics = baseline["metrics"]
    if (not isinstance(metrics, dict) or set(metrics) != {"precision", "recall", "f1"}
            or any(isinstance(value, bool) or not isinstance(value, (int, float))
                   or not math.isfinite(value) or not 0 <= value <= 1 for value in metrics.values())):
        raise ValueError("Invalid full-series reference metrics")
    validate_matrix(baseline["confusion_matrix"], full["is_anomaly"], full["mad_prediction"], 4032)
    matrices = metadata["confusion_matrices"]
    if not isinstance(matrices, dict) or set(matrices) != {"mad", "isolation_forest", "lof"}:
        raise ValueError("Missing reference test confusion matrices")
    for name in metadata["model_names"]:
        validate_matrix(matrices[name], result.predictions["is_anomaly"], result.predictions[f"{name}_prediction"], 482)
    # Keep the metadata consumed by the dashboard normalized exactly as checked.
    baseline["predictions"] = json.loads(full.to_json(
        orient="records", date_format="iso", date_unit="ns", double_precision=15,
    ))


def _validate_dbms_result(result: DetectionRun, noise_guard: bool, threshold: float) -> None:
    """Reject incomplete or inconsistent DBMS evidence before rendering it."""
    metadata, data = result.metadata, result.predictions
    expected = ["queries_per_second", "connections", "response_time_ms", "slow_queries", "connection_errors"]
    policy = metadata.get("noise_guard", {})
    if (metadata.get("analysis_mode") != "dbms" or metadata.get("metric_cols") != expected
            or policy.get("enabled") is not noise_guard
            or policy.get("deviation_threshold") != threshold):
        raise ValueError("Backend returned a different DBMS policy")
    if (not data["activity_deviation"].map(lambda value: isinstance(value, (bool, np.bool_))).all()
            or not data["suspected_indicators"].map(lambda value: isinstance(value, str)).all()):
        raise ValueError("Missing DBMS evidence")
    for metric in expected:
        for suffix in ("_deviation", "_deviation_score"):
            if not np.isfinite(pd.to_numeric(data[metric + suffix], errors="raise")).all():
                raise ValueError("Invalid DBMS deviations")
    names = metadata["model_names"]
    labeled = bool(metadata.get("label_col"))
    for key in ("raw_metrics", "confusion_matrices", "raw_confusion_matrices"):
        values = metadata.get(key)
        if not isinstance(values, dict) or set(values) != (set(names) if labeled else set()):
            raise ValueError("DBMS evaluation scope disagrees with selected labels")
    for name in metadata["model_names"]:
        raw = data[f"{name}_raw_prediction"]
        if not raw.isin([-1, 1]).all():
            raise ValueError("Invalid raw model predictions")
        alert = raw.eq(-1) & (data["activity_deviation"] if noise_guard else True)
        if not data[f"{name}_prediction"].eq(np.where(alert, -1, 1)).all():
            raise ValueError("DBMS alerts disagree with raw predictions and policy")
        if metadata.get("raw_anomaly_counts", {}).get(name) != int(raw.eq(-1).sum()):
            raise ValueError("DBMS raw counts disagree with predictions")
        if metadata.get("anomaly_counts", {}).get(name) != int(data[f"{name}_prediction"].eq(-1).sum()):
            raise ValueError("DBMS alert counts disagree with predictions")
        if labeled:
            truth = data[metadata["label_col"]]
            for key, predicted, scores in (
                ("confusion_matrices", data[f"{name}_prediction"], result.metrics[name]),
                ("raw_confusion_matrices", raw, metadata["raw_metrics"][name]),
            ):
                matrix = [[int(((truth == actual) & (predicted == prediction)).sum())
                           for prediction in (1, -1)] for actual in (1, -1)]
                if metadata.get(key, {}).get(name) != matrix:
                    raise ValueError("DBMS confusion matrix disagrees with observations")
                true_positive, false_positive, false_negative = matrix[1][1], matrix[0][1], matrix[1][0]
                precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.
                recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.
                expected_scores = {
                    "precision": precision, "recall": recall,
                    "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.,
                }
                if (not isinstance(scores, dict) or set(scores) != set(expected_scores)
                        or any(isinstance(value, bool) or not isinstance(value, (int, float))
                               or not math.isfinite(value) or not 0 <= value <= 1
                               or not math.isclose(value, expected_scores[metric], rel_tol=1e-12, abs_tol=1e-12)
                               for metric, value in scores.items())):
                    raise ValueError("DBMS evaluation metrics disagree with observations")


def detect_via_api(content: bytes, source_name: str, *, timestamp_col: str = "timestamp",
                   value_col: str | None = None, label_col: str | None = None,
                   train_fraction: float = .7, contamination: float = .01,
                   model_names=None, include_time: bool = False,
                   analysis_mode: str = "chronological", split_index: int | None = None,
                   noise_guard: bool = True, deviation_threshold: float = 3.5) -> DetectionRun:
    """Upload CSV and configuration; all model fitting takes place in FastAPI."""
    base_url = get_backend_url()
    try:
        address = urlsplit(base_url)
        if (address.scheme not in {"http", "https"} or not address.hostname
                or address.username or address.password or address.query or address.fragment):
            raise ValueError("Invalid backend URL")
    except ValueError as exc:
        raise BackendError("Địa chỉ BE chưa hợp lệ. Hãy kiểm tra cấu hình ANOMALY_API_URL.") from exc
    names = list(MODEL_NAMES if model_names is None else [model_names] if isinstance(model_names, str) else model_names)
    if value_col is None:
        value_col = "queries_per_second" if analysis_mode == "dbms" else "value"
    if analysis_mode == "notebook_reference":
        names, label_col = ["mad", "isolation_forest", "lof"], "is_anomaly"
        train_fraction, contamination, include_time, split_index = 3550 / 4032, 1 / 3550, False, 3550
    params = {
        "timestamp_col": timestamp_col, "value_col": value_col,
        "train_fraction": train_fraction, "contamination": contamination,
        "models": ",".join(names), "include_time": include_time, "include_context": True,
    }
    if label_col is not None:
        params["label_col"] = label_col
    if analysis_mode != "chronological":
        params["analysis_mode"] = analysis_mode
    if analysis_mode == "dbms":
        params.update(noise_guard=noise_guard, deviation_threshold=deviation_threshold)
    if split_index is not None:
        params["split_index"] = split_index
    try:
        response = httpx.post(
            base_url + "/detect", params=params,
            files={"file": (source_name or "data.csv", content, "text/csv")},
            timeout=REQUEST_TIMEOUT, trust_env=False,
        )
    except httpx.TimeoutException as exc:
        raise BackendError("BE xử lý quá lâu hoặc chưa phản hồi. Hãy kiểm tra terminal BE, giảm dữ liệu hoặc chọn ít thuật toán hơn rồi thử lại.") from exc
    except httpx.InvalidURL as exc:
        raise BackendError("Địa chỉ BE chưa hợp lệ. Hãy kiểm tra cấu hình ANOMALY_API_URL.") from exc
    except httpx.RequestError as exc:
        raise BackendError("Không kết nối được BE. Hãy chạy FastAPI trong terminal riêng, đợi Application startup complete rồi bấm Chạy phát hiện lại.") from exc
    if response.status_code == 413:
        raise BackendError("BE từ chối tệp vì vượt quá 10 MiB. Hãy chia tệp nhỏ hơn rồi thử lại.")
    if response.status_code in {400, 422}:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        message = error_message(ValueError(detail)) if isinstance(detail, str) else "Hãy kiểm tra lại dữ liệu và cấu hình đã chọn."
        raise BackendError("BE không thể phân tích: " + message)
    if not 200 <= response.status_code < 300:
        raise BackendError(f"BE trả về lỗi HTTP {response.status_code}. Hãy kiểm tra terminal BE và địa chỉ ANOMALY_API_URL rồi thử lại.")
    try:
        result = _read_result(response.json(), names, timestamp_col, value_col, label_col)
        if analysis_mode == "notebook_reference":
            _validate_reference_result(result)
        elif analysis_mode == "dbms":
            _validate_dbms_result(result, noise_guard, deviation_threshold)
        return result
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        raise BackendError("Phản hồi từ BE không đúng định dạng kết quả. Hãy cập nhật và khởi động lại BE từ cùng phiên bản dự án.") from exc


def compare_via_api(normal_content: bytes, anomalous_content: bytes,
                    normal_source_name: str = "normal.csv", anomalous_source_name: str = "anomalous.csv", *,
                    timestamp_col: str = "timestamp", value_col: str = "queries_per_second",
                    label_col: str | None = None, train_fraction: float = .7,
                    contamination: float = .01, model_names=None, include_time: bool = False,
                    split_index: int | None = None, noise_guard: bool = True,
                    deviation_threshold: float = 3.5) -> dict[str, DetectionRun]:
    """Upload a pair and validate one shared-reference fit; never fit locally."""
    base_url = get_backend_url()
    try:
        address = urlsplit(base_url)
        if (address.scheme not in {"http", "https"} or not address.hostname
                or address.username or address.password or address.query or address.fragment):
            raise ValueError("Invalid backend URL")
    except ValueError as exc:
        raise BackendError("Địa chỉ BE chưa hợp lệ. Hãy kiểm tra cấu hình ANOMALY_API_URL.") from exc
    for content in (normal_content, anomalous_content):
        if not isinstance(content, bytes) or not content:
            raise BackendError("Cần hai tệp CSV có dữ liệu để so sánh. Hãy chọn lại dữ liệu rồi thử lại.")
        if len(content) > 10 * 1024 * 1024:
            raise BackendError("Mỗi tệp CSV so sánh phải nhỏ hơn hoặc bằng 10 MiB. Hãy chia tệp nhỏ hơn rồi thử lại.")
    names = list(MODEL_NAMES if model_names is None else [model_names] if isinstance(model_names, str) else model_names)
    params = {
        "timestamp_col": timestamp_col, "value_col": value_col,
        "train_fraction": train_fraction, "contamination": contamination,
        "models": ",".join(names), "include_time": include_time, "include_context": True,
        "noise_guard": noise_guard, "deviation_threshold": deviation_threshold,
    }
    if label_col is not None:
        params["label_col"] = label_col
    if split_index is not None:
        params["split_index"] = split_index
    try:
        response = httpx.post(
            base_url + "/compare", params=params,
            files={
                "normal_file": (normal_source_name or "normal.csv", normal_content, "text/csv"),
                "anomalous_file": (anomalous_source_name or "anomalous.csv", anomalous_content, "text/csv"),
            }, timeout=REQUEST_TIMEOUT, trust_env=False,
        )
    except httpx.TimeoutException as exc:
        raise BackendError("BE xử lý so sánh quá lâu. Hãy kiểm tra terminal BE, giảm dữ liệu hoặc chọn ít thuật toán hơn rồi thử lại.") from exc
    except httpx.InvalidURL as exc:
        raise BackendError("Địa chỉ BE chưa hợp lệ. Hãy kiểm tra cấu hình ANOMALY_API_URL.") from exc
    except httpx.RequestError as exc:
        raise BackendError("Không kết nối được BE để so sánh. Hãy chạy FastAPI trong terminal riêng, đợi Application startup complete rồi thử lại.") from exc
    if response.status_code == 413:
        raise BackendError("BE từ chối tệp so sánh vì vượt quá 10 MiB. Hãy chia tệp nhỏ hơn rồi thử lại.")
    if response.status_code in {400, 422}:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        message = error_message(ValueError(detail)) if isinstance(detail, str) else "Hãy kiểm tra lại hai tệp và cấu hình đã chọn."
        raise BackendError("BE không thể so sánh: " + message)
    if not 200 <= response.status_code < 300:
        raise BackendError(f"BE trả về lỗi HTTP {response.status_code} khi so sánh. Hãy kiểm tra terminal BE và thử lại.")
    try:
        payload = response.json()
        if not isinstance(payload, dict) or set(payload) != {"normal", "anomalous"}:
            raise ValueError("Expected exactly two comparison results")
        runs = {role: _read_result(payload[role], names, timestamp_col, value_col, label_col)
                for role in ("normal", "anomalous")}
        normal = runs["normal"]
        reference_rows = normal.metadata["train_rows"]
        batch_rows = sum(run.metadata["test_rows"] for run in runs.values())
        for role, run in runs.items():
            _validate_dbms_result(run, noise_guard, deviation_threshold)
            comparison = run.metadata.get("comparison", {})
            expected_split = int(Decimal(len(run.frame)) * Decimal(str(train_fraction))) if split_index is None else split_index
            if (comparison.get("role") != role or comparison.get("reference_source") != "normal"
                    or type(comparison.get("shared_model_fit_calls")) is not int
                    or comparison["shared_model_fit_calls"] != 1
                    or type(comparison.get("shared_scaler_fit_calls")) is not int
                    or comparison["shared_scaler_fit_calls"] != 1
                    or comparison.get("reference_train_rows") != reference_rows
                    or comparison.get("local_excluded_prefix_rows") != run.metadata["train_rows"]
                    or comparison.get("prediction_batch_rows") != batch_rows
                    or comparison.get("same_model_parameters") is not True
                    or comparison.get("reference_start") != normal.frame[timestamp_col].iloc[0].isoformat()
                    or comparison.get("reference_end") != normal.frame[timestamp_col].iloc[reference_rows - 1].isoformat()
                    or run.metadata["train_rows"] != expected_split
                    or run.metadata.get("contamination") != contamination
                    or run.metadata.get("train_baselines") != normal.metadata.get("train_baselines")
                    or run.metadata.get("parameters") != normal.metadata.get("parameters")):
                raise ValueError("Comparison did not use the same normal training reference")
            for name in names:
                preprocessing = run.metadata["parameters"][name]["preprocessing"]
                if preprocessing.get("name") != "StandardScaler" or preprocessing.get("fit_rows") != reference_rows:
                    raise ValueError("Comparison normalization was not fitted on the normal reference")
        return runs
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        raise BackendError("Phản hồi so sánh từ BE không đúng định dạng kết quả hoặc không dùng chung mô hình tham chiếu. Hãy cập nhật và khởi động lại BE từ cùng phiên bản dự án.") from exc
