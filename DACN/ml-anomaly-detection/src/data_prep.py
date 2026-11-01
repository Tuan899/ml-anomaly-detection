"""Validated CSV loading, point labels, and causal feature helpers.

The supplied NAB timestamps are point annotations, not NAB anomaly windows.
"""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlretrieve

import numpy as np
import pandas as pd


LABEL_COLUMNS = frozenset({"is_anomaly", "anomaly", "label", "labels", "target", "ground_truth", "y_true"})
NAB_DATASETS = {
    "ec2_cpu_utilization": "https://raw.githubusercontent.com/numenta/NAB/master/data/realAWSCloudwatch/ec2_cpu_utilization_24ae8d.csv",
    "machine_temperature": "https://raw.githubusercontent.com/numenta/NAB/master/data/realKnownCause/machine_temperature_system_failure.csv",
    "network_traffic": "https://raw.githubusercontent.com/numenta/NAB/master/data/realTraffic/occupancy_t4013.csv",
}
NAB_ANOMALY_TIMESTAMPS = ("2014-02-26 22:05:00", "2014-02-27 17:15:00")


def database_metric_columns(frame: pd.DataFrame) -> list[str]:
    """Return numeric activity columns, excluding labels and booleans."""
    return [
        column for column in frame.columns
        if str(column).lower() not in LABEL_COLUMNS
        and pd.api.types.is_numeric_dtype(frame[column])
        and not pd.api.types.is_bool_dtype(frame[column])
    ]


def read_csv_frame(source: str | Path | object) -> pd.DataFrame:
    """Read raw CSV rows and reject empty or ambiguous table structure.

    Preview and analysis share this parser so invalid headers or field counts
    fail consistently. Timestamps, labels, row order and metric values are left
    unchanged. A DataFrame input is copied without mutating the original.
    """
    try:
        if isinstance(source, pd.DataFrame):
            frame = source.copy()
        else:
            # pandas suffixes duplicate CSV headers (value, value.1), which can
            # conceal ambiguous input before the normal uniqueness check.
            seekable = (hasattr(source, "seek") and hasattr(source, "tell")
                        and (not hasattr(source, "seekable") or source.seekable()))
            if isinstance(source, (str, Path)) or seekable:
                position = source.tell() if seekable else None
                try:
                    header = pd.read_csv(source, header=None, nrows=1, dtype=str, keep_default_na=False)
                finally:
                    if seekable:
                        source.seek(position)
                if header.iloc[0].duplicated().any():
                    raise ValueError("Column names must be unique")
            frame = pd.read_csv(source)
            if not isinstance(frame.index, pd.RangeIndex):
                raise ValueError("CSV row fields do not match the header; check the delimiter and column count")
    except pd.errors.EmptyDataError as exc:
        raise ValueError("CSV is empty") from exc
    if frame.empty:
        raise ValueError("CSV must contain data rows")
    if not frame.columns.is_unique:
        raise ValueError("Column names must be unique")
    return frame


def load_timeseries(
    source: str | Path | object,
    timestamp_col: str = "timestamp",
    value_col: str | None = None,
) -> pd.DataFrame:
    """Load, sort and validate CSV data; report removed metric rows in attrs.

    Invalid timestamps and duplicate timestamps are rejected. Missing, nonnumeric,
    or infinite values in the selected metric are removed and counted explicitly.
    Timezone-aware timestamps are normalized to UTC without a timezone suffix.
    Labels are never inferred as metrics. The original input is never modified.
    """
    frame = read_csv_frame(source)
    if timestamp_col not in frame.columns:
        raise ValueError(f"Missing timestamp column: {timestamp_col}")
    timestamps = pd.to_datetime(frame[timestamp_col], errors="coerce", utc=True)
    if timestamps.isna().any():
        raise ValueError(f"Column {timestamp_col} contains invalid timestamps")
    frame[timestamp_col] = timestamps.dt.tz_convert(None)
    if frame[timestamp_col].duplicated().any():
        raise ValueError("Duplicate timestamps are not supported; aggregate them before analysis")
    if value_col is None:
        for candidate in frame.columns:
            if candidate == timestamp_col or str(candidate).lower() in LABEL_COLUMNS:
                continue
            if pd.api.types.is_bool_dtype(frame[candidate]):
                continue
            candidate_values = pd.to_numeric(frame[candidate], errors="coerce")
            if np.isfinite(candidate_values.to_numpy(dtype=float, na_value=np.nan)).any():
                value_col = candidate
                break
    if value_col is None:
        raise ValueError("CSV must contain at least one numeric activity metric, excluding labels")
    if value_col not in frame.columns:
        raise ValueError(f"Missing value column: {value_col}")
    if value_col == timestamp_col or str(value_col).lower() in LABEL_COLUMNS:
        raise ValueError("value_col must be an activity metric, not a timestamp or label")
    if pd.api.types.is_bool_dtype(frame[value_col]):
        raise ValueError("Boolean columns cannot be used as activity metrics")
    original_rows = len(frame)
    frame[value_col] = pd.to_numeric(frame[value_col], errors="coerce")
    valid = np.isfinite(frame[value_col].to_numpy(dtype=float, na_value=np.nan))
    frame = frame.loc[valid].sort_values(timestamp_col, kind="stable").reset_index(drop=True)
    if frame.empty:
        raise ValueError(f"Column {value_col} has no finite numeric values")
    frame.attrs["cleaning"] = {
        "input_rows": original_rows,
        "output_rows": len(frame),
        "dropped_rows": original_rows - len(frame),
        "reason": "missing, nonnumeric, or infinite selected metric values",
    }
    frame.attrs["value_col"] = value_col
    frame.attrs["timestamp_col"] = timestamp_col
    return frame


def add_nab_labels(
    frame: pd.DataFrame,
    timestamp_col: str = "timestamp",
    anomaly_timestamps: tuple[str, ...] = NAB_ANOMALY_TIMESTAMPS,
) -> pd.DataFrame:
    """Add +/-1 labels for explicitly supplied NAB point annotations.

    The defaults apply only to ec2_cpu_utilization_24ae8d, not other NAB series.
    This helper does not implement the official NAB window scoring protocol.
    """
    if timestamp_col not in frame.columns:
        raise ValueError(f"Missing timestamp column: {timestamp_col}")
    result = frame.copy()
    timestamps = pd.to_datetime(result[timestamp_col], errors="raise", utc=True)
    known = pd.to_datetime(list(anomaly_timestamps), errors="raise", utc=True)
    result["is_anomaly"] = np.where(timestamps.isin(known), -1, 1)
    return result


def robust_location_scale(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fit median and raw MAD. Zero MAD uses a finite epsilon tolerance.

    A constant training feature considers values within max(1e-12, eps*|median|)
    of the training median normal. A new level beyond this tolerance is anomalous.
    No held-out values participate in fitting this fallback.
    """
    array = np.asarray(values, dtype=float)
    if array.ndim == 1:
        array = array.reshape(-1, 1)
    if array.ndim != 2 or array.shape[0] == 0 or array.shape[1] == 0 or not np.isfinite(array).all():
        raise ValueError("Reference values must be a non-empty finite numeric matrix")
    center = np.median(array, axis=0)
    with np.errstate(over="ignore", invalid="ignore"):
        mad = np.median(np.abs(array - center), axis=0)
    fallback = np.maximum(1e-12, np.finfo(float).eps * np.maximum(1.0, np.abs(center)))
    scale = np.where(mad > 0, mad, fallback)
    if not np.isfinite(center).all() or not np.isfinite(scale).all():
        raise ValueError("Metric magnitude is too large for robust statistics")
    return center, scale


def robust_z_values(values: np.ndarray, center: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """Return finite signed robust z-scores using already fitted statistics."""
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        z = 0.6745 * (np.asarray(values, dtype=float) - center) / scale
    bound = np.finfo(float).max / 4
    return np.nan_to_num(z, nan=0.0, posinf=bound, neginf=-bound)


def compute_robust_z_scores(
    frame: pd.DataFrame,
    value_col: str = "value",
    reference: pd.DataFrame | None = None,
    threshold: float = 3.5,
) -> pd.DataFrame:
    """Score a metric using reference statistics, or describe the full sample.

    Pass reference=train_frame for held-out evaluation. reference=None retains
    the original descriptive helper behavior and must not be used as a test fit.
    """
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("threshold must be positive and finite")
    reference = frame if reference is None else reference
    for data in (frame, reference):
        if value_col not in data.columns:
            raise ValueError(f"Missing value column: {value_col}")
        try:
            values = data[[value_col]].to_numpy(dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError("Metric must contain finite numeric values") from exc
        if values.size == 0 or not np.isfinite(values).all():
            raise ValueError("Metric must contain finite numeric values")
    center, scale = robust_location_scale(reference[[value_col]].to_numpy(dtype=float))
    result = frame.copy()
    result["z_score"] = robust_z_values(frame[[value_col]].to_numpy(dtype=float), center, scale).ravel()
    result["baseline"] = np.where(result["z_score"].abs() >= threshold, -1, 1)
    return result


def add_time_features(frame: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
    """Add deterministic calendar features without fitting on observations."""
    if timestamp_col not in frame.columns:
        raise ValueError(f"Missing timestamp column: {timestamp_col}")
    result = frame.copy()
    timestamps = pd.to_datetime(result[timestamp_col], errors="raise", utc=True)
    if timestamps.isna().any():
        raise ValueError("Timestamps must not be missing")
    result["hour"] = timestamps.dt.hour
    result["day_of_week"] = timestamps.dt.dayofweek
    result["is_weekend"] = (timestamps.dt.dayofweek >= 5).astype(int)
    result["day_of_month"] = timestamps.dt.day
    result["month"] = timestamps.dt.month
    result["hour_sin"] = np.sin(2 * np.pi * result["hour"] / 24)
    result["hour_cos"] = np.cos(2 * np.pi * result["hour"] / 24)
    result["dow_sin"] = np.sin(2 * np.pi * result["day_of_week"] / 7)
    result["dow_cos"] = np.cos(2 * np.pi * result["day_of_week"] / 7)
    return result


def summarize_seasonality(frame: pd.DataFrame, value_col: str, timestamp_col: str = "timestamp") -> dict[str, pd.DataFrame]:
    """Return observed hourly, weekday, and monthly descriptive aggregates."""
    enriched = add_time_features(frame, timestamp_col)
    if value_col not in enriched.columns:
        raise ValueError(f"Missing value column: {value_col}")
    return {
        "hourly": enriched.groupby("hour")[value_col].agg(["mean", "median", "std"]).reset_index(),
        "weekday": enriched.groupby("day_of_week")[value_col].agg(["mean", "median", "std"]).reset_index(),
        "monthly": enriched.groupby("month")[value_col].agg(["mean", "median", "std"]).reset_index(),
    }


def download_nab_dataset(name: str, output_dir: str | Path = "data") -> Path:
    """Download a named public NAB dataset; annotations are a separate input."""
    if name not in NAB_DATASETS:
        raise ValueError(f"Unknown NAB dataset {name!r}; choose from {sorted(NAB_DATASETS)}")
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{name}.csv"
    urlretrieve(NAB_DATASETS[name], target)
    return target
