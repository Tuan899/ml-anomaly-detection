"""DBMS monitoring interface. Estimators run exclusively behind the HTTP API."""
from __future__ import annotations

from hashlib import sha256
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from frontend.api_client import BackendError, detect_via_api, get_backend_url
from frontend.dbms_charts import build_trend_figure
from src.data_prep import read_csv_frame
from src.mysql_collector import MySQLCollectionError, collect_mysql_metrics

METRICS = {
    "queries_per_second": "Truy vấn mỗi giây (QPS)",
    "connections": "Số kết nối đang mở",
    "response_time_ms": "Thời gian phản hồi (ms)",
    "slow_queries": "Truy vấn chậm trong khoảng lấy mẫu",
    "connection_errors": "Kết nối thất bại trong khoảng lấy mẫu",
}
MODELS = {"mad": "MAD", "isolation_forest": "Isolation Forest", "lof": "LOF", "one_class_svm": "One-Class SVM"}


def _clear_results() -> None:
    for key in ("dbms_result", "dbms_result_signature"):
        st.session_state.pop(key, None)


def _mysql_source() -> tuple[bytes | None, str]:
    st.info("Thu thập một đợt số liệu thực tế bằng tài khoản giám sát chỉ đọc. Sau đó bấm Chạy phát hiện; ứng dụng không tự theo dõi liên tục.")
    st.caption("QPS = ΔQuestions / số giây thực tế; kết nối = Threads_connected; truy vấn chậm = ΔSlow_queries; kết nối thất bại = ΔAborted_connects. Bộ đếm bao gồm cả hoạt động của trình giám sát.")
    with st.form("mysql_connection"):
        left, right = st.columns(2)
        host = left.text_input("Máy chủ MySQL", value="127.0.0.1", key="mysql_host")
        port = right.number_input("Cổng MySQL", min_value=1, max_value=65535, value=3306, key="mysql_port")
        user = left.text_input("Tài khoản chỉ đọc", value="anomaly_monitor", key="mysql_user")
        password = right.text_input("Mật khẩu", type="password", key="mysql_password")
        database = left.text_input("CSDL mặc định (tùy chọn)", key="mysql_database")
        ssl_ca = right.text_input("Đường dẫn chứng chỉ CA trên máy chạy Streamlit (tùy chọn)", key="mysql_ca")
        samples = left.number_input("Số mẫu thu thập", min_value=4, max_value=600, value=60, step=1, key="mysql_samples")
        interval = right.number_input("Khoảng lấy mẫu (giây)", min_value=0.1, max_value=60.0, value=1.0, step=0.1, key="mysql_interval")
        no_tls = st.checkbox("Tắt TLS cho MySQL demo cục bộ", value=False, key="mysql_no_tls")
        st.caption("Mặc định xác minh TLS và tên máy chủ. Chỉ tắt TLS khi dùng môi trường cục bộ đã kiểm soát. Mật khẩu chỉ nằm trong phiên giao diện, không gửi tới API phân tích hay tệp kết quả.")
        submitted = st.form_submit_button("Thu thập chỉ số MySQL", key="mysql_collect")
    public_settings = dict(host=host, port=int(port), user=user, database=database or None,
                           samples=int(samples), interval_seconds=float(interval), ssl_ca=ssl_ca or None, ssl_disabled=no_tls)
    signature = sha256(json.dumps(public_settings, sort_keys=True).encode()).hexdigest()
    st.caption(f"Thời gian tối thiểu dự kiến: {samples * interval:.1f} giây, cộng thời gian phản hồi. Nên thu thập từ 100 mẫu và chọn giai đoạn đầu đã biết là ổn định để huấn luyện.")
    if submitted:
        _clear_results()
        st.session_state.pop("mysql_snapshot", None)
        st.session_state.pop("mysql_snapshot_signature", None)
        progress = st.progress(0.0, text="Đang đọc các bộ đếm MySQL...")
        try:
            frame = collect_mysql_metrics(**public_settings, password=password,
                progress_callback=lambda completed, total: progress.progress(completed / total, text=f"Đã thu thập {completed}/{total} mẫu thực tế"))
            content = frame.to_csv(index=False).encode("utf-8")
            st.session_state["mysql_snapshot"] = content
            st.session_state["mysql_snapshot_signature"] = signature
            st.success(f"Đã thu thập {len(frame)} mẫu. Chưa huấn luyện mô hình; kiểm tra dữ liệu rồi bấm Chạy phát hiện.")
        except MySQLCollectionError as exc:
            st.error(str(exc))
        finally:
            progress.empty()
    if st.session_state.get("mysql_snapshot_signature") != signature:
        return None, ""
    st.warning("response_time_ms là thời gian khứ hồi của SELECT 1 qua kết nối giám sát, gồm độ trễ mạng; không phải trung bình mọi truy vấn nghiệp vụ. Dữ liệu trực tiếp chưa có nhãn, nên không tính Precision/Recall/F1.")
    return st.session_state["mysql_snapshot"], "mysql_live_metrics.csv"


def _show_trend(run, model: str, metric: str, dark: bool, key: str,
                full_history: bool = False, show_labels: bool = False) -> None:
    figure = build_trend_figure(run, model, metric, dark=dark,
                                full_history=full_history, show_labels=show_labels)
    st.plotly_chart(figure, width="stretch", theme=None, key=key,
                    config={"displayModeBar": False, "displaylogo": False, "scrollZoom": False})


def _results(run, source: str, dark: bool, show_table, show_confusion) -> None:
    meta, data = run.metadata, run.predictions
    names = meta["model_names"]
    alerts = data[[f"{name}_prediction" for name in names]].eq(-1).any(axis=1)
    count = int(alerts.sum())
    st.subheader("3. Kết quả giám sát hoạt động CSDL")
    st.caption(f"Nguồn: {source} · {meta['train_rows']} mẫu huấn luyện · {len(data)} mẫu kiểm tra · Thời gian UTC.")
    if count:
        st.warning(f"Phát hiện dấu hiệu bất thường: {count} thời điểm cần quản trị viên kiểm tra trong tập kiểm tra.")
    else:
        st.success("Hoạt động ổn định trong phạm vi tập kiểm tra: chưa phát hiện bất thường theo cấu hình hiện tại.")
    latest = data.iloc[-1]
    latest_flag = any(latest[f"{name}_prediction"] == -1 for name in names)
    st.caption(f"Mẫu mới nhất {latest[meta['timestamp_col']]} UTC: {'có cảnh báo cần kiểm tra' if latest_flag else 'chưa có cảnh báo'}. Kết quả không bảo đảm hệ thống hoàn toàn không có sự cố.")
    cards = st.columns(4)
    for card, label, value in zip(cards, ["Mẫu kiểm tra", "Thời điểm cảnh báo", "Tỷ lệ cảnh báo", "Thuật toán đã chạy"],
                                  [str(len(data)), str(count), f"{count / len(data):.1%}", str(len(names))]):
        card.metric(label, value)
    overview, details, evaluation, guide = st.tabs(["Tổng quan", "Chi tiết", "Đánh giá", "Hướng dẫn"])
    with overview:
        left, right = st.columns([1, 2])
        model = left.selectbox("Thuật toán hiển thị trên biểu đồ", names, format_func=MODELS.get, key="dbms_chart_model")
        metric = right.selectbox("Chỉ số theo thời gian", list(METRICS), format_func=METRICS.get, key="dbms_chart_metric")
        scope_column, labels_column = st.columns([2, 1])
        scope = scope_column.radio("Phạm vi biểu đồ", ["Giai đoạn kiểm tra", "Toàn bộ dữ liệu"], horizontal=True, key="dbms_chart_scope")
        show_labels = labels_column.checkbox("Hiện nhãn kiểm thử", value=False, disabled=not bool(meta.get("label_col")), key="dbms_chart_labels")
        flagged = data[f"{model}_prediction"].eq(-1)
        flagged_count = int(flagged.sum())
        st.markdown("#### " + METRICS[metric])
        start, end = data[meta["timestamp_col"]].iloc[[0, -1]]
        st.caption(f"{MODELS[model]} · {len(data):,} mẫu kiểm tra · {start:%d/%m/%Y %H:%M} – {end:%d/%m/%Y %H:%M} UTC")
        if flagged_count:
            st.warning(f"{MODELS[model]} cảnh báo tại {flagged_count:,} thời điểm. Dấu đỏ đánh dấu thời điểm cần kiểm tra cả năm chỉ số.")
        else:
            st.success(f"{MODELS[model]}: không có cảnh báo trong {len(data):,} mẫu kiểm tra. Các nhấp nhô của đường xanh là dao động giá trị đo.")
        baseline = meta["train_baselines"][metric]
        st.markdown(f"Giá trị cuối: **{data[metric].iloc[-1]:,.2f}** · Mức tham chiếu thường gặp: **{baseline['median']:,.2f}** · Vùng tham chiếu: **{baseline['lower_bound']:,.2f} – {baseline['upper_bound']:,.2f}**")
        _show_trend(run, model, metric, dark, "dbms_main_trend", full_history=scope == "Toàn bộ dữ liệu", show_labels=show_labels)
        st.caption("Đường xanh: giá trị thực tế. Vùng xanh lá: khoảng dao động tham chiếu từ dữ liệu học. Ngoài vùng này chưa đủ để kết luận bất thường; mô hình xem đồng thời cả năm chỉ số.")
        with st.expander("Biểu đồ của cả năm chỉ số"):
            for item in METRICS:
                st.markdown("**" + METRICS[item] + "**")
                _show_trend(run, model, item, dark, "dbms_trend_" + item, full_history=scope == "Toàn bộ dữ liệu", show_labels=show_labels)
        st.markdown("#### So sánh khả năng phát hiện")
        rows = []
        for name in names:
            flagged = int(data[f"{name}_prediction"].eq(-1).sum())
            raw = int(data[f"{name}_raw_prediction"].eq(-1).sum())
            timing = meta.get("timings", {}).get(name, {})
            row = {"Thuật toán": MODELS[name], "Dự đoán bất thường gốc": raw,
                   "Cảnh báo sau lọc": flagged, "Dao động được lọc": raw - flagged,
                   "Tỷ lệ cảnh báo (%)": round(100 * flagged / len(data), 2),
                   "Huấn luyện + dự đoán (s)": timing.get("train_seconds", 0) + timing.get("predict_seconds", 0)}
            if run.metrics:
                row.update({f"{key} sau lọc": value for key, value in run.metrics[name].items()})
                row.update({f"{key} gốc": value for key, value in meta["raw_metrics"][name].items()})
            rows.append(row)
        compact = []
        for name in names:
            row = {"Thuật toán": MODELS[name], "Điểm cần kiểm tra": int(data[f"{name}_prediction"].eq(-1).sum())}
            if run.metrics:
                cm = meta["confusion_matrices"][name]
                row.update({"Cảnh báo đúng": cm[1][1], "Cảnh báo nhầm": cm[0][1], "Bỏ sót": cm[1][0]})
                if data[meta["label_col"]].eq(-1).any():
                    row["F1-score (%)"] = run.metrics[name]["f1"] * 100
            compact.append(row)
        show_table(pd.DataFrame(compact), dark, column_config={"F1-score (%)": st.column_config.NumberColumn(format="%.1f%%")})
        with st.expander("Xem chi tiết kết quả gốc và sau lọc"):
            show_table(pd.DataFrame(rows), dark, column_config={
                **{column: st.column_config.NumberColumn(format="%.3f") for column in rows[0] if column.startswith(("precision", "recall", "f1"))},
                "Huấn luyện + dự đoán (s)": st.column_config.NumberColumn(format="%.3f"),
            })
        st.caption("Cùng tập train/test, cùng năm chỉ số cho bốn thuật toán. Điểm quyết định là điểm gốc của mô hình, không phải điểm sau lọc. Nhiều cảnh báo hơn không chứng minh thuật toán tốt hơn.")
        with st.expander("Ngưỡng và độ biến động học từ tập huấn luyện"):
            st.json(meta["noise_guard"])
            show_table(pd.DataFrame.from_dict(meta["train_baselines"], orient="index").rename_axis("Chỉ số").reset_index(), dark)
            st.caption("Ngưỡng chỉ được học từ phần huấn luyện. Mức dung sai tối thiểu là giả định cho demo, cần hiệu chỉnh theo hệ thống và khoảng lấy mẫu thực tế. Có thể bỏ lọc để xem dự đoán gốc ở cấu hình.")
    with details:
        name = st.selectbox("Thuật toán cần xem", names, format_func=MODELS.get, key="dbms_detail_model")
        view = st.radio("Lọc thời điểm", ["Chỉ cảnh báo", "Tất cả"], horizontal=True, key="dbms_detail_filter")
        selected = data.loc[data[f"{name}_prediction"].eq(-1)] if view == "Chỉ cảnh báo" else data
        columns = [meta["timestamp_col"], *METRICS, f"{name}_raw_prediction", f"{name}_prediction", f"{name}_score", "suspected_indicators"]
        if meta.get("label_col"):
            columns.append(meta["label_col"])
        if selected.empty:
            st.info("Không có cảnh báo của thuật toán này. Chọn Tất cả để xem các giá trị thực tế.")
        else:
            show_table(selected[columns].head(1000), dark)
            row_index = st.selectbox("Thời điểm cần kiểm tra", list(selected.index),
                format_func=lambda idx: str(selected.loc[idx, meta["timestamp_col"]]), key="dbms_evidence_time")
            row = selected.loc[row_index]
            evidence = [{"Chỉ số": METRICS[metric], "Giá trị thực tế": row[metric],
                         "Độ lệch so với trung vị train": row[f"{metric}_deviation"],
                         "Điểm lệch theo ngưỡng": row[f"{metric}_deviation_score"]} for metric in METRICS]
            show_table(pd.DataFrame(evidence), dark)
            st.write("**Dấu hiệu nghi ngờ:** " + row["suspected_indicators"])
        st.info("QPS hoặc số kết nối tăng có thể đi kèm tải tăng; độ trễ và truy vấn chậm tăng có thể gợi ý suy giảm hiệu năng. Đây là giả thuyết cần đối chiếu log, lịch chạy tác vụ, khóa và tài nguyên máy chủ, chưa xác nhận nguyên nhân.")
        st.caption("1 = bình thường, -1 = bất thường. *_raw_prediction là dự đoán mô hình; *_prediction là cảnh báo vận hành sau chính sách lọc nếu đang bật. CSV tải xuống chứa mọi thời điểm kiểm tra và toàn bộ bằng chứng.")
    with evaluation:
        st.markdown("#### Precision, Recall, F1-score và confusion matrix")
        st.caption("Bất thường (-1) là lớp dương. Chỉ chấm phần kiểm tra; nhãn và tên kịch bản không tham gia huấn luyện. Các chỉ số nằm trong [0, 1].")
        if not run.metrics:
            st.info("Chưa có nhãn tham chiếu: không tính Precision, Recall, F1 hoặc confusion matrix. Không thể suy ra độ chính xác từ số cảnh báo.")
        else:
            scope = st.radio("Kết quả đánh giá", ["Cảnh báo sau lọc", "Dự đoán mô hình gốc"], horizontal=True, key="dbms_eval_scope")
            raw = scope == "Dự đoán mô hình gốc"
            metrics = meta["raw_metrics"] if raw else run.metrics
            matrices = meta["raw_confusion_matrices"] if raw else meta["confusion_matrices"]
            rows = []
            for name in names:
                cm = matrices[name]
                rows.append({"Thuật toán": MODELS[name], **metrics[name], "Accuracy": (cm[0][0] + cm[1][1]) / len(data), "TP": cm[1][1], "FP": cm[0][1], "FN": cm[1][0], "TN": cm[0][0]})
            show_table(pd.DataFrame(rows), dark)
            st.caption("Accuracy là tỷ lệ tất cả dự đoán đúng. Khi bất thường hiếm, hãy đọc cùng Precision, Recall và số điểm bỏ sót.")
            for column, name in zip(st.columns(len(names)), names):
                with column:
                    show_confusion(matrices[name], MODELS[name], dark)
            st.caption("Hàng = nhãn thật, cột = dự đoán; thứ tự Bình thường (1), Bất thường (-1). TP: cảnh báo đúng; FP: cảnh báo nhầm; FN: bỏ sót; TN: bình thường đúng.")
            if not data[meta["label_col"]].eq(-1).any():
                st.warning("Tập kiểm tra không có nhãn bất thường: Recall và F1 được quy ước bằng 0 khi không xác định. Hãy đánh giá cảnh báo nhầm trên bộ bình thường, rồi chuyển sang bộ bất thường để đo khả năng phát hiện.")
            st.caption("Các bộ demo là dữ liệu tổng hợp có nhãn theo sự kiện chèn, không phải bằng chứng chất lượng trên máy chủ thực. Không chọn tham số theo nhãn test rồi báo cáo đó là đánh giá độc lập.")
    with guide:
        _help()
        with st.expander("Thông tin mô hình và thời gian xử lý"):
            timings = [{"Thuật toán": MODELS[name], "Huấn luyện (giây)": meta.get("timings", {}).get(name, {}).get("train_seconds"),
                        "Dự đoán (giây)": meta.get("timings", {}).get(name, {}).get("predict_seconds")} for name in names]
            show_table(pd.DataFrame(timings), dark)
            st.json(meta.get("parameters", {}))
    warning_text = {
        "Suspected indicators": "Chỉ số lệch nền là bằng chứng quan sát, chưa xác định nguyên nhân.",
        "Tolerance floors": "Dung sai mặc định dành cho demo; chưa được hiệu chỉnh theo công suất hoặc SLA MySQL thực tế.",
        "Operational alerts": "Lọc dao động có thể bỏ sót dấu hiệu nhỏ hoặc thay đổi tương quan; hãy xem cả dự đoán và đánh giá gốc.",
        "Small dataset": "Dữ liệu ít hơn 100 mẫu, chưa đủ để kết luận chất lượng phát hiện.",
        "No ground-truth": "Không có nhãn tham chiếu: không tính Precision, Recall, F1 hay confusion matrix.",
        "Test labels contain no anomalies": "Tập kiểm tra không có bất thường có nhãn; hãy kiểm tra số cảnh báo nhầm, chưa kết luận khả năng phát hiện từ Recall/F1.",
        "Training labels contain anomalies": "Tập huấn luyện có nhãn bất thường. Mô hình vẫn học không giám sát, không dùng nhãn để lọc hàng; nền nhiễm bất thường có thể giảm độ nhạy.",
        "Calendar features": "Đã thêm đặc trưng lịch; cảnh báo sau lọc vẫn cần ít nhất một chỉ số MySQL lệch nền.",
    }
    with st.expander("Lưu ý nghiên cứu và giới hạn"):
        for message in meta.get("warnings", []):
            st.caption(next((translated for prefix, translated in warning_text.items() if message.startswith(prefix)), str(message)))
    st.divider()
    csv, export = st.columns(2)
    csv.download_button("Tải dự đoán CSV", run.export_csv(), "mysql_predictions.csv", "text/csv", key="dbms_download_csv", width="stretch")
    export.download_button("Tải kết quả và cấu hình JSON", json.dumps(run.summary(date_unit="ns"), ensure_ascii=False, indent=2),
                           "mysql_results.json", "application/json", key="dbms_download_json", width="stretch")


def _help() -> None:
    st.markdown("1. Chọn bộ kiểm thử, tải CSV năm chỉ số hoặc thu thập MySQL.\n2. Kiểm tra thời gian, đơn vị, nhãn 1/-1 và phần đầu dùng làm giai đoạn ổn định.\n3. Giữ bốn thuật toán và tỷ lệ train 70%, bấm Chạy phát hiện.\n4. Xem trạng thái, biểu đồ, giá trị và dấu hiệu nghi ngờ ở từng thời điểm.\n5. Khi có nhãn, so sánh kết quả gốc/sau lọc trong tab Đánh giá rồi xuất CSV/JSON.")
    st.caption("Mô hình chỉ học phần đầu, dự đoán phần cuối theo thời gian. Mọi lần thay dữ liệu hoặc cấu hình đều cần chạy lại. Không có nhãn thì không có chỉ số đánh giá.")
    st.markdown("**MAD:** lệch khỏi trung vị train. **Isolation Forest:** điểm dễ tách bởi cây. **LOF:** mật độ thấp hơn lân cận. **One-Class SVM:** ngoài vùng dữ liệu đã học. Bộ lọc vận hành yêu cầu thêm độ lệch chỉ số đủ lớn so với biến động train và dung sai demo; có thể tắt để nghiên cứu dự đoán gốc.")
    st.caption("Xem docs/DEMO_MYSQL.md để demo đầy đủ; docs/MYSQL_SETUP.md để tạo tài khoản và hiểu chính xác số liệu thu thập.")


def render_dbms_dashboard(project: Path, dark: bool, show_table, show_confusion) -> None:
    content, source_name = None, ""
    with st.container(border=True):
        st.subheader("1. Chọn dữ liệu hoạt động MySQL")
        source = st.radio("Nguồn dữ liệu MySQL", ["Dữ liệu kiểm thử MySQL", "Tải CSV MySQL", "Kết nối MySQL"], horizontal=True, key="dbms_source")
        if source == "Dữ liệu kiểm thử MySQL":
            sample = st.selectbox("Bộ dữ liệu kiểm thử", ["Hoạt động bình thường", "Hoạt động bất thường"], key="dbms_sample")
            path = project / "data" / ("mysql_normal.csv" if sample == "Hoạt động bình thường" else "mysql_anomalous.csv")
            if path.exists():
                content, source_name = path.read_bytes(), path.name
            else:
                st.error("Chưa có dữ liệu kiểm thử. Chạy python scripts/generate_mysql_demo.py tại thư mục dự án.")
            st.caption("Dữ liệu tổng hợp tái lập được, có dao động tự nhiên. Bộ bất thường chèn các đợt tăng QPS, kết nối, độ trễ và sự kiện phối hợp trong phần kiểm tra; nhãn theo kịch bản, không lấy từ mô hình.")
        elif source == "Tải CSV MySQL":
            uploaded = st.file_uploader("CSV MySQL (UTF-8, tối đa 10 MiB)", type=["csv"], key="dbms_csv_upload")
            if uploaded is not None:
                if uploaded.size > 10 * 1024 * 1024:
                    st.error("Tệp vượt quá 10 MiB. Hãy chia nhỏ rồi tải lại.")
                else:
                    content, source_name = uploaded.getvalue(), uploaded.name
        else:
            content, source_name = _mysql_source()
        with st.expander("Cấu trúc CSV năm chỉ số"):
            st.code("timestamp,queries_per_second,connections,response_time_ms,slow_queries,connection_errors,is_anomaly\n2026-01-01T00:00:00Z,50,20,8.2,0,0,1\n2026-01-01T00:01:00Z,51,21,8.4,0,0,1", language="csv")
            st.caption("Ví dụ chỉ minh họa định dạng. Nhãn tùy chọn: 1 bình thường, -1 bất thường. Cả năm chỉ số phải là số hữu hạn không âm; mỗi dòng có thời gian hợp lệ, duy nhất. QPS là tốc độ; slow_queries và connection_errors là số phát sinh trong khoảng, không phải bộ đếm tích lũy. Giữ khoảng lấy mẫu nhất quán.")
    if content is None:
        _help()
        return
    try:
        frame = read_csv_frame(BytesIO(content))
        missing = [metric for metric in METRICS if metric not in frame]
        if source == "Tải CSV MySQL":
            with st.expander("Cấu hình cột thời gian và cột đặc trưng", expanded=bool(missing)):
                manual = st.checkbox("Ánh xạ tên cột nguồn sang các chỉ số MySQL", value=False, key="dbms_manual_columns")
                if manual:
                    available = ["Chưa chọn", *list(frame.columns)]
                    mapping = {}
                    for canonical, title in {"timestamp": "Thời gian", **METRICS}.items():
                        mapping[canonical] = st.selectbox("Cột nguồn cho " + title.lower(), available,
                            index=available.index(canonical) if canonical in available else 0,
                            key="dbms_mapping_" + canonical)
                    selected_columns = list(mapping.values())
                    if "Chưa chọn" in selected_columns:
                        st.info("Chọn đủ một cột thời gian và năm cột chỉ số. Đơn vị phản hồi phải là ms; hai cột sự kiện phải là số phát sinh trong khoảng lấy mẫu.")
                        return
                    if len(set(selected_columns)) != len(selected_columns):
                        st.error("Mỗi cột nguồn chỉ được ánh xạ một lần; thời gian và các chỉ số cần khác nhau.")
                        return
                    original = frame
                    frame = original.drop(columns=list(mapping), errors="ignore").copy()
                    for canonical, selected in mapping.items():
                        frame[canonical] = original[selected]
                    content = frame.to_csv(index=False).encode("utf-8")
                    missing = []
                    st.caption("Chỉ đổi tên cột cho lần phân tích này. Giá trị đo và tệp gốc được giữ nguyên.")
        if missing:
            st.error("CSV thiếu chỉ số bắt buộc: " + ", ".join(missing))
            return
        with st.sidebar:
            time_col = st.selectbox("Cột thời gian MySQL", list(frame.columns), index=list(frame.columns).index("timestamp") if "timestamp" in frame else 0, key="dbms_timestamp")
            # Keep opting out distinct from an unset widget on later reruns.
            label_columns = [column for column in frame if column not in METRICS and column != time_col]
            default_label = next((column for column in ("is_anomaly", "label") if column in label_columns), None)
            no_label = "Không dùng nhãn"
            while no_label in label_columns:
                no_label += "_"
            labels = [no_label, *label_columns]
            selected_label = st.selectbox("Nhãn kiểm thử (tùy chọn)", labels,
                index=labels.index(default_label) if default_label else 0,
                format_func=lambda value: "Không dùng nhãn" if value == no_label else value, key="dbms_label")
            label_col = None if selected_label == no_label else selected_label
            names = st.multiselect("Thuật toán MySQL", list(MODELS), default=list(MODELS), format_func=MODELS.get, key="dbms_models",
                help="MAD: lệch khỏi trung vị. Isolation Forest: điểm dễ tách riêng bằng cây. LOF: mật độ thấp hơn lân cận. One-Class SVM: ngoài vùng hoạt động đã học.")
            fraction = st.slider("Dữ liệu huấn luyện MySQL (%)", 50, 90, 70, 5, key="dbms_train_fraction") / 100
            contamination = st.slider("Tỷ lệ bất thường dự kiến MySQL (%)", 0.1, 10.0, 1.0, 0.1, key="dbms_contamination") / 100
            with st.expander("Ngưỡng cảnh báo vận hành"):
                noise_guard = st.checkbox("Lọc dao động nhỏ theo thống kê và dung sai", value=True, key="dbms_noise_guard")
                threshold = st.slider("Ngưỡng độ lệch thống kê", 1.0, 10.0, 3.5, 0.5, key="dbms_deviation_threshold")
                st.caption("Mức 50 → 51 không tự động là bất thường. Cảnh báo sau lọc cần mô hình gắn cờ và có ít nhất một chỉ số vượt ngưỡng train cùng dung sai công khai. Dung sai demo cần hiệu chỉnh; bật lọc có thể tăng bỏ sót bất thường nhỏ.")
            st.caption("Năm chỉ số cùng tham gia huấn luyện; nhãn và tên kịch bản chỉ dùng đối chiếu. Tỷ lệ dự kiến không ép tập test phải có cảnh báo.")
        config = dict(timestamp_col=time_col, value_col="queries_per_second", label_col=label_col,
                      model_names=names, train_fraction=fraction, contamination=contamination,
                      analysis_mode="dbms", noise_guard=noise_guard, deviation_threshold=threshold)
        signature = sha256(content + json.dumps({"source": source_name, "backend": get_backend_url(), **config}, sort_keys=True).encode()).hexdigest()
        split = int(Decimal(len(frame)) * Decimal(str(fraction)))
        st.caption(f"{source_name} · {len(frame)} dòng · {split} dòng đầu huấn luyện, {len(frame)-split} dòng cuối kiểm tra sau sắp xếp thời gian.")
        if len(frame) < 100:
            st.warning("Dưới 100 mẫu: dùng thử quy trình; chưa đủ để kết luận chất lượng mô hình. Phần huấn luyện phải đại diện cho hoạt động bình thường.")
        with st.expander("Xem trước và tải dữ liệu đầu vào"):
            show_table(frame.head(50), dark)
            st.download_button("Tải CSV dữ liệu đầu vào", content, source_name, "text/csv", key="dbms_download_source")
        ready = bool(names) and split >= 3 and split < len(frame)
        if not ready:
            st.warning("Chọn ít nhất một thuật toán và cung cấp tối thiểu 3 dòng train, 1 dòng test.")
        if st.button("Chạy phát hiện", type="primary", key="dbms_run", disabled=not ready, width="stretch"):
            _clear_results()
            try:
                with st.spinner("Đang phân tích năm chỉ số MySQL trên FastAPI..."):
                    run = detect_via_api(content, source_name, **config)
                st.session_state["dbms_result"] = run
                st.session_state["dbms_result_signature"] = signature
            except BackendError as exc:
                st.error(str(exc))
        if ready and st.session_state.get("dbms_result_signature") == signature:
            _results(st.session_state["dbms_result"], source_name, dark, show_table, show_confusion)
        else:
            if "dbms_result" in st.session_state:
                st.info("Dữ liệu hoặc cấu hình đã thay đổi. Bấm Chạy phát hiện để cập nhật kết quả.")
            _help()
    except (ValueError, TypeError, pd.errors.ParserError, UnicodeDecodeError):
        st.error("Không đọc được CSV. Kiểm tra UTF-8, dấu phẩy phân cách, tiêu đề duy nhất và các dòng dữ liệu.")
