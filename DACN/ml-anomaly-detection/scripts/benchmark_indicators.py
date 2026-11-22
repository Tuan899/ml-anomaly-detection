"""Measure DBMS evidence generation without fitting models or changing data."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from src.dbms_monitoring import MYSQL_METRICS, _add_indicators, _fit_baselines


def benchmark(rows=20000, repeats=5):
    step = np.arange(rows)
    reference = pd.DataFrame({metric: 50.0 + np.sin(step / 10) for metric in MYSQL_METRICS})
    observed = reference.copy()
    observed.loc[step % 20 == 0, list(MYSQL_METRICS)] += 100
    baselines = _fit_baselines(reference.iloc[:1000], 3.5)
    timings = []
    for _ in range(repeats):
        frame = observed.copy()
        start = perf_counter()
        flags = _add_indicators(frame, baselines, 3.5)
        timings.append(perf_counter() - start)
    return {
        "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
        "rows": rows, "repeats": repeats, "material_rows": int(flags.sum()),
        "median_seconds": median(timings), "measurements_seconds": timings,
        "output_sha256": hashlib.sha256(frame.to_json(orient="split", double_precision=15).encode()).hexdigest(),
        "scope": "Evidence generation only; excludes model fitting, HTTP and browser rendering.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=20000)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.rows < 1000 or args.repeats < 1:
        parser.error("Use at least 1000 rows and one repetition")
    payload = json.dumps(benchmark(args.rows, args.repeats), indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload)
