"""Create four reproducible, explicitly synthetic algorithm teaching datasets.

No estimator, model score or test-label tuning is used to construct the data.
Run from the project root: python scripts/generate_algorithm_datasets.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROWS = 1000
TRAIN_ROWS = 700
ANOMALY_INDICES = (720, 735, 750, 775, 790, 810, 835, 850, 875, 890, 910, 935, 950, 975, 990)
COLUMNS = (
    "timestamp", "queries_per_second", "connections", "response_time_ms",
    "slow_queries", "connection_errors", "label", "scenario",
)
SEEDS = {"MAD.csv": 20261121, "Isolation_Forest.csv": 20261122,
         "LOF.csv": 20261123, "One_Class_SVM.csv": 20261124}
START = datetime(2026, 11, 1, tzinfo=timezone(timedelta(hours=7)))


def _bounded_noise(rng: random.Random) -> float:
    return max(-2.5, min(2.5, rng.gauss(0, 1)))


def _normal_row(name: str, rng: random.Random) -> tuple[list, str]:
    if name == "MAD.csv":
        return [50 + 1.5 * _bounded_noise(rng), 30 + rng.randint(-2, 2),
                15 + .3 * _bounded_noise(rng), 0, 0], "normal_stable_baseline"
    if name == "Isolation_Forest.csv":
        profile = rng.choices((0, 1, 2), weights=(.45, .35, .20))[0]
        qps, connections, latency, slow = ((80, 20, 12, 0), (160, 50, 20, 1),
                                           (260, 90, 35, 3))[profile]
        return [qps + 8 * _bounded_noise(rng),
                connections + rng.randint(-4, 4),
                latency + 1.2 * _bounded_noise(rng), slow, 0], f"normal_load_profile_{profile + 1}"
    if name == "LOF.csv":
        if rng.random() < .75:
            return [100 + .7 * _bounded_noise(rng), 40 + rng.randint(-1, 1),
                    15 + .2 * _bounded_noise(rng), 0, 0], "normal_dense_cluster"
        return [210 + 20 * _bounded_noise(rng), 85 + rng.randint(-12, 12),
                40 + 4 * _bounded_noise(rng), 0, 0], "normal_sparse_cluster"
    # A curved relationship, not a trend over time: both chronological
    # partitions sample the same load distribution. Event counts stay at zero.
    t = rng.uniform(-2, 2)
    return [100 + 30 * t + .4 * _bounded_noise(rng),
            round(60 + 15 * t + .3 * _bounded_noise(rng)),
            15 + 3 * t * t + .15 * _bounded_noise(rng), 0, 0], "normal_curved_relationship"


def _inject(name: str, position: int, metrics: list) -> tuple[list, str]:
    metrics = list(metrics)
    if name == "MAD.csv":
        metrics[0] = 150 + 8 * position if position % 2 == 0 else 5 + position % 4
        return metrics, "injected_qps_spike" if position % 2 == 0 else "injected_qps_drop"
    if name == "Isolation_Forest.csv":
        return [450 + 18 * position, 150 + 5 * position, 90 + 4 * position,
                12 + position % 6, 2 + position % 4], "injected_multivariate_extreme"
    if name == "LOF.csv":
        return [106 + .3 * position, 44 + position % 3, 17 + .1 * position,
                0, 0], "injected_local_density_deviation"
    return [100 + 2 * math.sin(position), 60 + position % 3 - 1,
            26 + .1 * position, 0, 0], "injected_relationship_violation"


def build_datasets() -> dict[str, list[list]]:
    anomaly_order = {index: position for position, index in enumerate(ANOMALY_INDICES)}
    datasets = {}
    for name, seed in SEEDS.items():
        rng = random.Random(seed)
        records = []
        for index in range(ROWS):
            metrics, scenario = _normal_row(name, rng)
            label = 1
            if index in anomaly_order:
                metrics, scenario = _inject(name, anomaly_order[index], metrics)
                label = -1
            metrics = [round(float(value), 3) if column in (0, 2) else int(value)
                       for column, value in enumerate(metrics)]
            assert all(math.isfinite(value) and value >= 0 for value in metrics)
            records.append([(START + timedelta(minutes=index)).isoformat(), *metrics, label, scenario])
        datasets[name] = records
    return datasets


def _csv_value(value):
    # Stable representation also used by the CSV-only artifact export.
    return format(value, ".3f").rstrip("0").rstrip(".") if isinstance(value, float) else value


def write_datasets(output_dir: Path, manifest_path: Path, json_path: Path | None = None) -> dict:
    datasets = build_datasets()
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, records in datasets.items():
        path = output_dir / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(COLUMNS)
            writer.writerows([_csv_value(value) for value in row] for row in records)
        files[name] = {"seed": SEEDS[name], "rows": len(records), "train_rows": TRAIN_ROWS,
                       "test_rows": ROWS - TRAIN_ROWS, "train_anomalies": 0,
                       "test_anomalies": len(ANOMALY_INDICES),
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {
        "provenance": "Synthetic teaching examples, not measured MySQL telemetry.",
        "generator": "scripts/generate_algorithm_datasets.py",
        "generation_policy": "Fixed independent seeds and predefined incidents; no estimator fitting or score-based selection.",
        "columns": list(COLUMNS), "sampling_interval_seconds": 60,
        "start_timestamp": START.isoformat(), "timezone": "UTC+07:00 (Asia/Ho_Chi_Minh)",
        "recommended_configuration": {"analysis_mode": "dbms", "label_col": "label",
            "train_fraction": .7, "split_index": TRAIN_ROWS, "contamination": .01,
            "include_time": False, "noise_guard": False},
        "label_policy": {"1": "generated normal operating pattern", "-1": "explicitly injected incident"},
        "anomaly_indices_zero_based": list(ANOMALY_INDICES),
        "anomaly_record_numbers_one_based": [index + 1 for index in ANOMALY_INDICES],
        "features": list(COLUMNS[1:6]), "excluded_from_features": ["timestamp", "label", "scenario"],
        "metric_definitions": {
            "queries_per_second": "queries/second during the one-minute sampling interval",
            "connections": "current active client connections (integer gauge)",
            "response_time_ms": "synthetic probe round-trip latency in milliseconds",
            "slow_queries": "slow-query count during this interval, not a cumulative counter",
            "connection_errors": "failed-connection count during this interval, not a cumulative counter"},
        "scenarios": {
            "MAD.csv": "Stable baseline with isolated high and low QPS values; other metrics unchanged.",
            "Isolation_Forest.csv": "Three normal load profiles and rare simultaneous extremes in five metrics.",
            "LOF.csv": "Dense and sparse normal clusters; incidents lie just outside the dense cluster, within overall marginal ranges.",
            "One_Class_SVM.csv": "QPS and connections follow latent load t; latency follows 15+3*t^2. Incidents combine middle QPS/connections with high latency."},
        "limitations": [
            "Filenames identify intended teaching concepts, not exclusive algorithm compatibility or guaranteed superiority.",
            "All four algorithms can be evaluated on every file using the same held-out rows.",
            "Synthetic results cannot establish accuracy on production workloads.",
            "Use all five metrics in DBMS mode; a one-metric CSV run loses relational information.",
            "The operational noise guard may suppress local and relational anomalies; disable it to examine raw algorithms.",
            "One percent contamination/nu does not guarantee one percent test alerts. Fifteen injected events occupy five percent of test rows.",
            "Event counts intentionally remain zero in the MAD, LOF and One-Class SVM baselines."
        ], "files": files,
        "algorithm_reference": "https://scikit-learn.org/stable/auto_examples/miscellaneous/plot_anomaly_comparison.html"
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps({"columns": list(COLUMNS), "datasets": datasets}), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "resources" / "algorithm_datasets")
    parser.add_argument("--manifest-path", type=Path, default=ROOT / "docs" / "algorithm_datasets_manifest.json")
    parser.add_argument("--json-path", type=Path, help="Optional typed intermediate for spreadsheet-tool verification.")
    args = parser.parse_args()
    result = write_datasets(args.output_dir, args.manifest_path, args.json_path)
    print(json.dumps(result["files"], indent=2))
