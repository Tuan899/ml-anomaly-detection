"""Vietnamese, evidence-based summaries of completed monitoring runs.

This module never fits a model or changes a prediction. The dashboard's severity
is a documented demonstration policy applied *after* model detection, and its
scores are shown per estimator rather than averaged across incompatible scales.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .contracts import DetectionRun


METRIC_NAMES = {
    "queries_per_second": "Số truy vấn mỗi giây",
    "connections": "Số kết nối đang mở",
    "response_time_ms": "Thời gian phản hồi",
    "slow_queries": "Truy vấn chậm mỗi khoảng lấy mẫu",
    "connection_errors": "Kết nối thất bại mỗi khoảng lấy mẫu",
}
METRIC_UNITS = {
    "queries_per_second": "truy vấn/giây", "connections": "kết nối",
    "response_time_ms": "ms", "slow_queries": "truy vấn/khoảng",
    "connection_errors": "lỗi/khoảng",
}
MODEL_NAMES = {
    "mad": "MAD", "isolation_forest": "Isolation Forest",
    "lof": "LOF", "one_class_svm": "One-Class SVM",
}
SEVERITY_RULE = (
    "Quy tắc mức cảnh báo của bản demo: chỉ xét các bản ghi đã được mô hình "
    "cảnh báo sau cấu hình vận hành. Một điểm có mức Cảnh báo cao khi ít nhất "
    "hai chỉ số vượt khoảng tham chiếu học từ tập huấn luyện; hoặc độ lệch "
    "của một chỉ số lớn hơn hai lần dung sai dương; hoặc kết nối thất bại "
    "tăng từ mức tham chiếu bằng 0. Toàn bộ lần phân tích có mức Cảnh báo cao "
    "nếu có điểm như trên hoặc ít nhất 10% bản ghi kiểm tra được cảnh báo. "
    "Có cảnh báo còn lại là Cần chú ý; không có cảnh báo là Bình thường. "
    "Đây là quy ước vận hành minh họa, không phải giới hạn MySQL hay SLA "
    "đã được xác nhận; bản thân quy tắc này không tạo dự đoán mô hình."
)
NOTABLE_COLUMNS = [
    "Thời gian", "Chỉ số có thay đổi đáng chú ý", "Giá trị quan sát",
    "Giá trị tham chiếu", "Điểm bất thường", "Thuật toán (điểm)",
    "Mức cảnh báo", "Giải thích ngắn",
]


def alert_mask(run: DetectionRun, raw: bool = False) -> pd.Series:
    """Union of exact selected-model predictions, without duplicate counting."""
    data = run.predictions
    result = pd.Series(False, index=data.index)
    suffix = "raw_prediction" if raw else "prediction"
    for name in run.metadata.get("model_names", []):
        column = f"{name}_{suffix}"
        if column in data:
            result |= data[column].eq(-1)
    return result


def evaluation_table(run: DetectionRun, raw: bool = False) -> pd.DataFrame:
    """Recompute point metrics from valid holdout labels, never synthetic truth.

    A supplied scenario label is valid for evaluating that scenario, but is not
    evidence about real-server accuracy. No label column means no evaluation.
    """
    columns = ["Thuật toán", "Precision", "Recall", "F1-score", "Accuracy", "TN", "FP", "FN", "TP"]
    label = run.metadata.get("label_col")
    data = run.predictions
    if not label or label not in data or data.empty:
        return pd.DataFrame(columns=columns)
    truth = data[label]
    if pd.api.types.is_bool_dtype(truth) or not pd.api.types.is_numeric_dtype(truth) or not truth.isin([-1, 1]).all():
        return pd.DataFrame(columns=columns)
    suffix = "raw_prediction" if raw else "prediction"
    rows = []
    for name in run.metadata.get("model_names", []):
        column = f"{name}_{suffix}"
        if column not in data or not data[column].isin([-1, 1]).all():
            continue
        prediction = data[column]
        tp = int((truth.eq(-1) & prediction.eq(-1)).sum())
        tn = int((truth.eq(1) & prediction.eq(1)).sum())
        fp = int((truth.eq(1) & prediction.eq(-1)).sum())
        fn = int((truth.eq(-1) & prediction.eq(1)).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        rows.append({"Thuật toán": MODEL_NAMES.get(name, name), "Precision": precision,
                     "Recall": recall, "F1-score": f1, "Accuracy": (tp + tn) / len(data),
                     "TN": tn, "FP": fp, "FN": fn, "TP": tp})
    return pd.DataFrame(rows, columns=columns)


def _number(value: float) -> str:
    return f"{float(value):,.4g}"


def _evidence_for_row(row: pd.Series, baselines: dict) -> list[dict]:
    evidence = []
    for metric, name in METRIC_NAMES.items():
        baseline = baselines.get(metric)
        if metric not in row or not baseline or "allowed_deviation" not in baseline:
            continue
        actual, reference = float(row[metric]), float(baseline["median"])
        tolerance = float(baseline["allowed_deviation"])
        delta = actual - reference
        # A zero tolerance is a count convention, not an infinite model score.
        material = abs(delta) > tolerance
        ratio = abs(delta) / tolerance if tolerance > 0 else (np.inf if delta else 0.0)
        evidence.append({"metric": metric, "name": name, "actual": actual,
                         "reference": reference, "delta": delta,
                         "allowed_deviation": tolerance, "material": material,
                         "deviation_ratio": ratio, "unit": METRIC_UNITS[metric]})
    return evidence


def _intervals(data: pd.DataFrame, time: str, flags: pd.Series) -> list[dict]:
    """Groups consecutive alerted observations; never invents gap durations."""
    intervals, current = [], None
    for position, flagged in enumerate(flags.to_numpy(dtype=bool)):
        if flagged:
            timestamp = data.iloc[position][time]
            if current is None:
                current = {"start": timestamp, "end": timestamp, "count": 1}
            else:
                current["end"], current["count"] = timestamp, current["count"] + 1
        elif current is not None:
            intervals.append(current)
            current = None
    if current is not None:
        intervals.append(current)
    return intervals


def summarize_run(run: DetectionRun) -> dict:
    """Answer what happened, when, and what to inspect using measured evidence."""
    data, meta = run.predictions, run.metadata
    names = meta.get("model_names", [])
    time = meta.get("timestamp_col", "timestamp")
    flags, raw_flags = alert_mask(run), alert_mask(run, raw=True)
    count, rows = int(flags.sum()), len(data)
    rate = count / rows if rows else 0.0
    baselines = meta.get("train_baselines", {})
    notable, all_evidence, material_metrics = [], [], set()
    high_points = 0
    for position in np.flatnonzero(flags.to_numpy()):
        row = data.iloc[position]
        evidence = _evidence_for_row(row, baselines)
        changed = [item for item in evidence if item["material"]]
        high = (len(changed) >= 2
                or any(item["allowed_deviation"] > 0 and item["deviation_ratio"] > 2 for item in changed)
                or any(item["metric"] == "connection_errors" and item["reference"] == 0
                       and item["actual"] > 0 for item in changed))
        high_points += int(high)
        detecting = [name for name in names if row.get(f"{name}_prediction", 1) == -1]
        # Select one detecting model; do not choose by incomparable score size.
        model = "mad" if "mad" in detecting else detecting[0]
        raw_score = row.get(f"{model}_score", np.nan)
        score = -float(raw_score) if pd.notna(raw_score) else np.nan
        selected = max(changed or evidence, key=lambda item: item["deviation_ratio"], default=None)
        for item in evidence:
            all_evidence.append({"Thời gian": row[time], **item,
                                 "models": ", ".join(MODEL_NAMES.get(name, name) for name in detecting)})
        material_metrics.update(item["metric"] for item in changed)
        if selected:
            direction = "tăng" if selected["delta"] > 0 else "giảm" if selected["delta"] < 0 else "giữ nguyên"
            detail = (f"{selected['name']} {direction}: {_number(selected['actual'])} "
                      f"{selected['unit']}; trung vị học {_number(selected['reference'])}; "
                      f"dung sai ±{_number(selected['allowed_deviation'])}.")
            if not changed:
                detail += " Chưa chỉ số riêng lẻ nào vượt dung sai; cần kiểm tra quan hệ đa chỉ số và cấu hình mô hình."
        else:
            detail = "Mô hình đánh dấu điểm khác với dữ liệu tham chiếu; chưa có thống kê từng chỉ số để giải thích."
        detail += " Đây là dấu hiệu nghi ngờ, chưa xác nhận nguyên nhân."
        notable.append({
            "Thời gian": row[time],
            "Chỉ số có thay đổi đáng chú ý": selected["name"] if selected else "Quan hệ đa chỉ số",
            "Giá trị quan sát": selected["actual"] if selected else np.nan,
            "Giá trị tham chiếu": selected["reference"] if selected else np.nan,
            "Điểm bất thường": score, "Thuật toán (điểm)": MODEL_NAMES.get(model, model),
            "Mức cảnh báo": "Cảnh báo cao" if high else "Cần chú ý", "Giải thích ngắn": detail,
        })
    if not count:
        level, status = "normal", "Bình thường"
        explanation = (f"Không có cảnh báo vận hành trong {rows:,} bản ghi kiểm tra theo cấu hình hiện tại. "
                       "Các dao động nhỏ trong khoảng tham chiếu không tự động trở thành cảnh báo.")
        if int(raw_flags.sum()):
            explanation += f" Mô hình đánh dấu {int(raw_flags.sum()):,} bản ghi ban đầu; bộ lọc vận hành đã loại các điểm này."
        explanation += " Kết quả này không bảo đảm máy chủ không có sự cố."
    else:
        level, status = ("high", "Cảnh báo cao") if high_points or rate >= .1 else ("attention", "Cần chú ý")
        indicators = ", ".join(METRIC_NAMES[metric].lower() for metric in METRIC_NAMES if metric in material_metrics)
        explanation = (f"Phát hiện {count:,}/{rows:,} bản ghi kiểm tra có cảnh báo ({rate:.1%}). "
                       + (f"Dấu hiệu đo được liên quan đến {indicators}. " if indicators else
                          "Chưa có chỉ số riêng lẻ vượt dung sai tham chiếu; mô hình có thể phản ứng với quan hệ đa chỉ số. ")
                       + "Đối chiếu các thời điểm được đánh dấu trước khi kết luận nguyên nhân.")
    next_checks = []
    if "queries_per_second" in material_metrics:
        next_checks.append("Đối chiếu lưu lượng ứng dụng và các truy vấn tại thời điểm cảnh báo; kiểm tra có tác vụ định kỳ hay tăng tải dự kiến.")
    if "connections" in material_metrics:
        next_checks.append("Kiểm tra nhóm kết nối ứng dụng, kết nối đang mở và giới hạn max_connections.")
    if {"response_time_ms", "slow_queries"} & material_metrics:
        next_checks.append("Đối chiếu slow query log, kế hoạch thực thi, khóa chờ và tải CPU/I/O trong cùng khoảng thời gian.")
    if "connection_errors" in material_metrics:
        next_checks.append("Đối chiếu log lỗi MySQL, giới hạn kết nối và tình trạng mạng; số lỗi kết nối chưa xác định được nguồn lỗi.")
    if not next_checks:
        next_checks.append("Tiếp tục thu thập số liệu và đối chiếu log vận hành; kiểm tra lại khoảng học có đại diện cho hoạt động bình thường hay không.")
    return {
        "rows_analyzed": rows, "total_rows": len(run.frame), "alert_count": count,
        "raw_count": int(raw_flags.sum()), "alert_rate": rate,
        "status": status, "status_level": level, "explanation": explanation,
        "next_checks": next_checks, "severity_rule": SEVERITY_RULE,
        "notable": pd.DataFrame(notable, columns=NOTABLE_COLUMNS),
        "evidence": pd.DataFrame(all_evidence),
        "intervals": _intervals(data, time, flags) if time in data else [],
        "high_point_count": high_points,
        "dataset_summary": {metric: {"mean": float(data[metric].mean()),
                                      "min": float(data[metric].min()), "max": float(data[metric].max())}
                            for metric in METRIC_NAMES if metric in data and not data.empty},
        "model_counts": {name: {"alerts": int(data[f"{name}_prediction"].eq(-1).sum()),
                                "raw": int(data.get(f"{name}_raw_prediction", data[f"{name}_prediction"]).eq(-1).sum())}
                         for name in names if f"{name}_prediction" in data},
        "score_note": "Điểm hiển thị = âm điểm quyết định gốc; điểm càng lớn càng nghi ngờ trong cùng thuật toán. Không so sánh trực tiếp điểm giữa các thuật toán.",
        "indicator_note": "Các chỉ số là dấu hiệu có thể kiểm chứng, chưa phải nguyên nhân đã xác minh. Dữ liệu kết nối thất bại không phải tỷ lệ truy vấn lỗi; chưa có số truy vấn lỗi để tính tỷ lệ này.",
    }
