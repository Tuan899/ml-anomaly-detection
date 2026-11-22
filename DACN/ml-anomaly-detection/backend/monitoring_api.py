"""Persistent monitoring API, alongside the existing offline research API."""
from __future__ import annotations

import os
from pathlib import Path
from threading import RLock
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.monitoring_controller import MonitoringController

router = APIRouter(prefix="/monitor", tags=["monitoring"])


_controllers: dict[str, MonitoringController] = {}
_controllers_lock = RLock()


def _controller_for_path(path: str) -> MonitoringController:
    with _controllers_lock:
        if path not in _controllers:
            _controllers[path] = MonitoringController(path)
        return _controllers[path]


def get_controller() -> MonitoringController:
    default = Path(__file__).resolve().parents[1] / ".runtime" / "monitoring.sqlite3"
    path = Path(os.environ.get("ANOMALY_MONITOR_DB", str(default))).resolve()
    return _controller_for_path(str(path))


def shutdown_monitoring():
    # get_controller is lazy: a legacy-only deployment need not create a DB.
    with _controllers_lock:
        for controller in _controllers.values():
            controller.close()
        _controllers.clear()


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrainRequest(Payload):
    source: str = Field("K1", min_length=1, max_length=100)
    records: list[dict[str, Any]] | None = Field(None, min_length=30, max_length=10000)
    start_index: int = Field(0, ge=0, strict=True)
    end_index: int | None = Field(None, ge=1, strict=True)
    contamination: float = Field(.01, gt=0, le=.5, allow_inf_nan=False, strict=True)
    deviation_threshold: float = Field(3.5, ge=1, le=10, allow_inf_nan=False, strict=True)


class SampleRequest(Payload):
    records: list[dict[str, Any]] = Field(min_length=1, max_length=1000)
    source: str = Field("live", min_length=1, max_length=100)
    session_id: str | None = Field(None, max_length=100)

    @field_validator("source")
    @classmethod
    def valid_source(cls, value):
        if not value.strip():
            raise ValueError("source cannot be blank")
        return value.strip()


class ReplayRequest(Payload):
    scenario: Literal["K1", "K2", "K3", "K4"] = "K1"
    interval_seconds: float = Field(1, ge=.1, le=60, allow_inf_nan=False, strict=True)
    rows: int = Field(180, ge=30, le=3600, strict=True)
    loop: bool = Field(False, strict=True)


class LiveRequest(Payload):
    interval_seconds: float = Field(1, ge=.1, le=60, allow_inf_nan=False, strict=True)
    stale_after_seconds: float | None = Field(None, ge=1, le=600, allow_inf_nan=False, strict=True)
    session_id: str | None = Field(None, min_length=1, max_length=100)
    target_id: str | None = Field(None, pattern=r"^[0-9a-f]{64}$", strict=True)


class StopLiveRequest(Payload):
    session_id: str = Field(min_length=1, max_length=100)


class InjectionRequest(Payload):
    scenario: Literal["K2", "K3", "K4"]
    duration_samples: int = Field(15, ge=1, le=120, strict=True)


class FeedbackRequest(Payload):
    verdict: Literal["true_incident", "false_alarm", "unreviewed"]
    note: str = Field("", max_length=2000)


class LiveFaultRequest(Payload):
    scenario: Literal["K2", "K3", "K4"]
    duration_seconds: int = Field(15, ge=1, le=60, strict=True)
    rate_per_second: int = Field(100, ge=1, le=500, strict=True)
    connections: int = Field(10, ge=1, le=20, strict=True)
    auth_failures: int = Field(0, ge=0, le=3, strict=True)


def _call(action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except KeyError:
        raise HTTPException(404, "Không tìm thấy bản ghi cần cập nhật.") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None


@router.get("/health")
def health(controller: MonitoringController = Depends(get_controller)):
    return _call(controller.health)


@router.get("/scenarios")
def scenarios():
    from src.demo_scenarios import scenario_catalog
    return {"scenarios": scenario_catalog()}


@router.get("/catalog")
def catalog(controller: MonitoringController = Depends(get_controller)):
    """Discover every stored baseline/source without truncating to recent points."""
    return _call(controller.engine.catalog)


@router.post("/train")
def train(request: TrainRequest, controller: MonitoringController = Depends(get_controller)):
    from src.demo_scenarios import baseline_records
    if request.records is None and request.source != "K1":
        raise HTTPException(422, "Học nền có sẵn chỉ dùng K1 bình thường; với nguồn khác hãy gửi khoảng dữ liệu nền riêng.")
    records = request.records if request.records is not None else baseline_records()
    baseline = _call(controller.train, records, source=request.source,
                     start_index=request.start_index, end_index=request.end_index,
                     contamination=request.contamination, deviation_threshold=request.deviation_threshold)
    return {"baseline": baseline}


@router.post("/samples")
def samples(request: SampleRequest, controller: MonitoringController = Depends(get_controller)):
    return {"samples": _call(controller.ingest_external, request.records,
                             source=request.source, session_id=request.session_id)}


@router.get("/history")
def history(limit: int = Query(300, ge=1, le=10000), after_id: int = Query(0, ge=0),
            source: str | None = Query(None, max_length=100), baseline_id: int | None = None,
            controller: MonitoringController = Depends(get_controller)):
    return {"samples": _call(controller.engine.history, limit=limit, after_id=after_id,
                             source=source, baseline_id=baseline_id)}


@router.get("/alerts")
def alerts(limit: int = Query(100, ge=1, le=10000), source: str | None = Query(None, max_length=100),
           baseline_id: int | None = None, controller: MonitoringController = Depends(get_controller)):
    return {"alerts": _call(controller.engine.alerts, limit=limit, source=source, baseline_id=baseline_id)}


@router.post("/alerts/{sample_id}/feedback")
def feedback(sample_id: int, request: FeedbackRequest, controller: MonitoringController = Depends(get_controller)):
    return {"alert": _call(controller.engine.feedback, sample_id, request.verdict, request.note)}


@router.get("/evaluation")
def evaluation(source: str | None = Query(None, max_length=100), baseline_id: int | None = None,
               controller: MonitoringController = Depends(get_controller)):
    return _call(controller.engine.evaluation, source=source, baseline_id=baseline_id)


@router.get("/evidence")
def evidence(source: str | None = Query(None, max_length=100), baseline_id: int | None = None,
             controller: MonitoringController = Depends(get_controller)):
    return _call(controller.engine.evidence, source=source, baseline_id=baseline_id)


@router.post("/source/live")
def source_live(request: LiveRequest, controller: MonitoringController = Depends(get_controller)):
    return {"collector": _call(controller.start_live, interval_seconds=request.interval_seconds,
                               stale_after_seconds=request.stale_after_seconds, session_id=request.session_id,
                               target_id=request.target_id)}


@router.post("/source/stop")
def source_stop(request: StopLiveRequest, controller: MonitoringController = Depends(get_controller)):
    return {"collector": _call(controller.stop_live, request.session_id)}


@router.post("/replay/start")
def replay_start(request: ReplayRequest, controller: MonitoringController = Depends(get_controller)):
    return {"collector": _call(controller.start_replay, **request.model_dump())}


@router.post("/replay/stop")
def replay_stop(controller: MonitoringController = Depends(get_controller)):
    return {"collector": _call(controller.stop)}


@router.post("/inject")
def inject(request: InjectionRequest, controller: MonitoringController = Depends(get_controller)):
    return _call(controller.inject, **request.model_dump())


@router.post("/demo/alert")
def alert_demo(controller: MonitoringController = Depends(get_controller)):
    return _call(controller.start_alert_demo)


@router.get("/faults/live")
def live_fault_status(controller: MonitoringController = Depends(get_controller)):
    return _call(controller.fault_status)


@router.post("/faults/live")
def live_fault_start(request: LiveFaultRequest, controller: MonitoringController = Depends(get_controller)):
    return _call(controller.start_live_fault, **request.model_dump())


@router.post("/faults/live/stop")
def live_fault_stop(controller: MonitoringController = Depends(get_controller)):
    return _call(controller.stop_live_fault)
