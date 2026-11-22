"""Compare inline/worker result preparation; excludes fitting and HTTP encoding.

Run from the project directory:
    python reports/benchmark_api_serialization.py

The synthetic frame is constructed once. No source data or model output is
changed. Worker scheduling improves availability, not model computation speed;
Python's GIL can still delay the event loop during JSON conversion.
"""

import asyncio
import gc
import json
from pathlib import Path
from statistics import median
import sys
import time

import numpy as np
import pandas as pd
from starlette.concurrency import run_in_threadpool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import _result_payload
from src.contracts import DetectionRun


def synthetic_run(rows=100_000):
    metrics = ["queries_per_second", "connections", "response_time_ms", "slow_queries", "connection_errors"]
    frame = pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=rows, freq="s")})
    for index, metric in enumerate(metrics):
        frame[metric] = index + np.arange(rows) % 10
    split = int(rows * .7)
    predictions = frame.iloc[split:].copy()
    names = ["mad", "isolation_forest", "lof", "one_class_svm"]
    for name in names:
        predictions[f"{name}_prediction"] = 1
        predictions[f"{name}_score"] = 0.5
    metadata = {"timestamp_col": "timestamp", "value_col": metrics[0], "label_col": None,
                "metric_cols": metrics, "model_names": names, "rows": rows,
                "train_rows": split, "test_rows": rows - split}
    return DetectionRun(frame, predictions, {}, metadata)


async def measure(run, worker):
    active, intervals = True, []

    async def heartbeat():
        previous = time.perf_counter()
        while active:
            await asyncio.sleep(.002)
            current = time.perf_counter()
            intervals.append(max(0., current - previous - .002))
            previous = current

    monitor = asyncio.create_task(heartbeat())
    await asyncio.sleep(.005)
    started = time.perf_counter()
    if worker:
        payload = await run_in_threadpool(_result_payload, run, True)
    else:
        payload = _result_payload(run, True)
    elapsed = time.perf_counter() - started
    active = False
    await monitor
    assert len(payload["context"]) == len(run.frame)
    return {"preparation_ms": elapsed * 1000, "maximum_loop_delay_ms": max(intervals) * 1000}


async def main():
    run = synthetic_run()
    measurements = {"before_inline": [], "after_worker": []}
    for _ in range(3):
        for name, worker in (("before_inline", False), ("after_worker", True)):
            gc.collect()
            measurements[name].append(await measure(run, worker))
    result = {"rows": len(run.frame), "test_rows": len(run.predictions), "repeats": 3,
              "scope": "result.summary and context preparation only; excludes fitting and final HTTP encoding",
              "median": {name: {key: round(median(item[key] for item in values), 2)
                                 for key in values[0]} for name, values in measurements.items()},
              "measurements": measurements}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
