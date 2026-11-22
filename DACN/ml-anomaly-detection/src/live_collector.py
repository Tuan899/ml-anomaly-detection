"""Long-running, read-only interval collector with reset-aware rebasing.

Credentials stay in this process. Only the timestamp and five measurements are
sent to the analysis service. Missing values and a reset interval are never
turned into zero-valued observations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import ssl
from threading import Event
from typing import Callable
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from . import mysql_collector as protocol


@dataclass(frozen=True)
class CollectorConfig:
    host: str
    user: str
    password: str = field(repr=False)
    port: int = 3306
    database: str | None = None
    interval_seconds: float = 1.0
    connect_timeout: int = 5
    ssl_ca: str | None = None
    ssl_disabled: bool = False
    retry_seconds: float = 2.0

    def validate(self):
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("Cần cấu hình địa chỉ máy chủ CSDL.")
        if not isinstance(self.user, str) or not self.user.strip():
            raise ValueError("Cần cấu hình tài khoản giám sát.")
        if not isinstance(self.password, str):
            raise ValueError("Mật khẩu phải là chuỗi ký tự.")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("Cổng phải nằm trong khoảng 1 đến 65535.")
        for value, low, high, name in ((self.interval_seconds, .1, 60, "Chu kỳ"),
                                       (self.connect_timeout, 1, 60, "Thời gian chờ"),
                                       (self.retry_seconds, .1, 60, "Thời gian thử lại")):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} không hợp lệ.")
        if type(self.ssl_disabled) is not bool:
            raise ValueError("Tùy chọn TLS không hợp lệ.")
        if self.ssl_disabled and self.ssl_ca:
            raise ValueError("Không thể vừa cung cấp CA vừa tắt TLS.")
        if self.ssl_ca is not None and (not isinstance(self.ssl_ca, str) or not self.ssl_ca.strip()):
            raise ValueError("Đường dẫn CA không hợp lệ.")
        if self.database is not None and not isinstance(self.database, str):
            raise ValueError("Tên CSDL không hợp lệ.")


def interval_observation(previous: tuple, current: tuple) -> dict | None:
    """Return a measured interval, or None when a counter reset invalidates it."""
    before, before_at, _, _ = previous
    after, after_at, timestamp, latency = current
    elapsed = after_at - before_at
    if not math.isfinite(elapsed) or elapsed <= 0:
        raise ValueError("Khoảng thời gian lấy mẫu không hợp lệ.")
    if any(after[name] < before[name] for name in protocol._CUMULATIVE_COUNTERS):
        return None
    result = {
        "timestamp": timestamp,
        "queries_per_second": (after["Questions"] - before["Questions"]) / elapsed,
        "connections": after["Threads_connected"], "response_time_ms": latency,
        "slow_queries": after["Slow_queries"] - before["Slow_queries"],
        "connection_errors": after["Aborted_connects"] - before["Aborted_connects"],
    }
    if any(not math.isfinite(value) or value < 0 for key, value in result.items() if key != "timestamp"):
        raise ValueError("Chỉ số lấy mẫu không hợp lệ.")
    return result


class LiveCollector:
    def __init__(self, config: CollectorConfig, *, stop_event: Event | None = None,
                 status_callback: Callable[[str], None] | None = None,
                 wait: Callable[[float], bool] | None = None):
        config.validate()
        self.config = config
        self.stop_event = stop_event or Event()
        self.status_callback = status_callback or (lambda status: None)
        self._wait = wait or self.stop_event.wait

    def _connect(self):
        driver = protocol.pymysql
        if driver is None or tuple(getattr(driver, "VERSION", (0, 0, 0))[:3]) < (1, 2, 3):
            raise ValueError("Cần PyMySQL phiên bản 1.2.3 trở lên để thu trực tiếp với TLS được xác minh.")
        config = self.config
        options = dict(host=config.host.strip(), port=config.port, user=config.user.strip(),
                       password=config.password, database=config.database or None,
                       charset="utf8mb4", autocommit=True, connect_timeout=config.connect_timeout,
                       read_timeout=config.connect_timeout, write_timeout=config.connect_timeout,
                       local_infile=False, ssl_disabled=config.ssl_disabled)
        if not config.ssl_disabled:
            options["ssl"] = ssl.create_default_context(cafile=config.ssl_ca)
        return driver.connect(**options)

    def samples(self, *, max_samples: int | None = None):
        if max_samples is not None and (type(max_samples) is not int or max_samples < 1):
            raise ValueError("Số mẫu phải là số nguyên dương.")
        # Check configuration dependencies before retrying connection failures.
        driver = protocol.pymysql
        if driver is None or tuple(getattr(driver, "VERSION", (0, 0, 0))[:3]) < (1, 2, 3):
            raise ValueError("Cần cài PyMySQL >= 1.2.3.")
        completed = 0
        while not self.stop_event.is_set() and (max_samples is None or completed < max_samples):
            connection = None
            try:
                connection = self._connect()
                with connection.cursor() as cursor:
                    cursor.execute(protocol._READ_ONLY_SESSION_SQL)
                    previous = protocol._status_snapshot(cursor)
                    self.status_callback("connected")
                    while not self.stop_event.is_set() and (max_samples is None or completed < max_samples):
                        if self._wait(self.config.interval_seconds):
                            return
                        current = protocol._status_snapshot(cursor)
                        observation = interval_observation(previous, current)
                        # Rebase after *every* valid snapshot, including reset.
                        # The next interval therefore excludes pre-restart totals.
                        previous = current
                        if observation is None:
                            self.status_callback("counter_reset")
                            continue
                        completed += 1
                        yield observation
            except (ValueError, protocol.MySQLCollectionError):
                self.status_callback("invalid_sample")
                if self._wait(self.config.retry_seconds):
                    return
            except Exception:
                # Never expose raw driver messages, host/user or credentials.
                self.status_callback("connection_error")
                if self._wait(self.config.retry_seconds):
                    return
            finally:
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:
                        pass


def run_collector(config: CollectorConfig, *, backend_url: str = "http://127.0.0.1:8000",
                  max_samples: int | None = None, stop_event: Event | None = None,
                  status_callback: Callable[[str], None] | None = None) -> int:
    """Publish bounded batches, retrying the same event ID after HTTP failures."""
    from .live_faults import database_target_id
    config.validate()
    if max_samples is not None and (type(max_samples) is not int or max_samples < 1):
        raise ValueError("Số mẫu phải là số nguyên dương.")
    address = urlsplit(backend_url)
    if (address.scheme not in ("http", "https") or not address.hostname or
            address.username or address.password or address.query or address.fragment):
        raise ValueError("Địa chỉ dịch vụ phân tích không hợp lệ.")
    root = backend_url.rstrip("/")
    stop = stop_event or Event()
    notify = status_callback or (lambda status: None)
    sampler = LiveCollector(config, stop_event=stop, status_callback=notify)
    session = str(uuid4())
    sent = 0
    with httpx.Client(timeout=httpx.Timeout(5, connect=3), trust_env=False) as client:
        try:
            response = client.post(root + "/monitor/source/live", json={
                "interval_seconds": config.interval_seconds, "session_id": session,
                "target_id": database_target_id(config.host, config.port)})
            response.raise_for_status()
        except httpx.HTTPError:
            raise RuntimeError("Không bật được nguồn trực tiếp. Kiểm tra dịch vụ phân tích và học mức nền trước.") from None
        stream = sampler.samples(max_samples=max_samples)
        try:
            for sample in stream:
                # This ID contains no DB details and remains fixed across retries.
                sample["event_id"] = f"{session}-{sent}"
                delivered = False
                while not stop.is_set():
                    try:
                        response = client.post(root + "/monitor/samples", json={
                            "records": [sample], "source": "live", "session_id": session})
                        response.raise_for_status()
                        delivered = True
                        sent += 1
                        notify("sample_sent")
                        break
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code in (400, 401, 403, 404, 409, 422):
                            raise RuntimeError("Dịch vụ từ chối mẫu. Kiểm tra mức nền và cấu hình nguồn; không gửi thông tin đăng nhập.") from None
                        notify("backend_unavailable")
                    except httpx.RequestError:
                        notify("backend_unavailable")
                    if stop.wait(config.retry_seconds):
                        break
                if not delivered:
                    break
        finally:
            stream.close()
            try:
                client.post(root + "/monitor/source/stop", json={"session_id": session})
            except httpx.HTTPError:
                # Backend liveness will expire even if graceful stop cannot be sent.
                pass
    return sent
