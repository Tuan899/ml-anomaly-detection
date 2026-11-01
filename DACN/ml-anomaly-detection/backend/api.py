"""CSV-only anomaly detection API backed by the shared research pipeline."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from starlette.concurrency import run_in_threadpool

from src.models import MODEL_NAMES
from src.pipeline import run_detection

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

app = FastAPI(title="ML Anomaly Detection API", version="2.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/detect")
async def detect(
    file: UploadFile = File(...),
    timestamp_col: str = "timestamp",
    value_col: str = "value",
    label_col: str | None = None,
    contamination: float = Query(0.01, gt=0, le=0.5),
    train_fraction: float = Query(0.7, gt=0, lt=1),
    models: str = ",".join(MODEL_NAMES),
    include_time: bool = False,
    split_index: int | None = Query(None, ge=3),
) -> dict:
    """Analyze held-out CSV observations; labels are used only when selected.

    Model names are comma-separated query parameters. Labels must use 1 for
    normal observations and -1 for anomalies. There is no live DBMS connection.
    """
    selected = list(dict.fromkeys(name.strip() for name in models.split(",") if name.strip()))
    if not selected or any(name not in MODEL_NAMES for name in selected):
        raise HTTPException(status_code=422, detail=f"models must contain: {', '.join(MODEL_NAMES)}")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV upload exceeds 10 MiB")
    if not content:
        raise HTTPException(status_code=422, detail="CSV upload is empty")
    try:
        # Model fitting is CPU-bound and must not block the ASGI event loop.
        result = await run_in_threadpool(
            run_detection,
            BytesIO(content),
            timestamp_col=timestamp_col,
            value_col=value_col,
            label_col=label_col or None,
            train_fraction=train_fraction,
            contamination=contamination,
            model_names=selected,
            include_time=include_time,
            split_index=split_index,
        )
        summary = result.summary()
        # Preserve the original response fields for existing API clients.
        summary["rows"] = len(result.frame)
        summary["models"] = summary["anomalies"]
        return summary
    except (ValueError, TypeError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
