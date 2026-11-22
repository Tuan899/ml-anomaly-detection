"""Opt-in, bounded workloads against a separately configured test database.

Only fixed SELECT statements and session settings are used. Credentials never
enter the audit database or public status. This runner does not generate metric
observations: the independent collector measures whatever actually happens.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import sqlite3
import ssl
from threading import Event, RLock, Thread
import time
from typing import Callable, Mapping
from uuid import uuid4

try:
    import pymysql
except ImportError:  # Offline analysis must remain usable without the driver.
    pymysql = None


_LIMITS = {
    "duration_seconds": (1, 60), "rate_per_second": (1, 500),
    "connections": (1, 20), "auth_failures": (0, 3),
}
_ACTIVE = frozenset(("running", "stopping"))
_IO_TIMEOUT_SECONDS = 2
_STOP_JOIN_SECONDS = 6.0
_SELECT_SQL = "SELECT 1"
_SLOW_SESSION_SQL = "SET SESSION long_query_time = 0.05"
_SLOW_SQL = "SELECT SLEEP(0.2)"


def _normalized_host(host: str) -> str:
    if not isinstance(host, str) or not host.strip():
        raise ValueError("Địa chỉ máy chủ thử tải không hợp lệ.")
    value = host.strip().lower().rstrip(".")
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    if not value or any(char.isspace() for char in value) or any(char in value for char in "/\\@?#"):
        raise ValueError("Địa chỉ máy chủ thử tải không hợp lệ.")
    try:
        return ipaddress.ip_address(value).compressed
    except ValueError:
        return value


def database_target_id(host: str, port: int) -> str:
    """Stable identity shared with the independent collector, without credentials."""
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Cổng máy chủ thử tải phải là số nguyên từ 1 đến 65535.")
    normalized = _normalized_host(host)
    return hashlib.sha256(f"{normalized}:{port}".encode("utf-8")).hexdigest()


def _is_loopback(host: str) -> bool:
    normalized = _normalized_host(host)
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class FaultConfig:
    enabled: bool = False
    host: str = ""
    port: int = 3306
    user: str = field(default="", repr=False)
    password: str | None = field(default=None, repr=False)
    database: str | None = None
    ssl_ca: str | None = field(default=None, repr=False)
    no_tls: bool = False
    _environment_error: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "FaultConfig":
        """Read only the dedicated fault account; never collector credentials."""
        env = os.environ if environ is None else environ
        port = 3306
        error = None
        try:
            raw_port = env.get("FAULT_MYSQL_PORT", "3306")
            if not isinstance(raw_port, str) or not raw_port.isascii() or not raw_port.isdecimal():
                raise ValueError
            port = int(raw_port)
            if not 1 <= port <= 65535:
                raise ValueError
        except (TypeError, ValueError):
            error = "FAULT_MYSQL_PORT phải là số nguyên từ 1 đến 65535."
        return cls(
            enabled=env.get("ANOMALY_FAULT_ENABLED") == "1",
            host=env.get("FAULT_MYSQL_HOST", ""), port=port,
            user=env.get("FAULT_MYSQL_USER", ""),
            password=env.get("FAULT_MYSQL_PASSWORD"),
            database=env.get("FAULT_MYSQL_DATABASE") or None,
            ssl_ca=env.get("FAULT_MYSQL_SSL_CA") or None,
            no_tls=env.get("FAULT_MYSQL_NO_TLS") == "1",
            _environment_error=error,
        )

    def validate(self) -> None:
        if self._environment_error:
            raise ValueError(self._environment_error)
        if type(self.enabled) is not bool or type(self.no_tls) is not bool:
            raise ValueError("Tùy chọn bật thử tải hoặc TLS không hợp lệ.")
        database_target_id(self.host, self.port)
        if not isinstance(self.user, str) or not self.user.strip() or not isinstance(self.password, str):
            raise ValueError("Cần cấu hình đầy đủ tài khoản thử tải riêng bằng FAULT_MYSQL_HOST/USER/PASSWORD.")
        if self.database is not None and (not isinstance(self.database, str) or not self.database.strip()):
            raise ValueError("Tên CSDL thử tải không hợp lệ.")
        if self.ssl_ca is not None and (not isinstance(self.ssl_ca, str) or not self.ssl_ca.strip()):
            raise ValueError("Đường dẫn CA thử tải không hợp lệ.")
        if self.no_tls and self.ssl_ca:
            raise ValueError("Không thể vừa cung cấp CA vừa tắt TLS cho thử tải.")
        if self.no_tls and not _is_loopback(self.host):
            raise ValueError("Chỉ cho phép FAULT_MYSQL_NO_TLS=1 với máy chủ loopback cục bộ.")

    @property
    def configured(self) -> bool:
        try:
            self.validate()
            return True
        except ValueError:
            return False

    def target(self) -> dict | None:
        if not self.configured:
            return None
        return {"host": _normalized_host(self.host), "port": self.port,
                "database": self.database, "target_id": database_target_id(self.host, self.port)}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class _WorkloadError(RuntimeError):
    """Only trusted, static messages may be placed in this exception."""


def _serialized_transition(method):
    @wraps(method)
    def transition(self, *args, **kwargs):
        with self._transition_lock:
            return method(self, *args, **kwargs)
    return transition


class LiveFaultRunner:
    """One cancellable worker and a credential-free SQLite job audit.

    ``config``, ``clock`` and ``wait`` are optional seams for deterministic
    tests. Normal callers need only the database path. ``wait`` must obey the
    same contract as Event.wait and return true when cancellation was observed.
    """

    def __init__(self, db_path: str | Path, *, config: FaultConfig | None = None,
                 clock: Callable[[], float] | None = None,
                 wait: Callable[[float], bool] | None = None):
        self.config = config if config is not None else FaultConfig.from_env()
        self._clock = clock or time.monotonic
        self._lock = RLock()
        self._transition_lock = RLock()
        self._stop_event = Event()
        self._wait = wait or self._stop_event.wait
        self._thread: Thread | None = None
        self._pending_cleanup: list = []
        self._completion_failure: str | None = None
        self._closed = False
        self._job: dict | None = None
        self._last_persist = self._clock()
        self._db = sqlite3.connect(str(db_path), timeout=5, check_same_thread=False)
        self._db.execute("""CREATE TABLE IF NOT EXISTS live_fault_jobs (
            id TEXT PRIMARY KEY, started_at TEXT NOT NULL, payload TEXT NOT NULL
        )""")
        # A process restart cannot continue a previous worker. Audit every
        # unfinished record before making the last job visible to the UI.
        for job_id, payload in self._db.execute("SELECT id, payload FROM live_fault_jobs").fetchall():
            previous = json.loads(payload)
            if previous.get("status") in _ACTIVE:
                previous.update(status="interrupted", finished_at=_utc_now(),
                                message="Tiến trình đã khởi động lại; lần thử tải trước bị gián đoạn.")
                self._db.execute("UPDATE live_fault_jobs SET payload = ? WHERE id = ?",
                                 (json.dumps(previous, ensure_ascii=False), job_id))
        self._db.commit()
        row = self._db.execute(
            "SELECT payload FROM live_fault_jobs ORDER BY started_at DESC, id DESC LIMIT 1"
        ).fetchone()
        if row:
            self._job = json.loads(row[0])

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Bộ thử tải đã đóng.")

    def _status_locked(self) -> dict:
        configured = self.config.configured
        if not self.config.enabled:
            message = "Chưa bật thử tải thật. Đặt ANOMALY_FAULT_ENABLED=1 trên máy chủ thử nghiệm."
        elif not configured:
            try:
                self.config.validate()
            except ValueError as exc:
                message = str(exc)
        else:
            message = "Đã cấu hình tài khoản thử tải riêng; chỉ chạy trên đích thử nghiệm đã chọn."
        return {"enabled": self.config.enabled, "configured": configured,
                "target": self.config.target(),
                "limits": {key: list(bounds) for key, bounds in _LIMITS.items()},
                "job": json.loads(json.dumps(self._job, ensure_ascii=False)),
                "configuration_message": message}

    def status(self) -> dict:
        with self._lock:
            self._ensure_open()
            return self._status_locked()

    def _persist_locked(self) -> None:
        if self._job is None:
            return
        self._db.execute("INSERT OR REPLACE INTO live_fault_jobs (id, started_at, payload) VALUES (?, ?, ?)",
                         (self._job["id"], self._job["started_at"],
                          json.dumps(self._job, ensure_ascii=False)))
        self._db.commit()
        self._last_persist = self._clock()

    def _bump(self, key: str) -> None:
        with self._lock:
            self._job["counters"][key] += 1
            # At high QPS, audit writes must not dominate the paced workload.
            if self._clock() - self._last_persist >= 0.25:
                self._persist_locked()

    @_serialized_transition
    def start(self, scenario: str, duration_seconds: int = 15,
              rate_per_second: int = 100, connections: int = 10,
              auth_failures: int = 0) -> dict:
        if not isinstance(scenario, str) or scenario not in ("K2", "K3", "K4"):
            raise ValueError("Kịch bản thử tải phải là K2, K3 hoặc K4.")
        options = dict(duration_seconds=duration_seconds, rate_per_second=rate_per_second,
                       connections=connections, auth_failures=auth_failures)
        for name, (low, high) in _LIMITS.items():
            if type(options[name]) is not int or not low <= options[name] <= high:
                raise ValueError(f"{name} phải là số nguyên từ {low} đến {high}.")
        with self._lock:
            self._ensure_open()
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Đang có một lần thử tải chạy hoặc dừng; chờ đóng toàn bộ kết nối.")
            if self._job is not None and self._job["status"] in _ACTIVE:
                raise RuntimeError("Lần thử tải trước chưa hoàn tất việc dừng.")
            if self._pending_cleanup:
                raise RuntimeError("Chưa xác nhận đóng toàn bộ kết nối thử tải trước.")
            if not self.config.enabled:
                raise ValueError("Thử tải thật chưa được bật bằng ANOMALY_FAULT_ENABLED=1.")
            self.config.validate()
            if pymysql is None or tuple(getattr(pymysql, "VERSION", (0, 0, 0))[:3]) < (1, 2, 3):
                raise ValueError("Cần cài PyMySQL phiên bản 1.2.3 trở lên để thử tải với TLS được xác minh.")
            self._stop_event.clear()
            self._completion_failure = None
            self._job = {"id": uuid4().hex, "scenario": scenario, "status": "running",
                         "started_at": _utc_now(), "finished_at": None, **options,
                         "target": self.config.target(),
                         "counters": {"successful_queries": 0, "opened_connections": 0,
                                      "expected_auth_failures": 0, "slow_queries": 0},
                         "message": "Đang chạy tải thật có giới hạn trên CSDL thử nghiệm."}
            self._persist_locked()
            self._thread = Thread(target=self._run, name="anomaly-live-fault", daemon=True)
            try:
                self._thread.start()
            except Exception:
                self._job.update(status="failed", finished_at=_utc_now(),
                                 message="Không khởi tạo được tiến trình thử tải.")
                self._persist_locked()
                raise RuntimeError("Không khởi tạo được tiến trình thử tải.") from None
            return self._status_locked()

    def _connection_options(self, *, invalid_user: bool = False) -> dict:
        options = dict(host=_normalized_host(self.config.host), port=self.config.port,
                       user=("_anomaly_invalid_" + uuid4().hex[:15]) if invalid_user else self.config.user.strip(),
                       password=uuid4().hex if invalid_user else self.config.password,
                       database=self.config.database, charset="utf8mb4", autocommit=True,
                       connect_timeout=_IO_TIMEOUT_SECONDS, read_timeout=_IO_TIMEOUT_SECONDS,
                       write_timeout=_IO_TIMEOUT_SECONDS, local_infile=False,
                       ssl_disabled=self.config.no_tls)
        if not self.config.no_tls:
            options["ssl"] = ssl.create_default_context(cafile=self.config.ssl_ca)
        return options

    def _connect(self):
        connection = pymysql.connect(**self._connection_options())
        try:
            self._bump("opened_connections")
        except Exception:
            self._try_close(connection)
            raise
        return connection

    def _try_close(self, connection) -> bool:
        try:
            connection.close()
            return True
        except Exception:
            with self._lock:
                if not any(connection is item for item in self._pending_cleanup):
                    self._pending_cleanup.append(connection)
            return False

    def _cancelled_or_expired(self, deadline: float) -> bool:
        return self._stop_event.is_set() or self._clock() >= deadline

    def _paced_queries(self, connection, deadline: float, rate: int, *, slow: bool) -> None:
        with connection.cursor() as cursor:
            if slow and not self._cancelled_or_expired(deadline):
                cursor.execute(_SLOW_SESSION_SQL)
            next_due = self._clock()
            while not self._cancelled_or_expired(deadline):
                delay = min(next_due, deadline) - self._clock()
                if delay > 0 and self._wait(delay):
                    return
                if self._cancelled_or_expired(deadline):
                    return
                cursor.execute(_SLOW_SQL if slow else _SELECT_SQL)
                result = cursor.fetchone()
                if result != ((0,) if slow else (1,)):
                    raise _WorkloadError("Truy vấn thử tải không trả về kết quả mong đợi; đã dừng.")
                self._bump("successful_queries")
                if slow:
                    # Completed SLEEP requests, not inferred server metric data.
                    self._bump("slow_queries")
                # Never catch up missed slots with a burst above the target rate.
                next_due = max(next_due + 1.0 / rate, self._clock())

    def _authentication_attempt(self) -> None:
        unexpected_connection = None
        try:
            unexpected_connection = pymysql.connect(**self._connection_options(invalid_user=True))
        except Exception as exc:
            if exc.args and type(exc.args[0]) is int and exc.args[0] in (1045, 1698):
                self._bump("expected_auth_failures")
                return
            raise _WorkloadError("Phép thử xác thực gặp lỗi khác lỗi từ chối tài khoản; đã dừng.") from None
        finally:
            if unexpected_connection is not None:
                self._try_close(unexpected_connection)
        raise _WorkloadError("Máy chủ chấp nhận tài khoản thử lỗi ngẫu nhiên; đã dừng phép thử.")

    def _run(self) -> None:
        held = []
        failed = None
        with self._lock:
            options = dict(self._job)
        deadline = self._clock() + options["duration_seconds"]
        try:
            if options["scenario"] == "K3":
                for _ in range(options["connections"]):
                    if self._cancelled_or_expired(deadline):
                        break
                    held.append(self._connect())
                for _ in range(options["auth_failures"]):
                    if self._cancelled_or_expired(deadline):
                        break
                    self._authentication_attempt()
                remaining = deadline - self._clock()
                if remaining > 0 and not self._stop_event.is_set():
                    self._wait(remaining)
            elif not self._cancelled_or_expired(deadline):
                connection = self._connect()
                held.append(connection)
                self._paced_queries(connection, deadline, options["rate_per_second"],
                                    slow=options["scenario"] == "K4")
        except _WorkloadError as exc:
            failed = str(exc)
        except Exception:
            # Raw driver messages can include credentials and must never escape.
            failed = "Kết nối hoặc truy vấn thử tải thất bại; đã dừng và đóng các kết nối."
        finally:
            for connection in reversed(held):
                self._try_close(connection)
            with self._lock:
                if self._pending_cleanup:
                    failed = "Có lỗi khi đóng kết nối thử tải; cần kiểm tra các phiên trên máy chủ thử nghiệm."
                self._completion_failure = failed
                stopped = self._stop_event.is_set()
                if self._pending_cleanup:
                    self._job.update(status="stopping", finished_at=None,
                                     message="Chưa đóng được toàn bộ kết nối thử tải; cần dừng lại để thử đóng tiếp.")
                else:
                    status = "failed" if failed else "stopped" if stopped else "completed"
                    self._job.update(status=status, finished_at=_utc_now(),
                                     message=failed or ("Đã dừng tải và đóng toàn bộ kết nối thử."
                                                        if stopped else "Đã hoàn tất tải và đóng toàn bộ kết nối thử."))
                self._persist_locked()

    def _retry_cleanup(self) -> None:
        with self._lock:
            pending = list(self._pending_cleanup)
        closed = []
        for connection in pending:
            if self._try_close(connection):
                closed.append(connection)
        with self._lock:
            self._pending_cleanup = [item for item in self._pending_cleanup
                                     if not any(item is done for done in closed)]
            if not self._pending_cleanup:
                self._job.update(status="failed", finished_at=_utc_now(),
                                 message="Đã đóng toàn bộ kết nối; lần thử tải trước gặp lỗi và đã kết thúc.")
            self._persist_locked()

    @_serialized_transition
    def stop(self) -> dict:
        with self._lock:
            self._ensure_open()
            worker = self._thread
            if worker is None or not worker.is_alive():
                if not self._pending_cleanup:
                    return self._status_locked()
                worker = Thread(target=self._retry_cleanup, name="anomaly-fault-cleanup", daemon=True)
                self._thread = worker
                worker.start()
            self._stop_event.set()
            if self._job["status"] == "running":
                self._job.update(status="stopping", message="Đang hủy chờ và đóng các kết nối thử tải.")
                self._persist_locked()
        worker.join(timeout=_STOP_JOIN_SECONDS)
        with self._lock:
            if worker.is_alive():
                raise RuntimeError("Đang chờ thao tác CSDL kết thúc và đóng kết nối; lần thử tải vẫn đang dừng.")
            if self._pending_cleanup:
                raise RuntimeError("Chưa đóng được toàn bộ kết nối thử tải; cần dừng lại để thử đóng tiếp.")
            return self._status_locked()

    @_serialized_transition
    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
        self.stop()
        with self._lock:
            self._closed = True
            self._db.close()
