"""Prepare a measured baseline and start a local MySQL test demonstration.

Passwords are prompted privately and passed only through child environments.
No load is started here: choose K2, K3 or K4 explicitly in the web interface.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from getpass import getpass
import ipaddress
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class DemoError(RuntimeError):
    """Only deliberately sanitized messages are displayed to the operator."""


def _integer(low: int, high: int):
    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"Cần số nguyên từ {low} đến {high}.") from None
        if not low <= number <= high:
            raise argparse.ArgumentTypeError(f"Cần số nguyên từ {low} đến {high}.")
        return number
    return parse


def _interval(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Chu kỳ phải nằm trong khoảng 0,1–60 giây.") from None
    if not math.isfinite(number) or not .1 <= number <= 60:
        raise argparse.ArgumentTypeError("Chu kỳ phải nằm trong khoảng 0,1–60 giây.")
    return number


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="MySQL thử nghiệm; để trống để nhập tại lời nhắc.")
    parser.add_argument("--port", type=_integer(1, 65535), help="Cổng MySQL, mặc định tại lời nhắc: 3306.")
    parser.add_argument("--user", help="Tài khoản chỉ đọc trạng thái của bộ thu.")
    parser.add_argument("--fault-user", help="Tài khoản riêng dùng để diễn tập tạo tải.")
    parser.add_argument("--database", help="Tùy chọn; thường để trống với tài khoản USAGE.")
    parser.add_argument("--ssl-ca", help="Tệp CA dùng chung cho bộ thu và tác vụ tạo tải.")
    parser.add_argument("--no-tls", action="store_true", help="Chỉ dùng với MySQL thử nghiệm trên localhost/địa chỉ loopback.")
    parser.add_argument("--baseline-samples", type=_integer(30, 300), default=60)
    parser.add_argument("--interval", type=_interval, default=1.0)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--check", action="store_true", help="Chỉ kiểm tra thư viện; không hỏi mật khẩu, không kết nối máy chủ.")
    return parser.parse_args(argv)


def _check_dependencies() -> None:
    try:
        import fastapi
        import httpx
        import multipart
        import numpy
        import pandas
        import plotly
        import pydantic
        import pymysql
        import sklearn
        import streamlit
        import uvicorn
        from packaging.version import Version
        if sys.version_info < (3, 10) or Version(streamlit.__version__) < Version("1.65.0"):
            raise ValueError
        if Version(pydantic.__version__) < Version("2.0") or tuple(pymysql.VERSION[:3]) < (1, 2, 3):
            raise ValueError
    except (ImportError, ValueError, AttributeError):
        raise DemoError("Môi trường thiếu thư viện. Cài requirements.txt bằng Python đang chạy rồi thử lại.") from None


def _prompt(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip() or default
    if not value or any(ord(character) < 32 for character in value):
        raise DemoError("Thông tin kết nối không hợp lệ.")
    return value


def _loopback(host: str) -> bool:
    if host.rstrip(".").lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _free_port(first: int, excluded=()) -> int:
    for port in range(first, first + 10):
        if port in excluded:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            if os.name == "nt":
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                listener.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise DemoError(f"Không có cổng trống từ {first} đến {first + 9}.")


def _child_environment(base: dict, role: str) -> dict:
    """Give each child only its own database credentials."""
    result = {key: value for key, value in base.items()
              if not key.startswith("FAULT_MYSQL_") and not key.startswith("MYSQL_")
              and not key.startswith(("OPENAI_", "SMTP_", "ALERT_EMAIL_"))
              and key not in {"ANOMALY_FAULT_ENABLED", "ANOMALY_AI_ENABLED", "ANOMALY_EMAIL_ENABLED"}}
    if role == "backend":
        result.update({key: value for key, value in base.items()
                       if key.startswith(("FAULT_MYSQL_", "OPENAI_", "SMTP_", "ALERT_EMAIL_"))
                       or key in {"ANOMALY_FAULT_ENABLED", "ANOMALY_AI_ENABLED", "ANOMALY_EMAIL_ENABLED"}})
    elif role == "collector":
        result.update({key: value for key, value in base.items() if key.startswith("MYSQL_")})
    elif role != "frontend":
        raise ValueError("Unknown child role")
    return result


@contextmanager
def _exclusive_demo(runtime: Path):
    """Prevent two independent controllers from using the live demo database."""
    runtime.mkdir(parents=True, exist_ok=True)
    lock = (runtime / "live_demo.lock").open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise DemoError("Một phiên demo trực tiếp đang chạy. Dừng phiên đó trước khi mở lại.") from None
        else:
            import fcntl
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise DemoError("Một phiên demo trực tiếp đang chạy. Dừng phiên đó trước khi mở lại.") from None
        locked = True
        yield
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        lock.close()


def _start(command: list[str], environment: dict, log_file):
    options = {"cwd": str(ROOT), "env": environment, "stdin": subprocess.DEVNULL,
               "stdout": log_file, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        # Inherit this console without opening another window. A process group
        # lets Ctrl+Break reach the venv launcher and its Python descendant.
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def _stop_owned(process) -> None:
    """Stop only the process group created by this launcher."""
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=8)
        return
    except (OSError, subprocess.TimeoutExpired):
        pass
    if process.poll() is None:
        if os.name == "nt":
            # Exact owned PID; /T includes the venv Python launcher descendant.
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass


def _wait_backend(client, process, address: str) -> None:
    import httpx
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            response = client.get(address + "/health")
            if response.status_code == 200 and response.json().get("status") == "ok":
                return
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(.25)
    raise DemoError("Backend chưa khởi động được. Xem .runtime/live_backend.log.")


def _run(args) -> None:
    import httpx
    from src.mysql_collector import MySQLCollectionError, collect_mysql_metrics

    print("DEMO MYSQL THỬ NGHIỆM — thu nền thật, bộ thu riêng, tạo tải bằng nút trên web.")
    host = (args.host or _prompt("Host MySQL thử nghiệm", "127.0.0.1")).strip()
    port = args.port or _integer(1, 65535)(_prompt("Cổng MySQL", "3306"))
    user = (args.user or _prompt("Tài khoản bộ thu chỉ đọc trạng thái", "anomaly_monitor")).strip()
    fault_user = (args.fault_user or _prompt("Tài khoản riêng dùng tạo tải", "anomaly_demo")).strip()
    if not host or not user or not fault_user or any(ord(c) < 32 for value in (host, user, fault_user) for c in value):
        raise DemoError("Host và tên tài khoản không được để trống hoặc chứa ký tự điều khiển.")
    if args.no_tls and (not _loopback(host) or args.ssl_ca):
        raise DemoError("--no-tls chỉ dùng cho máy thử nghiệm loopback và không kết hợp --ssl-ca.")
    collector_password = getpass("Mật khẩu tài khoản bộ thu (ẩn): ")
    fault_password = getpass("Mật khẩu tài khoản tạo tải (ẩn): ")
    runtime = ROOT / ".runtime"
    with _exclusive_demo(runtime):
        print(f"Đang thu {args.baseline_samples} mẫu bình thường, tối thiểu {args.baseline_samples * args.interval:g} giây. Chưa bơm tải trong giai đoạn này.", flush=True)
        def progress(completed, requested):
            if completed == 1 or completed == requested or completed % 10 == 0:
                print(f"Mức nền: {completed}/{requested} mẫu", flush=True)
        try:
            frame = collect_mysql_metrics(host=host, port=port, user=user, password=collector_password,
                database=args.database, samples=args.baseline_samples, interval_seconds=args.interval,
                ssl_ca=args.ssl_ca, ssl_disabled=args.no_tls, progress_callback=progress)
        except MySQLCollectionError as exc:
            raise DemoError(str(exc)) from None
        records = json.loads(frame.to_json(orient="records", date_format="iso", date_unit="ns", double_precision=15))
        frame.to_csv(runtime / "live_baseline.csv", index=False)
        backend_port, frontend_port = _free_port(8000), _free_port(8501)
        backend_url, frontend_url = f"http://127.0.0.1:{backend_port}", f"http://127.0.0.1:{frontend_port}"
        environment = os.environ.copy()
        # Delete inherited database variables before assigning this exact target.
        for name in list(environment):
            if name.startswith("MYSQL_") or name.startswith("FAULT_MYSQL_"):
                del environment[name]
        environment.update(ANOMALY_MONITOR_DB=str(runtime / "live_monitoring.sqlite3"),
            ANOMALY_API_URL=backend_url, ANOMALY_FAULT_ENABLED="1", PYTHONIOENCODING="utf-8",
            MYSQL_HOST=host, MYSQL_PORT=str(port), MYSQL_USER=user, MYSQL_PASSWORD=collector_password,
            FAULT_MYSQL_HOST=host, FAULT_MYSQL_PORT=str(port), FAULT_MYSQL_USER=fault_user,
            FAULT_MYSQL_PASSWORD=fault_password)
        if args.database:
            environment.update(MYSQL_DATABASE=args.database, FAULT_MYSQL_DATABASE=args.database)
        if args.ssl_ca:
            environment.update(MYSQL_SSL_CA=args.ssl_ca, FAULT_MYSQL_SSL_CA=args.ssl_ca)
        if args.no_tls:
            environment["FAULT_MYSQL_NO_TLS"] = "1"
        children, logs = [], []
        try:
            def launch(name, command, role):
                log_file = (runtime / f"live_{name}.log").open("a", encoding="utf-8")
                logs.append(log_file)
                process = _start(command, _child_environment(environment, role), log_file)
                children.append(process)
                return process
            backend = launch("backend", [sys.executable, "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1", "--port", str(backend_port)], "backend")
            with httpx.Client(timeout=3, trust_env=False) as client:
                _wait_backend(client, backend, backend_url)
                try:
                    response = client.post(backend_url + "/monitor/train", json={"source": "live-baseline", "records": records}, timeout=60)
                    response.raise_for_status()
                except httpx.HTTPError:
                    raise DemoError("Không học được mức nền thật. Xem .runtime/live_backend.log.") from None
            collector_command = [sys.executable, "scripts/run_collector.py", "--backend-url", backend_url, "--interval", str(args.interval)]
            if args.no_tls:
                collector_command.append("--no-tls")
            launch("collector", collector_command, "collector")
            frontend = launch("frontend", [sys.executable, "-m", "streamlit", "run", "frontend/app.py",
                "--server.address", "127.0.0.1", "--server.port", str(frontend_port), "--server.headless", "true",
                "--server.runOnSave", "true", "--browser.gatherUsageStats", "false"], "frontend")
            # Wait for the actual frontend server before opening a browser.
            with httpx.Client(timeout=2, trust_env=False) as client:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if frontend.poll() is not None:
                        raise DemoError("Giao diện chưa khởi động được. Xem .runtime/live_frontend.log.")
                    try:
                        if client.get(frontend_url + "/_stcore/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.25)
                else:
                    raise DemoError("Giao diện chưa sẵn sàng. Xem .runtime/live_frontend.log.")
            print(f"\nỨng dụng: {frontend_url}\nAPI: {backend_url}/docs", flush=True)
            print("Mở Điều khiển demo, chọn Bộ thu trực tiếp để dùng nút tạo tải thật. Bộ thu đã chạy riêng; không cần bấm bật lại nguồn.", flush=True)
            print("Giữ cửa sổ này mở. Ctrl+C dừng các tiến trình do phiên này tạo.", flush=True)
            if not args.no_browser:
                webbrowser.open(frontend_url)
            while True:
                if any(child.poll() is not None for child in children):
                    raise DemoError("Một tiến trình demo đã dừng. Xem các tệp .runtime/live_*.log.")
                time.sleep(.5)
        finally:
            for child in reversed(children):
                _stop_owned(child)
            for log_file in logs:
                log_file.close()


def main(argv=None) -> int:
    args = arguments(argv)
    try:
        _check_dependencies()
        if args.check:
            print("Thư viện sẵn sàng. Không kết nối MySQL và không tạo tải.")
            return 0
        _run(args)
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\nĐã dừng phiên demo trực tiếp.", flush=True)
        return 0
    except (DemoError, argparse.ArgumentTypeError) as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 1
    except Exception:
        print("Không hoàn tất được phiên demo. Kiểm tra môi trường và các nhật ký live trong .runtime; thông tin nhạy cảm không được in ra.", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
