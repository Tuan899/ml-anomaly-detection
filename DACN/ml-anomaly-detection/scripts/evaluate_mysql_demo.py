"""Compute actual demo results; no stored or expected model scores are used."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd
import sklearn

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from src.dbms_monitoring import run_dbms_detection
from src.monitoring_summary import summarize_run
from frontend.reporting import build_report_markdown


DATASET_NAMES = (
    "mysql_normal.csv", "mysql_query_spike.csv", "mysql_latency_spike.csv",
)


def evaluate(output_dir: Path, data_dir: Path = PROJECT / "data") -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows, datasets = [], {}
    for name in DATASET_NAMES:
        source = Path(data_dir) / name
        run = run_dbms_detection(source, label_col="label")
        run.metadata.update(source_kind="synthetic", source_name=name)
        summary = summarize_run(run)
        run.predictions.to_csv(output_dir / f"{source.stem}_predictions.csv", index=False)
        (output_dir / f"{source.stem}_report.md").write_bytes(build_report_markdown(run, summary))
        datasets[name] = {"sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                          "metadata": run.metadata, "metrics": run.metrics,
                          "operational_summary": {key: summary[key] for key in
                                                  ("rows_analyzed", "raw_count", "alert_count",
                                                   "alert_rate", "status", "status_level")}}
        for scope, metrics, matrices, counts in (
            ("raw_model", run.metadata["raw_metrics"], run.metadata["raw_confusion_matrices"], run.metadata["raw_anomaly_counts"]),
            ("operational_alert", run.metrics, run.metadata["confusion_matrices"], run.metadata["anomaly_counts"]),
        ):
            for model, values in metrics.items():
                matrix = matrices[model]
                rows.append({"dataset": name, "scope": scope, "algorithm": model,
                             "test_rows": len(run.predictions), "alerts": counts[model], **values,
                             "accuracy": (matrix[0][0] + matrix[1][1]) / len(run.predictions),
                             "TN": matrix[0][0], "FP": matrix[0][1], "FN": matrix[1][0], "TP": matrix[1][1]})
    comparison = pd.DataFrame(rows)
    comparison.to_csv(output_dir / "comparison.csv", index=False)
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "environment": {"python": platform.python_version(), "numpy": np.__version__,
                              "pandas": pd.__version__, "scikit_learn": sklearn.__version__},
              "data_manifest": "docs/mysql_datasets_manifest.json",
              "protocol": "Each ten-row dataset uses the same first seven normal training samples and last three chronological held-out prediction samples, deterministic algorithms and train-only normalization. Incidents in the abnormal files are test rows eight and nine; row ten is normal. Labels/scenarios are evaluation context only.",
              "limitations": "Only seven train and three test rows per synthetic file: verifies functionality, not detection quality or model rankings on real MySQL workloads. No positive labels in the normal dataset: recall/F1 there are zero by convention.",
              "datasets": datasets, "comparison": comparison.to_dict(orient="records")}
    (output_dir / "evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return comparison


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT / "reports" / "mysql_demo")
    parser.add_argument("--data-dir", type=Path, default=PROJECT / "data")
    args = parser.parse_args()
    print(evaluate(args.output_dir, args.data_dir).to_string(index=False))
