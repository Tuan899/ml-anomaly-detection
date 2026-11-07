"""Generate reproducible, explicitly synthetic MySQL activity test fixtures.

Run: python scripts/generate_mysql_demo.py
No model predictions or benchmark results are embedded in these files.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 20261107
ROWS = 1440
TRAIN_FRACTION = .7


def build_demo_frames(seed=SEED, rows=ROWS):
    if isinstance(rows, bool) or not isinstance(rows, int) or rows < 1200:
        raise ValueError("Demo generation requires at least 1200 rows")
    rng = np.random.default_rng(seed)
    step = np.arange(rows)
    cycle = np.sin(2 * np.pi * step / 60)
    slow_cycle = np.sin(2 * np.pi * step / 240)
    normal = pd.DataFrame({
        "timestamp": pd.date_range("2026-10-01", periods=rows, freq="min"),
        "queries_per_second": np.round(50 + 6 * cycle + 2 * slow_cycle + rng.uniform(-1.0, 1.0, rows), 3),
        "connections": np.rint(30 + 4 * cycle + 2 * slow_cycle + rng.uniform(-1, 1, rows)).astype(int),
        "response_time_ms": np.round(15 + 2 * cycle + .8 * slow_cycle + rng.uniform(-.6, .6, rows), 3),
        # Integer event counts during each interval, not cumulative counters.
        # Occasional isolated slow queries are deliberately labeled normal.
        "slow_queries": ((step % 90) < 12).astype(int),
        "connection_errors": np.zeros(rows, dtype=int),
        "label": np.ones(rows, dtype=int),
        "scenario": ["normal_natural_variation"] * rows,
    })
    anomalous = normal.copy(deep=True)
    split = int(Decimal(rows) * Decimal(str(TRAIN_FRACTION)))
    held_out = rows - split
    incidents = []
    definitions = [
        (.10, .18, "query_spike", {"queries_per_second": (5.0, 100.0)}),
        (.30, .38, "connection_spike", {"connections": (4.0, 90.0)}),
        (.50, .58, "latency_spike", {"response_time_ms": (9.0, 90.0)}),
        (.72, .82, "combined_pressure", {"queries_per_second": (4.0, 90.0), "connections": (3.0, 60.0),
                                          "response_time_ms": (8.0, 100.0), "slow_queries": (1.0, 8.0),
                                          "connection_errors": (1.0, 3.0)}),
    ]
    for start_fraction, end_fraction, scenario, transforms in definitions:
        start = split + int(held_out * start_fraction)
        end = split + int(held_out * end_fraction)
        for metric, (factor, offset) in transforms.items():
            values = anomalous.loc[start:end - 1, metric] * factor + offset
            if metric in ("connections", "slow_queries", "connection_errors"):
                values = np.rint(values).astype(int)
            anomalous.loc[start:end - 1, metric] = np.round(values, 3)
        anomalous.loc[start:end - 1, "label"] = -1
        anomalous.loc[start:end - 1, "scenario"] = scenario
        incidents.append({"scenario": scenario, "start_index": start, "end_index_exclusive": end,
                          "start_timestamp": str(anomalous.loc[start, "timestamp"]),
                          "end_timestamp": str(anomalous.loc[end - 1, "timestamp"]),
                          "affected_metrics": list(transforms)})
    return normal, anomalous, incidents


def write_demo_datasets(output_dir: Path, seed=SEED, rows=ROWS):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    normal, anomalous, incidents = build_demo_frames(seed, rows)
    files = {}
    for name, frame in (("mysql_normal.csv", normal), ("mysql_anomalous.csv", anomalous)):
        path = output_dir / name
        frame.to_csv(path, index=False, date_format="%Y-%m-%d %H:%M:%S", lineterminator="\n")
        files[name] = {"rows": len(frame), "anomalies": int((frame["label"] == -1).sum()),
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {
        "provenance": "Synthetic MySQL activity demonstration fixtures, not measurements from a real MySQL server.",
        "generator": "scripts/generate_mysql_demo.py", "seed": seed, "rows": rows,
        "sampling_interval_seconds": 60, "recommended_train_fraction": TRAIN_FRACTION,
        "recommended_split_index": int(Decimal(rows) * Decimal(str(TRAIN_FRACTION))),
        "training_baseline": "Both datasets have identical normal chronological training rows; incidents occur only after the recommended split.",
        "label_policy": {"1": "normal, including bounded natural variation", "-1": "explicitly injected incident"},
        "metric_definitions": {
            "queries_per_second": "queries/second averaged over the sampling interval",
            "connections": "active client connections sampled as a gauge",
            "response_time_ms": "milliseconds for a lightweight probe; synthetic baseline in these fixtures",
            "slow_queries": "count of slow queries during the sampling interval (delta Slow_queries), not a lifetime counter",
            "connection_errors": "count of failed connection attempts during the sampling interval (delta Aborted_connects), not all MySQL error categories or a lifetime counter",
        },
        "scenario_policy": "scenario is test context only; neither labels nor scenario are model features",
        "incidents": incidents, "files": files,
        "limitations": "Designed functional tests with separated incident magnitudes; performance must be recomputed and cannot establish effectiveness on real workloads.",
    }
    (output_dir / "mysql_demo_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--rows", type=int, default=ROWS)
    args = parser.parse_args()
    result = write_demo_datasets(args.output_dir, args.seed, args.rows)
    print(json.dumps({"output_dir": str(args.output_dir), "files": result["files"]}, indent=2))
