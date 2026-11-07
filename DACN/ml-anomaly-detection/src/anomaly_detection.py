"""Reusable NAB CPU anomaly-detection workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .data_prep import add_nab_labels, load_timeseries
from .pipeline import DetectionRun, run_detection


def _run_nab_detection(source: str | Path, split_index: int | None, contamination: float | None) -> DetectionRun:
    frame = add_nab_labels(load_timeseries(source, value_col="value"))
    return run_detection(
        frame,
        label_col="is_anomaly",
        split_index=split_index,
        contamination=0.01 if contamination is None else contamination,
    )


def run_nab_analysis(
    source: str | Path,
    split_index: int | None = None,
    contamination: float | None = None,
) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    """Evaluate four models on the held-out portion of the NAB CPU CSV.

    The default split uses the first 70% for training and works with the bundled
    short sample. Every estimator, including MAD, fits training observations
    only. Fixed NAB CPU point annotations are never used for fitting; a sample
    without annotated events cannot establish recall or detection quality.
    """
    result = _run_nab_detection(source, split_index, contamination)
    return result.frame, result.metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Phan tich bat thuong CSV NAB CPU theo thu tu thoi gian.")
    parser.add_argument("source", nargs="?", type=Path,
                        default=Path(__file__).parents[1] / "data" / "cpu_0.csv")
    parser.add_argument("--split-index", type=int, help="So dong huan luyen; mac dinh 70%% du lieu.")
    parser.add_argument("--contamination", type=float, default=0.01)
    args = parser.parse_args()
    try:
        result = _run_nab_detection(args.source, args.split_index, args.contamination)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        parser.error(str(exc))
    print(json.dumps({"source": str(args.source), "metadata": result.metadata,
                      "metrics": result.metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
