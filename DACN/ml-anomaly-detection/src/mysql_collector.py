"""Bounded MySQL activity sampling using fixed, non-writing SQL statements.

This does not turn an administrator account into a least-privilege account.
Provision a separate monitor account as described in docs/MYSQL_SETUP.md.
No workload data, SQL texts, credentials, or labels are produced by this module.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import math
from numbers import Real
import ssl
import time

import pandas as pd

try:
    import pymysql
except ImportError:  # CSV/offline analysis must work without a database driver.
    pymysql = None


class MySQLCollectionError(RuntimeError):
    """A user-safe collection error; never contains raw driver error text."""


METRIC_COLUMNS = (
    "timestamp", "queries_per_second", "connections", "response_time_ms",
    "slow_queries", "connection_errors",
)
_REQUIRED_COUNTERS = (
    "Questions", "Threads_connected", "Slow_queries", "Aborted_connects", "Uptime",
)
_CUMULATIVE_COUNTERS = ("Questions", "Slow_queries", "Aborted_connects", "Uptime")
_READ_ONLY_SESSION_SQL = "SET SESSION TRANSACTION READ ONLY"
_STATUS_SQL = "SHOW GLOBAL STATUS"
_PROBE_SQL = "SELECT 1"


def _number_in_range(value: object, low: float, high: float, field: str) -> float:
    if (isinstance(value, bool) or not isinstance(value, Real)
            or not math.isfinite(float(value)) or not low <= value <= high):
        raise MySQLCollectionError(f"{field} phải nằm trong khoảng {low:g} đến {high:g}.")
    return float(value)


def _status_snapshot(cursor) -> tuple[dict[str, int], float, str, float]:
    """Time an actual SELECT 1 round trip, then read current global counters."""
    probe_started = time.perf_counter()
    cursor.execute(_PROBE_SQL)
    probe = cursor.fetchone()
    probe_ms = (time.perf_counter() - probe_started) * 1000
    if probe != (1,) or not math.isfinite(probe_ms) or probe_ms < 0:
        raise MySQLCollectionError("Phép đo SELECT 1 không trả về kết quả hợp lệ; dừng thu thập.")
    cursor.execute(_STATUS_SQL)
    raw = dict(cursor.fetchall())
    sampled_at = time.monotonic()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    missing = [name for name in _REQUIRED_COUNTERS if name not in raw]
    if missing:
        raise MySQLCollectionError(
            "Máy chủ thiếu bộ đếm bắt buộc: " + ", ".join(missing)
            + ". Không thay chỉ số thiếu bằng 0. Kiểm tra phiên bản và quyền SHOW GLOBAL STATUS."
        )
    counters = {}
    for name in _REQUIRED_COUNTERS:
        value = str(raw[name])
        if not value.isascii() or not value.isdecimal():
            raise MySQLCollectionError(f"Bộ đếm {name} không phải số nguyên không âm; dừng thu thập.")
        counters[name] = int(value)
    return counters, sampled_at, timestamp, probe_ms


def collect_mysql_metrics(
    *,
    host: str,
    port: int = 3306,
    user: str,
    password: str,
    database: str | None = None,
    samples: int = 60,
    interval_seconds: float = 1.0,
    connect_timeout: int = 5,
    ssl_ca: str | None = None,
    ssl_disabled: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """Collect ``samples`` real interval observations, without inferred labels.

    ``queries_per_second`` = delta(Questions) / actual monotonic elapsed seconds.
    ``connections`` = Threads_connected, including this monitoring connection.
    ``response_time_ms`` = the client-to-server SELECT 1 round-trip time (a probe,
    not average application query latency). ``slow_queries`` and
    ``connection_errors`` are interval deltas of Slow_queries and Aborted_connects;
    the latter measures failed connection attempts, not every transport error.
    Connection_errors_* are deliberately not added to avoid overlapping totals.

    One initial snapshot is discarded: pre-existing counters are never reported
    as current events. Polling contributes to Questions/Threads_connected.
    Any counter reset, missing field, or interrupted connection fails the entire
    batch rather than returning fabricated values or an ambiguous partial batch.
    The supplied interval is a minimum delay; probe/status costs add to it.
    The callback receives (completed_rows, requested_rows) after each sample.
    """
    if not isinstance(host, str) or not host.strip():
        raise MySQLCollectionError("Cần nhập địa chỉ máy chủ MySQL.")
    if not isinstance(user, str) or not user.strip():
        raise MySQLCollectionError("Cần nhập tên tài khoản giám sát MySQL.")
    if not isinstance(password, str):
        raise MySQLCollectionError("Mật khẩu MySQL phải là chuỗi ký tự.")
    if database is not None and not isinstance(database, str):
        raise MySQLCollectionError("Tên CSDL phải là chuỗi ký tự hoặc để trống.")
    if type(port) is not int or not 1 <= port <= 65535:
        raise MySQLCollectionError("Cổng MySQL phải là số nguyên từ 1 đến 65535.")
    if type(samples) is not int or not 4 <= samples <= 600:
        raise MySQLCollectionError("Số mẫu MySQL phải là số nguyên từ 4 đến 600.")
    interval = _number_in_range(interval_seconds, 0.1, 60, "Chu kỳ lấy mẫu (giây)")
    timeout = _number_in_range(connect_timeout, 1, 60, "Thời gian chờ kết nối (giây)")
    if type(ssl_disabled) is not bool:
        raise MySQLCollectionError("Tùy chọn tắt TLS phải là giá trị đúng/sai.")
    if ssl_ca is not None and (not isinstance(ssl_ca, str) or not ssl_ca.strip()):
        raise MySQLCollectionError("Đường dẫn CA phải là chuỗi không rỗng hoặc để trống.")
    if ssl_disabled and ssl_ca is not None:
        raise MySQLCollectionError("Không thể vừa cung cấp CA vừa tắt TLS.")
    if progress_callback is not None and not callable(progress_callback):
        raise MySQLCollectionError("Hàm cập nhật tiến độ không hợp lệ.")
    if pymysql is None:
        raise MySQLCollectionError("Chưa cài PyMySQL. Chạy pip install -r requirements.txt rồi thử lại.")
    # Older versions can silently downgrade TLS despite an explicit SSLContext.
    if tuple(getattr(pymysql, "VERSION", (0, 0, 0))[:3]) < (1, 2, 3):
        raise MySQLCollectionError("Cần PyMySQL phiên bản 1.2.3 trở lên. Cập nhật requirements.txt.")

    connection = None
    try:
        options = {
            "host": host.strip(), "port": port, "user": user.strip(), "password": password,
            "database": database or None, "charset": "utf8mb4", "autocommit": True,
            "connect_timeout": timeout, "read_timeout": timeout, "write_timeout": timeout,
            "local_infile": False, "ssl_disabled": ssl_disabled,
        }
        if not ssl_disabled:
            # Explicit context makes TLS required in the supported driver, with
            # trusted-CA and hostname verification. No insecure fallback.
            options["ssl"] = ssl.create_default_context(cafile=ssl_ca)
        connection = pymysql.connect(**options)
        rows = []
        with connection.cursor() as cursor:
            # Session setting only; no table writes, DDL, grants, or global SET.
            # Autocommit avoids holding a transaction open during sleeps.
            cursor.execute(_READ_ONLY_SESSION_SQL)
            previous, previous_at, _, _ = _status_snapshot(cursor)
            for completed in range(1, samples + 1):
                time.sleep(interval)
                current, current_at, timestamp, probe_ms = _status_snapshot(cursor)
                elapsed = current_at - previous_at
                if not math.isfinite(elapsed) or elapsed <= 0:
                    raise MySQLCollectionError("Không đo được khoảng thời gian lấy mẫu hợp lệ; dừng thu thập.")
                reset = [name for name in _CUMULATIVE_COUNTERS if current[name] < previous[name]]
                if reset:
                    raise MySQLCollectionError(
                        "Bộ đếm MySQL bị đặt lại hoặc máy chủ khởi động lại: " + ", ".join(reset)
                        + ". Không trả kết quả của đợt thu thập này; hãy bắt đầu đợt mới."
                    )
                rows.append({
                    "timestamp": timestamp,
                    "queries_per_second": (current["Questions"] - previous["Questions"]) / elapsed,
                    "connections": current["Threads_connected"],
                    "response_time_ms": probe_ms,
                    "slow_queries": current["Slow_queries"] - previous["Slow_queries"],
                    "connection_errors": current["Aborted_connects"] - previous["Aborted_connects"],
                })
                previous, previous_at = current, current_at
                if progress_callback is not None:
                    progress_callback(completed, samples)
        frame = pd.DataFrame(rows, columns=METRIC_COLUMNS)
        frame.attrs["source"] = "mysql_live"
        frame.attrs["sampling"] = {
            "requested_interval_seconds": interval,
            "rate_elapsed_clock": "monotonic",
            "timestamp_timezone": "UTC",
            "initial_snapshot_excluded": True,
            "counter_reset_policy": "fail_entire_batch",
            "response_time_ms": "SELECT 1 client round-trip proxy, not average workload latency",
            "connection_errors": "interval delta Aborted_connects; failed connection attempts",
            "slow_queries": "interval delta Slow_queries; depends on server long_query_time",
            "monitor_contributes_to_questions_and_connections": True,
            "tls": "disabled_explicitly" if ssl_disabled else "certificate_and_hostname_verified",
        }
        return frame
    except MySQLCollectionError:
        raise
    except Exception as exc:
        # Do not attach raw driver text, which can expose account/server details
        # or credential-bearing exceptions from adapters and callbacks.
        code = exc.args[0] if exc.args and type(exc.args[0]) is int else None
        if code in (1044, 1045, 1142, 1227):
            message = "MySQL từ chối truy cập. Kiểm tra tài khoản giám sát, mật khẩu và quyền đọc trạng thái."
        elif isinstance(exc, (ssl.SSLError, OSError)) and not ssl_disabled:
            message = "Không thiết lập được kết nối TLS MySQL. Kiểm tra máy chủ, CA, tên máy và chứng chỉ."
        else:
            message = "Không thể hoàn tất thu thập MySQL. Kiểm tra kết nối, TLS, thời gian chờ và nhật ký máy chủ."
        raise MySQLCollectionError(message) from None
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
