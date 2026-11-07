"""Detection result shared by HTTP clients and the research pipeline.

This module contains no estimators or training code, so the dashboard can use
the result format without importing the machine-learning pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
import json

import pandas as pd


@dataclass
class DetectionRun:
    frame: pd.DataFrame
    predictions: pd.DataFrame
    metrics: dict
    metadata: dict

    def summary(self, date_unit: str = "ms") -> dict:
        records = json.loads(self.predictions.to_json(
            orient="records", date_format="iso", date_unit=date_unit, double_precision=15,
        ))
        anomalies = {
            name: [row for row in records if row[f"{name}_prediction"] == -1]
            for name in self.metadata["model_names"]
        }
        return {"metadata": self.metadata, "metrics": self.metrics,
                "anomalies": anomalies, "predictions": records}

    def export_csv(self) -> bytes:
        return self.predictions.to_csv(index=False).encode("utf-8-sig")
