"""Generate three small, explicitly synthetic MySQL demonstration CSVs.

Run: python scripts/generate_mysql_demo.py
Each file contains ten one-minute observations: seven normal training rows,
then three test rows. No estimator is fitted when constructing these fixtures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


ROWS = 10
TRAIN_FRACTION = .7
SPLIT_INDEX = 7
DATASET_FILES = (
    "mysql_normal.csv", "mysql_query_spike.csv", "mysql_latency_spike.csv",
)
INCIDENT_DEFINITIONS = (
    ("mysql_query_spike.csv", "query_spike", "queries_per_second",
     {"queries_per_second": [300, 350]}),
    ("mysql_latency_spike.csv", "latency_spike", "response_time_ms",
     {"response_time_ms": [180.0, 220.0], "slow_queries": [8, 10]}),
)


def _normal_frame() -> pd.DataFrame:
    """Fixed, readable baseline; modest variation is normal by design."""
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-10-01 09:00:00", periods=ROWS, freq="min"),
        "queries_per_second": [50, 52, 49, 51, 48, 53, 50, 51, 49, 52],
        "connections": [30, 31, 29, 30, 28, 32, 30, 31, 29, 30],
        "response_time_ms": [15.0, 16.0, 14.0, 15.0, 14.5, 16.5, 15.5, 15.0, 14.5, 16.0],
        # Event counts in each one-minute interval, not lifetime counters.
        "slow_queries": [0, 1, 0, 0, 1, 0, 0, 0, 1, 0],
        "connection_errors": [0] * ROWS,
        "label": [1] * ROWS,
        "scenario": ["normal_natural_variation"] * ROWS,
    })


def _incident_records(normal: pd.DataFrame) -> list[dict]:
    incidents = []
    for filename, scenario, primary, values in INCIDENT_DEFINITIONS:
        incidents.append({
            "file": filename, "scenario": scenario,
            "start_index": SPLIT_INDEX, "end_index_exclusive": SPLIT_INDEX + 2,
            "row_numbers": [8, 9],
            "start_timestamp": str(normal.loc[SPLIT_INDEX, "timestamp"]),
            "end_timestamp": str(normal.loc[SPLIT_INDEX + 1, "timestamp"]),
            "primary_metric": primary, "affected_metrics": list(values),
            "secondary_metrics": [metric for metric in values if metric != primary],
            "injected_values": values,
        })
    return incidents


def build_mysql_datasets() -> dict[str, pd.DataFrame]:
    """Build normal, query-spike and latency-spike fixtures with the same baseline.

    Only rows eight and nine are changed in each abnormal file. Row ten returns
    to normal. Labels and scenario names are test context, never model features.
    The values illustrate symptoms; they make no claim about their root cause.
    """
    normal = _normal_frame()
    datasets = {DATASET_FILES[0]: normal}
    for incident in _incident_records(normal):
        frame = normal.copy(deep=True)
        start, end = incident["start_index"], incident["end_index_exclusive"]
        for metric, values in incident["injected_values"].items():
            frame.loc[start:end - 1, metric] = values
        frame.loc[start:end - 1, "label"] = -1
        frame.loc[start:end - 1, "scenario"] = incident["scenario"]
        datasets[incident["file"]] = frame
    return datasets


def write_demo_datasets(output_dir: Path, manifest_path: Path | None = None) -> dict:
    """Write three ten-row CSVs and a provenance manifest outside their directory.

    Unrelated files are preserved. Cleanup is a separate explicitly requested
    action. A custom output directory uses its parent's docs folder by default.
    """
    output_dir = Path(output_dir)
    manifest_path = Path(manifest_path) if manifest_path is not None else output_dir.parent / "docs" / "mysql_datasets_manifest.json"
    if manifest_path.resolve().is_relative_to(output_dir.resolve()):
        raise ValueError("The provenance manifest must be outside the CSV data directory")
    datasets = build_mysql_datasets()
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, frame in datasets.items():
        path = output_dir / name
        frame.to_csv(path, index=False, date_format="%Y-%m-%d %H:%M:%S", lineterminator="\n")
        files[name] = {"rows": len(frame), "anomalies": int((frame["label"] == -1).sum()),
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {
        "provenance": "Synthetic MySQL activity demonstration fixtures, not measurements from a real MySQL server.",
        "generator": "scripts/generate_mysql_demo.py", "generation_policy": "fixed readable values; no estimator fitting or score-based selection",
        "rows": ROWS, "sampling_interval_seconds": 60,
        "recommended_train_fraction": TRAIN_FRACTION, "recommended_split_index": SPLIT_INDEX,
        "training_baseline": "All three datasets have identical first seven normal chronological training rows; incidents occur only in test rows eight and nine, followed by normal row ten.",
        "label_policy": {"1": "normal, including bounded natural variation", "-1": "explicitly injected incident"},
        "metric_definitions": {
            "queries_per_second": "queries/second averaged over the sampling interval",
            "connections": "active client connections sampled as a gauge",
            "response_time_ms": "milliseconds for a lightweight probe; synthetic baseline in these fixtures",
            "slow_queries": "count of slow queries during the sampling interval (delta Slow_queries), not a lifetime counter",
            "connection_errors": "count of failed connection attempts during the sampling interval (delta Aborted_connects), not all MySQL error categories or a lifetime counter",
        },
        "scenario_policy": "Each abnormal CSV contains one isolated scenario. Secondary event counts are explicitly injected symptoms, not evidence of root cause. Neither labels nor scenario are model features.",
        "incidents": _incident_records(datasets[DATASET_FILES[0]]), "files": files,
        "limitations": "Only ten rows per file (seven train, three test): suitable for showing the interface and checking functionality, not training a reliable production detector or ranking algorithms. Computed model predictions may differ; no detection result is guaranteed. Does not establish effectiveness on real workloads.",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--manifest-path", type=Path, default=None,
                        help="Provenance JSON outside data; default: output-dir/../docs/mysql_datasets_manifest.json")
    args = parser.parse_args()
    result = write_demo_datasets(args.output_dir, args.manifest_path)
    print(json.dumps({"output_dir": str(args.output_dir), "files": result["files"]}, indent=2))
