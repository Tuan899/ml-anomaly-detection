"""HTTP boundary for the persistent monitoring workspace.

The frontend never fits estimators, fabricates samples or substitutes cached
health for a failed backend request.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

import httpx

from frontend.api_client import BackendError, get_backend_url


def monitor_request(method: str, path: str, *, payload: dict | None = None,
                    params: dict | None = None) -> dict:
    base = get_backend_url()
    try:
        address = urlsplit(base)
        if (address.scheme not in {"http", "https"} or not address.hostname
                or address.username or address.password or address.query or address.fragment
                or address.port == 0):
            raise ValueError
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError
        if payload is not None:
            # Reject NaN/Infinity before httpx or the server can reinterpret it.
            json.dumps(payload, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise BackendError("Địa chỉ dịch vụ hoặc dữ liệu gửi đi chưa hợp lệ.") from exc
    seconds = 120 if path == "/train" else 35 if path == "/assistant/chat" else 12
    timeout = httpx.Timeout(seconds, connect=3)
    try:
        response = httpx.request(
            method.upper(), base.rstrip("/") + "/monitor" + path,
            params={key: value for key, value in (params or {}).items() if value is not None},
            json=payload, timeout=timeout, trust_env=False,
        )
    except httpx.TimeoutException as exc:
        raise BackendError("Dịch vụ giám sát chưa phản hồi kịp. Chưa thể xác nhận trạng thái hiện tại.") from exc
    except httpx.RequestError as exc:
        raise BackendError("Mất kết nối Backend. Kiểm tra dịch vụ trước khi tiếp tục giám sát.") from exc
    except httpx.InvalidURL as exc:
        raise BackendError("Địa chỉ dịch vụ giám sát chưa hợp lệ.") from exc
    if response.status_code == 404:
        raise BackendError("Backend chưa hỗ trợ chức năng giám sát này. Khởi động Backend từ phiên bản dự án hiện tại.")
    if not 200 <= response.status_code < 300:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        if isinstance(detail, str) and len(detail) <= 600:
            raise BackendError(detail)
        raise BackendError(f"Yêu cầu giám sát không thực hiện được (HTTP {response.status_code}). Kiểm tra dữ liệu và cấu hình.")
    try:
        result = response.json()
    except ValueError as exc:
        raise BackendError("Backend trả về dữ liệu giám sát không hợp lệ.") from exc
    if not isinstance(result, dict):
        raise BackendError("Backend trả về cấu trúc giám sát không hợp lệ.")
    return result


def monitor_get(path: str, **params) -> dict:
    return monitor_request("GET", path, params=params)


def monitor_post(path: str, payload: dict | None = None) -> dict:
    return monitor_request("POST", path, payload=payload or {})
