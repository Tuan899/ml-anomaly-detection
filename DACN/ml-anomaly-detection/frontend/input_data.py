"""Recognize common CSV headers without changing measurements or label meaning."""
from __future__ import annotations

from io import BytesIO
import re
import unicodedata

import numpy as np
import pandas as pd

from src.data_prep import read_csv_frame

METRIC_NAMES = {
    "queries_per_second": "số truy vấn mỗi giây",
    "connections": "số kết nối",
    "response_time_ms": "thời gian phản hồi (ms)",
    "slow_queries": "số truy vấn chậm trong khoảng lấy mẫu",
    "connection_errors": "số kết nối thất bại trong khoảng lấy mẫu",
}

ALIASES = {
    "timestamp": ("timestamp", "time", "datetime", "date_time", "recorded_at", "observed_at", "thoi_gian", "ngay_gio"),
    "queries_per_second": ("queries_per_second", "qps", "queries_per_sec", "questions_per_second", "so_truy_van_moi_giay"),
    "connections": ("connections", "threads_connected", "active_connections", "connection_count", "so_ket_noi"),
    "response_time_ms": ("response_time_ms", "latency_ms", "response_ms", "query_latency_ms", "thoi_gian_phan_hoi_ms", "do_tre_ms"),
    "slow_queries": ("slow_queries", "slow_query_count", "slow_queries_count", "truy_van_cham", "so_truy_van_cham"),
    "connection_errors": ("connection_errors", "connection_failures", "failed_connections", "loi_ket_noi", "so_loi_ket_noi"),
    "label": ("label", "is_anomaly", "anomaly_label", "ground_truth", "nhan"),
}


def _name(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value).strip().lower().replace("đ", "d"))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def prepare_mysql_csv(content: bytes) -> tuple[bytes, pd.DataFrame, dict[str, str]]:
    """Return canonical CSV and verified preview, preserving original input bytes.

    No values are imputed, no counters are converted into rates by guessing,
    and 0/1 label semantics are never inferred. Label columns remain optional.
    """
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("Tệp vượt quá 10 MiB. Hãy chia thành các khoảng thời gian nhỏ hơn.")
    try:
        frame = read_csv_frame(BytesIO(content))
    except (ValueError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise ValueError("Không đọc được CSV. Hãy lưu UTF-8, dùng dấu phẩy phân cách và đặt tên cột duy nhất.") from exc
    rename = {}
    for canonical, aliases in ALIASES.items():
        candidates = [column for column in frame if _name(column) in aliases]
        if len(candidates) > 1:
            raise ValueError(f"Có nhiều cột cùng biểu diễn {canonical}: {', '.join(map(str, candidates))}. Giữ một cột rõ ràng hoặc dùng cấu hình cột trong chế độ Nâng cao.")
        if candidates:
            rename[candidates[0]] = canonical
    frame = frame.rename(columns=rename)
    missing = [column for column in ("timestamp", *METRIC_NAMES) if column not in frame]
    if missing:
        descriptions = ["thời gian (timestamp)" if column == "timestamp" else f"{METRIC_NAMES[column]} ({column})" for column in missing]
        raise ValueError("Tệp còn thiếu: " + "; ".join(descriptions) + ". Bổ sung cột hoặc chọn Nâng cao để ánh xạ tên cột.")
    if len(frame) < 4:
        raise ValueError("Cần ít nhất 4 bản ghi để học mức tham chiếu và kiểm tra dữ liệu tiếp theo.")
    raw_time = frame["timestamp"]
    if pd.api.types.is_numeric_dtype(raw_time):
        raise ValueError("Cột thời gian cần ngày giờ rõ ràng, ví dụ 2026-01-01T08:00:00Z.")
    times = pd.to_datetime(raw_time, errors="coerce", utc=True)
    if times.isna().any() or times.duplicated().any():
        raise ValueError("Thời gian có ô trống, sai định dạng hoặc bị trùng. Sửa mỗi thời điểm thành một dòng rồi thử lại.")
    frame["timestamp"] = times.dt.tz_convert(None)
    for column, title in METRIC_NAMES.items():
        raw = frame[column]
        values = pd.to_numeric(raw, errors="coerce")
        if (pd.api.types.is_bool_dtype(raw) or raw.map(lambda value: isinstance(value, (bool, np.bool_))).any()
                or not np.isfinite(values.to_numpy(dtype=float, na_value=np.nan)).all() or values.lt(0).any()):
            raise ValueError(f"Cột {title} cần số hữu hạn không âm và không được bỏ trống. Ứng dụng chưa phân tích; hãy sửa dữ liệu rồi thử lại.")
        frame[column] = values
    if "label" in frame:
        labels = pd.to_numeric(frame["label"], errors="coerce")
        if pd.api.types.is_bool_dtype(frame["label"]) or not labels.isin([1, -1]).all():
            raise ValueError("Nhãn kiểm thử phải dùng 1 = bình thường, -1 = bất thường. Với nhãn 0/1, hãy xác định ý nghĩa rồi chuyển đổi trước; không tự suy đoán nhãn.")
        frame["label"] = labels.astype(int)
    frame = frame.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return frame.to_csv(index=False).encode("utf-8"), frame, rename
