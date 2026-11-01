"""Testable presentation helpers for the Vietnamese dashboard."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data_prep import LABEL_COLUMNS


def metric_candidates(frame: pd.DataFrame, timestamp_col: str) -> list[str]:
    """Offer measurements, excluding timestamps, labels and booleans."""
    candidates = []
    for name in frame.columns:
        if name == timestamp_col or str(name).lower() in LABEL_COLUMNS:
            continue
        if pd.api.types.is_bool_dtype(frame[name]):
            continue
        values = pd.to_numeric(frame[name], errors="coerce")
        if np.isfinite(values.to_numpy(dtype=float, na_value=np.nan)).any():
            candidates.append(name)
    return candidates


def error_message(error: Exception) -> str:
    """Translate validation failures into instructions, without a traceback."""
    if isinstance(error, UnicodeDecodeError):
        return "Không đọc được bảng mã. Hãy lưu CSV với bảng mã UTF-8 rồi tải lại."
    if isinstance(error, pd.errors.ParserError):
        return "Các dòng CSV có số cột không khớp. Hãy kiểm tra dấu phẩy, dấu ngoặc kép và dòng tiêu đề."
    translations = (
        (("empty", "contain data rows", "no columns to parse"), "CSV chưa có dữ liệu. Hãy thêm dòng tiêu đề và ít nhất 4 dòng đo."),
        (("column names must be unique", "duplicate column"), "Tên cột bị trùng. Hãy đặt tên riêng cho từng cột trong CSV."),
        (("row fields",), "Số trường trên các dòng CSV không khớp tiêu đề. Hãy kiểm tra dấu phẩy và số cột."),
        (("conflict with generated",), "Tên cột đầu vào trùng với tên cột kết quả. Hãy đổi tên cột đó rồi tải lại."),
        (("missing timestamp",), "Không tìm thấy cột thời gian. Hãy chọn lại cột chứa ngày giờ đo."),
        (("invalid timestamp", "timestamps must not be missing"), "Cột thời gian có giá trị trống hoặc sai định dạng. Hãy dùng ngày giờ như 2026-01-01 08:00:00."),
        (("duplicate timestamp",), "Có nhiều dòng cùng thời điểm. Hãy gộp chúng hoặc giữ một dòng cho mỗi thời điểm rồi tải lại."),
        (("missing value column", "numeric activity metric", "activity metric, not", "boolean columns"), "Chưa có cột số phù hợp. Không chọn thời gian, nhãn hoặc cột đúng/sai làm chỉ số đo."),
        (("no finite numeric", "finite numbers", "finite numeric", "real numeric"), "Cột giá trị không có đủ số hợp lệ. Hãy kiểm tra ô trống, văn bản và các giá trị vô hạn."),
        (("missing label column",), "Không tìm thấy cột nhãn. Hãy chọn lại nhãn tham chiếu hoặc chọn Không dùng nhãn."),
        (("labels must", "label columns must not", "ground-truth label", "label column must not"), "Nhãn phải dùng 1 cho bình thường và -1 cho bất thường, không để trống. Không dùng cột nhãn làm chỉ số đo."),
        (("must be distinct",), "Cột thời gian, cột giá trị và cột nhãn phải khác nhau."),
        (("training rows", "at least 3", "split_index", "adjust split"), "Cần ít nhất 3 dòng huấn luyện và 1 dòng kiểm tra sau làm sạch. Hãy bổ sung dữ liệu hoặc điều chỉnh tỷ lệ huấn luyện."),
        (("select unique algorithms", "model_names must", "unknown model"), "Hãy chọn ít nhất một thuật toán được hỗ trợ."),
        (("contamination",), "Tỷ lệ bất thường dự kiến chưa hợp lệ. Hãy chọn lại trong thanh cấu hình."),
        (("train_fraction",), "Tỷ lệ huấn luyện chưa hợp lệ. Hãy chọn lại trong thanh cấu hình."),
        (("too large", "overflow", "non-finite scores"), "Giá trị đo quá lớn để tính toán ổn định. Hãy đổi đơn vị hoặc giảm độ lớn của chỉ số rồi thử lại."),
    )
    lowered = str(error).lower()
    for patterns, translated in translations:
        if any(pattern in lowered for pattern in patterns):
            return translated
    return "Không thể phân tích tệp này. Hãy kiểm tra cột thời gian, cột số và quy ước nhãn 1/-1 rồi thử lại."


def warning_message(message: str) -> str:
    """Keep research limitations visible in the user's language."""
    if message.startswith("Small dataset"):
        return "Dữ liệu có dưới 100 dòng: phù hợp để thử thao tác, chưa đủ để kết luận chất lượng phát hiện."
    if message.startswith("No ground-truth"):
        return "Chưa chọn nhãn tham chiếu: hệ thống chỉ thống kê cảnh báo, chưa tính Precision, Recall và F1."
    if message.startswith("Test labels contain no anomalies"):
        return "Nhãn của tập kiểm tra không có điểm bất thường. Recall và F1 chưa đủ cơ sở để đánh giá khả năng phát hiện."
    if "calendar features" in message or message.startswith("MAD uses the value"):
        return "Đã thêm đặc trưng giờ và ngày. Các thời điểm hiếm gặp cũng có thể tạo cảnh báo; hãy kiểm tra lại ngữ cảnh."
    if message.startswith("Rows with missing"):
        return "Đã loại dòng có giá trị trống, không phải số hoặc vô hạn trước khi chia tập. Xem số dòng ở phần Chất lượng dữ liệu."
    return "Có lưu ý về dữ liệu hoặc mô hình. Hãy xem thông số đầy đủ trong tệp JSON tải xuống."
