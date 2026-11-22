"""Fixed synthetic K1–K4 workloads, defined independently of model predictions.

The normal training window and the replay window are disjoint. Fault buttons
modify these simulated measurements only; they never execute workload SQL.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random


METRICS = ("queries_per_second", "connections", "response_time_ms", "slow_queries", "connection_errors")
LOCAL_ZONE = timezone(timedelta(hours=7))
BASELINE_START = datetime(2026, 11, 1, 0, 0, tzinfo=LOCAL_ZONE)
REPLAY_START = datetime(2026, 11, 1, 12, 0, tzinfo=LOCAL_ZONE)
_CATALOG = (
    {"id": "K1", "name": "K1 · Hoạt động bình thường",
     "description": "Các chỉ số dao động nhẹ quanh mức nền, không chèn sự cố."},
    {"id": "K2", "name": "K2 · Tăng truy vấn",
     "description": "QPS tăng từ khoảng 50 lên 300–350; các chỉ số khác giữ nguyên."},
    {"id": "K3", "name": "K3 · Tăng kết nối và lỗi",
     "description": "Số kết nối tăng lên 120–180 và xuất hiện 5–10 kết nối thất bại trong khoảng lấy mẫu."},
    {"id": "K4", "name": "K4 · Độ trễ và truy vấn chậm",
     "description": "Độ trễ tăng lên 180–220 ms và có 8–10 truy vấn chậm trong khoảng lấy mẫu."},
)


def scenario_catalog() -> list[dict]:
    return [dict(item, synthetic=True, sampling_interval_seconds=1, default_rows=180,
                 default_incident_start=60 if item["id"] != "K1" else None,
                 default_incident_end_exclusive=90 if item["id"] != "K1" else None)
            for item in _CATALOG]


def _count(rows: int, minimum: int = 1) -> int:
    if isinstance(rows, bool) or not isinstance(rows, int) or not minimum <= rows <= 10000:
        raise ValueError(f"Số dòng phải là số nguyên từ {minimum} đến 10000.")
    return rows


def _normal_records(rows: int, seed: int, start: datetime) -> list[dict]:
    rng = random.Random(seed)
    records = []
    for index in range(rows):
        noise = lambda: max(-2.5, min(2.5, rng.gauss(0, 1)))
        records.append({
            "timestamp": (start + timedelta(seconds=index)).isoformat(),
            "queries_per_second": round(50 + 1.5 * noise(), 3),
            "connections": 30 + rng.randint(-2, 2),
            "response_time_ms": round(15 + .4 * noise(), 3),
            "slow_queries": int(rng.random() < .15),
            "connection_errors": 0,
            "label": 1,
            "scenario": "K1",
        })
    return records


def baseline_records(rows: int = 300) -> list[dict]:
    """Normal-only training observations, never copied out of the test window."""
    return _normal_records(_count(rows, 30), 20261121, BASELINE_START)


def inject_record(record: dict, scenario: str) -> dict:
    """Return an injected copy; caller-owned records and real servers are untouched."""
    if scenario not in {"K2", "K3", "K4"}:
        raise ValueError("Chọn một kịch bản mô phỏng K2, K3 hoặc K4.")
    result = dict(record)
    phase = datetime.fromisoformat(str(record["timestamp"]).replace("Z", "+00:00")).second
    if scenario == "K2":
        result["queries_per_second"] = 300 + 5 * (phase % 11)
    elif scenario == "K3":
        result["connections"] = 120 + 6 * (phase % 11)
        result["connection_errors"] = 5 + phase % 6
    else:
        result["response_time_ms"] = 180 + 4 * (phase % 11)
        result["slow_queries"] = 8 + phase % 3
    result.update(label=-1, scenario=scenario)
    return result


def scenario_records(scenario: str, rows: int = 180) -> list[dict]:
    if scenario not in {item["id"] for item in _CATALOG}:
        raise ValueError("Kịch bản phải là K1, K2, K3 hoặc K4.")
    records = _normal_records(_count(rows), 20261122, REPLAY_START)
    start, end = len(records) // 3, len(records) // 2
    for index, record in enumerate(records):
        record["scenario"] = scenario
        if scenario != "K1" and start <= index < end:
            records[index] = inject_record(record, scenario)
    return records
