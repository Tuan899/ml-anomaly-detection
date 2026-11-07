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


def evaluate(output_dir: Path) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows, datasets = [], {}
    for name in ("mysql_normal.csv", "mysql_anomalous.csv"):
        source = PROJECT / "data" / name
        run = run_dbms_detection(source, label_col="label")
        run.predictions.to_csv(output_dir / f"{source.stem}_predictions.csv", index=False)
        datasets[name] = {"sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                          "metadata": run.metadata, "metrics": run.metrics}
        for scope, metrics, matrices, counts in (
            ("raw_model", run.metadata["raw_metrics"], run.metadata["raw_confusion_matrices"], run.metadata["raw_anomaly_counts"]),
            ("operational_alert", run.metrics, run.metadata["confusion_matrices"], run.metadata["anomaly_counts"]),
        ):
            for model, values in metrics.items():
                matrix = matrices[model]
                rows.append({"dataset": name, "scope": scope, "algorithm": model,
                             "test_rows": len(run.predictions), "alerts": counts[model], **values,
                             "TN": matrix[0][0], "FP": matrix[0][1], "FN": matrix[1][0], "TP": matrix[1][1]})
    comparison = pd.DataFrame(rows)
    comparison.to_csv(output_dir / "comparison.csv", index=False)
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "environment": {"python": platform.python_version(), "numpy": np.__version__,
                              "pandas": pd.__version__, "scikit_learn": sklearn.__version__},
              "limitations": "Computed on deliberately synthetic fixtures; does not establish effectiveness on real MySQL workloads. No positive labels in the normal dataset: recall/F1 there are zero by convention.",
              "datasets": datasets, "comparison": comparison.to_dict(orient="records")}
    (output_dir / "evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return comparison


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT / "reports" / "mysql_demo")
    args = parser.parse_args()
    print(evaluate(args.output_dir).to_string(index=False))
