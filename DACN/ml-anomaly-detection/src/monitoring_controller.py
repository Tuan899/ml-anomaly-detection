"""Single-source monitoring orchestration, independent of browser sessions.

The fitted engine owns observations and model artifacts. This controller owns
only replay scheduling and collector liveness; observation time is never used
as a heartbeat. Reopening a browser does not train models or restart a replay.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
from functools import wraps
import json
import logging
import math
from pathlib import Path
import sqlite3
from threading import Event, RLock, Thread
from typing import Any
from uuid import uuid4


_LOGGER = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialized_transition(method):
    """Keep stop/join/reconfigure/start atomic without blocking the worker lock.

    A separate reentrant lock is essential: source transitions call stop(),
    while replay workers acquire only _lock. Holding _lock during join would
    deadlock a worker that is finishing its current database write.
    """
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self._transition_lock:
            return method(self, *args, **kwargs)
    return guarded


class MonitoringController:
    def __init__(self, db_path: str | Path, *, engine=None, fault_runner=None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if engine is None:
            from .monitoring_engine import MonitoringEngine
            engine = MonitoringEngine(self.db_path)
        self.engine = engine
        self._transition_lock = RLock()
        self._lock = RLock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._closed = False
        self._fault_runner = fault_runner
        self._notifier = None
        self._injections: list[dict[str, Any]] = []
        with self._connection() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS monitor_runtime (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            found = connection.execute("SELECT value FROM monitor_runtime WHERE key = 'collector'").fetchone()
        self._state = json.loads(found[0]) if found else {
            "mode": "idle", "status": "idle", "source": None,
            "last_received_at": None, "started_at": None,
            "interval_seconds": 1.0, "stale_after_seconds": 5.0,
            "message": "Chưa chọn nguồn giám sát.", "session_id": None,
            "target_id": None,
        }
        self._state.setdefault("target_id", None)
        if self._state["status"] == "running":
            self._state["status"] = "stale"
            self._state["message"] = "Dịch vụ đã khởi động lại; cần khởi động lại nguồn dữ liệu."
        self._persist()

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _persist(self):
        with self._connection() as connection:
            connection.execute("INSERT OR REPLACE INTO monitor_runtime (key,value) VALUES ('collector',?)",
                               (json.dumps(self._state, ensure_ascii=False),))

    def collector_status(self) -> dict:
        with self._lock:
            state = dict(self._state)
            last = state.get("last_received_at")
            age = max(0.0, (_utcnow() - datetime.fromisoformat(last)).total_seconds()) if last else None
            state["age_seconds"] = round(age, 3) if age is not None else None
            state["pending_injection_samples"] = sum(item["remaining"] for item in self._injections)
            if state["mode"] in ("live", "replay") and state["status"] in ("running", "stale"):
                if age is None:
                    state["status"] = "stale"
                    state["message"] = "Đang chờ mẫu đầu tiên; chưa thể kết luận hệ thống bình thường."
                elif age > state["stale_after_seconds"]:
                    state["status"] = "stale"
                    state["message"] = "Mất tín hiệu: nguồn dữ liệu chưa gửi mẫu trong thời gian quy định."
            return state

    def health(self) -> dict:
        with self._lock:
            baseline = self.engine.baseline()
            recent = self.engine.history(limit=1, baseline_id=baseline["id"]) if baseline else []
            return {"backend": "ok", "baseline": baseline,
                    "collector": self.collector_status(), "latest": recent[-1] if recent else None}

    @_serialized_transition
    def train(self, records, **options) -> dict:
        # Training changes are explicit and cannot race a live scoring worker.
        self.stop()
        with self._lock:
            return self.engine.train_baseline(records, **options)

    def _require_baseline(self):
        if self.engine.baseline() is None:
            raise RuntimeError("Chưa có mức nền. Hãy học mức nền trước khi giám sát.")

    @property
    def notifier(self):
        # Configuration/status and newly committed samples share one notifier.
        # Its SMTP worker performs network I/O outside controller/model locks.
        with self._lock:
            if self._closed:
                raise RuntimeError("Dịch vụ giám sát đã đóng.")
            if self._notifier is None:
                from .admin_notifications import EmailNotifier
                self._notifier = EmailNotifier(self.db_path)
            return self._notifier

    def _notify_samples(self, samples):
        if not samples:
            return
        try:
            self.notifier.enqueue(samples)
        except Exception:
            # Measurements are already committed. Notification setup failures
            # must not turn successful scoring into an HTTP or replay failure.
            _LOGGER.warning("Không thể cập nhật thông báo; kết quả chấm điểm đã được lưu.")

    @property
    def fault_runner(self):
        # One lazy runner per monitoring database/controller. Merely training,
        # viewing CSVs or shutting down an unused monitor never opens a DB target.
        with self._transition_lock:
            if self._fault_runner is None:
                from .live_faults import LiveFaultRunner
                self._fault_runner = LiveFaultRunner(self.db_path)
            return self._fault_runner

    def fault_status(self) -> dict:
        return self.fault_runner.status()

    @_serialized_transition
    def start_live_fault(self, **options) -> dict:
        self._require_baseline()
        collector = self.collector_status()
        age, threshold = collector.get("age_seconds"), collector.get("stale_after_seconds")
        fresh = (all(isinstance(value, (int, float)) and not isinstance(value, bool)
                     and math.isfinite(value) for value in (age, threshold))
                 and age >= 0 and threshold > 0 and age <= threshold)
        if (collector.get("mode") != "live" or collector.get("status") != "running"
                or not collector.get("last_received_at") or not fresh):
            raise RuntimeError("Chỉ bơm tải thử nghiệm khi bộ thu trực tiếp đang gửi số liệu mới. Hãy bật bộ thu trước.")
        status = self.fault_runner.status()
        if not status.get("enabled") or not status.get("configured"):
            raise RuntimeError("Chưa bật hoặc chưa cấu hình tài khoản bơm tải riêng cho máy chủ thử nghiệm.")
        target = status.get("target") or {}
        if not collector.get("target_id") or not target.get("target_id"):
            raise RuntimeError("Chưa xác nhận được máy chủ thử nghiệm trùng với nguồn đang đo. Khởi chạy bộ thu đã cập nhật và cấu hình tài khoản bơm tải riêng.")
        if collector["target_id"] != target["target_id"]:
            raise RuntimeError("Máy chủ bơm tải khác máy chủ bộ thu đang đo. Kiểm tra lại cấu hình máy chủ và cổng.")
        return self.fault_runner.start(**options)

    @_serialized_transition
    def stop_live_fault(self) -> dict:
        return self.fault_runner.stop()

    def _stop_faults(self):
        if self._fault_runner is not None:
            # Fail the source transition if workload cleanup has not finished.
            # The old source must remain observable until its load is stopped.
            self._fault_runner.stop()

    @_serialized_transition
    def start_live(self, *, interval_seconds: float = 1.0, stale_after_seconds: float | None = None,
                   session_id: str | None = None, target_id: str | None = None) -> dict:
        self._require_baseline()
        self.stop()
        with self._lock:
            self._state.update(mode="live", status="stale", source="live", session_id=session_id,
                               target_id=target_id,
                               last_received_at=None, started_at=_utcnow().isoformat(),
                               interval_seconds=float(interval_seconds),
                               stale_after_seconds=float(stale_after_seconds or max(5, interval_seconds * 3)),
                               message="Đang chờ bộ thu độc lập gửi số liệu.")
            self._persist()
            return self.collector_status()

    @_serialized_transition
    def ingest_external(self, records, *, source: str = "live", session_id: str | None = None) -> list[dict]:
        with self._lock:
            self._require_baseline()
            if self._state["mode"] == "replay":
                raise RuntimeError("Đang phát lại dữ liệu. Dừng phát lại trước khi nhận nguồn trực tiếp.")
            if self._state["mode"] == "live" and self._state["status"] == "stopped":
                raise RuntimeError("Nguồn trực tiếp đã dừng. Bật lại nguồn trước khi gửi mẫu mới.")
            expected_session = self._state.get("session_id")
            if self._state["mode"] == "live" and expected_session is not None and session_id != expected_session:
                raise RuntimeError("Phiên bộ thu đã thay đổi. Khởi động lại bộ thu để chọn nguồn trực tiếp mới.")
            if self._state["mode"] != "live":
                self._state.update(mode="live", interval_seconds=1.0, stale_after_seconds=5.0,
                                   started_at=_utcnow().isoformat())
            samples = self.engine.ingest(records, source=source, session_id=session_id)
            if samples:
                # The immutable receipt time comes from the engine. An exact
                # retry may return an old point and must not renew liveness.
                latest_receipt = max(point["received_at"] for point in samples)
                previous_receipt = self._state.get("last_received_at")
                if previous_receipt and latest_receipt < previous_receipt:
                    latest_receipt = previous_receipt
                self._state.update(status="running", source=source, session_id=session_id,
                                   last_received_at=latest_receipt, message="Đang nhận dữ liệu từ bộ thu độc lập.")
                self._persist()
        self._notify_samples(samples)
        return samples

    @_serialized_transition
    def stop_live(self, session_id: str) -> dict:
        # A collector exiting after the user switches to replay must not stop
        # that newer source. The ownership check and state update are atomic.
        with self._lock:
            owns_source = self._state["mode"] == "live" and self._state.get("session_id") == session_id
        if owns_source:
            self._stop_faults()
            with self._lock:
                self._state.update(status="stopped", message="Bộ thu độc lập đã dừng; không còn nhận mẫu mới.")
                self._persist()
        return self.collector_status()

    @_serialized_transition
    def start_replay(self, *, scenario: str = "K1", interval_seconds: float = 1.0,
                     rows: int = 180, loop: bool = False) -> dict:
        from .demo_scenarios import scenario_records
        self._require_baseline()
        records = scenario_records(scenario, rows=rows)
        if not records:
            raise ValueError("Kịch bản không có dữ liệu.")
        # Fail synchronously on the first point if the chosen baseline is later
        # than this replay, rather than returning a successful start then error.
        baseline = self.engine.baseline()
        end = datetime.fromisoformat(str(baseline["end"]).replace("Z", "+00:00"))
        first = datetime.fromisoformat(str(records[0]["timestamp"]).replace("Z", "+00:00"))
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        if first <= end:
            raise ValueError("Kịch bản phải xảy ra sau khoảng học nền. Hãy học nền K1 mặc định để phát lại demo.")
        self.stop()
        with self._lock:
            self._stop = Event()
            self._injections.clear()
            self._state.update(mode="replay", status="running", source=scenario,
                               target_id=None,
                               last_received_at=None, started_at=_utcnow().isoformat(),
                               interval_seconds=float(interval_seconds),
                               stale_after_seconds=max(5.0, interval_seconds * 3),
                               message="Đang phát lại dữ liệu giả lập.", session_id=str(uuid4()))
            self._persist()
            self._thread = Thread(target=self._replay_worker,
                                  args=(records, bool(loop), self._stop), daemon=True, name="anomaly-replay")
            self._thread.start()
            return self.collector_status()

    def _replay_worker(self, records: list[dict], loop: bool, stop: Event):
        from .demo_scenarios import inject_record
        try:
            sequence = 0
            while not stop.is_set():
                for original in records:
                    if stop.is_set():
                        return
                    record = dict(original)
                    with self._lock:
                        if self._injections:
                            item = self._injections[0]
                            record = inject_record(record, item["scenario"])
                            record["scenario"] = item["scenario"]
                            item["remaining"] -= 1
                            if item["remaining"] == 0:
                                self._injections.pop(0)
                        record["event_id"] = f"replay-{sequence}"
                        sequence += 1
                        samples = self.engine.ingest([record], source=self._state["source"],
                                                     session_id=self._state["session_id"])
                        self._state.update(status="running", last_received_at=samples[-1]["received_at"],
                                           message="Đang phát lại dữ liệu giả lập.")
                        self._persist()
                        interval = self._state["interval_seconds"]
                    self._notify_samples(samples)
                    if stop.wait(interval):
                        return
                if not loop:
                    with self._lock:
                        self._state.update(status="completed", message="Đã phát hết kịch bản; không còn nhận mẫu mới.")
                        self._injections.clear()
                        self._persist()
                    return
        except Exception:
            # User-controlled values or backend errors must not leak arbitrary
            # exception text (which may include file paths or credentials).
            with self._lock:
                self._state.update(status="error", message="Nguồn phát lại gặp lỗi. Kiểm tra mức nền và dữ liệu kịch bản.")
                self._persist()

    @_serialized_transition
    def start_alert_demo(self) -> dict:
        """Explicit one-click K3 simulation using the existing frozen baseline.

        This never starts SQL workloads, replaces an operator-provided baseline
        or changes a live-collector context. All alert votes are model outputs.
        """
        from .demo_scenarios import baseline_records
        with self._lock:
            if self._state["mode"] == "live":
                raise RuntimeError("Đang ở nguồn trực tiếp. Demo cảnh báo mô phỏng không thay đổi nguồn hoặc dữ liệu trực tiếp.")
            baseline = self.engine.baseline()
        if baseline is None:
            baseline = self.train(baseline_records(), source="K1")
        elif baseline.get("source") != "K1":
            raise RuntimeError("Mức nền hiện tại do bạn cung cấp. Demo mô phỏng không ghi đè mức nền này; hãy chọn nền K1 trước.")
        # start_replay checks the replay timestamps against the baseline before
        # it stops/replaces any existing source. Existing history is retained.
        self.start_replay(scenario="K1", interval_seconds=1.0, rows=180, loop=False)
        self.inject(scenario="K3", duration_samples=15)
        return {"collector": self.collector_status(), "baseline": baseline,
                "scenario": "K3", "simulated": True}

    @_serialized_transition
    def inject(self, *, scenario: str, duration_samples: int = 15) -> dict:
        with self._lock:
            if self._state["mode"] != "replay" or self._thread is None or not self._thread.is_alive():
                raise RuntimeError("Bơm sự cố mô phỏng chỉ dùng khi đang phát lại; không tạo tải lên máy chủ thật.")
            self._injections.append({"scenario": scenario, "remaining": int(duration_samples)})
            return {"synthetic": True, "scenario": scenario, "duration_samples": duration_samples,
                    "collector": self.collector_status()}

    @_serialized_transition
    def stop(self) -> dict:
        # Never join a worker while holding the lock it needs for shutdown.
        self._stop_faults()
        with self._lock:
            worker = self._thread
            self._stop.set()
        if worker is not None and worker.is_alive():
            worker.join(timeout=10)
            if worker.is_alive():
                raise RuntimeError("Chưa dừng được nguồn phát lại; hãy thử lại sau.")
        with self._lock:
            self._thread = None
            self._injections.clear()
            if self._state["mode"] != "idle":
                self._state.update(status="stopped", message="Nguồn dữ liệu đã dừng; trạng thái không đại diện cho hiện tại.")
                self._persist()
            return self.collector_status()

    @_serialized_transition
    def close(self):
        if not self._closed:
            self.stop()
            if self._fault_runner is not None:
                self._fault_runner.close()
            if self._notifier is not None:
                self._notifier.close()
            self.engine.close()
            self._closed = True
