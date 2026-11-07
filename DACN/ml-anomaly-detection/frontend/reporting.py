"""Downloadable Vietnamese reports from measured results, without a second run."""
from __future__ import annotations

import pandas as pd

from src.monitoring_summary import MODEL_NAMES, evaluation_table, summarize_run


def _table(frame: pd.DataFrame) -> str:
    # Avoid an optional tabulate dependency; escape Markdown cell separators.
    def cell(value):
        if pd.isna(value):
            return "Chưa có"
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(map(str, frame.columns)) + " |",
             "| " + " | ".join("---" for _ in frame.columns) + " |"]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |"
                 for row in frame.itertuples(index=False, name=None))
    return "\n".join(lines)


def build_report_markdown(run, summary=None, source_name=None) -> bytes:
    """Export exact counts, explanations, evidence and valid-label evaluations."""
    summary = summarize_run(run) if summary is None else summary
    meta, data = run.metadata, run.predictions
    source = str(source_name or meta.get("source_name") or "Nguồn dữ liệu của lần phân tích hiện tại")
    source_kind = str(meta.get("source_kind", meta.get("source_type", ""))).lower()
    synthetic = any(word in (source + " " + source_kind).lower() for word in
                    ("demo", "mẫu", "tổng hợp", "synthetic", "mysql_normal.csv", "mysql_anomalous.csv"))
    provenance = ("Dữ liệu mẫu tổng hợp phục vụ kiểm thử kịch bản; các kết quả này không xác nhận hiệu quả trên máy chủ thật."
                  if synthetic else "Nguồn và nhãn do người dùng cung cấp; báo cáo không tự xác minh nguyên nhân sự cố.")
    comparison = meta.get("comparison")
    training_scope = (
        f"- Mô hình chung học {comparison['reference_train_rows']:,} bản ghi đầu của bộ tham chiếu bình thường; "
        f"{comparison['local_excluded_prefix_rows']:,} bản ghi đầu của bộ đang báo cáo không được chấm. "
        + ("Phần đầu bộ đối chiếu không tham gia huấn luyện." if comparison.get("role") == "anomalous" else "Phần đầu bộ này là nền huấn luyện chung.")
        if comparison else
        f"- Bản ghi huấn luyện: {meta.get('train_rows', summary['total_rows'] - summary['rows_analyzed']):,}."
    )
    lines = ["# ANOMALY LAB — Báo cáo giám sát hoạt động MySQL", "", f"Nguồn dữ liệu: {source}", "", provenance, "",
             "## Phạm vi phân tích", "",
             f"- Tổng số bản ghi: {summary['total_rows']:,}.",
             training_scope,
             f"- Bản ghi kiểm tra đã phân tích: {summary['rows_analyzed']:,}.",
             "- Thuật toán: " + ", ".join(MODEL_NAMES.get(name, name) for name in meta.get("model_names", [])) + ".",
             "- Chia theo thứ tự thời gian; số liệu kết quả chỉ thuộc phần kiểm tra. Nhãn không được dùng làm đặc trưng học."]
    time = meta.get("timestamp_col", "timestamp")
    if not data.empty and time in data:
        lines.append(f"- Khoảng kiểm tra: {data[time].iloc[0]} → {data[time].iloc[-1]} UTC.")
    lines += ["", "## Kết quả", "", f"Trạng thái: **{summary['status']}**.", "",
              f"Số bản ghi được mô hình đánh dấu ban đầu (hợp các thuật toán): {summary['raw_count']:,}.",
              f"Số bản ghi cảnh báo sau cấu hình vận hành (mỗi thời điểm chỉ tính một lần): {summary['alert_count']:,} ({summary['alert_rate']:.2%}).", "",
              summary["explanation"], "", "## Vì sao hệ thống cảnh báo?", "", summary["indicator_note"], "",
              summary["severity_rule"], "", summary["score_note"], ""]
    if summary["notable"].empty:
        lines.append("Không có thời điểm cảnh báo theo cấu hình hiện tại.")
    else:
        lines += [_table(summary["notable"]), "", "### Giá trị các chỉ số tại thời điểm cảnh báo", ""]
        evidence = summary["evidence"]
        if not evidence.empty:
            detail = evidence[["Thời gian", "name", "actual", "reference", "delta", "allowed_deviation", "unit", "material"]].rename(columns={
                "name": "Chỉ số", "actual": "Quan sát", "reference": "Trung vị học", "delta": "Độ lệch",
                "allowed_deviation": "Dung sai", "unit": "Đơn vị", "material": "Vượt dung sai",
            })
            detail["Vượt dung sai"] = detail["Vượt dung sai"].map({True: "Có", False: "Không"})
            lines.append(_table(detail))
    lines += ["", "## Việc nên kiểm tra tiếp", ""] + ["- " + item for item in summary["next_checks"]]
    lines += ["", "## Đánh giá trên nhãn kiểm thử", ""]
    metrics = evaluation_table(run)
    if metrics.empty:
        lines.append("Không có nhãn kiểm thử hợp lệ: không tính Precision, Recall, F1-score, Accuracy hoặc ma trận nhầm lẫn.")
    else:
        lines += ["Các chỉ số dưới đây được tính lại từ nhãn và dự đoán thực tế trên cùng phần kiểm tra. "
                  "Lớp bất thường là -1; lớp bình thường là 1. Mẫu số bằng 0 được quy ước trả về 0.", "",
                  "### Sau cấu hình vận hành", "", _table(metrics), "",
                  "Ma trận nhầm lẫn mỗi thuật toán: hàng là nhãn thật [bình thường, bất thường], "
                  "cột là dự đoán [bình thường, bất thường], tương ứng [[TN, FP], [FN, TP]].", "",
                  "### Dự đoán gốc của mô hình", "", _table(evaluation_table(run, raw=True))]
        label = meta.get("label_col")
        if label and not data[label].eq(-1).any():
            lines += ["", "Phần kiểm tra không có nhãn bất thường; Recall/F1 không đủ để đánh giá khả năng phát hiện. Hãy kiểm tra số báo nhầm (FP)."]
    lines += ["", "## Cấu hình và thời gian đo", "",
              f"- Bộ lọc vận hành: {'bật' if meta.get('noise_guard', {}).get('enabled', False) else 'tắt'}.",
              f"- Contamination/nu cấu hình: {meta.get('contamination', 'không có')}.",
              f"- Ngưỡng độ lệch vận hành: {meta.get('noise_guard', {}).get('deviation_threshold', 'không có')}."]
    for name, timing in meta.get("timings", {}).items():
        lines.append(f"- {MODEL_NAMES.get(name, name)}: huấn luyện {timing['train_seconds']:.6g} giây; dự đoán {timing['predict_seconds']:.6g} giây.")
    if comparison:
        lines.append("- Thời gian mô hình thuộc một lần học chung và dự đoán gộp hai bộ; không cộng thời gian lặp lại trong hai phần báo cáo.")
    lines += ["", "Không suy ra tấn công, quá tải hay nguyên nhân gốc chỉ từ điểm bất thường. "
              "Đối chiếu nhật ký, truy vấn, tài nguyên máy chủ và bối cảnh vận hành trước khi kết luận.", ""]
    return "\n".join(lines).encode("utf-8-sig")
