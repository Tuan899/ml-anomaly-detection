"""Durable, bounded alert emails with an independent verified-TLS SMTP worker.

SMTP credentials exist only in memory. The outbox stores the exact public
message and recipients, never an SMTP username, password or raw server error.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate
import hashlib
import json
import math
import os
from pathlib import Path
import smtplib
import sqlite3
import ssl
from threading import Event, RLock, Thread
import time
from uuid import uuid4


MODEL_NAMES = {"mad": "MAD", "isolation_forest": "Isolation Forest", "lof": "LOF", "one_class_svm": "One-Class SVM"}
METRICS = {"queries_per_second": "Truy vấn/giây (QPS)", "connections": "Kết nối đang mở",
           "response_time_ms": "Phản hồi (ms)", "slow_queries": "Truy vấn chậm/kỳ",
           "connection_errors": "Kết nối thất bại/kỳ"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _clean(value, maximum=160) -> str:
    return " ".join(str(value if value is not None else "—").split())[:maximum]


def _address(value: str, *, empty=False) -> str:
    if not isinstance(value, str) or len(value) > 254 or any(char in value for char in "\r\n\x00"):
        raise ValueError("Địa chỉ email không hợp lệ.")
    value = value.strip()
    if empty and not value:
        return ""
    try:
        parsed = Address(addr_spec=value)
        if not parsed.username or not parsed.domain or parsed.addr_spec != value:
            raise ValueError
    except (ValueError, IndexError):
        raise ValueError("Địa chỉ email không hợp lệ; nhập địa chỉ thuần, không kèm tên hiển thị.") from None
    return value


@dataclass(frozen=True, repr=False)
class _Settings:
    enabled: bool = False
    host: str = ""
    port: int = 587
    security: str = "starttls"
    username: str = ""
    password: str = ""
    sender: str = ""
    recipients: tuple[str, ...] = ()
    cooldown_seconds: int = 300
    auth_required: bool = False

    def configured(self) -> bool:
        return bool(self.host and self.sender and self.recipients and
                    (not self.auth_required or (self.username and self.password)))

    def public(self) -> dict:
        return {key: getattr(self, key) for key in ("enabled", "host", "port", "security", "sender",
                                                  "recipients", "cooldown_seconds", "auth_required")}


class EmailNotifier:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._wake, self._stop = Event(), Event()
        self._thread: Thread | None = None
        self._closed = False
        self._last_error = ""
        with self._db() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS email_settings (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS email_outbox (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, sample_id INTEGER UNIQUE,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
                    subject TEXT NOT NULL, body TEXT NOT NULL, recipients TEXT NOT NULL,
                    generation INTEGER NOT NULL, group_key TEXT, baseline_id INTEGER,
                    source TEXT, session_id TEXT, severity TEXT, message TEXT NOT NULL,
                    accepted_count INTEGER NOT NULL DEFAULT 0, refused_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS email_seen_samples (
                    sample_id INTEGER PRIMARY KEY, seen_at TEXT NOT NULL, outcome TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS email_cooldowns (
                    group_key TEXT PRIMARY KEY, queued_at REAL NOT NULL, job_id TEXT NOT NULL
                );
            """)
            stored = connection.execute("SELECT payload FROM email_settings WHERE id=1").fetchone()
            public = json.loads(stored[0]) if stored else {}
            connection.execute("""UPDATE email_outbox SET status='unknown', finished_at=?,
                message='Dịch vụ đã khởi động lại khi đang gửi; chưa xác định SMTP đã nhận hay chưa. Không tự gửi lại.'
                WHERE status='sending'""", (_now(),))
        self._generation = int(public.pop("generation", 1))
        self._activation_id = int(public.pop("activation_id", 0))
        public["recipients"] = tuple(public.get("recipients", ()))
        self._settings = _Settings(**{key: value for key, value in public.items() if key in _Settings.__dataclass_fields__})
        self._load_environment()
        self._persist_settings()
        self._ensure_worker()

    @contextmanager
    def _db(self):
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _ensure_open(self):
        if self._closed:
            raise RuntimeError("Bộ gửi email đã đóng.")

    def _load_environment(self):
        env = os.environ
        mapping = {"ANOMALY_EMAIL_ENABLED": "enabled", "SMTP_HOST": "host", "SMTP_PORT": "port",
                   "SMTP_SECURITY": "security", "SMTP_USER": "username", "SMTP_PASSWORD": "password",
                   "SMTP_FROM": "sender", "ALERT_EMAIL_TO": "recipients",
                   "ALERT_EMAIL_COOLDOWN_SECONDS": "cooldown_seconds"}
        changes = {}
        try:
            for name, field in mapping.items():
                if name not in env:
                    continue
                value = env[name]
                if field == "enabled":
                    value = value == "1"
                elif field in {"port", "cooldown_seconds"}:
                    if not value.isascii() or not value.isdecimal():
                        raise ValueError
                    value = int(value)
                elif field == "recipients":
                    value = [part.strip() for part in value.split(",") if part.strip()]
                changes[field] = value
            self._settings = self._validated_settings(changes)
        except ValueError:
            self._settings = replace(self._settings, enabled=False)
            self._last_error = "Cấu hình email trong môi trường chưa hợp lệ; chưa gửi email."

    def _validated_settings(self, changes: dict) -> _Settings:
        current = self._settings
        enabled = changes.get("enabled", current.enabled)
        host = changes.get("host", current.host)
        port = changes.get("port", current.port)
        security = changes.get("security", current.security)
        username = changes.get("username") or current.username
        password = changes.get("password") or current.password
        sender = changes.get("sender", current.sender)
        recipients = changes.get("recipients", current.recipients)
        cooldown = changes.get("cooldown_seconds", current.cooldown_seconds)
        if type(enabled) is not bool:
            raise ValueError("Tùy chọn bật email phải là đúng hoặc sai.")
        if (not isinstance(host, str) or len(host) > 255 or any(c.isspace() or c in "/\\\x00" for c in host)):
            raise ValueError("Máy chủ SMTP phải là tên máy hoặc địa chỉ IP hợp lệ, không chứa URL hay dòng mới.")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Cổng SMTP phải là số nguyên từ 1 đến 65535.")
        if security not in {"starttls", "ssl"}:
            raise ValueError("Chỉ hỗ trợ SMTP STARTTLS hoặc SSL với xác minh chứng chỉ.")
        if not isinstance(username, str) or not isinstance(password, str):
            raise ValueError("Thông tin xác thực SMTP phải là chuỗi ký tự.")
        if len(username) > 1024 or len(password) > 4096:
            raise ValueError("Thông tin xác thực SMTP quá dài.")
        sender = _address(sender, empty=True)
        if not isinstance(recipients, (list, tuple)) or len(recipients) > 20:
            raise ValueError("Cần danh sách tối đa 20 địa chỉ nhận email.")
        recipients = tuple(dict.fromkeys(_address(value) for value in recipients))
        if type(cooldown) is not int or not 60 <= cooldown <= 3600:
            raise ValueError("Thời gian giãn email phải là số nguyên từ 60 đến 3600 giây.")
        auth_required = current.auth_required or bool(username or password)
        return _Settings(enabled, host.strip(), port, security, username, password, sender, recipients, cooldown, auth_required)

    def _persist_settings(self, connection=None):
        payload = {**self._settings.public(), "generation": self._generation, "activation_id": self._activation_id}
        if connection is not None:
            connection.execute("INSERT OR REPLACE INTO email_settings(id,payload) VALUES (1,?)",
                               (json.dumps(payload, ensure_ascii=False),))
        else:
            with self._db() as connection:
                self._persist_settings(connection)

    @staticmethod
    def _max_sample_id(connection) -> int:
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='engine_samples'").fetchone()
        return int(connection.execute("SELECT COALESCE(MAX(id),0) FROM engine_samples").fetchone()[0]) if exists else 0

    def configure(self, *, enabled=None, host=None, port=None, security=None, username=None, password=None,
                  sender=None, recipients=None, cooldown_seconds=None) -> dict:
        changes = {key: value for key, value in locals().copy().items() if key != "self" and value is not None}
        with self._lock:
            self._ensure_open()
            previous = self._settings
            updated = self._validated_settings(changes)
            old_target = (previous.host, previous.port, previous.security, previous.sender, previous.recipients)
            new_target = (updated.host, updated.port, updated.security, updated.sender, updated.recipients)
            credentials_changed = bool(previous.username and updated.username != previous.username or
                                       previous.password and updated.password != previous.password)
            changed = old_target != new_target or credentials_changed
            activating = updated.enabled and updated.configured() and (not previous.enabled or not previous.configured() or changed)
            with self._db() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if changed or not updated.enabled:
                    connection.execute("""UPDATE email_outbox SET status='cancelled', finished_at=?,
                        message='Đã hủy email còn chờ vì cấu hình hoặc đích nhận thay đổi. Email đang gửi có thể hoàn tất với cấu hình cũ.'
                        WHERE status='queued'""", (_now(),))
                if changed:
                    self._generation += 1
                if activating:
                    self._activation_id = self._max_sample_id(connection)
                self._settings = updated
                self._last_error = ""
                self._persist_settings(connection)
            self._wake.set()
            self._ensure_worker()
            return self.status()

    def status(self) -> dict:
        with self._lock:
            self._ensure_open()
            with self._db() as connection:
                jobs = [self._job(row) for row in connection.execute("SELECT * FROM email_outbox ORDER BY created_at DESC,id DESC LIMIT 20")]
                counts = {row["status"]: row["amount"] for row in connection.execute("SELECT status,COUNT(*) amount FROM email_outbox GROUP BY status")}
            config = self._settings
            if self._last_error:
                message = self._last_error
            elif not config.enabled:
                message = "Email đang tắt; chưa gửi thông báo."
            elif not config.configured():
                message = "Chưa đủ cấu hình SMTP/người nhận hoặc cần nhập lại tài khoản SMTP sau khi khởi động dịch vụ."
            else:
                message = "Email đã bật. Trạng thái sent chỉ có nghĩa SMTP đã chấp nhận, chưa xác nhận thư tới hộp thư."
            return {"enabled": config.enabled, "configured": config.configured(),
                    "host": config.host, "port": config.port, "security": config.security,
                    "sender": config.sender, "recipients": list(config.recipients),
                    "cooldown_seconds": config.cooldown_seconds,
                    "auth_configured": bool(config.username and config.password),
                    "message": message, "jobs": jobs,
                    "sent_count": counts.get("sent", 0),
                    "pending_count": counts.get("queued", 0) + counts.get("sending", 0),
                    "failed_count": counts.get("failed", 0), "unknown_count": counts.get("unknown", 0),
                    "cancelled_count": counts.get("cancelled", 0)}

    @staticmethod
    def _job(row) -> dict:
        value = dict(row)
        value["recipients"] = json.loads(value["recipients"])
        return value

    def preview(self, sample: dict) -> dict:
        if not isinstance(sample, dict) or type(sample.get("id")) is not int or sample["id"] < 1:
            raise ValueError("Cần bản ghi đã được chấm điểm để xem trước email.")
        votes = sample.get("votes", 0)
        if isinstance(votes, bool) or not isinstance(votes, int) or not 0 <= votes <= 4:
            raise ValueError("Số phiếu cảnh báo không hợp lệ.")
        level = "Nghiêm trọng" if votes >= 3 else "Cảnh báo" if votes == 2 else "Theo dõi" if votes else "Chưa có cảnh báo"
        simulated = sample.get("source") in {"K1", "K2", "K3", "K4"} or sample.get("scenario") in {"K1", "K2", "K3", "K4"}
        subject = f"ANOMALY LAB | {'[MÔ PHỎNG] ' if simulated else ''}{level} {votes}/4 | mẫu #{sample['id']}"
        lines = ["THÔNG BÁO MÔ PHỎNG — không phải số đo từ CSDL thật." if simulated else "THÔNG BÁO TỪ DỮ LIỆU GIÁM SÁT — cần đối chiếu vận hành.",
                 f"Mức: {level}; đồng thuận sau lọc: {votes}/4.",
                 f"Mã mẫu: {sample['id']}; mức nền: {_clean(sample.get('baseline_id'))}.",
                 f"Thời điểm nguồn: {_clean(sample.get('timestamp'))}.",
                 f"Thời điểm Backend nhận: {_clean(sample.get('received_at'))}.",
                 f"Nguồn: {_clean(sample.get('source'))}; phiên: {_clean(sample.get('session_id'))}.",
                 "Thuật toán bỏ phiếu: " + ", ".join(MODEL_NAMES.get(name, _clean(name, 40)) for name in sample.get("voters", [])) + ".", "", "Năm chỉ số và mức nền:"]
        evidence = {item.get("metric"): item for item in sample.get("evidence", []) if isinstance(item, dict)}
        def number(value):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                return "chưa có"
            return f"{value:.6g}"
        for metric, label in METRICS.items():
            item = evidence.get(metric, {})
            relative = item.get("relative_change")
            percent = "không xác định khi mức nền bằng 0" if relative is None else number(100 * relative) + "%"
            lines.append(f"- {label}: thực tế {number(sample.get(metric))}; nền {number(item.get('baseline'))}; "
                         f"chênh {number(item.get('delta'))} ({percent}); dung sai {number(item.get('allowed_deviation'))}; "
                         f"{'vượt dung sai' if item.get('material') else 'chưa vượt dung sai'}.")
        lines += ["", "Kiểm tra tiếp: đối chiếu nhật ký truy vấn, số kết nối, lỗi đăng nhập và bối cảnh thay đổi tải.",
                  "Đồng thuận là quy tắc cảnh báo, không xác định nguyên nhân hoặc xác suất sự cố.",
                  "Phản hồi của quản trị viên được lưu riêng; không tự thay nhãn tham chiếu hay huấn luyện lại mô hình."]
        return {"subject": subject, "body": "\n".join(lines)}

    def _queue(self, connection, *, kind, subject, body, sample=None, group_key=None, severity=None):
        job_id, created = uuid4().hex, _now()
        connection.execute("""INSERT INTO email_outbox
            (id,kind,sample_id,status,created_at,subject,body,recipients,generation,group_key,
             baseline_id,source,session_id,severity,message)
            VALUES (?,?,?,'queued',?,?,?,?,?,?,?,?,?,?,?)""",
            (job_id, kind, sample.get("id") if sample else None, created, subject, body,
             json.dumps(self._settings.recipients), self._generation, group_key,
             sample.get("baseline_id") if sample else None, _clean(sample.get("source")) if sample else None,
             _clean(sample.get("session_id")) if sample else None, severity,
             "Đã xếp hàng; chưa gửi tới SMTP."))
        return self._job(connection.execute("SELECT * FROM email_outbox WHERE id=?", (job_id,)).fetchone())

    def enqueue(self, samples):
        """Record every considered alert ID, including cooldown suppression."""
        try:
            with self._lock:
                self._ensure_open()
                with self._db() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    for sample in samples:
                        if not isinstance(sample, dict) or type(sample.get("id")) is not int or sample["id"] < 1:
                            continue
                        sample_id, votes = sample["id"], sample.get("votes", 0)
                        if isinstance(votes, bool) or not isinstance(votes, int) or not 2 <= votes <= 4:
                            continue
                        inserted = connection.execute("INSERT OR IGNORE INTO email_seen_samples VALUES (?,?,?)",
                                                      (sample_id, _now(), "considered")).rowcount
                        if not inserted:
                            continue
                        outcome = "inactive"
                        config = self._settings
                        if sample_id > self._activation_id and config.enabled and config.configured():
                            severity = "critical" if votes >= 3 else "warning"
                            group = json.dumps([sample.get("baseline_id"), sample.get("source"),
                                                sample.get("session_id"), severity, self._generation], ensure_ascii=False)
                            group_key = hashlib.sha256(group.encode()).hexdigest()
                            previous = connection.execute("SELECT queued_at FROM email_cooldowns WHERE group_key=?", (group_key,)).fetchone()
                            if previous and time.time() - previous[0] < config.cooldown_seconds:
                                outcome = "cooldown"
                            else:
                                message = self.preview(sample)
                                job = self._queue(connection, kind="alert", sample=sample, severity=severity,
                                                  group_key=group_key, **message)
                                connection.execute("INSERT OR REPLACE INTO email_cooldowns VALUES (?,?,?)",
                                                   (group_key, time.time(), job["id"]))
                                outcome = "queued"
                        connection.execute("UPDATE email_seen_samples SET outcome=? WHERE sample_id=?", (outcome, sample_id))
                self._wake.set()
                self._ensure_worker()
        except Exception:
            # Alert delivery must never turn successfully stored scoring into
            # an HTTP failure. Keep error text static; drivers may echo secrets.
            self._last_error = "Không thể cập nhật hàng đợi email; kết quả chấm điểm vẫn được giữ."

    def test_email(self) -> dict:
        with self._lock:
            self._ensure_open()
            if not self._settings.enabled or not self._settings.configured():
                raise RuntimeError("Bật email và hoàn tất cấu hình SMTP/người nhận trước khi gửi thư thử.")
            with self._db() as connection:
                job = self._queue(connection, kind="test", subject="ANOMALY LAB | [THƯ THỬ] Kiểm tra cấu hình",
                                  body="Đây là email thử do người dùng yêu cầu. Không phải cảnh báo sự cố.\n"
                                       "Trạng thái sent nghĩa là máy chủ SMTP đã chấp nhận, chưa xác nhận thư đã đến hộp thư.")
            self._wake.set()
            self._ensure_worker()
            return job

    def _ensure_worker(self):
        with self._lock:
            if self._closed or not self._settings.enabled or not self._settings.configured():
                return
            if self._thread is None or not self._thread.is_alive():
                with self._db() as connection:
                    pending = connection.execute("SELECT 1 FROM email_outbox WHERE status='queued' LIMIT 1").fetchone()
                if not pending:
                    return
                self._thread = Thread(target=self._worker, name="anomaly-email", daemon=True)
                self._thread.start()

    def _worker(self):
        while not self._stop.is_set():
            job, config = None, None
            try:
                with self._lock:
                    if self._closed:
                        return
                    if self._settings.enabled and self._settings.configured():
                        with self._db() as connection:
                            connection.execute("BEGIN IMMEDIATE")
                            row = connection.execute("SELECT * FROM email_outbox WHERE status='queued' AND generation=? ORDER BY created_at,id LIMIT 1",
                                                     (self._generation,)).fetchone()
                            if row:
                                connection.execute("UPDATE email_outbox SET status='sending',started_at=?,message='Đang trao đổi với SMTP; chưa xác nhận chấp nhận thư.' WHERE id=?", (_now(), row["id"]))
                                job, config = self._job(row), self._settings
                if job is None:
                    self._wake.wait(.5)
                    self._wake.clear()
                    continue
                # All socket I/O is outside notifier/controller/model locks.
                outcome, message, accepted, refused = self._deliver(config, job)
                with self._lock:
                    if self._closed:
                        return
                    with self._db() as connection:
                        connection.execute("""UPDATE email_outbox SET status=?,finished_at=?,message=?,
                            accepted_count=?,refused_count=? WHERE id=? AND status='sending'""",
                            (outcome, _now(), message, accepted, refused, job["id"]))
            except Exception:
                self._last_error = "Bộ gửi email gặp lỗi lưu trạng thái; không tự gửi lại email chưa xác định."
                if job:
                    try:
                        with self._lock:
                            if self._closed:
                                return
                            with self._db() as connection:
                                connection.execute("UPDATE email_outbox SET status='unknown',finished_at=?,message=? WHERE id=? AND status='sending'",
                                                   (_now(), self._last_error, job["id"]))
                    except Exception:
                        pass
                if self._stop.wait(.5):
                    return

    @staticmethod
    def _deliver(config: _Settings, job: dict) -> tuple[str, str, int, int]:
        client, submitting = None, False
        try:
            message = EmailMessage()
            message["From"], message["To"], message["Subject"] = config.sender, ", ".join(job["recipients"]), job["subject"]
            message["Date"] = formatdate(localtime=False)
            message["Message-ID"] = f"<anomaly-{job['id']}@anomalylab.local>"
            message.set_content(job["body"])
            context = ssl.create_default_context()
            if config.security == "ssl":
                client = smtplib.SMTP_SSL(config.host, config.port, timeout=5, context=context)
            else:
                client = smtplib.SMTP(config.host, config.port, timeout=5)
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
            if config.username:
                client.login(config.username, config.password)
            submitting = True
            refused = client.send_message(message, from_addr=config.sender, to_addrs=job["recipients"]) or {}
            rejected, accepted = len(refused), len(job["recipients"]) - len(refused)
            if not accepted:
                return "failed", "SMTP từ chối toàn bộ người nhận; chưa có thư được chấp nhận.", 0, rejected
            text = "SMTP đã chấp nhận thư; chưa xác nhận thư đã tới hộp thư."
            if rejected:
                text = "SMTP chỉ chấp nhận một phần người nhận; kiểm tra số địa chỉ bị từ chối. Chưa xác nhận thư đã tới hộp thư."
            return "sent", text, accepted, rejected
        except smtplib.SMTPAuthenticationError:
            return "failed", "SMTP từ chối xác thực. Kiểm tra cấu hình tài khoản; thông tin đăng nhập không được lưu trong lịch sử.", 0, 0
        except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError):
            return "failed", "SMTP từ chối thư hoặc địa chỉ gửi/nhận; chưa xác nhận chấp nhận thư.", 0, 0
        except Exception:
            if submitting:
                return "unknown", "Mất phản hồi trong khi gửi; chưa xác định SMTP đã nhận thư hay chưa. Không tự gửi lại.", 0, 0
            return "failed", "Không kết nối hoặc thiết lập TLS SMTP được; chưa gửi thư.", 0, 0
        finally:
            if client is not None:
                try:
                    client.quit()
                except Exception:
                    try:
                        client.close()
                    except Exception:
                        pass

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._stop.set()
            self._wake.set()
            worker = self._thread
        if worker is not None and worker.is_alive():
            worker.join(timeout=6)
        with self._lock:
            if worker is not None and worker.is_alive():
                with self._db() as connection:
                    connection.execute("""UPDATE email_outbox SET status='unknown',finished_at=?,
                        message='Dịch vụ đang đóng khi SMTP chưa trả kết quả; không tự gửi lại.' WHERE status='sending'""", (_now(),))
            self._closed = True
