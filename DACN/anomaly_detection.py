"""Synthetic anomaly-detection demo using the shared chronological pipeline.

This generated metric is not the NAB CPU dataset and cannot establish detection
quality on real measurements. Importing this module does not fit or plot models.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from src.pipeline import DetectionRun


# Two training events and two held-out events, including a lower-tail event.
SYNTHETIC_SPIKES = {1000: 2.0, 2500: 1.5, 3100: 1.8, 3600: -1.5}


def make_synthetic_data(seed: int = 42) -> pd.DataFrame:
    """Generate reproducible observations and label exactly the inserted spikes.

    A local generator leaves NumPy's process-wide random state untouched. Values
    are a generic synthetic metric, so the negative spike is intentional.
    """
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2014-02-14 14:30:00", periods=4032, freq="5min"),
        "value": rng.normal(0.1, 0.02, 4032),
        "is_anomaly": np.ones(4032, dtype=int),
    })
    for index, value in SYNTHETIC_SPIKES.items():
        frame.loc[index, ["value", "is_anomaly"]] = [value, -1]
    return frame


def run_demo(seed: int = 42, model_names=None) -> DetectionRun:
    """Fit the first 70% and evaluate only the last 30% of synthetic data.

    All estimators, including two-sided MAD, use the shared train-only pipeline.
    The sibling project is resolved relative to this file, independently of cwd.
    """
    project_root = str(Path(__file__).resolve().parent / "ml-anomaly-detection")
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from src.pipeline import run_detection

    result = run_detection(
        make_synthetic_data(seed),
        label_col="is_anomaly",
        train_fraction=0.7,
        contamination=0.01,
        model_names=model_names,
    )
    result.metadata["data_source"] = "Synthetic generated metric; not NAB CPU data."
    result.metadata["synthetic_seed"] = seed
    result.metadata["warnings"].append(
        "Synthetic demonstration only: these scores do not establish quality on real data."
    )
    return result


def _show_predictions(result: DetectionRun) -> None:
    """Plot held-out predictions only when explicitly requested with --show."""
    import matplotlib.pyplot as plt

    predictions = result.predictions
    names = result.metadata["model_names"]
    figure, axes = plt.subplots(len(names), 1, figsize=(11, 3 * len(names)), squeeze=False)
    for axis, name in zip(axes.flat, names):
        axis.plot(predictions["timestamp"], predictions["value"], color="steelblue", lw=0.8)
        alerts = predictions[predictions[f"{name}_prediction"] == -1]
        truth = predictions[predictions["is_anomaly"] == -1]
        axis.scatter(alerts["timestamp"], alerts["value"], color="orange", s=22, label="Predicted anomaly")
        axis.scatter(truth["timestamp"], truth["value"], color="red", marker="x", s=55, label="Inserted spike")
        axis.set_title(f"{name} — held-out synthetic observations")
        axis.set_xlabel("Time")
        axis.set_ylabel("Synthetic metric")
        axis.legend()
    figure.suptitle("Synthetic demo; scores do not establish real-world quality")
    figure.tight_layout()
    plt.show()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run a synthetic demo with a chronological 70/30 split.")
    parser.add_argument("--show", action="store_true", help="Show held-out prediction plots.")
    parser.add_argument("--seed", type=int, default=42, help="Seed for the local synthetic-data generator.")
    args = parser.parse_args(argv)
    result = run_demo(seed=args.seed)
    print(json.dumps({"metadata": result.metadata, "metrics": result.metrics}, indent=2, ensure_ascii=False))
    if args.show:
        _show_predictions(result)


if __name__ == "__main__":
    main()
