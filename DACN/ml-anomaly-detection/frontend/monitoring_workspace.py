"""Three-step workspace for readers who do not need model configuration."""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from frontend.api_client import BackendError, compare_via_api, detect_via_api, get_backend_url
from frontend.dbms_charts import METRIC_NAMES, build_trend_figure
from frontend.demo_data import DEFAULT_ANOMALOUS_SAMPLE, NORMAL_SAMPLE
from frontend.input_data import prepare_mysql_csv
from frontend.monitoring_charts import build_comparison_figure, build_count_figure, build_score_figure
from frontend.reporting import build_report_markdown
from src.monitoring_summary import summarize_run

MODELS = ["mad", "isolation_forest", "lof", "one_class_svm"]
SCENARIOS = {
    "normal": ("Hoạt động bình thường", "Quan sát hệ thống khi tải ổn định và có dao động tự nhiên."),
    "anomalous": ("Hoạt động bất thường", "Thử một đợt tăng lượng truy vấn trong bộ dữ liệu có nhãn."),
    "compare": ("So sánh hai bộ dữ liệu", "Đặt hai giai đoạn cạnh nhau để thấy khác biệt và cảnh báo."),
}
CHART_CONFIG = {"displayModeBar": False, "displaylogo": False, "scrollZoom": False}


def clear_basic_results() -> None:
    if "basic_result" in st.session_state:
        st.session_state["basic_reset_notice"] = "Dữ liệu hoặc cấu hình đã thay đổi. Bắt đầu phân tích lại để cập nhật kết quả."
    for key in ("basic_result", "basic_result_signature", "basic_result_sources", "basic_result_backend"):
        st.session_state.pop(key, None)
    st.session_state["basic_stage"] = "input"


def choose_scenario(scenario: str) -> None:
    clear_basic_results()
    st.session_state["basic_scenario"] = scenario
    st.session_state["basic_navigation"] = "So sánh dữ liệu" if scenario == "compare" else "Kiểm tra hoạt động"


def navigation_changed() -> None:
    clear_basic_results()
    if st.session_state["basic_navigation"] == "So sánh dữ liệu":
        st.session_state["basic_scenario"] = "compare"
    elif st.session_state.get("basic_scenario") == "compare":
        st.session_state["basic_scenario"] = "normal"


@st.cache_data(show_spinner=False, max_entries=8)
def _prepare(content: bytes):
    # Cache parsing only. Models are never fitted in the frontend or on reruns.
    return prepare_mysql_csv(content)


def _upload(key: str, label: str) -> tuple[bytes | None, str]:
    uploaded = st.file_uploader(label, type=["csv"], key=key,
        help="Tệp UTF-8, tối đa 10 MiB. Mỗi dòng gồm thời gian và đủ năm chỉ số; nhãn 1/-1 là tùy chọn.")
    if uploaded is None:
        return None, ""
    if uploaded.size > 10 * 1024 * 1024:
        st.error("Tệp vượt quá 10 MiB. Chia nhỏ theo thời gian rồi tải lại.")
        return None, ""
    return uploaded.getvalue(), uploaded.name


def _source_notice(kind: str) -> None:
    if kind == "synthetic":
        title = "Dữ liệu mẫu mô phỏng"
        detail = "Có nhãn kịch bản để thực hành và đối chiếu kết quả. Các giá trị được tạo để kiểm thử."
    else:
        title = "CSV do bạn cung cấp"
        detail = "Nguồn số đo và nhãn chưa được ứng dụng xác minh. Hãy kiểm tra cách thu thập, đơn vị và giai đoạn hoạt động bình thường."
    tone = "simulated" if kind == "synthetic" else "unknown"
    st.markdown(f'<div class="source-notice source-{tone}"><strong>{title}</strong><p>{detail}</p></div>', unsafe_allow_html=True)


def _status(summary: dict) -> None:
    message = summary["explanation"]
    if summary["status_level"] == "normal":
        st.success(f"Bình thường · Chưa phát hiện thời điểm cần cảnh báo trong {summary['rows_analyzed']:,} bản ghi kiểm tra theo cấu hình hiện tại.")
    elif summary["status_level"] == "high":
        st.error("Cảnh báo cao · " + message)
    else:
        st.warning("Cần chú ý · " + message)


def _metric_cards(summary: dict) -> None:
    cards = st.columns(4)
    values = [f"{summary['rows_analyzed']:,}", f"{summary['alert_count']:,}",
              f"{summary['alert_rate']:.1%}", summary["status"]]
    for card, title, value in zip(cards, ["Bản ghi được kiểm tra", "Thời điểm cần kiểm tra", "Tỷ lệ cần chú ý", "Trạng thái giám sát"], values):
        card.metric(title, value)


def _why(run, summary: dict, show_table, dark: bool) -> None:
    st.markdown("### Vì sao hệ thống đưa ra cảnh báo?" if summary["alert_count"] else "### Kết quả này có nghĩa gì?")
    if summary["alert_count"]:
        evidence = summary.get("evidence")
        if isinstance(evidence, pd.DataFrame) and not evidence.empty:
            # Show a few measured examples first; the complete observations
            # remain available in the timeline table and exported predictions.
            display = evidence.head(5)[["name", "actual", "reference", "delta", "unit", "material"]].rename(columns={
                "name": "Chỉ số", "actual": "Giá trị quan sát", "reference": "Mức tham chiếu",
                "delta": "Chênh lệch", "unit": "Đơn vị", "material": "Vượt dung sai vận hành",
            })
            display["Vượt dung sai vận hành"] = display["Vượt dung sai vận hành"].map({True: "Có", False: "Không"})
            show_table(display, dark, column_config={key: st.column_config.NumberColumn(format="%.3g") for key in ("Giá trị quan sát", "Mức tham chiếu", "Chênh lệch")})
            st.caption(f"Giá trị thực tại {evidence.iloc[0]['Thời gian']} UTC. Bảng bên dưới liệt kê các thời điểm còn lại.")
        for check in summary.get("next_checks", [])[:3]:
            st.markdown("- " + check)
        st.caption("Đây là các dấu hiệu quan sát được; cần đối chiếu nhật ký và bối cảnh vận hành để xác minh nguyên nhân.")
    else:
        st.write("Các thuật toán chưa tìm thấy thời điểm cần cảnh báo sau quy tắc vận hành. Những nhấp nhô trên biểu đồ có thể là dao động thường gặp.")
        st.caption("Kết luận chỉ áp dụng cho phần dữ liệu được kiểm tra và cấu hình hiện tại.")
    with st.expander("Hệ thống xác định trạng thái như thế nào?"):
        st.write(summary["severity_rule"])
        st.write(f"Có {summary['raw_count']:,} thời điểm được ít nhất một mô hình gắn cờ ban đầu; {summary['alert_count']:,} thời điểm trở thành cảnh báo sau quy tắc vận hành.")
        st.caption("Điểm mô hình và ngưỡng vận hành là hai thành phần riêng. Các mô hình học từ lịch sử; quy tắc vận hành lọc dao động nhỏ và phân mức chú ý, không thay thế mô hình.")
        st.caption("Số kết nối thất bại không phải tỷ lệ truy vấn lỗi. Dữ liệu hiện tại chưa cung cấp bộ đếm lỗi truy vấn để tính tỷ lệ đó.")


def _notable(summary: dict, show_table, dark: bool, key: str = "basic_level_filter") -> None:
    st.markdown("### Các thời điểm đáng chú ý")
    table = summary["notable"]
    if table.empty:
        st.info("Chưa có thời điểm cần kiểm tra trong dữ liệu này.")
        return
    level = st.radio("Mức cảnh báo", ["Tất cả", "Cần chú ý", "Cảnh báo cao"], horizontal=True, key=key)
    selected = table if level == "Tất cả" else table.loc[table["Mức cảnh báo"].eq(level)]
    if selected.empty:
        st.info(f"Không có thời điểm ở mức {level.lower()}. Chọn Tất cả để xem các cảnh báo hiện có.")
        return
    show_table(selected.head(500), dark)
    if len(selected) > 500:
        st.caption("Hiển thị 500 thời điểm đầu. Tải CSV để xem toàn bộ kết quả.")


def _downloads(run, summary: dict, source: str) -> None:
    st.divider()
    st.markdown("### Lưu kết quả phân tích")
    st.caption("Báo cáo: phần diễn giải để đọc và chia sẻ. CSV: toàn bộ dự đoán của phần kiểm tra. JSON: cấu hình và kết quả để đối chiếu lại.")
    first, second, third = st.columns(3)
    first.download_button("Tải báo cáo", build_report_markdown(run, summary, source_name=source),
                          "bao_cao.md", "text/markdown", key="basic_report", width="stretch")
    second.download_button("Tải dữ liệu kết quả", run.export_csv(), "ket_qua.csv", "text/csv", key="basic_csv", width="stretch")
    payload = run.summary(date_unit="ns")
    payload["monitoring_status"] = {"status": summary["status"], "rule": summary["severity_rule"]}
    third.download_button("Tải cấu hình và kết quả", json.dumps(payload, ensure_ascii=False, indent=2),
                          "ket_qua.json", "application/json", key="basic_json", width="stretch")


def _single_results(run, source: str, dark: bool, show_table) -> None:
    summary = summarize_run(run)
    st.subheader("3. Kết quả kiểm tra hoạt động CSDL")
    _source_notice(run.metadata.get("source_kind", "upload"))
    st.caption(f"{source} · Học mức tham chiếu từ {run.metadata['train_rows']:,} bản ghi đầu, kiểm tra {summary['rows_analyzed']:,} bản ghi tiếp theo.")
    _metric_cards(summary)
    _status(summary)
    _why(run, summary, show_table, dark)
    st.markdown("### Hoạt động CSDL theo thời gian")
    metric = st.selectbox("Bạn muốn xem chỉ số nào?", list(METRIC_NAMES), format_func=METRIC_NAMES.get, key="basic_metric")
    # The first selected model is the score reference. Activity markers show
    # the union used by the overview without altering stored model predictions.
    names = run.metadata["model_names"]
    primary = "mad" if "mad" in names else names[0]
    figure = build_trend_figure(run, primary, metric, dark=dark)
    flags = run.predictions[[f"{name}_prediction" for name in names]].eq(-1).any(axis=1)
    flagged = run.predictions.loc[flags]
    figure.data[1].x = flagged[run.metadata["timestamp_col"]]
    figure.data[1].y = flagged[metric]
    figure.data[1].customdata = flagged[run.metadata["metric_cols"]].to_numpy()
    figure.data[1].name = "Thời điểm cần kiểm tra"
    st.plotly_chart(figure, width="stretch", theme=None, config=CHART_CONFIG, key="basic_activity_chart")
    st.caption("Đường xanh: giá trị thực tế. Vùng xanh lá: khoảng tham chiếu học từ lịch sử. Dấu đỏ: thời điểm ít nhất một thuật toán cảnh báo sau quy tắc vận hành.")
    left, right = st.columns([2, 1])
    with left:
        st.markdown("#### Mức khác thường theo thời gian")
        st.plotly_chart(build_score_figure(run, primary, dark=dark), width="stretch", theme=None, config=CHART_CONFIG, key="basic_score_chart")
        st.caption(f"Điểm riêng của {primary.upper()}; điểm cao hơn là khác thường hơn. Dấu cam: mô hình gắn cờ ban đầu; dấu đỏ: cảnh báo sau quy tắc vận hành. Điểm không phải xác suất xảy ra sự cố.")
    with right:
        st.markdown("#### Số bản ghi theo trạng thái")
        st.plotly_chart(build_count_figure(run, dark=dark), width="stretch", theme=None, config=CHART_CONFIG, key="basic_count_chart")
    _notable(summary, show_table, dark)
    with st.expander("Xem thông tin của lần phân tích"):
        st.write(f"Nguồn có {summary['total_rows']:,} bản ghi. Chỉ phần sau giai đoạn học được chấm; số liệu trên các thẻ không bao gồm phần đã dùng để học.")
        st.caption("Chuyển sang Nâng cao để chọn thuật toán, xem chỉ số đánh giá khi có nhãn và kiểm tra tham số mô hình.")
    _downloads(run, summary, source)


def _comparison_results(results: dict, sources: dict, dark: bool, show_table) -> None:
    st.subheader("3. So sánh dữ liệu")
    demo = all(run.metadata.get("source_kind") == "synthetic" for run in results.values())
    _source_notice("synthetic" if demo else "upload")
    st.caption("Hai bộ dùng chung mô hình và cách chuẩn hóa, được học một lần từ giai đoạn tham chiếu của bộ bên trái.")
    st.caption("Bộ bên trái do người dùng chọn làm tham chiếu; cần xác nhận giai đoạn này đại diện cho hoạt động ổn định.")
    summaries = {key: summarize_run(run) for key, run in results.items()}
    titles = ("Hoạt động bình thường", "Hoạt động có dấu hiệu bất thường") if demo else ("Hoạt động tham chiếu", "Hoạt động cần đối chiếu")
    for column, key, title in zip(st.columns(2), ("normal", "anomalous"), titles):
        run, summary = results[key], summaries[key]
        with column:
            with st.container(border=True):
                st.markdown("#### " + title)
                st.caption(sources[key])
                st.metric("Bản ghi được kiểm tra", f"{len(run.predictions):,}")
                st.metric("Thời điểm cần kiểm tra", f"{summary['alert_count']:,}")
                _status(summary)
                st.write(f"Truy vấn trung bình: **{run.predictions['queries_per_second'].mean():,.2f}/giây**")
                st.write(f"Kết nối trung bình: **{run.predictions['connections'].mean():,.2f}**")
                st.write(f"Phản hồi trung bình: **{run.predictions['response_time_ms'].mean():,.2f} ms**")
                primary = "mad" if "mad" in run.metadata["model_names"] else run.metadata["model_names"][0]
                st.write(f"Điểm khác thường trung bình ({primary.upper()}): **{-run.predictions[f'{primary}_score'].mean():,.3g}**")
    st.markdown("### Các chỉ số thay đổi ra sao?")
    rows = []
    for metric, title in METRIC_NAMES.items():
        left = results["normal"].predictions[metric].mean()
        right = results["anomalous"].predictions[metric].mean()
        rows.append({"Chỉ số trung bình": title, "Bộ tham chiếu": left, "Bộ đối chiếu": right, "Chênh lệch": right - left})
    show_table(pd.DataFrame(rows), dark, column_config={column: st.column_config.NumberColumn(format="%.2f") for column in ("Bộ tham chiếu", "Bộ đối chiếu", "Chênh lệch")})
    metric = st.selectbox("Chỉ số so sánh theo thời gian", list(METRIC_NAMES), format_func=METRIC_NAMES.get, key="basic_compare_metric")
    st.plotly_chart(build_comparison_figure(results["normal"], results["anomalous"], metric, dark=dark),
                    width="stretch", theme=None, config=CHART_CONFIG, key="basic_comparison_chart")
    st.caption("Chênh lệch trung bình chỉ mô tả dữ liệu. Kết luận cảnh báo vẫn cần kết quả mô hình và quy tắc vận hành; giá trị lớn hơn không tự động là bất thường.")
    st.markdown("### Các khoảng thời gian cần kiểm tra")
    intervals = summaries["anomalous"].get("intervals", [])
    if intervals:
        show_table(pd.DataFrame(intervals).rename(columns={"start": "Bắt đầu (UTC)", "end": "Kết thúc (UTC)", "count": "Số bản ghi"}), dark)
    else:
        st.info("Chưa tìm thấy khoảng thời gian cần kiểm tra trong bộ đối chiếu.")
    _notable(summaries["anomalous"], show_table, dark, "basic_compare_level")
    for check in summaries["anomalous"].get("next_checks", [])[:3]:
        st.markdown("- " + check)
    st.caption(summaries["anomalous"]["severity_rule"])
    if len({run.metadata.get("source_has_labels", bool(run.metadata.get("label_col"))) for run in results.values()}) > 1:
        st.info("Chỉ một tệp có nhãn kiểm thử. Lần so sánh này vẫn phát hiện cảnh báo nhưng không tính Precision, Recall và F1 cho cả hai bộ. Cung cấp nhãn 1/-1 cho cả hai tệp để đánh giá.")
    st.divider()
    st.markdown("### Lưu kết quả so sánh")
    st.caption("Báo cáo gồm diễn giải của cả hai bộ. CSV gộp toàn bộ dự đoán và ghi rõ bộ dữ liệu; JSON giữ cấu hình để đối chiếu lại.")
    report = b"\n\n".join(build_report_markdown(results[key], summaries[key], source_name=sources[key]) for key in ("normal", "anomalous"))
    exported = pd.concat([results[key].predictions.assign(bo_du_lieu=key) for key in ("normal", "anomalous")], ignore_index=True)
    left, middle, right = st.columns(3)
    left.download_button("Tải báo cáo", report, "bao_cao_so_sanh.md", "text/markdown", key="basic_report", width="stretch")
    middle.download_button("Tải dữ liệu kết quả", exported.to_csv(index=False).encode("utf-8-sig"), "so_sanh.csv", "text/csv", key="basic_csv", width="stretch")
    right.download_button("Tải cấu hình và kết quả", json.dumps({key: run.summary(date_unit="ns") for key, run in results.items()}, ensure_ascii=False, indent=2),
                          "so_sanh.json", "application/json", key="basic_json", width="stretch")


def render_basic_workspace(project: Path, dark: bool, show_table) -> None:
    st.session_state.setdefault("basic_scenario", "normal")
    source_options = ["Dùng dữ liệu mẫu", "Tải tệp CSV"]
    if "basic_source" in st.session_state and st.session_state["basic_source"] not in source_options:
        st.session_state["basic_source"] = source_options[0]
        clear_basic_results()
    if st.session_state.get("basic_stage") == "results" and "basic_result" in st.session_state:
        if st.session_state.get("basic_result_backend") != get_backend_url():
            clear_basic_results()
            st.info("Địa chỉ dịch vụ phân tích đã thay đổi. Bắt đầu phân tích lại để lấy kết quả phù hợp.")
        else:
            st.button("Phân tích dữ liệu khác", key="basic_other_data", on_click=clear_basic_results)
            result = st.session_state["basic_result"]
            sources = st.session_state["basic_result_sources"]
            if isinstance(result, dict):
                _comparison_results(result, sources, dark, show_table)
            else:
                _single_results(result, sources["single"], dark, show_table)
            return
    if notice := st.session_state.pop("basic_reset_notice", None):
        st.info(notice)
    st.subheader("1. Bạn muốn kiểm tra hoạt động nào?")
    st.caption("Chọn một kịch bản để dùng mẫu có sẵn, hoặc tải CSV của bạn ở bước bên dưới. Ứng dụng phân tích dữ liệu trong tệp theo từng lần chạy.")
    for column, (key, (title, caption)) in zip(st.columns(3), SCENARIOS.items()):
        with column:
            with st.container(border=True):
                st.button(title, key="basic_" + key, width="stretch",
                          type="primary" if st.session_state["basic_scenario"] == key else "secondary",
                          on_click=choose_scenario, args=(key,))
                st.caption(caption)
    comparing = st.session_state["basic_scenario"] == "compare"
    source = st.radio("Nguồn dữ liệu", source_options, horizontal=True, key="basic_source", on_change=clear_basic_results)
    _source_notice("synthetic" if source == "Dùng dữ liệu mẫu" else "upload")
    raw_inputs, source_names = {}, {}
    if source == "Dùng dữ liệu mẫu":
        keys = ("normal", "anomalous") if comparing else (st.session_state["basic_scenario"],)
        try:
            for key in keys:
                path = project / "data" / (NORMAL_SAMPLE if key == "normal" else DEFAULT_ANOMALOUS_SAMPLE)
                raw_inputs[key] = path.read_bytes()
                source_names[key] = path.name
            st.caption("Dữ liệu mẫu được tạo để kiểm thử, có nhãn kịch bản rõ ràng; không phải số đo từ máy chủ thật.")
        except OSError:
            st.error("Thiếu dữ liệu mẫu. Hãy chọn Tải tệp CSV để tiếp tục với dữ liệu của bạn.")
    elif source == "Tải tệp CSV":
        if comparing:
            for column, key, title in zip(st.columns(2), ("normal", "anomalous"), ("Tệp tham chiếu bình thường", "Tệp cần đối chiếu")):
                with column:
                    content, name = _upload("basic_" + key + "_upload", title)
                    if content is not None:
                        raw_inputs[key], source_names[key] = content, name
        else:
            content, name = _upload("basic_csv_upload", "Chọn tệp CSV hoạt động CSDL")
            if content is not None:
                raw_inputs["single"], source_names["single"] = content, name
        st.caption("Tự nhận diện thời gian, truy vấn/giây, kết nối, phản hồi (ms), truy vấn chậm và kết nối thất bại. Nhãn kiểm thử là tùy chọn.")
        with st.expander("Chuẩn bị CSV để phân tích"):
            st.write("Mỗi dòng cần một thời điểm duy nhất và đủ năm chỉ số. Thời gian phản hồi dùng ms; truy vấn chậm và kết nối thất bại là số phát sinh trong khoảng lấy mẫu.")
            st.write("Sắp xếp và kiểm tra phần đầu là giai đoạn hoạt động bình thường: ứng dụng dùng khoảng 70% dữ liệu đầu để học nền, phần còn lại để kiểm tra.")
            st.caption("Nếu có nhãn, dùng 1 cho bình thường và -1 cho bất thường. Không có nhãn vẫn phân tích được, nhưng chưa tính được Precision, Recall và F1.")
        if len(raw_inputs) < (2 if comparing else 1):
            st.info("Tải đủ tệp tham chiếu và tệp cần đối chiếu để bắt đầu so sánh." if comparing else "Chọn một tệp CSV ở trên để xem trước dữ liệu và mở bước phân tích.")
    prepared, previews, ready = {}, {}, False
    try:
        for key, content in raw_inputs.items():
            prepared[key], previews[key], mapping = _prepare(content)
        ready = len(prepared) == (2 if comparing else 1)
        if comparing and len(previews) == 2 and len({"label" in frame for frame in previews.values()}) > 1:
            st.info("Chỉ một tệp có nhãn kiểm thử. Hai bộ vẫn được so sánh nhưng chưa tính Precision, Recall và F1. Muốn đánh giá, hãy cung cấp nhãn 1/-1 cho cả hai tệp.")
        if previews:
            st.caption(" · ".join(f"{source_names[key]}: {len(frame):,} bản ghi" for key, frame in previews.items()))
            with st.expander("Xem dữ liệu trước khi phân tích"):
                preview_time = ""
                if any(len(frame) > 20 for frame in previews.values()):
                    preview_time = st.text_input("Tìm thời điểm", placeholder="Ví dụ: 09:07",
                                                 help="Nhập giờ hoặc ngày rồi nhấn Enter để tìm trong toàn bộ dữ liệu. Khi so sánh, cả hai bảng dùng cùng thời điểm.",
                                                 key="basic_preview_time").strip()
                for key, frame in previews.items():
                    st.caption(source_names[key])
                    has_anomaly_labels = "label" in frame and frame["label"].eq(-1).any()
                    if preview_time:
                        timestamps = frame["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
                        preview_rows = frame.loc[timestamps.str.contains(preview_time, regex=False)]
                    elif len(frame) <= 20:
                        preview_rows = frame
                    else:
                        preview_options = ["20 dòng đầu", "Toàn bộ dữ liệu"]
                        if has_anomaly_labels:
                            preview_options.insert(1, "Dòng có nhãn bất thường")
                        preview_choice = st.radio("Phần dữ liệu muốn xem", preview_options, horizontal=True,
                                                  key=f"basic_preview_{key}_{sha256(prepared[key]).hexdigest()[:12]}")
                        if preview_choice == "Dòng có nhãn bất thường":
                            preview_rows = frame.loc[frame["label"].eq(-1)]
                        elif preview_choice == "Toàn bộ dữ liệu":
                            preview_rows = frame
                        else:
                            preview_rows = frame.head(20)
                    st.caption(f"Đang hiển thị {len(preview_rows):,} / {len(frame):,} bản ghi.")
                    if preview_rows.empty:
                        st.info("Không tìm thấy thời điểm khớp. Thử nhập giờ theo dạng 09:07 hoặc xóa ô tìm kiếm để xem lại dữ liệu.")
                    if has_anomaly_labels and not preview_time:
                        if len(frame) > 20:
                            st.caption("Các dòng đầu có thể chưa chứa bất thường. Chọn Dòng có nhãn bất thường để xem ngay các thời điểm đó.")
                        st.caption("Nhãn kiểm thử: 1 là bình thường, -1 là bất thường có sẵn trong tệp, chưa phải kết quả dự đoán.")
                    show_table(preview_rows.rename(columns={"timestamp": "Thời gian", **METRIC_NAMES, "label": "Nhãn kiểm thử", "scenario": "Kịch bản"}), dark)
    except ValueError as exc:
        st.error(str(exc))
        st.caption("Sửa thông tin được báo trong tệp, lưu lại rồi tải lên lần nữa. Bạn cũng có thể chọn dữ liệu mẫu để thử quy trình.")
        ready = False
    st.subheader("2. Phân tích tự động")
    st.caption("Ứng dụng tự học mức hoạt động thường gặp từ giai đoạn đầu rồi kiểm tra dữ liệu tiếp theo.")
    if ready:
        st.markdown('<div class="workflow-note"><strong>Dữ liệu đã sẵn sàng</strong><p>Xem trước các giá trị, sau đó bấm <b>Bắt đầu phân tích</b>. Kết quả gồm trạng thái, thời điểm cần chú ý và tệp có thể tải về.</p></div>', unsafe_allow_html=True)
    if st.button("Bắt đầu phân tích", type="primary", width="stretch", key="basic_start", disabled=not ready):
        clear_basic_results()
        try:
            with st.status("Đang đọc dữ liệu", expanded=True) as progress:
                st.write("Đang đọc dữ liệu.")
                st.write("Đang chuẩn bị dữ liệu.")
                st.write(f"Đã kiểm tra {sum(len(frame) for frame in previews.values()):,} bản ghi; không tự điền hoặc loại bỏ giá trị lỗi.")
                config = dict(label_col="label" if all("label" in frame for frame in previews.values()) else None,
                              model_names=MODELS, train_fraction=.7, contamination=.01,
                              noise_guard=True, deviation_threshold=3.5)
                minimum_split = min(int(Decimal(len(frame)) * Decimal(".7")) for frame in previews.values())
                if minimum_split < 3:
                    config["split_index"] = 3
                progress.update(label="Đang phân tích hoạt động")
                st.write("Đang phân tích hoạt động.")
                if comparing:
                    result = compare_via_api(prepared["normal"], prepared["anomalous"],
                        normal_source_name=source_names["normal"], anomalous_source_name=source_names["anomalous"], **config)
                else:
                    key = next(iter(prepared))
                    result = detect_via_api(prepared[key], source_names[key], analysis_mode="dbms", **config)
                    source_names = {"single": source_names[key]}
                st.write("Đang tổng hợp kết quả.")
                runs = result.items() if isinstance(result, dict) else [(next(iter(previews)), result)]
                for key, run in runs:
                    run.metadata["source_kind"] = "synthetic" if source == "Dùng dữ liệu mẫu" else "upload"
                    run.metadata["source_has_labels"] = "label" in previews[key]
                    summarize_run(run)
                progress.update(label="Hoàn tất", state="complete", expanded=False)
            signature_data = b"".join(prepared.values()) + json.dumps({"backend": get_backend_url(), **config}, sort_keys=True).encode()
            st.session_state["basic_result"] = result
            st.session_state["basic_result_signature"] = sha256(signature_data).hexdigest()
            st.session_state["basic_result_sources"] = source_names
            st.session_state["basic_result_backend"] = get_backend_url()
            st.session_state["basic_stage"] = "results"
            st.rerun()
        except (BackendError, ValueError) as exc:
            clear_basic_results()
            st.error(str(exc))
            st.caption("Kiểm tra thông báo trên, giữ ứng dụng đang chạy rồi bấm Bắt đầu phân tích để thử lại.")
    if not st.session_state.get("basic_result"):
        st.markdown('<div class="empty-state"><strong>Sẵn sàng kiểm tra hoạt động CSDL</strong><p>Chọn dữ liệu ở trên rồi bấm <b>Bắt đầu phân tích</b>. Kết quả sẽ cho biết thời điểm cần chú ý và các chỉ số nên kiểm tra.</p></div>', unsafe_allow_html=True)
