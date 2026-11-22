"""Three-screen persistent demo: monitor, control and academic evidence."""
from __future__ import annotations

import json
from html import escape
import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.api_client import BackendError, get_backend_url
from frontend.input_data import prepare_mysql_csv
from frontend.monitoring_client import monitor_get, monitor_post
from frontend.live_charts import activity_figure, comparison_figure
from frontend.admin_assistant import render_assistant_entry
from frontend.algorithm_status import render_algorithm_status


METRICS = {
    "queries_per_second": ("Truy vấn/giây", "QPS"),
    "connections": ("Kết nối đang mở", "kết nối"),
    "response_time_ms": ("Thời gian phản hồi", "ms"),
    "slow_queries": ("Truy vấn chậm", "sự kiện/kỳ"),
    "connection_errors": ("Kết nối thất bại", "sự kiện/kỳ"),
}
METRIC_HELP = {
    "queries_per_second": "Số truy vấn MySQL xử lý mỗi giây; giúp nhận biết thay đổi về tải.",
    "connections": "Số kết nối đang mở đến MySQL tại thời điểm lấy mẫu.",
    "response_time_ms": "Thời gian gửi và nhận phản hồi SELECT 1 của bộ thu; không phải thời gian trung bình của mọi truy vấn.",
    "slow_queries": "Số truy vấn vượt ngưỡng chậm của MySQL trong một khoảng lấy mẫu.",
    "connection_errors": "Số lần kết nối thất bại phát sinh trong một khoảng lấy mẫu.",
}
METRIC_DESCRIPTIONS = {
    "queries_per_second": "Lượng truy vấn mỗi giây",
    "connections": "Kết nối đang mở đến MySQL",
    "response_time_ms": "Độ trễ phép thăm dò SELECT 1",
    "slow_queries": "Truy vấn chậm trong kỳ lấy mẫu",
    "connection_errors": "Kết nối thất bại trong kỳ lấy mẫu",
}
MODELS = {"mad": "MAD", "isolation_forest": "Isolation Forest", "lof": "LOF", "one_class_svm": "One-Class SVM"}
LEVELS = {"normal": "Chưa có cảnh báo", "watch": "Theo dõi", "warning": "Cảnh báo", "critical": "Nghiêm trọng"}
COLORS = {"normal": "#16a34a", "watch": "#64748b", "warning": "#d97706", "critical": "#dc2626"}
SCREENS = ["Giám sát & Cảnh báo", "Điều khiển demo", "Đối chiếu thuật toán"]
CHART_CONFIG = {"displayModeBar": False, "displaylogo": False, "scrollZoom": False}


def _number(value, metric: str = "") -> str:
    if value is None:
        return "—"
    precision = 0 if metric in {"connections", "slow_queries", "connection_errors"} else 2
    return f"{float(value):,.{precision}f}"


def health_presentation(health: dict) -> tuple[str, str]:
    """Operational liveness takes precedence over the last model prediction."""
    collector = health.get("collector") or {}
    status = collector.get("status", "idle")
    if status == "stale":
        return "error", "Mất tín hiệu từ bộ thu. Giá trị cũ không thể xác nhận hệ thống đang bình thường."
    if status == "error":
        return "error", "Bộ thu hoặc phát lại gặp lỗi. " + str(collector.get("message") or "Kiểm tra nguồn dữ liệu.")
    if not health.get("baseline"):
        return "warning", "Chưa học mức nền. Mở Điều khiển demo để chọn dữ liệu bình thường và huấn luyện."
    if status == "completed":
        return "info", "Đã phát hết dữ liệu. Các giá trị bên dưới là lịch sử, không phải tín hiệu mới."
    if status == "stopped":
        return "info", "Nguồn đã dừng. Lịch sử được giữ lại; hệ thống chưa nhận số đo mới."
    if status in {"idle", "waiting"} or not collector.get("last_received_at"):
        return "info", "Đang chờ dữ liệu. Chọn nguồn phát lại hoặc khởi chạy bộ thu độc lập."
    if status != "running":
        return "warning", "Trạng thái nguồn chưa xác định. Chưa thể xác nhận nguồn đang gửi dữ liệu."
    age, threshold = collector.get("age_seconds"), collector.get("stale_after_seconds")
    if (any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            for value in (age, threshold)) or age < 0 or threshold <= 0):
        return "warning", "Thông tin thời gian nhận tín hiệu chưa hợp lệ. Chưa thể xác nhận nguồn đang gửi dữ liệu."
    if age > threshold:
        return "error", "Mất tín hiệu từ bộ thu. Giá trị cũ không thể xác nhận hệ thống đang bình thường."
    return "success", "Đang nhận dữ liệu từ nguồn giám sát."


def _health_bar(health: dict) -> None:
    collector = health.get("collector") or {}
    baseline = health.get("baseline") or {}
    mode = collector.get("mode")
    kind, message = health_presentation(health)
    tone, source, source_detail = source_presentation(health)
    mysql_status = "Đang nhận số đo" if mode == "live" and kind == "success" else "Chưa xác nhận"
    mysql_detail = "Bộ thu MySQL đang gửi dữ liệu mới" if mode == "live" and kind == "success" else (
        "Mô phỏng không cho biết tình trạng MySQL thật" if mode == "replay" else "Cần số đo mới từ bộ thu MySQL")
    age = collector.get("age_seconds")
    valid_age = isinstance(age, (int, float)) and not isinstance(age, bool) and math.isfinite(age) and age >= 0
    signal = f"{age:.1f} giây trước" if valid_age else "Chưa có mẫu mới"
    threshold = collector.get("stale_after_seconds")
    signal_meta = f"Ngưỡng mất tín hiệu: {threshold:g} giây" if isinstance(threshold, (int, float)) and not isinstance(threshold, bool) and math.isfinite(threshold) and threshold > 0 else "Theo thời điểm nhận dữ liệu"
    facts = [("Nguồn dữ liệu", source, source_detail),
             ("Tín hiệu MySQL", mysql_status, mysql_detail),
             ("Tín hiệu gần nhất", signal, signal_meta),
             ("Mức nền đang dùng", f"#{baseline['id']} · {baseline.get('rows', '—')} mẫu" if baseline else "Chưa học mức nền",
              ("Nền K1 · dữ liệu mô phỏng" if baseline.get("source") == "K1" else f"Nguồn nền: {baseline.get('source', '—')}") if baseline else "Thiết lập tại Điều khiển demo")]
    cells = "".join(f'<div class="health-cell"><div class="health-label">{escape(label)}</div><div class="health-value">{escape(value)}</div><div class="health-meta">{escape(meta)}</div></div>'
                    for label, value, meta in facts)
    st.markdown(f'<div class="health-grid">{cells}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="source-notice source-{tone}"><span class="status-dot" aria-hidden="true"></span><strong>{escape(source)}</strong><span>{escape(source_detail)}</span></div>', unsafe_allow_html=True)
    getattr(st, kind)(message)


def source_presentation(health: dict) -> tuple[str, str, str]:
    """Describe provenance independently of model votes or source availability."""
    collector = health.get("collector") or {}
    mode = collector.get("mode")
    if mode == "replay":
        return "simulated", "Dữ liệu mô phỏng", "Phát lại kịch bản để thử cảnh báo; không phản ánh MySQL thật."
    if mode == "live":
        if health_presentation(health)[0] == "success":
            return "live", "Dữ liệu trực tiếp", "Đang nhận số đo từ bộ thu MySQL; xem kết quả phát hiện bên dưới."
        return "waiting", "Nguồn MySQL trực tiếp", "Chưa có tín hiệu mới được xác nhận; số đo đã lưu chỉ là lịch sử."
    return "unknown", "Chưa chọn nguồn", "Vào Điều khiển demo để chọn mô phỏng hoặc bộ thu MySQL."


def flatten_history(samples: list[dict]) -> pd.DataFrame:
    """Export exact stored measurements, decisions, evidence and human feedback."""
    result = []
    for point in samples:
        row = {key: point.get(key) for key in ("id", "timestamp", "received_at", "source", "session_id", "scenario", "event_id", "baseline_id", "label", *METRICS,
                                                "raw_votes", "votes", "raw_level", "level")}
        for name in MODELS:
            row[f"{name}_raw_prediction"] = point.get("raw_predictions", {}).get(name)
            row[f"{name}_prediction"] = point.get("predictions", {}).get(name)
            row[f"{name}_score"] = point.get("scores", {}).get(name)
        row["voters"] = ",".join(point.get("voters", []))
        row["raw_voters"] = ",".join(point.get("raw_voters", []))
        feedback = point.get("feedback") or {}
        row["feedback_verdict"], row["feedback_note"] = feedback.get("verdict"), feedback.get("note")
        for evidence in point.get("evidence", []):
            for field in ("baseline", "delta", "relative_change", "allowed_deviation", "material"):
                row[f"{evidence['metric']}_{field}"] = evidence.get(field)
        result.append(row)
    return pd.DataFrame(result)


def _alert_reason(point: dict) -> str:
    descriptions = []
    for item in point.get("evidence", []):
        if not item.get("material"):
            continue
        metric = item["metric"]
        label, unit = METRICS.get(metric, (metric, ""))
        delta = item["delta"]
        change = f"{'tăng' if delta >= 0 else 'giảm'} {_number(abs(delta), metric)} {unit}"
        relative = item.get("relative_change")
        if relative is not None:
            change += f" ({abs(relative) * 100:,.1f}%)"
        descriptions.append(f"{label}: {_number(item['actual'], metric)} {unit}, {change} so với nền {_number(item['baseline'], metric)} {unit}")
    return "; ".join(descriptions) or "Điểm có đặc trưng khác với mức nền đã học."


def _alert_overview(health: dict, alerts: list[dict]) -> None:
    """Keep recorded incidents visible independently of current source liveness."""
    critical = [point for point in alerts if point.get("votes", 0) >= 3]
    warnings = [point for point in alerts if point.get("votes", 0) == 2]
    watched = [point for point in alerts if point.get("votes", 0) == 1]
    actionable = [point for point in alerts if point.get("votes", 0) >= 2]
    pending = sum((point.get("feedback") or {}).get("verdict", "unreviewed") == "unreviewed" for point in actionable)
    baseline_id = (health.get("baseline") or {}).get("id", "—")
    with st.container(border=True, key="monitor_alert_overview"):
        _section_header("Cảnh báo đã ghi nhận", f"Mức nền #{baseline_id} · Tối đa 100 điểm có phiếu gần nhất · {pending} điểm chưa đánh giá")
        if critical:
            st.error(f"NGHIÊM TRỌNG · Đã ghi nhận {len(critical)} thời điểm có 3–4/4 thuật toán báo động.", icon="🚨")
        elif warnings:
            st.warning(f"CẢNH BÁO · Đã ghi nhận {len(warnings)} thời điểm có 2/4 thuật toán báo động.", icon="⚠️")
        elif watched:
            st.info(f"Theo dõi · {len(watched)} thời điểm có 1/4 thuật toán gắn cờ; chưa đạt mức cảnh báo.")
        else:
            st.info("Chưa ghi nhận cảnh báo trong mức nền này. Có thể chạy demo K3 bên dưới để kiểm tra luồng cảnh báo.")
        cells = "".join(f'<div class="incident-count level-{level}"><strong>{count}</strong><span>{label}</span></div>'
                        for level, count, label in (("critical", len(critical), "Nghiêm trọng · 3–4/4"),
                                                     ("warning", len(warnings), "Cảnh báo · 2/4"),
                                                     ("watch", len(watched), "Theo dõi · 1/4")))
        st.markdown(f'<div class="incident-counts">{cells}</div>', unsafe_allow_html=True)
        if actionable:
            recent = actionable[0]
            st.write(f"**Cảnh báo gần nhất:** {_time_label(recent.get('received_at') or recent.get('timestamp'))} giờ VN · {recent.get('votes', 0)}/4 thuật toán.")
            st.write(_alert_reason(recent))
            st.caption("Thuật toán báo động: " + ", ".join(MODELS.get(name, name) for name in recent.get("voters", [])))
            st.caption("Đây là cảnh báo đã lưu. Trạng thái nguồn phía trên cho biết hiện có nhận dữ liệu mới hay không; phản hồi nằm ở nhật ký bên dưới.")
        with st.expander("Thử một cảnh báo mô phỏng", expanded=False):
            _demo_alert_button(health)


def _demo_alert_button(health: dict) -> None:
    baseline = health.get("baseline") or {}
    allowed = (health.get("collector") or {}).get("mode") != "live" and (not baseline or baseline.get("source") == "K1")
    if st.button("Chạy demo cảnh báo K3", key="monitor_demo_alert", type="primary", width="stretch", disabled=not allowed):
        _action("/demo/alert", {}, "Đang chạy mô phỏng K3. Chờ mẫu tiếp theo để xem cảnh báo và thuật toán bỏ phiếu.")
    if allowed:
        st.caption("Dùng dữ liệu mô phỏng: học nền K1 nếu chưa có, phát lại K1 và chèn 15 mẫu tăng kết nối/lỗi. Không tác động CSDL thật.")
    else:
        st.caption("Demo nhanh dùng mức nền K1 và nguồn mô phỏng. Với nguồn trực tiếp hoặc nền riêng, dùng Điều khiển demo để giữ đúng ngữ cảnh dữ liệu.")


def _alert_card(point: dict, show_table, dark: bool) -> None:
    level = point.get("level", "watch")
    if level not in {"watch", "warning", "critical"}:
        level = "watch"
    material = [item for item in point.get("evidence", []) if item.get("material")]
    voters = ", ".join(MODELS.get(name, name) for name in point.get("voters", []))
    reason = _alert_reason(point)
    scenario = point.get("scenario")
    origin = str(point.get("source") or "—")
    if scenario and scenario != origin:
        origin += f" / sự cố {scenario}"
    feedback = point.get("feedback") or {}
    reviewed = {"true_incident": "Đã xác nhận", "false_alarm": "Đã đánh dấu cảnh báo giả"}.get(feedback.get("verdict"), "Chưa đánh giá")
    with st.container(border=True, key=f"monitor_alert_{point['id']}"):
        st.markdown(f'<div class="alert-summary level-{level}"><div class="alert-summary-title"><strong>{escape(LEVELS.get(level, level))}</strong><span class="inline-badge">{point.get("votes", 0)}/4 thuật toán</span></div><div class="alert-summary-meta">Nhận lúc {escape(_time_label(point.get("received_at") or point.get("timestamp")))} giờ VN · Nguồn {escape(origin)} · {escape(reviewed)}</div><p><strong>Dấu hiệu:</strong> {escape(reason)}</p><div class="alert-summary-voters">Thuật toán phát hiện: {escape(voters)}</div></div>', unsafe_allow_html=True)
        with st.expander(f"Số liệu và phản hồi #{point['id']}", expanded=False):
            st.caption(f"Thời điểm gốc của mẫu tại nguồn: {_time_label(point.get('timestamp'))} giờ VN (UTC+7). Các dấu hiệu lệch nền chưa xác định nguyên nhân sự cố.")
            if material:
                table = pd.DataFrame([{
                    "Chỉ số": METRICS.get(item["metric"], (item["metric"], ""))[0],
                    "Thực tế": item["actual"], "Mức nền": item["baseline"], "Chênh lệch": item["delta"],
                    "Thay đổi (%)": None if item.get("relative_change") is None else 100 * item["relative_change"],
                    "Dung sai": item["allowed_deviation"],
                } for item in material])
                show_table(table, dark)
                st.caption("Phần trăm không xác định khi mức nền bằng 0; khi đó xem chênh lệch tuyệt đối.")
            else:
                st.caption("Không có chỉ số vượt dung sai vận hành tại điểm này. Xem dự đoán gốc để đối chiếu.")
            verdicts = {"Chưa đánh giá": "unreviewed", "Xác nhận sự cố thật": "true_incident", "Cảnh báo giả": "false_alarm"}
            selected = next((label for label, value in verdicts.items() if value == feedback.get("verdict")), "Chưa đánh giá")
            with st.form(f"monitor_feedback_{point['id']}"):
                verdict = st.radio("Phản hồi của quản trị viên", list(verdicts), index=list(verdicts).index(selected),
                                   horizontal=True, key=f"monitor_verdict_{point['id']}")
                note = st.text_input("Ghi chú", value=feedback.get("note") or "", max_chars=1000,
                                     key=f"monitor_note_{point['id']}")
                if st.form_submit_button("Lưu phản hồi", key=f"monitor_save_{point['id']}"):
                    try:
                        monitor_post(f"/alerts/{point['id']}/feedback", {"verdict": verdicts[verdict], "note": note})
                        st.success("Đã lưu phản hồi vào lịch sử.")
                    except BackendError as exc:
                        st.error(str(exc))


@st.fragment(run_every="1s")
def _monitor_panel(dark: bool, show_table, limit: int = 300) -> None:
    try:
        health = monitor_get("/health")
        baseline = health.get("baseline") or {}
        if not baseline:
            _health_bar(health)
            render_algorithm_status(None, [], fresh=False, dark=dark, show_table=show_table)
            _getting_started(health)
            return
        samples = monitor_get("/history", limit=limit, baseline_id=baseline["id"]).get("samples", [])
        alerts = monitor_get("/alerts", limit=100, baseline_id=baseline["id"]).get("alerts", [])
    except BackendError as exc:
        st.error(str(exc))
        st.warning("Trạng thái hiện tại chưa xác định. Không dùng số đo cũ để kết luận hệ thống bình thường.")
        st.caption("Trang sẽ tự thử kết nối lại. Nếu dịch vụ chưa chạy, mở CHAY_UNG_DUNG.bat trong thư mục dự án.")
        return
    _health_bar(health)
    latest = samples[-1] if samples else None
    description = "Giá trị mới nhất" if health_presentation(health)[0] == "success" else "Số đo đã lưu · Chưa có tín hiệu mới được xác nhận"
    _section_header("5 chỉ số đang theo dõi", description + " · Chênh lệch so với mức nền · Dấu ? giải thích từng chỉ số.")
    titles = ["Truy vấn / giây", "Kết nối đang mở", "Phản hồi (ms)", "Truy vấn chậm / kỳ", "Kết nối lỗi / kỳ"]
    with st.container(key="monitor_metrics"):
        cards = st.columns(5, gap="small")
        for card, title, (metric, (label, unit)) in zip(cards, titles, METRICS.items()):
            evidence = next((e for e in (latest or {}).get("evidence", []) if e["metric"] == metric), {})
            delta = evidence.get("delta")
            direction = "↑" if delta is not None and delta > 0 else "↓" if delta is not None and delta < 0 else "="
            material = evidence.get("material") is True
            has_vote = (latest or {}).get("votes", 0) > 0
            state = "is-deviating" if material and has_vote else "is-outside" if material else "is-neutral"
            state_label = "Cần kiểm tra · vượt nền" if material and has_vote else "Vượt dung sai nền" if material else "Trong dung sai nền" if evidence else "Chưa có số đo"
            with card.container(key=f"monitor_metric_{metric}"):
                st.metric(title, _number((latest or {}).get(metric), metric),
                          delta=f"{direction} {delta:+.2f} so với nền" if delta is not None else None, delta_color="off",
                          help=METRIC_HELP[metric] + f" Đơn vị: {unit}. Tăng hoặc giảm chưa đủ để kết luận bất thường.")
                st.markdown(f'<div class="metric-context"><span class="metric-state {state}">{state_label}</span><span class="metric-description">{METRIC_DESCRIPTIONS[metric]}</span></div>', unsafe_allow_html=True)
    if not latest:
        render_algorithm_status(None, samples, fresh=False, dark=dark, show_table=show_table)
        st.info("Chưa có mẫu được chấm bằng mức nền này. Mở Điều khiển demo để bắt đầu phát lại.")
        st.button("Thiết lập nguồn dữ liệu", key="monitor_open_setup", type="primary", on_click=_open_control)
        return
    if health_presentation(health)[0] == "success":
        level = latest.get("level", "normal")
        message = f"Mẫu gần nhất: {LEVELS.get(level, level)} · {latest.get('votes', 0)}/4 thuật toán đồng thuận sau lọc."
        if level == "critical":
            st.error(message)
        elif level == "warning":
            st.warning(message)
        elif level == "watch":
            st.caption(message)
        else:
            st.success(message)
    else:
        st.caption("Các thẻ chỉ số đang hiển thị số đo đã lưu. Chưa thể kết luận tình trạng MySQL hiện tại khi thiếu tín hiệu mới.")
    render_algorithm_status(latest, samples, fresh=health_presentation(health)[0] == "success", dark=dark, show_table=show_table)
    _alert_overview(health, alerts)
    actionable = [point for point in alerts if point.get("votes", 0) >= 2]
    watched = [point for point in alerts if point.get("votes", 0) == 1]
    _section_header("Nhật ký cảnh báo", "Các thời điểm cần xem xét, mới nhất ở trên. Mở từng thẻ để xem số liệu và lưu phản hồi.")
    if not actionable:
        st.info("Chưa có cảnh báo từ 2 thuật toán trở lên trong lịch sử đang xem.")
    for point in actionable[:3]:
        _alert_card(point, show_table, dark)
    if len(actionable) > 3:
        with st.expander(f"Xem thêm {min(len(actionable), 8) - 3} cảnh báo gần đây"):
            for point in actionable[3:8]:
                _alert_card(point, show_table, dark)
    if len(actionable) > 8:
        st.caption("Hiển thị 8 cảnh báo gần nhất. Mở Đối chiếu thuật toán để tải đầy đủ lịch sử.")
    with st.expander(f"Nhật ký theo dõi nhẹ (1/4): {len(watched)} điểm gần nhất"):
        if watched:
            show_table(pd.DataFrame([{"Thời điểm (giờ VN)": _time_label(point["timestamp"]), "Nguồn": point.get("source"),
                                      "Thuật toán": ", ".join(MODELS.get(m, m) for m in point.get("voters", []))}
                                     for point in watched]), dark)
        else:
            st.caption("Chưa có điểm theo dõi nhẹ.")
    with st.container(border=True, key="monitor_signal_chart"):
        _section_header("Diễn biến hoạt động", f"{len(samples)} mẫu gần nhất · Cập nhật {_time_label(latest.get('received_at'))} giờ VN")
        st.plotly_chart(activity_figure(samples, dark), width="stretch", theme=None, config=CHART_CONFIG, key="monitor_activity")
        st.caption("Nét đứt: mức nền. Vùng xanh nhạt: dung sai học từ nền. Điểm màu chỉ đánh dấu chỉ số vượt dung sai có thuật toán gắn cờ, không đánh dấu toàn bộ chỉ số. Thời gian biểu đồ: UTC.")
        st.markdown('<div class="vote-guide"><span class="level-watch">Theo dõi 1/4</span><span class="level-warning">Cảnh báo 2/4</span><span class="level-critical">Nghiêm trọng 3–4/4</span><span>Chạm hoặc rê chuột để xem giá trị và thuật toán phát hiện.</span></div>', unsafe_allow_html=True)


def _action(path: str, payload: dict, success: str) -> None:
    try:
        with st.spinner("Đang thực hiện..."):
            monitor_post(path, payload)
        st.session_state["monitor_notice"] = success
        st.rerun()
    except BackendError as exc:
        st.error(str(exc))


def _control(project: Path, dark: bool, show_table) -> None:
    try:
        health = monitor_get("/health")
        scenarios = monitor_get("/scenarios").get("scenarios", [])
    except BackendError as exc:
        st.error(str(exc))
        return
    _health_bar(health)
    st.markdown('<div class="guide-grid"><div class="guide-card"><strong>1 · Chọn mức hoạt động bình thường</strong><p>Học nền K1 để thử mô phỏng, hoặc dùng CSV đo từ chính MySQL của bạn.</p></div><div class="guide-card"><strong>2 · Bắt đầu nguồn dữ liệu</strong><p>Chọn phát lại mô phỏng hoặc bật bộ thu MySQL. Nguồn và trạng thái luôn được ghi rõ.</p></div><div class="guide-card"><strong>3 · Theo dõi và thử sự cố</strong><p>Mở Giám sát & Cảnh báo để xem chỉ số. Quay lại đây khi cần chèn sự cố hoặc dừng nguồn.</p></div></div>', unsafe_allow_html=True)
    st.button("Mở màn hình giám sát", key="monitor_control_view", on_click=_open_monitor, icon=":material/monitoring:")
    with st.container(key="monitor_control_columns"):
        training_column, source_column = st.columns([1, 1.12], gap="large")
        with training_column:
            with st.container(border=True, key="monitor_training_card"):
                _section_header("Học mức nền", "Mức nền là mốc hoạt động bình thường để cả 4 thuật toán đối chiếu.", "BƯỚC 1 · CHUẨN BỊ")
                live_source = (health.get("collector") or {}).get("mode") == "live"
                source_kind = st.radio("Dữ liệu học nền", ["K1 bình thường", "CSV của bạn"],
                                       index=int(live_source and (health.get("baseline") or {}).get("source") != "K1"),
                                       horizontal=True, key="monitor_baseline_source")
                if live_source:
                    st.info("Giám sát trực tiếp cần mức nền đo khi chính máy chủ này hoạt động bình thường. Trình chạy trực tiếp đã học nền thật; chỉ tải CSV mới khi muốn học lại.")
                records, source, row_count, invalid = None, "K1", 300, False
                if source_kind == "CSV của bạn":
                    upload = st.file_uploader("CSV nền có đủ năm chỉ số", type=["csv"], key="monitor_baseline_csv")
                    if upload is None:
                        row_count, invalid = 0, True
                    else:
                        source = upload.name
                        try:
                            _, frame, _ = prepare_mysql_csv(upload.getvalue())
                            if len(frame) > 10000:
                                raise ValueError("Tối đa 10.000 mẫu để học nền. Hãy chọn một khoảng dữ liệu ngắn hơn.")
                            records = json.loads(frame.to_json(orient="records", date_format="iso"))
                            row_count = len(frame)
                        except (ValueError, UnicodeDecodeError, pd.errors.ParserError) as exc:
                            st.error(str(exc))
                            row_count, invalid = 0, True
                else:
                    st.markdown('<div class="page-help">K1 có sẵn <strong>300 mẫu bình thường</strong>, tách riêng khỏi dữ liệu phát lại. Có thể giữ mặc định để bắt đầu.</div>', unsafe_allow_html=True)
                start, end, selected = 1, 0, 0
                with st.expander("Khoảng dữ liệu và tham số học", expanded=source_kind == "CSV của bạn"):
                    if row_count:
                        left, right = st.columns(2)
                        start = left.number_input("Từ bản ghi", min_value=1, max_value=row_count, value=1, key=f"monitor_baseline_start_{source}_{row_count}")
                        end = right.number_input("Đến bản ghi (gồm dòng này)", min_value=1, max_value=row_count, value=row_count,
                                                 key=f"monitor_baseline_end_{source}_{row_count}")
                        selected = max(0, int(end - start + 1))
                    contamination = st.slider("Tỷ lệ dự kiến khi học (%)", .1, 10., 1., .1, key="monitor_contamination") / 100
                    threshold = st.slider("Ngưỡng dung sai vận hành", 1., 10., 3.5, .5, key="monitor_deviation_threshold")
                    st.caption("Các tham số chỉ thay đổi khi bấm Học mức nền. Mẫu giám sát không tham gia bước học.")
                if row_count:
                    st.caption(f"Khoảng đã chọn: dòng {start}–{end}, gồm {selected} mẫu. Cần ít nhất 30 mẫu.")
                    if end < start:
                        invalid = True
                        st.error("Dòng kết thúc phải nằm sau hoặc trùng dòng bắt đầu.")
                    if records:
                        selected_frame = pd.DataFrame(records[int(start) - 1:int(end)])
                        if "label" in selected_frame and selected_frame["label"].eq(-1).any():
                            invalid = True
                            st.error("Khoảng được chọn có nhãn bất thường. Chọn lại giai đoạn nền bình thường; ứng dụng không tự bỏ dòng để làm sạch nhãn.")
                        with st.expander("Xem dữ liệu nền đã chọn"):
                            show_table(selected_frame.head(12), dark)
                if st.button("Học mức nền", type="primary", width="stretch", key="monitor_train", disabled=invalid or selected < 30):
                    payload = {"source": source, "start_index": int(start) - 1, "end_index": int(end),
                               "contamination": contamination, "deviation_threshold": threshold}
                    if records is not None:
                        payload["records"] = records
                    _action("/train", payload, "Đã học và lưu mức nền mới. Lịch sử cũ vẫn được giữ theo phiên nền.")
                if baseline := health.get("baseline"):
                    with st.expander(f"Thông tin mức nền #{baseline['id']}"):
                        st.write(f"Thời gian nguồn: {_time_label(baseline.get('start'))} đến {_time_label(baseline.get('end'))} giờ VN (UTC+7).")
                        show_table(pd.DataFrame([{"Chỉ số": METRICS.get(metric, (metric, ""))[0],
                                                  "Trung vị": values.get("median"), "Dung sai": values.get("allowed_deviation")}
                                                 for metric, values in baseline.get("baselines", {}).items()]), dark)
                st.caption("Chỉ học lại khi bạn chủ động chọn một giai đoạn nền mới.")
        with source_column:
            with st.container(border=True, key="monitor_source_card"):
                _section_header("Nguồn dữ liệu", "Phát lại kịch bản hoặc nhận số đo từ bộ thu độc lập.", "BƯỚC 2 · BẮT ĐẦU")
                mode = st.radio("Chế độ nguồn", ["Phát lại mô phỏng", "Bộ thu trực tiếp"],
                                index=int((health.get("collector") or {}).get("mode") == "live"),
                                horizontal=True, key="monitor_source_mode")
                if mode == "Phát lại mô phỏng":
                    st.caption("MÔ PHỎNG · Các nút trong chế độ này không tác động đến MySQL thật.")
                    catalog = {item.get("id", item.get("scenario")): item for item in scenarios}
                    options = [key for key in ("K1", "K2", "K3", "K4") if key in catalog] or ["K1", "K2", "K3", "K4"]
                    scenario = st.selectbox("Kịch bản", options, format_func=lambda key: catalog.get(key, {}).get("name", key), key="monitor_scenario")
                    interval = st.number_input("Giây giữa hai mẫu", min_value=.1, max_value=60., value=1., step=.1, key="monitor_interval")
                    st.markdown(f'<div class="page-help">{escape(catalog.get(scenario, {}).get("description", "Dữ liệu giả lập để diễn tập chức năng giám sát."))}</div>', unsafe_allow_html=True)
                    if not health.get("baseline"):
                        st.caption("Học mức nền trước khi bắt đầu phát lại.")
                    left, right = st.columns(2)
                    if left.button("Bắt đầu phát lại", key="monitor_replay_start", type="primary", width="stretch", disabled=not health.get("baseline")):
                        _action("/replay/start", {"scenario": scenario, "interval_seconds": float(interval), "rows": 180, "loop": False}, "Đang phát lại. Chuyển sang Giám sát & Cảnh báo để theo dõi.")
                    if right.button("Dừng nguồn", key="monitor_replay_stop", width="stretch"):
                        _action("/replay/stop", {}, "Đã dừng nguồn; lịch sử được giữ lại.")
                    st.caption("180 mẫu mỗi kịch bản. Chuyển màn hình không làm dừng luồng phát lại.")
                else:
                    st.write("Nhận số đo thật bằng tài khoản giám sát chỉ đọc. Tài khoản tạo tải được cấu hình riêng cho máy chủ thử nghiệm.")
                    left, right = st.columns(2)
                    if left.button("Chờ bộ thu trực tiếp", key="monitor_live_start", width="stretch", type="primary", disabled=not health.get("baseline")):
                        _action("/source/live", {"interval_seconds": 1., "stale_after_seconds": 5.}, "Đã chuyển sang nguồn trực tiếp. Khởi chạy bộ thu độc lập để gửi mẫu.")
                    if right.button("Dừng nhận dữ liệu", key="monitor_live_stop", width="stretch"):
                        _action("/replay/stop", {}, "Đã dừng nhận nguồn giám sát.")
                    with st.expander("Thiết lập bộ thu dữ liệu"):
                        st.code("$env:MYSQL_HOST = \"127.0.0.1\"\n$env:MYSQL_USER = \"anomaly_monitor\"\n$env:MYSQL_SSL_CA = \"C:\\certs\\ca.pem\"\n# Cung cấp MYSQL_PASSWORD trong môi trường riêng của bộ thu.\npython scripts/run_collector.py --backend-url " + get_backend_url() + " --interval 1", language="powershell")
                        st.caption("Chọn nền có thời gian trước các số đo trực tiếp. Bộ thu chỉ đọc trạng thái, thăm dò SELECT 1 và bỏ qua chu kỳ reset bộ đếm.")
            if mode == "Phát lại mô phỏng":
                with st.container(border=True, key="monitor_injection_card"):
                    _section_header("Chèn sự cố mô phỏng", "Chèn 15 mẫu sự cố vào luồng đang phát; không tạo tải trên CSDL thật.", "BƯỚC 3 · DIỄN TẬP")
                    collector = health.get("collector") or {}
                    can_inject = collector.get("mode") == "replay" and collector.get("status") == "running"
                    if not can_inject:
                        st.caption("Bắt đầu phát lại để bật các nút bên dưới.")
                    for column, code, title in zip(st.columns(3), ("K2", "K3", "K4"), ("K2 · Tăng truy vấn", "K3 · Kết nối và lỗi", "K4 · Tăng độ trễ")):
                        if column.button(title, key=f"monitor_inject_{code}", disabled=not can_inject, width="stretch"):
                            _action("/inject", {"scenario": code, "duration_samples": 15}, f"Đã xếp 15 mẫu sự cố mô phỏng {code} vào luồng phát lại.")
            else:
                _live_fault_panel()


@st.fragment(run_every="1s")
def _live_fault_panel() -> None:
    with st.container(border=True, key="monitor_live_fault_card"):
        _section_header("Tạo tải trên máy chủ thử nghiệm", "Thực thi tác vụ có giới hạn; bộ thu trực tiếp đo lại kết quả.", "DIỄN TẬP THỰC TẾ")
        try:
            state = monitor_get("/faults/live")
            health = monitor_get("/health")
        except BackendError as exc:
            st.error(str(exc))
            return
        target = state.get("target") or {}
        configured = state.get("enabled") and state.get("configured")
        if target:
            st.write(f"Máy chủ đích: **{target.get('host')}:{target.get('port')}**")
        if not configured:
            st.info(state.get("configuration_message") or "Chưa cấu hình tài khoản tạo tải cho máy chủ thử nghiệm.")
            st.code(".\\CHAY_DEMO_TRUC_TIEP.bat", language="powershell")
            st.caption("Công cụ sẽ hỏi địa chỉ, tài khoản và mật khẩu, rồi thu mức nền trước khi mở giao diện. Có thể thêm --no-tls cho MySQL cục bộ.")
        collector = health.get("collector") or {}
        same_target = bool(target.get("target_id")) and collector.get("target_id") == target.get("target_id")
        ready = configured and same_target and collector.get("mode") == "live" and health_presentation(health)[0] == "success"
        if configured and not ready:
            st.warning("Cần bộ thu đang gửi số đo mới từ đúng máy chủ đích. Chạy bộ thu trực tiếp trước khi tạo tải.")
        job = state.get("job") or {}
        active = job.get("status") in {"running", "stopping"}
        with st.expander("Thời lượng và cường độ tải"):
            duration = st.slider("Thời lượng tối đa (giây)", 1, 60, 15, key="monitor_fault_duration")
            rate = st.slider("K2 · Truy vấn mục tiêu mỗi giây", 1, 500, 100, key="monitor_fault_rate")
            connections = st.slider("K3 · Số kết nối giữ mở", 1, 20, 10, key="monitor_fault_connections")
            auth_failures = st.number_input("K3 · Số lần thử đăng nhập lỗi", min_value=0, max_value=3, value=0,
                                            key="monitor_fault_auth_failures",
                                            help="Dùng tên tài khoản ngẫu nhiên không tồn tại; mặc định không tạo lỗi đăng nhập.")
            st.caption("K2 dùng SELECT 1. K3 giữ kết nối và tùy chọn tạo tối đa 3 lần xác thực lỗi. K4 chạy SLEEP(0.2), hạ long_query_time riêng trên phiên tạo tải.")
        for column, code, title in zip(st.columns(3), ("K2", "K3", "K4"),
                                       ("K2 · Tăng truy vấn", "K3 · Tăng kết nối", "K4 · Truy vấn chậm")):
            if column.button(title, key=f"monitor_live_fault_{code}", disabled=not ready or active, width="stretch"):
                _action("/faults/live", {"scenario": code, "duration_seconds": int(duration),
                                          "rate_per_second": int(rate), "connections": int(connections),
                                          "auth_failures": int(auth_failures)},
                        f"Đã bắt đầu tạo tải thật {code}. Chuyển sang Giám sát & Cảnh báo để xem số đo.")
        if job:
            labels = {"running": "Đang tạo tải", "stopping": "Đang dừng và đóng kết nối", "completed": "Đã hoàn tất",
                      "stopped": "Đã dừng", "failed": "Tác vụ gặp lỗi", "interrupted": "Bị ngắt khi dịch vụ khởi động lại"}
            message = f"{job.get('scenario', '')} · {labels.get(job.get('status'), job.get('status', ''))}"
            getattr(st, "warning" if active else "error" if job.get("status") in {"failed", "interrupted"} else "info")(message)
            counters = job.get("counters") or {}
            st.caption(f"Truy vấn hoàn tất: {counters.get('successful_queries', 0)} · Kết nối đã mở: {counters.get('opened_connections', 0)} · Lỗi xác thực đo được: {counters.get('expected_auth_failures', 0)}")
            if job.get("message"):
                st.caption(job["message"])
        left, right = st.columns(2)
        if left.button("Dừng tạo tải", key="monitor_live_fault_stop", disabled=not active, width="stretch"):
            _action("/faults/live/stop", {}, "Đã dừng tác vụ tạo tải và đóng các kết nối của tác vụ.")
        right.button("Xem giám sát", key="monitor_live_fault_view", width="stretch", on_click=_open_monitor)
        st.caption("K4 giúp tăng bộ đếm truy vấn chậm; không bảo đảm thời gian phản hồi SELECT 1 của bộ thu cũng tăng. Dữ liệu thật không tự được gắn nhãn sự cố để tính Precision/Recall/F1.")


def _comparison(dark: bool, show_table) -> None:
    try:
        health = monitor_get("/health")
        catalog = monitor_get("/catalog")
    except BackendError as exc:
        st.error(str(exc))
        return
    _health_bar(health)
    available = [item for item in catalog.get("baselines", []) if item.get("sample_count", 0) > 0]
    if not available:
        st.info("Chưa có lịch sử chấm điểm. Học mức nền rồi phát lại một kịch bản trước.")
        st.button("Thiết lập demo", key="monitor_open_setup", type="primary", on_click=_open_control)
        return
    baseline_ids = sorted({item["id"] for item in available}, reverse=True)
    current_id = (health.get("baseline") or {}).get("id")
    if current_id in baseline_ids:
        baseline_ids.remove(current_id)
        baseline_ids.insert(0, current_id)
    with st.container(border=True, key="monitor_comparison_filters"):
        _section_header("Phạm vi đối chiếu", "Giữ cùng mức nền và tập mẫu để so sánh công bằng.")
        left, right = st.columns(2)
        baseline_id = left.selectbox("Mức nền đối chiếu", baseline_ids, format_func=lambda value: f"Mức nền #{value}", key="monitor_comparison_baseline")
        sources = sorted({item["source"] for item in catalog.get("sources", [])
                          if item["baseline_id"] == baseline_id and item.get("sample_count", 0) > 0})
        source = right.selectbox("Nguồn đối chiếu", ["Tất cả nguồn", *sources], key=f"monitor_comparison_source_{baseline_id}")
        selected_source = None if source == "Tất cả nguồn" else source
        toggle_column, update_column = st.columns([2, 1])
        raw = toggle_column.toggle("Xem dự đoán gốc của mô hình", value=False, key="monitor_raw_predictions",
                                   help="Tắt để xem cảnh báo sau bộ lọc vận hành. Đổi công tắc không học lại mô hình.")
        refresh = update_column.button("Cập nhật chứng cứ", key="monitor_refresh_evidence", width="stretch")
    scope = (get_backend_url(), baseline_id, selected_source)
    snapshot = st.session_state.get("monitor_evidence_snapshot")
    if refresh or not snapshot or snapshot["scope"] != scope:
        try:
            evidence = monitor_get("/evidence", source=selected_source, baseline_id=baseline_id)
        except BackendError as exc:
            st.error(str(exc))
            return
        st.session_state["monitor_evidence_snapshot"] = {"scope": scope, "data": evidence}
    else:
        evidence = snapshot["data"]
    samples = evidence.get("samples", [])
    chart_samples = samples[-1000:]
    evaluation = evidence.get("evaluation") or {}
    with st.container(border=True, key="monitor_comparison_panel"):
        _section_header("Dấu hiệu của từng thuật toán", "Dự đoán gốc" if raw else "Sau bộ lọc vận hành")
        st.plotly_chart(comparison_figure(chart_samples, raw, dark), width="stretch", theme=None, config=CHART_CONFIG, key="monitor_comparison_chart")
        st.caption(f"{len(chart_samples)} / {len(samples)} mẫu trên biểu đồ. Chứng cứ chốt lúc {_time_label(evidence.get('exported_at'))} giờ VN. Trục biểu đồ dùng UTC. Đổi công tắc giữ nguyên tập mẫu.")
        st.caption("Mỗi hàng là một thuật toán; mỗi cột là cùng một thời điểm. Ô có màu cảnh báo là mẫu được thuật toán đó gắn cờ.")
        decision_key = "raw_predictions" if raw else "predictions"
        counts = pd.DataFrame([{"Thuật toán": label, "Số mẫu đã xem": len(samples),
                                "Số mẫu được gắn cờ": sum(point.get(decision_key, {}).get(name) == -1 for point in samples)}
                               for name, label in MODELS.items()])
        show_table(counts, dark)
        st.caption("Số mẫu gắn cờ mô tả hoạt động phát hiện; nhiều cảnh báo hơn không đồng nghĩa thuật toán tốt hơn.")
    with st.container(border=True, key="monitor_evaluation_panel"):
        _section_header("Hiệu quả phát hiện", "Đánh giá bằng nhãn tham chiếu của cùng phiên mức nền.")
        section = evaluation.get("raw" if raw else "guarded") or {}
        if not section:
            st.info("Nguồn đang chọn chưa có nhãn tham chiếu. Không tự tạo Precision, Recall, F1 hay ma trận nhầm lẫn.")
        else:
            table = pd.DataFrame([{"Thuật toán": MODELS.get(name, name), **{key: values.get(key) for key in ("precision", "recall", "f1", "fp", "fn")}}
                                  for name, values in section.items()]).rename(columns={"precision": "Precision", "recall": "Recall", "f1": "F1", "fp": "FP", "fn": "FN"})
            show_table(table, dark, column_config={name: st.column_config.NumberColumn(format="%.3f") for name in ("Precision", "Recall", "F1")})
            st.caption(f"Dùng toàn bộ {evaluation.get('labeled_rows', 0)} mẫu có nhãn trong phạm vi đã chọn. FP: báo nhầm; FN: bỏ sót.")
            quality = go.Figure()
            for key, label, color in (("precision", "Cảnh báo đúng", "#2563eb"),
                                      ("recall", "Phát hiện đủ", "#0d9488"),
                                      ("f1", "F1 · Kết hợp", "#94a3b8")):
                quality.add_bar(name=label, x=[MODELS.get(name, name) for name in section],
                                y=[values.get(key) for values in section.values()], marker_color=color,
                                hovertemplate="%{x}<br>" + label + ": %{y:.3f}<extra></extra>")
            quality.update_layout(barmode="group", height=300, margin={"l": 35, "r": 10, "t": 70, "b": 35},
                                  yaxis={"range": [0, 1.05], "title": "Điểm (0–1)", "fixedrange": True},
                                  xaxis={"fixedrange": True, "automargin": True, "tickangle": 0,
                                         "tickvals": list(MODELS.values()), "ticktext": ["MAD", "Isolation<br>Forest", "LOF", "One-Class<br>SVM"]},
                                  legend={"orientation": "h", "x": 0, "y": 1.25, "font": {"size": 12}},
                                  font={"family": "Segoe UI, Arial, sans-serif", "size": 13},
                                  template="plotly_dark" if dark else "plotly_white", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(quality, width="stretch", theme=None, config=CHART_CONFIG, key="monitor_quality_chart")
            if not evaluation.get("anomaly_rows"):
                st.info("Không có bất thường được gắn nhãn trong phạm vi này; Recall/F1 chưa phản ánh khả năng phát hiện sự cố.")
            with st.expander("Ma trận nhầm lẫn của 4 thuật toán", expanded=False):
                items = list(section.items())
                for offset in range(0, len(items), 2):
                    for column, (name, values) in zip(st.columns(2), items[offset:offset + 2]):
                        matrix = values.get("confusion_matrix")
                        if matrix is None:
                            continue
                        figure = go.Figure(go.Heatmap(z=matrix, x=["Bình thường", "Bất thường"], y=["Bình thường", "Bất thường"],
                                                     text=matrix, texttemplate="%{text}", textfont={"size": 22}, colorscale="Blues", showscale=False,
                                                     hovertemplate="Nhãn thật: %{y}<br>Dự đoán: %{x}<br>Số mẫu: %{z}<extra></extra>"))
                        figure.update_layout(title={"text": MODELS.get(name, name), "font": {"size": 16}},
                                             xaxis_title="Dự đoán", yaxis_title="Nhãn thật", height=280,
                                             margin={"l": 65, "r": 20, "t": 50, "b": 60},
                                             font={"size": 13}, template="plotly_dark" if dark else "plotly_white",
                                             paper_bgcolor="rgba(0,0,0,0)")
                        figure.update_yaxes(autorange="reversed", automargin=True)
                        column.plotly_chart(figure, width="stretch", theme=None, config=CHART_CONFIG, key=f"monitor_cm_{name}")
    report = {"baseline_id": baseline_id, "source": selected_source,
              "baseline": evidence.get("baseline"), "exported_at": evidence.get("exported_at"),
              "evaluation": evaluation, "samples": samples,
              "policy": "Voting: 1 watch, 2 warning, 3–4 critical. Raw and guarded results preserved; synthetic results are not production validation."}
    with st.container(border=True, key="monitor_export_panel"):
        _section_header("Lưu báo cáo và chứng cứ", f"{len(samples)} mẫu đầy đủ, kèm phiên nền, dự đoán và phản hồi đã lưu.")
        left, right = st.columns(2)
        left.download_button("Tải chứng cứ CSV", flatten_history(samples).to_csv(index=False).encode("utf-8-sig"), "chung_cu_giam_sat.csv", "text/csv", key="monitor_export_csv", width="stretch")
        right.download_button("Tải chứng cứ JSON", json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), "chung_cu_giam_sat.json", "application/json", key="monitor_export_json", width="stretch")
        st.caption("CSV dùng để xử lý dữ liệu. JSON giữ thêm mức nền và toàn bộ cấu hình, đánh giá.")
    with st.expander("Hiểu cách đọc kết quả"):
        st.write("Precision cho biết tỷ lệ cảnh báo đúng. Recall cho biết tỷ lệ bất thường được phát hiện. F1 kết hợp hai chỉ số này.")
        show_table(pd.DataFrame([{"Thuật toán": "MAD", "Cách tìm dấu hiệu": "Tìm chỉ số lệch xa mức thông thường."},
                                 {"Thuật toán": "Isolation Forest", "Cách tìm dấu hiệu": "Tìm mẫu khác biệt, dễ tách khỏi các mẫu còn lại."},
                                 {"Thuật toán": "LOF", "Cách tìm dấu hiệu": "Tìm mẫu ít giống các mẫu lân cận."},
                                 {"Thuật toán": "One-Class SVM", "Cách tìm dấu hiệu": "Học vùng hoạt động thông thường, gắn cờ mẫu ở ngoài vùng đó."}]), dark)
        st.caption("Điểm quyết định thuộc riêng từng mô hình, không phải xác suất và không so sánh trực tiếp giữa các thuật toán. Mức đồng thuận là quy tắc minh họa, không bảo đảm phát hiện mọi sự cố.")


def render_live_workspace(project: Path, dark: bool, show_table, *, with_chat: bool = False) -> None:
    selected_screen = st.session_state.get("monitor_screen", SCREENS[0])
    title, description = {
        SCREENS[0]: ("Trung tâm giám sát", "Nắm trạng thái nguồn, theo dõi chỉ số và xử lý các thời điểm cần chú ý."),
        SCREENS[1]: ("Điều khiển demo", "Học mức nền, chọn luồng dữ liệu và diễn tập các kịch bản sự cố."),
        SCREENS[2]: ("Đối chiếu thuật toán", "So sánh bốn mô hình trên cùng tập dữ liệu và lưu chứng cứ của phiên phân tích."),
    }.get(selected_screen, ("Trung tâm giám sát", "Theo dõi hoạt động cơ sở dữ liệu."))
    st.markdown(f'<div class="workspace-header"><div><div class="workspace-kicker">ANOMALY LAB / MYSQL</div><h1>{escape(title)}</h1><p class="workspace-subtitle">{escape(description)}</p></div></div>', unsafe_allow_html=True)
    if selected_screen != SCREENS[0]:
        st.button("Quay về giám sát MySQL", key="monitor_return_main", on_click=_open_monitor, icon=":material/arrow_back:")
    with st.expander("Công cụ bổ sung · Demo và đối chiếu", expanded=selected_screen != SCREENS[0]):
        screen = st.radio("Không gian làm việc", SCREENS, horizontal=True, key="monitor_screen", label_visibility="collapsed")
    if notice := st.session_state.pop("monitor_notice", None):
        st.success(notice)
    if screen == SCREENS[0]:
        if with_chat:
            from frontend.alert_chat import render_alert_chat
            with st.expander("Cấu hình AI và email", expanded=False):
                render_assistant_entry()
            with st.container(key="monitor_dashboard"):
                monitor_column, chat_column = st.columns([2.1, 1], gap="large")
                with monitor_column:
                    _monitor_panel(dark, show_table)
                with chat_column:
                    st.markdown('<div id="bot-canh-bao"></div>', unsafe_allow_html=True)
                    render_alert_chat(dark=dark)
        else:
            render_assistant_entry()
            _monitor_panel(dark, show_table)
    elif screen == SCREENS[1]:
        _control(project, dark, show_table)
    else:
        _comparison(dark, show_table)

def _time_label(value) -> str:
    if not value:
        return "—"
    try:
        stamp = pd.Timestamp(value)
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize("UTC")
        stamp = stamp.tz_convert("Asia/Ho_Chi_Minh")
        return stamp.strftime("%H:%M:%S · %d/%m/%Y")
    except (ValueError, TypeError):
        return str(value)


def _section_header(title: str, description: str = "", kicker: str = "") -> None:
    eyebrow = f'<div class="section-kicker">{escape(kicker)}</div>' if kicker else ""
    detail = f'<p>{escape(description)}</p>' if description else ""
    st.markdown(f'<div class="section-heading"><div>{eyebrow}<h2>{escape(title)}</h2>{detail}</div></div>', unsafe_allow_html=True)


def _open_control() -> None:
    st.session_state["monitor_screen"] = SCREENS[1]


def _open_monitor() -> None:
    st.session_state["monitor_screen"] = SCREENS[0]


def _getting_started(health: dict) -> None:
    st.markdown('<div class="guide-grid"><div class="guide-card"><strong>Học mức nền</strong><p>Dùng K1 có sẵn hoặc chọn một khoảng dữ liệu bình thường của bạn.</p></div><div class="guide-card"><strong>Bắt đầu nguồn dữ liệu</strong><p>Phát lại K1–K4 để diễn tập hoặc nhận số đo từ bộ thu độc lập.</p></div><div class="guide-card"><strong>Đọc và đối chiếu cảnh báo</strong><p>Xem chỉ số lệch nền, thuật toán bỏ phiếu và lưu phản hồi.</p></div></div>', unsafe_allow_html=True)
    st.button("Thiết lập demo", key="monitor_open_setup", type="primary", on_click=_open_control)
    _demo_alert_button(health)

