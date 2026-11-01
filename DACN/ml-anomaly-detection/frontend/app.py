"""Vietnamese dashboard: select data, configure a run, inspect current results."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.helpers import error_message, metric_candidates, warning_message
from src.data_prep import load_timeseries, read_csv_frame
from src.eda import seasonality_figure
from src.pipeline import DetectionRun, run_detection

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MODEL_LABELS = {
    "mad": "MAD · độ lệch so với trung vị",
    "isolation_forest": "Isolation Forest",
    "lof": "LOF · mật độ lân cận",
    "one_class_svm": "One-Class SVM",
}
MODEL_DESCRIPTIONS = {
    "mad": "So giá trị với trung vị và độ phân tán của tập huấn luyện. Ngưỡng robust Z-score mặc định là 3,5.",
    "isolation_forest": "Tìm các điểm dễ bị tách riêng khỏi phần lớn dữ liệu bằng các cây phân chia ngẫu nhiên.",
    "lof": "So mật độ của một điểm với các điểm lân cận. Điểm ở vùng thưa hơn có thể được cảnh báo.",
    "one_class_svm": "Học vùng chứa phần lớn dữ liệu huấn luyện và cảnh báo các điểm nằm ngoài vùng đó.",
}


def apply_style(dark: bool) -> None:
    """Use a consistent palette across the page, sidebar and charts."""
    palette = (
        {"bg": "#101827", "surface": "#182338", "text": "#e5edf9", "muted": "#a4b4ce", "line": "#2e405c", "accent": "#a5b4fc", "soft": "#222e50"}
        if dark else
        {"bg": "#f5f7fb", "surface": "#ffffff", "text": "#17233b", "muted": "#52627b", "line": "#dce3ef", "accent": "#4338ca", "soft": "#eef0ff"}
    )
    st.markdown("""<style>
    :root, .stApp, [data-testid="stSidebar"] {
        --page-bg:%(bg)s; --surface:%(surface)s; --ink:%(text)s;
        --muted:%(muted)s; --line:%(line)s; --accent:%(accent)s; --soft:%(soft)s;
    }
    .stApp {background:var(--page-bg); color:var(--ink);}
    [data-testid="stHeader"] {background:var(--page-bg);}
    [data-testid="stExpandSidebarButton"] button,
    [data-testid="stSidebarCollapseButton"] button,
    button[aria-label="Expand sidebar"], button[aria-label="Collapse sidebar"] {color:var(--ink);}
    [data-testid="stSidebar"] {background:var(--surface); border-right:1px solid var(--line);}
    .block-container {max-width:1380px; padding-top:4.8rem; padding-bottom:3rem;}
    [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"],
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"],
    [data-testid="stCaptionContainer"], [data-testid="stExpander"] {color:var(--ink);}
    [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3 {color:var(--ink); letter-spacing:-.035em;}
    [data-testid="stVerticalBlockBorderWrapper"] > div {border-color:var(--line);}
    [data-testid="stMetric"] {background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:16px;}
    [data-testid="stMetricValue"] {font-size:1.8rem;}
    [data-testid="stBaseButton-primary"] {background:#4f46e5; border-color:#4f46e5; color:white; border-radius:9px; min-height:2.8rem;}
    [data-testid="stBaseButton-primary"] [data-testid="stMarkdownContainer"] {color:white;}
    [data-testid="stBaseButton-primary"]:disabled {opacity:.5;}
    [data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button {
        background:var(--surface); color:var(--ink); border-color:var(--line); border-radius:9px;
    }
    [data-baseweb="select"] > div, [data-baseweb="input"] > div,
    [data-baseweb="popover"] ul {background:var(--surface); color:var(--ink);}
    [data-testid="stSelectbox"] .react-aria-ComboBox > [role="group"],
    [data-testid="stMultiSelect"] .react-aria-ComboBox > [role="group"] {
        background:var(--surface); color:var(--ink); border:1px solid var(--line); border-radius:8px;
    }
    [data-testid="stSelectbox"] input, [data-testid="stMultiSelect"] input {
        color:var(--ink); background:transparent;
    }
    [data-testid="stSelectbox"] button, [data-testid="stMultiSelect"] button {color:var(--muted);}
    [data-testid="stMultiSelect"] [data-tag] {background:var(--soft); color:var(--accent);}
    [role="listbox"], [role="option"] {background:var(--surface); color:var(--ink);}
    [role="option"][data-focused], [role="option"][aria-selected="true"] {background:var(--soft); color:var(--accent);}
    [data-testid="stTooltipIcon"] button {color:var(--muted);}
    [data-testid="stFileUploaderDropzone"] {background:var(--surface); color:var(--ink);}
    button[data-baseweb="tab"] {color:var(--muted);}
    button[data-baseweb="tab"][aria-selected="true"] {color:var(--accent);}
    .brand {font-size:1.05rem; font-weight:750; color:var(--accent); margin-bottom:2px;}
    .eyebrow {color:var(--accent); font-size:.72rem; font-weight:750; letter-spacing:.14em; margin-bottom:8px;}
    .hero {padding:0 0 22px;}
    .hero h1 {font-size:clamp(1.8rem,3vw,2.6rem); font-weight:750; line-height:1.2; margin:0 0 12px; color:var(--ink);}
    .hero p {color:var(--muted); margin:0; max-width:780px; line-height:1.65;}
    .steps {display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin:4px 0 25px;}
    .step {background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:13px 16px; color:var(--ink); font-size:.9rem;}
    .step b {display:inline-grid; place-items:center; width:26px; height:26px; background:var(--soft); color:var(--accent); border-radius:7px; margin-right:9px;}
    .empty-state {padding:35px 24px; text-align:center; background:var(--surface); border:1px dashed var(--line); border-radius:12px; margin-top:12px;}
    .empty-state strong {display:block; font-size:1.1rem; color:var(--ink); margin-bottom:7px;}
    .empty-state p {color:var(--muted); margin:0; font-size:.92rem;}
    @media(max-width:700px) {
        .block-container {padding:4.5rem 1rem 2rem;}
        .steps {grid-template-columns:1fr; gap:7px;}
        .step {padding:9px 12px;}
        [data-testid="stMetric"] {padding:10px;}
    }
    </style>""" % palette, unsafe_allow_html=True)


@st.cache_data(show_spinner=False, max_entries=4)
def read_preview(content: bytes) -> pd.DataFrame:
    return read_csv_frame(BytesIO(content))


@st.cache_data(show_spinner=False, max_entries=4)
def validated_row_count(content: bytes, timestamp_col: str, value_col: str) -> int:
    """Validate and sort once per file/column selection, rather than per widget."""
    return len(load_timeseries(read_preview(content), timestamp_col, value_col))


def show_table(frame: pd.DataFrame, dark: bool, **options) -> None:
    """Keep cell text readable even when the browser's native theme differs."""
    styled = frame.style.set_properties(**{
        "background-color": "#182338" if dark else "#ffffff",
        "color": "#e5edf9" if dark else "#17233b",
    })
    st.dataframe(styled, width="stretch", hide_index=True, **options)


def show_help() -> None:
    st.markdown("### Đọc kết quả như thế nào?")
    st.markdown(
        "1. **Chọn dữ liệu:** CSV cần một cột ngày giờ và một cột số cần theo dõi.\n"
        "2. **Cấu hình:** chọn đúng cột, thuật toán và tỷ lệ huấn luyện ở thanh bên.\n"
        "3. **Phân tích:** bấm **Chạy phát hiện**, kiểm tra cảnh báo rồi tải kết quả."
    )
    st.info("Phần đầu chuỗi thời gian dùng để huấn luyện; phần cuối dùng để kiểm tra. Mô hình chỉ dự đoán trên phần kiểm tra. Cảnh báo là gợi ý cần xem xét, chưa phải lỗi đã được xác nhận.")
    for name, description in MODEL_DESCRIPTIONS.items():
        st.markdown(f"**{MODEL_LABELS[name]}** — {description}")
    st.markdown("### Những thông số cần biết")
    st.markdown(
        "- **Tỷ lệ bất thường dự kiến:** giúp đặt ngưỡng cho Isolation Forest, LOF và tham số nu của SVM. Không đảm bảo tỷ lệ cảnh báo trên tập kiểm tra bằng con số này. MAD dùng ngưỡng riêng 3,5.\n"
        "- **Nhãn tham chiếu:** cột do bạn cung cấp, dùng **1 = bình thường**, **-1 = bất thường**. Chỉ dùng để đánh giá, không đưa vào huấn luyện.\n"
        "- **Điểm quyết định:** điểm càng lớn càng nghiêng về bình thường trong cùng một mô hình. Không so sánh trực tiếp điểm giữa các thuật toán.\n"
        "- **Đặc trưng chu kỳ:** bổ sung giờ và ngày; thời điểm hiếm gặp có thể tạo cảnh báo ngay cả khi giá trị đo không tăng mạnh."
    )
    st.caption("Phạm vi: phân tích CSV ngoại tuyến, chưa kết nối trực tiếp cơ sở dữ liệu hoặc giám sát thời gian thực. CSV/JSON xuất ra giữ tên cột kỹ thuật để dùng lại với API.")


def show_trend(run: DetectionRun, model_name: str, dark: bool) -> None:
    frame, predictions, metadata = run.frame, run.predictions, run.metadata
    time_col, value_col = metadata["timestamp_col"], metadata["value_col"]
    flagged = predictions.loc[predictions[f"{model_name}_prediction"] == -1]
    figure = go.Figure()
    figure.add_trace(go.Scatter(
        x=frame[time_col], y=frame[value_col], mode="lines", name="Giá trị đo",
        line={"color": "#a5b4fc" if dark else "#6366f1", "width": 2},
    ))
    figure.add_trace(go.Scatter(
        x=flagged[time_col], y=flagged[value_col], mode="markers", name="Điểm được cảnh báo",
        marker={"color": "#f97316", "size": 11, "symbol": "x", "line": {"width": 2}},
    ))
    if metadata.get("label_col"):
        truth = predictions.loc[predictions[metadata["label_col"]] == -1]
        figure.add_trace(go.Scatter(
            x=truth[time_col], y=truth[value_col], mode="markers", name="Nhãn bất thường tham chiếu",
            marker={"color": "#14b8a6", "size": 16, "symbol": "circle-open", "line": {"width": 2}},
        ))
    boundary = predictions[time_col].iloc[0].isoformat()
    figure.add_vrect(x0=boundary, x1=frame[time_col].iloc[-1].isoformat(), fillcolor="#818cf8", opacity=.08, line_width=0)
    figure.add_vline(x=boundary, line_dash="dash", line_color="#94a3b8")
    figure.add_annotation(x=boundary, y=1, yref="paper", text="Bắt đầu tập kiểm tra", showarrow=False, yshift=15)
    figure.update_layout(
        template="plotly_dark" if dark else "plotly_white", height=440,
        font={"color": "#e5edf9" if dark else "#17233b"},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 15, "r": 15, "t": 45, "b": 25}, hovermode="x unified",
        xaxis_title="Thời gian (UTC)", yaxis_title=value_col,
        legend={"orientation": "h", "y": -.22, "x": 0},
    )
    st.plotly_chart(figure, width="stretch", theme=None, config={"displaylogo": False})
    st.caption("Vùng nền tím là tập kiểm tra; dấu × màu cam là điểm mô hình cảnh báo. Phần bên trái mốc chia cung cấp bối cảnh huấn luyện.")


def show_results(run: DetectionRun, source_name: str, dark: bool) -> None:
    metadata, predictions = run.metadata, run.predictions
    names = metadata["model_names"]
    count = int(predictions[[f"{name}_prediction" for name in names]].eq(-1).any(axis=1).sum())
    st.subheader("3. Kết quả phân tích")
    st.caption(f"Nguồn: {source_name} · Chỉ thống kê dự đoán trên {len(predictions):,} dòng kiểm tra.")
    cards = st.columns(4)
    for card, label, value, help_text in (
        (cards[0], "Điểm kiểm tra", f"{len(predictions):,}", "Các điểm nằm sau phần huấn luyện theo thứ tự thời gian."),
        (cards[1], "Điểm cần xem xét", f"{count:,}", "Điểm được ít nhất một thuật toán cảnh báo; mỗi điểm chỉ đếm một lần."),
        (cards[2], "Tỷ lệ cần xem xét", f"{count / len(predictions):.1%}", "Số điểm cần xem xét chia cho số điểm kiểm tra; không phải độ chính xác."),
        (cards[3], "Thuật toán đã chạy", str(len(names)), "Mỗi thuật toán có thể đưa ra cảnh báo khác nhau."),
    ):
        card.metric(label, value, help=help_text)
    for message in metadata.get("warnings", []):
        if not message.startswith(("No ground-truth", "Small dataset")):
            st.warning(warning_message(str(message)))

    overview, details, evaluation, guide = st.tabs(["Tổng quan", "Chi tiết", "Đánh giá", "Hướng dẫn"])
    with overview:
        st.markdown("#### Diễn biến và cảnh báo")
        name = st.selectbox("Thuật toán hiển thị trên biểu đồ", names, format_func=MODEL_LABELS.get, key="chart_model")
        show_trend(run, name, dark)
        st.markdown("#### So sánh số cảnh báo")
        rows = []
        for name in names:
            flagged = int(predictions[f"{name}_prediction"].eq(-1).sum())
            timings = metadata.get("timings", {}).get(name, {})
            rows.append({
                "Thuật toán": MODEL_LABELS[name], "Bình thường": len(predictions) - flagged, "Cảnh báo": flagged,
                "Tỷ lệ cảnh báo": flagged / len(predictions) * 100,
                "Thời gian (giây)": timings.get("train_seconds", 0) + timings.get("predict_seconds", 0),
            })
        show_table(pd.DataFrame(rows), dark, column_config={
            "Tỷ lệ cảnh báo": st.column_config.NumberColumn(format="%.1f%%"),
            "Thời gian (giây)": st.column_config.NumberColumn(format="%.3f"),
        })
        st.caption("Nhiều cảnh báo hơn không đồng nghĩa với phát hiện chính xác hơn. Các thuật toán có thể cảnh báo cùng một điểm.")
        with st.expander("Chất lượng dữ liệu và cách chia tập"):
            cleaning = metadata.get("cleaning", {})
            st.write(f"Đầu vào: **{cleaning.get('input_rows', len(run.frame)):,} dòng** · Loại bỏ: **{cleaning.get('dropped_rows', 0):,} dòng** · Còn lại: **{len(run.frame):,} dòng**.")
            st.write(f"Huấn luyện: **{metadata['train_rows']:,} dòng đầu** · Kiểm tra: **{metadata['test_rows']:,} dòng cuối**.")
            st.caption("Loại dòng có giá trị trống, không phải số hoặc vô hạn. Dữ liệu được sắp xếp theo thời gian; thời gian có múi giờ được quy đổi về UTC.")
            st.write("Đặc trưng đã dùng: " + ", ".join(metadata["features"]))
        with st.expander("Khám phá chu kỳ theo giờ và ngày"):
            figure = seasonality_figure(run.frame, metadata["value_col"], metadata["timestamp_col"])
            figure.update_layout(
                template="plotly_dark" if dark else "plotly_white", height=360,
                font={"color": "#e5edf9" if dark else "#17233b"},
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", title="Giá trị trung bình theo thời điểm",
                showlegend=False, xaxis2={"tickmode": "array", "tickvals": list(range(7)), "ticktext": ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]},
            )
            st.plotly_chart(figure, width="stretch", theme=None, config={"displaylogo": False})
            st.caption("Biểu đồ mô tả toàn bộ dữ liệu. Cần nhiều chu kỳ quan sát để kết luận về quy luật lặp lại.")
    with details:
        st.markdown("#### Kiểm tra từng điểm dữ liệu")
        left, right = st.columns([2, 1])
        name = left.selectbox("Thuật toán cần xem", names, format_func=MODEL_LABELS.get, key="detail_model")
        view = right.radio("Lọc kết quả", ["Chỉ cảnh báo", "Tất cả", "Bình thường"], key="detail_filter")
        selected = predictions
        if view != "Tất cả":
            selected = predictions.loc[predictions[f"{name}_prediction"].eq(-1 if view == "Chỉ cảnh báo" else 1)]
        display = pd.DataFrame({
            "Thời gian (UTC)": selected[metadata["timestamp_col"]], "Giá trị đo": selected[metadata["value_col"]],
            "Kết luận": selected[f"{name}_prediction"].map({1: "Bình thường", -1: "Cần xem xét"}),
            "Điểm quyết định": selected[f"{name}_score"],
        })
        if metadata.get("label_col"):
            display["Nhãn tham chiếu"] = selected[metadata["label_col"]].map({1: "Bình thường", -1: "Bất thường"})
        st.caption(f"{len(display):,} điểm phù hợp bộ lọc. Điểm quyết định càng lớn càng nghiêng về bình thường trong cùng mô hình.")
        if display.empty:
            st.info("Không có điểm nào phù hợp bộ lọc này. Bạn có thể chuyển sang Tất cả để xem dự đoán.")
        else:
            show_table(display.head(1000), dark, column_config={"Điểm quyết định": st.column_config.NumberColumn(format="%.5f")})
            if len(display) > 1000:
                st.caption("Bảng hiển thị 1.000 điểm đầu tiên. Tải CSV bên dưới để xem đầy đủ.")
    with evaluation:
        st.markdown("#### Đối chiếu với nhãn tham chiếu")
        if not run.metrics:
            st.info("Chưa chọn nhãn tham chiếu nên chưa thể tính Precision, Recall và F1. Nếu CSV có nhãn 1/-1, hãy chọn cột nhãn ở thanh bên rồi chạy lại.")
        else:
            metric_rows, confusion_rows = [], []
            truth = predictions[metadata["label_col"]].eq(-1)
            for name, values in run.metrics.items():
                metric_rows.append({"Thuật toán": MODEL_LABELS[name], **{key: value * 100 for key, value in values.items()}})
                predicted = predictions[f"{name}_prediction"].eq(-1)
                confusion_rows.append({
                    "Thuật toán": MODEL_LABELS[name], "Cảnh báo đúng": int((truth & predicted).sum()),
                    "Cảnh báo nhầm": int((~truth & predicted).sum()), "Bỏ sót": int((truth & ~predicted).sum()),
                    "Bình thường đúng": int((~truth & ~predicted).sum()),
                })
            show_table(pd.DataFrame(metric_rows), dark, column_config={
                key: st.column_config.NumberColumn(label, format="%.1f%%")
                for key, label in (("precision", "Precision"), ("recall", "Recall"), ("f1", "F1"))
            })
            show_table(pd.DataFrame(confusion_rows), dark)
            st.caption("Chỉ tính trên nhãn thật của tập kiểm tra; bất thường (-1) là lớp cần phát hiện. Đây là đánh giá từng điểm, chưa phải điểm NAB theo cửa sổ thời gian.")
        st.markdown(
            "- **Precision:** trong các điểm được cảnh báo, bao nhiêu điểm thực sự bất thường?\n"
            "- **Recall:** trong các điểm thực sự bất thường, hệ thống tìm được bao nhiêu?\n"
            "- **F1:** cân bằng giữa Precision và Recall. Mức 0% cũng có thể do không có nhãn bất thường để đánh giá."
        )
    with guide:
        show_help()

    st.divider()
    st.markdown("#### Tải kết quả của lần chạy này")
    csv_column, json_column = st.columns(2)
    csv_column.download_button("Tải dự đoán CSV", data=run.export_csv(), file_name="anomaly_predictions.csv", mime="text/csv", key="download_csv", width="stretch")
    json_column.download_button("Tải kết quả và cấu hình JSON", data=json.dumps(run.summary(), ensure_ascii=False, indent=2), file_name="anomaly_results.json", mime="application/json", key="download_json", width="stretch")
    st.caption("CSV chứa toàn bộ dự đoán của tập kiểm tra, không phụ thuộc bộ lọc trên màn hình. JSON bổ sung cấu hình, thời gian chạy và chỉ số đánh giá.")


def main() -> None:
    st.set_page_config(page_title="Phân tích bất thường | Anomaly Lab", page_icon="📈", layout="wide")
    with st.sidebar:
        st.markdown('<div class="brand">ANOMALY LAB</div>', unsafe_allow_html=True)
        st.caption("Phân tích chuỗi thời gian")
        dark = st.toggle("Giao diện tối", value=False, key="dark_mode")
        st.divider()
        st.header("2. Cấu hình phân tích")
    apply_style(dark)
    st.markdown(
        '<div class="hero"><div class="eyebrow">KHÁM PHÁ DỮ LIỆU · HIỂU CẢNH BÁO</div>'
        '<h1>Phát hiện bất thường<br>trong chuỗi thời gian</h1>'
        '<p>Từ một tệp CSV, tìm các điểm cần xem xét, so sánh bốn thuật toán và hiểu lý do cần kiểm tra lại dữ liệu.</p></div>'
        '<div class="steps"><div class="step"><b>1</b> Chọn dữ liệu</div>'
        '<div class="step"><b>2</b> Cấu hình phân tích</div>'
        '<div class="step"><b>3</b> Xem và tải kết quả</div></div>', unsafe_allow_html=True,
    )

    content, source_name = None, ""
    with st.container(border=True):
        st.subheader("1. Chọn dữ liệu")
        source_choice = st.radio("Nguồn dữ liệu", ["Dữ liệu mẫu có sẵn", "Tải CSV của bạn"], horizontal=True, key="data_source")
        if source_choice == "Tải CSV của bạn":
            uploaded = st.file_uploader("Chọn tệp CSV (tối đa 10 MiB)", type=["csv"], key="csv_upload")
            if uploaded is not None:
                if uploaded.size > MAX_UPLOAD_BYTES:
                    st.error("Tệp CSV vượt quá 10 MiB. Hãy chia tệp nhỏ hơn rồi tải lại.")
                else:
                    content, source_name = uploaded.getvalue(), uploaded.name
            st.caption("Tệp cần một cột thời gian và một cột số. Nhãn 1/-1 là tùy chọn; hãy lưu bằng UTF-8, phân cách bằng dấu phẩy.")
            with st.expander("Ví dụ định dạng CSV"):
                st.code("timestamp,value\n2026-01-01 08:00:00,12.5\n2026-01-01 08:05:00,13.2\n2026-01-01 08:10:00,12.8\n2026-01-01 08:15:00,25.1", language="csv")
                st.caption("Ví dụ chỉ minh họa cấu trúc. Nên cung cấp nhiều dòng đo liên tục để phân tích có ý nghĩa.")
        else:
            sample = PROJECT_ROOT / "data" / "nab_cpu_labeled.csv"
            if not sample.exists():
                sample = PROJECT_ROOT / "data" / "cpu_0.csv"
            if sample.exists():
                content, source_name = sample.read_bytes(), sample.name
                st.caption("Dữ liệu CPU AWS EC2 có sẵn trong dự án. Số dòng thực tế được kiểm tra bên dưới.")
            else:
                st.error("Chưa có tệp mẫu. Hãy chọn Tải CSV của bạn để bắt đầu.")

    configuration, signature, ready = None, None, False
    if content is not None:
        try:
            preview = read_preview(content)
            if preview.empty:
                raise ValueError("CSV must contain data rows")
            if len(preview.columns) < 2:
                st.error("CSV cần ít nhất hai cột: thời gian và giá trị đo. Hãy kiểm tra dấu phẩy phân cách cột.")
            else:
                columns = list(preview.columns)
                source_key = sha256(content).hexdigest()[:12]
                with st.sidebar:
                    st.markdown("**Chọn cột dữ liệu**")
                    time_col = st.selectbox("Cột thời gian", columns, index=columns.index("timestamp") if "timestamp" in columns else 0, key=f"timestamp_{source_key}")
                    candidates = metric_candidates(preview, time_col)
                if not candidates:
                    st.error("Không tìm thấy cột giá trị dạng số. Cột nhãn và cột đúng/sai không được dùng làm chỉ số đo.")
                else:
                    with st.sidebar:
                        value_col = st.selectbox("Cột giá trị", candidates, index=candidates.index("value") if "value" in candidates else 0, key=f"value_{source_key}_{time_col}")
                        labels = [None] + [name for name in columns if name not in {time_col, value_col}]
                        label_col = st.selectbox("Nhãn tham chiếu (tùy chọn)", labels, format_func=lambda item: "Không dùng nhãn" if item is None else str(item), key=f"label_{source_key}_{time_col}_{value_col}", help="1 = bình thường, -1 = bất thường. Nhãn chỉ dùng để đánh giá, không tự sinh nhãn.")
                        st.divider()
                        selected_models = st.multiselect("Thuật toán", list(MODEL_LABELS), default=list(MODEL_LABELS), format_func=MODEL_LABELS.get, key="selected_models", help="Chọn một hoặc nhiều thuật toán để đối chiếu cảnh báo.")
                        contamination = st.slider("Tỷ lệ bất thường dự kiến (%)", .1, 10., 1., .1, key="contamination", help="Dùng cho Isolation Forest, LOF và nu của SVM. MAD dùng ngưỡng riêng 3,5.") / 100
                        train_fraction = st.slider("Dữ liệu dùng huấn luyện (%)", 50, 90, 70, 5, key="train_fraction", help="Các dòng đầu dùng để học, các dòng cuối dùng để kiểm tra sau khi làm sạch và sắp xếp.") / 100
                        with st.expander("Tùy chọn nâng cao"):
                            include_time = st.checkbox("Thêm đặc trưng chu kỳ thời gian", value=False, key="include_time")
                            st.caption("Bổ sung giờ và ngày. Mặc định chỉ dùng chỉ số đã chọn để dễ giải thích kết quả.")
                    configuration = {"timestamp_col": time_col, "value_col": value_col, "label_col": label_col, "contamination": contamination, "train_fraction": train_fraction, "model_names": selected_models, "include_time": include_time}
                    # A new source or configuration must never inherit an old export.
                    signature = sha256(content + json.dumps({"source": source_name, **configuration}, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
                    cleaned_rows = validated_row_count(content, time_col, value_col)
                    train_rows = int(cleaned_rows * train_fraction)
                    ready = train_rows >= 3 and cleaned_rows > train_rows and bool(selected_models)
                    st.caption(f"Tệp: {source_name} · {len(preview):,} dòng đầu vào · {cleaned_rows:,} dòng hợp lệ · {len(columns)} cột.")
                    if cleaned_rows < 100:
                        st.warning(f"Tệp hiện có {cleaned_rows:,} dòng hợp lệ. Bạn có thể thử giao diện; cần thêm dữ liệu để đánh giá chất lượng mô hình.")
                    if cleaned_rows != len(preview):
                        st.warning(f"Có {len(preview) - cleaned_rows:,} dòng giá trị trống hoặc không hợp lệ sẽ bị loại trước khi phân tích.")
                    with st.expander("Xem trước dữ liệu và cách chia tập"):
                        show_table(preview.head(50), dark)
                        st.caption(f"Hiển thị tối đa 50 dòng gốc. Sau làm sạch và sắp xếp: {train_rows:,} dòng đầu huấn luyện, {cleaned_rows - train_rows:,} dòng cuối kiểm tra.")
                    if not selected_models:
                        st.warning("Hãy chọn ít nhất một thuật toán ở thanh bên để chạy phân tích.")
                    if train_rows < 3 or cleaned_rows <= train_rows:
                        st.error("Chưa đủ dữ liệu để chia tập. Cần ít nhất 3 dòng huấn luyện và 1 dòng kiểm tra; hãy thêm dữ liệu hoặc chỉnh tỷ lệ.")
        except (ValueError, TypeError, UnicodeDecodeError, pd.errors.ParserError) as exc:
            st.error(error_message(exc))

    with st.sidebar:
        if configuration is None:
            st.info("Chọn tệp CSV hợp lệ để cấu hình các cột và thuật toán.")
        st.caption("Khi đổi dữ liệu hoặc cấu hình, hãy chạy lại để cập nhật kết quả.")
        st.divider()
        st.caption("Phân tích CSV ngoại tuyến · Chưa giám sát thời gian thực.")

    st.caption("Cấu hình nằm ở thanh bên. Trên điện thoại, mở thanh bên bằng nút ở góc trên bên trái.")
    if st.button("Chạy phát hiện", type="primary", key="run_analysis", disabled=not ready, width="stretch"):
        try:
            with st.spinner("Đang làm sạch dữ liệu, huấn luyện và phát hiện..."):
                run = run_detection(BytesIO(content), **configuration)
            st.session_state["detection_run"] = run
            st.session_state["detection_signature"] = signature
            st.session_state["detection_source"] = source_name
        except (ValueError, TypeError, UnicodeDecodeError, pd.errors.ParserError) as exc:
            st.error(error_message(exc))

    if ready and signature is not None and st.session_state.get("detection_signature") == signature:
        show_results(st.session_state["detection_run"], st.session_state["detection_source"], dark)
    else:
        if "detection_run" in st.session_state:
            st.info("Dữ liệu hoặc cấu hình đã thay đổi. Bấm Chạy phát hiện để tạo kết quả mới.")
        st.markdown('<div class="empty-state"><strong>Sẵn sàng khám phá dữ liệu</strong><p>Chọn dữ liệu, kiểm tra cấu hình ở thanh bên rồi bấm <b>Chạy phát hiện</b> để xem kết quả.</p></div>', unsafe_allow_html=True)
        with st.expander("Hướng dẫn sử dụng và ý nghĩa thuật toán"):
            show_help()


if __name__ == "__main__":
    main()
