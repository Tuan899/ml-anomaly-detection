"""CSV and DBMS metric detection, preserving the notebook research protocol."""

from __future__ import annotations

from contextlib import asynccontextmanager
from io import BytesIO
import json
from typing import Literal

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from starlette.concurrency import run_in_threadpool

from src.models import MODEL_NAMES
from src.notebook_reference import run_notebook_reference
from src.pipeline import run_detection
from src.dbms_monitoring import run_dbms_detection
from src.dbms_comparison import compare_dbms_datasets
from backend.monitoring_api import router as monitoring_router, shutdown_monitoring
from backend.admin_api import router as admin_router, shutdown_admin

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

@asynccontextmanager
async def lifespan(application: FastAPI):
    try:
        yield
    finally:
        shutdown_admin()
        shutdown_monitoring()


app = FastAPI(title="ANOMALY LAB · DBMS Monitoring API", version="4.0.0", lifespan=lifespan)
app.include_router(monitoring_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _result_payload(result, include_context: bool) -> dict:
    """Serialize observations in the analysis worker, preserving the HTTP contract."""
    summary = result.summary(date_unit="ns" if include_context else "ms")
    summary["rows"] = len(result.frame)
    summary["models"] = summary["anomalies"]
    if include_context:
        columns = [result.metadata["timestamp_col"], result.metadata["value_col"]]
        columns = list(dict.fromkeys(columns + result.metadata.get("metric_cols", [])))
        if result.metadata["label_col"]:
            columns.append(result.metadata["label_col"])
        summary["context"] = json.loads(result.frame[columns].to_json(
            orient="records", date_format="iso", date_unit="ns", double_precision=15,
        ))
    return summary


@app.post("/detect")
async def detect(
    file: UploadFile = File(...),
    timestamp_col: str = "timestamp",
    value_col: str | None = None,
    label_col: str | None = None,
    contamination: float = Query(0.01, gt=0, le=0.5),
    train_fraction: float = Query(0.7, gt=0, lt=1),
    models: str = ",".join(MODEL_NAMES),
    include_time: bool = False,
    split_index: int | None = Query(None, ge=3),
    include_context: bool = False,
    analysis_mode: Literal["chronological", "notebook_reference", "dbms"] = "chronological",
    noise_guard: bool = True,
    deviation_threshold: float = Query(3.5, ge=1.0, le=10.0),
) -> dict:
    """Analyze held-out CSV observations; labels are used only when selected.

    Model names are comma-separated query parameters. Labels must use 1 for
    normal observations and -1 for anomalies. Set include_context to return the
    cleaned full timeline for visualization; predictions still cover test rows
    only. The dbms profile uses five MySQL activity metrics; the dashboard can
    collect them with a read-only MySQL account or upload an offline CSV.
    The notebook_reference profile
    requires the canonical 4032-row NAB EC2 series and overrides model names,
    labels, split, contamination and calendar features with the fixed notebook
    protocol. Its full-series descriptive MAD baseline is returned separately
    in metadata.reference_baseline; main predictions still contain 482 test rows.
    """
    if value_col is None:
        value_col = "queries_per_second" if analysis_mode == "dbms" else "value"
    selected = list(dict.fromkeys(name.strip() for name in models.split(",") if name.strip()))
    if analysis_mode != "notebook_reference" and (not selected or any(name not in MODEL_NAMES for name in selected)):
        raise HTTPException(status_code=422, detail=f"models must contain: {', '.join(MODEL_NAMES)}")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV upload exceeds 10 MiB")
    if not content:
        raise HTTPException(status_code=422, detail="CSV upload is empty")

    def analyze() -> dict:
        # Fitting and DataFrame serialization both belong outside the event loop.
        if analysis_mode == "notebook_reference":
            result = run_notebook_reference(
                BytesIO(content),
                timestamp_col=timestamp_col, value_col=value_col,
            )
        elif analysis_mode == "dbms":
            result = run_dbms_detection(
                BytesIO(content),
                timestamp_col=timestamp_col, value_col=value_col, label_col=label_col or None,
                train_fraction=train_fraction, contamination=contamination,
                model_names=selected, include_time=include_time, split_index=split_index,
                noise_guard=noise_guard, deviation_threshold=deviation_threshold,
            )
        else:
            result = run_detection(
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
        return _result_payload(result, include_context)

    try:
        return await run_in_threadpool(analyze)
    except (ValueError, TypeError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/compare")
async def compare(
    normal_file: UploadFile = File(...),
    anomalous_file: UploadFile = File(...),
    timestamp_col: str = "timestamp",
    value_col: str = "queries_per_second",
    label_col: str | None = None,
    contamination: float = Query(0.01, gt=0, le=0.5),
    train_fraction: float = Query(0.7, gt=0, lt=1),
    models: str = ",".join(MODEL_NAMES),
    include_time: bool = False,
    split_index: int | None = Query(None, ge=3),
    include_context: bool = True,
    noise_guard: bool = True,
    deviation_threshold: float = Query(3.5, ge=1.0, le=10.0),
) -> dict:
    """Compare two CSVs with one fit on the normal chronological prefix.

    Each upload is limited to 10 MiB. Both result objects use the existing DBMS
    result contract; metadata.comparison discloses the shared fit and the local
    excluded prefix. Labels are opt-in and never used to fit estimators.
    """
    selected = [name.strip() for name in models.split(",") if name.strip()]
    if not selected or len(set(selected)) != len(selected) or any(name not in MODEL_NAMES for name in selected):
        raise HTTPException(status_code=422, detail=f"models must contain unique names from: {', '.join(MODEL_NAMES)}")
    contents = {}
    for role, file in (("normal", normal_file), ("anomalous", anomalous_file)):
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"{role} CSV upload exceeds 10 MiB")
        if not content:
            raise HTTPException(status_code=422, detail=f"{role} CSV upload is empty")
        contents[role] = content

    def analyze() -> dict:
        runs = compare_dbms_datasets(
            BytesIO(contents["normal"]), BytesIO(contents["anomalous"]),
            timestamp_col=timestamp_col, value_col=value_col, label_col=label_col or None,
            train_fraction=train_fraction, contamination=contamination, model_names=selected,
            include_time=include_time, split_index=split_index, noise_guard=noise_guard,
            deviation_threshold=deviation_threshold,
        )
        return {role: _result_payload(result, include_context) for role, result in runs.items()}

    try:
        return await run_in_threadpool(analyze)
    except (ValueError, TypeError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
