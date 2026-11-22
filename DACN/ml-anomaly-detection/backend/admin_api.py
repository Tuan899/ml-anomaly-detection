"""Read-only assistant and explicit email configuration/test endpoints."""
from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from backend.monitoring_api import get_controller
from src.admin_assistant import AdminAssistant, DEFAULT_MODEL
from src.monitoring_controller import MonitoringController


class _PrivateValidationRoute(APIRoute):
    """FastAPI's default validation payload includes rejected input values."""
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private_handler(request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                # Include locations/types for correction, never secret inputs or
                # Pydantic exception contexts containing original values.
                detail = [{"loc": list(item["loc"]), "type": item["type"],
                           "msg": "Giá trị không hợp lệ."} for item in exc.errors()]
                return JSONResponse(status_code=422, content={"detail": detail})
        return private_handler


router = APIRouter(prefix="/monitor/assistant", tags=["assistant"], route_class=_PrivateValidationRoute)
_services: dict[str, AdminAssistant] = {}
_services_lock = RLock()


def _assistant(controller: MonitoringController) -> AdminAssistant:
    path = str(Path(controller.db_path).resolve())
    with _services_lock:
        if path not in _services:
            _services[path] = AdminAssistant(path)
        return _services[path]


def shutdown_admin() -> None:
    with _services_lock:
        for service in _services.values():
            service.close()
        _services.clear()


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class ChatRequest(_Payload):
    question: str = Field(min_length=1, max_length=2000, strict=True)
    conversation_id: str | None = Field(None, pattern=r"^[0-9a-f]{32}$", strict=True)
    alert_id: int | None = Field(None, ge=1, le=9223372036854775807, strict=True)

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value):
        if not value.strip():
            raise ValueError("Câu hỏi không được để trống.")
        return value


class AIConfigRequest(_Payload):
    enabled: bool = Field(strict=True)
    api_key: SecretStr | None = Field(None, max_length=4096)
    model: str = Field(DEFAULT_MODEL, min_length=1, max_length=100,
                       pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$", strict=True)


class EmailConfigRequest(_Payload):
    enabled: bool = Field(strict=True)
    host: str = Field("", max_length=253, strict=True)
    port: int = Field(587, ge=1, le=65535, strict=True)
    security: Literal["starttls", "ssl"] = "starttls"
    username: str = Field("", max_length=320, strict=True)
    password: SecretStr | None = Field(None, max_length=4096)
    sender: str = Field("", max_length=320, strict=True)
    recipients: list[str] = Field(default_factory=list, max_length=20)
    cooldown_seconds: int = Field(300, ge=60, le=3600, strict=True)


def _call(action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except KeyError:
        raise HTTPException(404, "Không tìm thấy bản ghi được chọn.") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None


@router.get("/status")
def status(controller: MonitoringController = Depends(get_controller)):
    return {"ai": _call(_assistant(controller).status), "email": _call(controller.notifier.status)}


@router.get("/briefing")
def briefing(controller: MonitoringController = Depends(get_controller)):
    return _call(_assistant(controller).briefing, controller)


@router.get("/history")
def history(conversation_id: str = Query(..., pattern=r"^[0-9a-f]{32}$"),
            controller: MonitoringController = Depends(get_controller)):
    return _call(_assistant(controller).history, conversation_id)


@router.post("/chat")
def chat(request: ChatRequest, controller: MonitoringController = Depends(get_controller)):
    return _call(_assistant(controller).chat, controller, **request.model_dump())


@router.post("/config/ai")
def config_ai(request: AIConfigRequest, controller: MonitoringController = Depends(get_controller)):
    return _call(_assistant(controller).configure, enabled=request.enabled,
                 api_key=request.api_key.get_secret_value() if request.api_key is not None else None,
                 model=request.model)


@router.post("/config/email")
def config_email(request: EmailConfigRequest, controller: MonitoringController = Depends(get_controller)):
    values = request.model_dump(exclude={"password"})
    values["password"] = request.password.get_secret_value() if request.password is not None else None
    return _call(controller.notifier.configure, **values)


@router.get("/email/preview")
def email_preview(alert_id: int = Query(..., ge=1, le=9223372036854775807),
                  controller: MonitoringController = Depends(get_controller)):
    sample = _call(controller.engine.get_sample, alert_id)
    return _call(controller.notifier.preview, sample)


@router.post("/email/test")
def email_test(controller: MonitoringController = Depends(get_controller)):
    return _call(controller.notifier.test_email)
