"""Run the independent read-only collector; secrets come from environment only.

Example: python scripts/run_collector.py --backend-url http://127.0.0.1:8000
Required environment: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD.
Optional: MYSQL_PORT, MYSQL_DATABASE, MYSQL_SSL_CA. TLS verification is default.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import sys
from threading import Event

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.live_collector import CollectorConfig, run_collector


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-url", default=os.environ.get("ANOMALY_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--samples", type=int, default=None, help="Stop after this many sent samples; otherwise keep running.")
    parser.add_argument("--no-tls", action="store_true", help="Explicitly disable TLS for a controlled local demo server only.")
    args = parser.parse_args()
    stop = Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
    messages = {"connected": "Đã kết nối bộ thu; chờ khoảng đo đầu tiên.",
                "counter_reset": "Bộ đếm bị đặt lại: bỏ qua chu kỳ này và lấy lại mốc nền.",
                "invalid_sample": "Mẫu chưa hợp lệ; đang kết nối lại và lấy mốc mới.",
                "connection_error": "Nguồn đo bị ngắt; đang thử kết nối lại.",
                "backend_unavailable": "Dịch vụ phân tích chưa nhận được mẫu; đang thử gửi lại."}
    def notify(status):
        if status in messages:
            print(messages[status], flush=True)
    try:
        port = int(os.environ.get("MYSQL_PORT", "3306"))
        config = CollectorConfig(host=os.environ.get("MYSQL_HOST", ""),
            user=os.environ.get("MYSQL_USER", ""), password=os.environ.get("MYSQL_PASSWORD", ""),
            port=port, database=os.environ.get("MYSQL_DATABASE") or None,
            interval_seconds=args.interval, ssl_ca=os.environ.get("MYSQL_SSL_CA") or None,
            ssl_disabled=args.no_tls)
        config.validate()
        count = run_collector(config, backend_url=args.backend_url, max_samples=args.samples,
                              stop_event=stop, status_callback=notify)
        print(f"Đã dừng bộ thu; gửi thành công {count} mẫu.", flush=True)
        return 0
    except (ValueError, RuntimeError) as exc:
        # These are our sanitized errors, never raw driver exceptions.
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
