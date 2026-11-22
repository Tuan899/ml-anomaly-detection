"""In-app warning bot grounded in saved alerts; provider calls require a question."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
import math
from uuid import uuid4

import streamlit as st

from frontend.api_client import BackendError, get_backend_url
from frontend.monitoring_client import monitor_get, monitor_post


PREFIX = "alert_chat_"
FEED_LIMIT = 50
MODELS = {"mad": "MAD", "isolation_forest": "Isolation Forest", "lof": "LOF", "one_class_svm": "One-Class SVM"}
METRICS = {
    "queries_per_second": ("Truy vấn/giây", "QPS"),
    "connections": ("Kết nối đang mở", "kết nối"),
    "response_time_ms": ("Phản hồi", "ms"),
    "slow_queries": ("Truy vấn chậm", "lượt/kỳ"),
    "connection_errors": ("Kết nối lỗi", "lượt/kỳ"),
}


def _key(name: str) -> str:
    return PREFIX + name


def _positive_id(value) -> bool:
    return type(value) is int and value > 0


def _snapshot(previous: dict | None, scope: tuple, records: list, latest_id=None, context=None) -> tuple[dict, list[int]]:
    """Advance a bounded feed cursor; an initial/recovered scope is history."""
    by_id = {}
    for point in records if isinstance(records, list) else []:
        if not isinstance(point, dict) or not _positive_id(point.get("id")):
            continue
        if point.get("baseline_id") != scope[1] or type(point.get("votes")) is not int or not 2 <= point["votes"] <= 4:
            continue
        by_id[point["id"]] = point
    points = [by_id[identifier] for identifier in sorted(by_id)[-FEED_LIMIT:]]
    ids = {point["id"] for point in points}
    watermark = max([*ids, latest_id if _positive_id(latest_id) else 0])
    reset = (not previous or previous.get("scope") != scope or previous.get("context") != context
             or previous.get("disconnected", False))
    old_watermark = 0 if reset else previous.get("last_id", 0)
    arrived = [] if reset else sorted(identifier for identifier in ids if identifier > old_watermark)
    marked = set() if reset else set(previous.get("new_ids", []))
    state = {"scope": scope, "points": points, "last_id": max(watermark, old_watermark),
             "new_ids": sorted((marked | set(arrived)) & ids), "disconnected": False, "context": context}
    return state, arrived


def _time(value) -> str:
    if not value:
        return "chưa có thời gian"
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone(timedelta(hours=7))).strftime("%d/%m %H:%M:%S") + " giờ VN"
    except ValueError:
        pass
    return text


def _number(value) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "chưa có"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


def _source(point: dict) -> str:
    source, scenario = str(point.get("source") or "chưa rõ"), point.get("scenario")
    if scenario in {"K1", "K2", "K3", "K4"} or source in {"K1", "K2", "K3", "K4"} or source.startswith("replay:"):
        return "Dữ liệu mô phỏng · " + str(scenario or source)
    if source == "live":
        return "Bộ thu trực tiếp"
    return "Nguồn: " + source + " · cần đối chiếu nguồn gốc"


def _source_note(health: dict) -> str:
    collector = health.get("collector") or {}
    age, threshold = collector.get("age_seconds"), collector.get("stale_after_seconds")
    fresh = (collector.get("status") == "running" and collector.get("last_received_at")
             and all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                     for value in (age, threshold)) and 0 <= age <= threshold and threshold > 0)
    if fresh and collector.get("mode") == "replay":
        return "Đang nhận dữ liệu mô phỏng. Các cảnh báo dưới đây không phải sự cố trên MySQL thật."
    if fresh and collector.get("mode") == "live":
        return "Đang nhận mẫu mới từ bộ thu. Mỗi cảnh báo ghi riêng nguồn và thời điểm của bản ghi."
    return "Nguồn chưa có tín hiệu mới được xác nhận. Bot đang hiển thị lịch sử, chưa thể kết luận tình trạng MySQL hiện tại."


def _safe(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _evidence(point: dict) -> list[dict]:
    return [item for item in point.get("evidence", [])
            if isinstance(item, dict) and item.get("material") is True and item.get("metric") in METRICS]


def _evidence_text(point: dict, item: dict) -> str:
    metric = item["metric"]
    label, unit = METRICS[metric]
    return (f"{label}: {_number(point.get(metric, item.get('actual')))} {unit} · "
            f"nền {_number(item.get('baseline'))} · chênh {_number(item.get('delta'))}.")


def _alert_html(point: dict, new: bool = False) -> str:
    level = "critical" if point["votes"] >= 3 else "warning"
    title = "Nghiêm trọng" if level == "critical" else "Cảnh báo"
    evidence = _evidence(point)
    details = "".join(f'<div class="messenger-event-detail">{_safe(_evidence_text(point, item))}</div>' for item in evidence[:2])
    if len(evidence) > 2:
        details += f'<div class="messenger-event-detail">Còn {len(evidence) - 2} chỉ số lệch nền trong phần chi tiết.</div>'
    if not evidence:
        details = '<div class="messenger-event-detail">Mẫu có dấu hiệu khác mức nền. Mở chi tiết để đối chiếu.</div>'
    voters = ", ".join(MODELS.get(name, str(name)) for name in point.get("voters", []))
    marker = '<span class="messenger-badge badge-new">Mới trong phiên này</span>' if new else ""
    return (f'<div class="messenger-bubble bubble-alert alert-{level}">'
            f'<div class="messenger-event-title"><span class="messenger-badge badge-{level}">{title}</span>{marker}</div>'
            f'<strong>Cảnh báo #{point["id"]} · {point["votes"]}/4 thuật toán</strong>{details}'
            f'<div class="messenger-event-detail">Phát hiện bởi: {_safe(voters or "chưa có danh sách thuật toán")}</div>'
            f'<span class="messenger-badge badge-source">{_safe(_source(point))}</span></div>'
            f'<div class="messenger-meta">{_safe(_time(point.get("received_at") or point.get("timestamp")))} · '
            f'{"Mới trong phiên này" if new else "Lịch sử đã lưu"}</div>')


def _message_html(message: dict) -> str:
    user = message.get("role") == "user"
    body = _safe(message.get("content", "")).replace("\n", "<br>")
    who = "Bạn" if user else "AI · OpenAI" if message.get("mode") == "ai" else "Giải thích theo quy tắc"
    stamp = _time(message["created_at"]) + " · " if message.get("created_at") else ""
    sources = message.get("sources") if not user else None
    evidence = (" · Chứng cứ: " + ", ".join(f"#{identifier}" for identifier in sources)) if sources else ""
    return (f'<div class="messenger-bubble {"bubble-user" if user else "bubble-bot"}">{body}</div>'
            f'<div class="messenger-meta">{_safe(stamp + who + evidence)}</div>')


def _sort_time(value) -> float | None:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        result = stamp.timestamp()
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _timeline_events(points: list[dict], history: list[dict]) -> list[dict]:
    """Use receipt time for alerts and keep authoritative message order stable."""
    alert_times = []
    for point in points:
        received = _sort_time(point.get("received_at"))
        alert_times.append(received if received is not None else _sort_time(point.get("timestamp")))
    message_times = [_sort_time(message.get("created_at")) for message in history]
    known = [stamp for stamp in [*alert_times, *message_times] if stamp is not None]
    fallback = max(known, default=0) + 1
    ordered = []
    for index, (point, stamp) in enumerate(zip(points, alert_times)):
        ordered.append((fallback if stamp is None else stamp, 0, point.get("id", index), {"kind": "alert", "item": point}))
    previous = float("-inf")
    for index, (message, stamp) in enumerate(zip(history, message_times)):
        if stamp is None:
            stamp = next((value for value in message_times[index + 1:] if value is not None), fallback)
        previous = max(previous, stamp)
        ordered.append((previous, 1, index, {"kind": "message", "item": message}))
    return [event for _, _, _, event in sorted(ordered, key=lambda row: row[:3])]


def _render_timeline(state: dict, history: list[dict], *, connected: bool, scroll: bool) -> None:
    marked = set(state.get("new_ids", [])) if connected else set()
    events = _timeline_events(state.get("points", []), history)
    with st.container(height=440, border=False, key=_key("timeline"), autoscroll=scroll):
        if not events:
            st.markdown('<div class="messenger-empty"><div class="messenger-avatar">AL</div><strong>Chào bạn, mình là Anomaly Bot</strong><p>Mình sẽ nhắn khi có cảnh báo mới. Bạn cũng có thể hỏi về chỉ số và bước cần kiểm tra.</p></div>', unsafe_allow_html=True)
            st.caption("Chưa có cảnh báo từ 2/4 thuật toán trở lên trong phạm vi đang xem.")
        for event in events:
            item = event["item"]
            if event["kind"] == "message":
                role = "user" if item.get("role") == "user" else "assistant"
                with st.chat_message(role, avatar=":material/person:" if role == "user" else ":material/smart_toy:"):
                    st.markdown(_message_html(item), unsafe_allow_html=True)
                continue
            with st.chat_message("assistant", avatar=":material/smart_toy:"):
                st.markdown(_alert_html(item, item["id"] in marked), unsafe_allow_html=True)
                with st.expander(f"Chi tiết cảnh báo #{item['id']}", expanded=False):
                    st.caption("Thời điểm số đo: " + _time(item.get("timestamp")) + " · Ghi nhận: " + _time(item.get("received_at")))
                    for evidence in _evidence(item):
                        st.write(_evidence_text(item, evidence))
                    if not _evidence(item):
                        st.caption("Bản ghi chưa có giải thích chỉ số vượt nền; xem chi tiết cảnh báo để đối chiếu.")
                    st.caption("Chưa xác định nguyên nhân. Hãy đối chiếu nhật ký và thay đổi tải cùng thời điểm.")


def _conversation_id(backend: str) -> str:
    if st.session_state.get(_key("conversation_backend")) != backend:
        st.session_state[_key("conversation_backend")] = backend
        st.session_state[_key("conversation_id")] = uuid4().hex
        st.session_state[_key("alert")] = None
    return st.session_state[_key("conversation_id")]


def _render_context(state: dict) -> int | None:
    points = state.get("points", [])
    labels = {point["id"]: f"#{point['id']} · {point['votes']}/4 · {_time(point.get('timestamp'))}" for point in reversed(points)}
    options = [None, *labels]
    if st.session_state.get(_key("alert")) not in options:
        st.session_state[_key("alert")] = None
    with st.expander("Ngữ cảnh trò chuyện", expanded=False):
        alert_id = st.selectbox("Hỏi về cảnh báo", options, key=_key("alert"),
                               format_func=lambda value: "Tổng quan giám sát" if value is None else labels[value],
                               help="Chọn một bản ghi để bot giải thích đúng cảnh báo đó.")
    return alert_id


def _send_question(question: str, conversation_id: str, alert_id: int | None) -> None:
    payload = {"question": question, "conversation_id": conversation_id}
    if alert_id is not None:
        payload["alert_id"] = alert_id
    try:
        with st.spinner("Bot đang soạn trả lời…"):
            monitor_post("/assistant/chat", payload)
    except BackendError as exc:
        st.error(str(exc))
    else:
        st.session_state[_key("scroll_to_latest")] = True
        st.rerun()


def _render_header(health: dict | None = None, *, disconnected: bool = False) -> None:
    note = _source_note(health or {})
    collector = (health or {}).get("collector") or {}
    if disconnected:
        tone, label = "error", "Đang mất kết nối"
    elif collector.get("status") == "running" and note.startswith("Đang nhận"):
        tone, label = ("simulated", "Đang nhận mô phỏng") if collector.get("mode") == "replay" else ("live", "Đang nhận số đo MySQL")
    else:
        tone, label = "stale", "Đang xem lịch sử"
    st.markdown('<div class="messenger-header"><div class="messenger-avatar">AL</div><div><h3 class="messenger-title">Bot cảnh báo</h3><div class="messenger-subtitle">Anomaly Bot · Trợ lý giám sát MySQL</div></div><span class="messenger-action" title="Cảnh báo được cập nhật mỗi 3 giây">3s</span></div>'
                f'<div class="messenger-status status-{tone}" title="{_safe(note)}"><span class="status-dot" aria-hidden="true"></span>{_safe(label)}</div>', unsafe_allow_html=True)


def _render_composer(conversation_id: str, alert_id: int | None) -> None:
    with st.container(key=_key("prompts")):
        prompts = (("summary", "Tóm tắt", "Tóm tắt tình trạng nguồn giám sát và các cảnh báo gần đây."),
                   ("why", "Vì sao?", "Giải thích cảnh báo đang chọn dựa trên các chỉ số và thuật toán phát hiện."),
                   ("check", "Kiểm tra gì?", "Tôi cần kiểm tra gì tiếp? Hãy phân biệt chứng cứ với giả thuyết."))
        for column, (key, label, question) in zip(st.columns(3, gap="small"), prompts):
            if column.button(label, key=_key("quick_" + key), width="stretch"):
                _send_question(question, conversation_id, alert_id)
    question = st.chat_input("Nhắn tin cho Anomaly Bot…", key=_key("question"), max_chars=2000)
    if question:
        _send_question(question, conversation_id, alert_id)


@st.fragment(run_every="3s")
def render_alert_chat(dark: bool = False) -> None:
    """Poll saved alerts automatically; chat/AI only runs on an explicit question."""
    with st.container(border=True, key=_key("panel")):
        previous = st.session_state.get(_key("feed_state"))
        backend = get_backend_url()
        if previous and previous.get("scope", (None,))[0] != backend:
            previous = None
        try:
            health = monitor_get("/health")
            baseline_id = (health.get("baseline") or {}).get("id")
            alerts = [] if baseline_id is None else monitor_get("/alerts", limit=100, baseline_id=baseline_id).get("alerts", [])
        except BackendError as exc:
            state = dict(previous or {})
            state["disconnected"] = True
            st.session_state[_key("feed_state")] = state
            _render_header(disconnected=True)
            st.error("Bot chưa cập nhật được cảnh báo. " + str(exc))
            st.caption("Dữ liệu bên dưới là lịch sử đã tải; chưa thể xác nhận có cảnh báo mới. Bot sẽ tự thử kết nối lại.")
            _render_timeline(state, [], connected=False, scroll=False)
            return
        recovered = bool(previous and previous.get("disconnected"))
        collector = health.get("collector") or {}
        context = (collector.get("mode"), collector.get("source"), collector.get("session_id"))
        state, arrived = _snapshot(previous, (backend, baseline_id), alerts,
                                   (health.get("latest") or {}).get("id"), context)
        st.session_state[_key("feed_state")] = state
        _render_header(health)
        if recovered:
            st.info("Đã kết nối lại. Các bản ghi hiện có được hiển thị là lịch sử; bot sẽ tiếp tục theo dõi cảnh báo mới.")
        if baseline_id is None:
            st.info("Chưa có mức nền để chấm điểm. Thiết lập giám sát trước để bot nhận cảnh báo.")
        if arrived:
            st.toast(f"Đã ghi nhận {len(arrived)} cảnh báo mới.", icon=":material/notifications_active:")
        if state["new_ids"]:
            st.caption(f"{len(state['new_ids'])} cảnh báo mới trong phiên này, thuộc {len(state['points'])} bản ghi đang hiển thị.")
        conversation_id = _conversation_id(backend)
        with st.container(key=_key("context_row")):
            context_column, latest_column = st.columns([3, 1], gap="small")
            with context_column:
                alert_id = _render_context(state)
            with latest_column:
                if st.button("Tin mới ↓", key=_key("jump_latest"), help="Cuộn xuống cuối cuộc trò chuyện", width="stretch"):
                    st.session_state[_key("scroll_to_latest")] = True
        history, history_error = [], None
        try:
            history = monitor_get("/assistant/history", conversation_id=conversation_id).get("messages", [])
        except BackendError as exc:
            history_error = exc
        scroll = st.session_state.pop(_key("scroll_to_latest"), False) or not previous or previous.get("scope") != state["scope"]
        _render_timeline(state, history, connected=True, scroll=scroll)
        if history_error:
            st.warning("Chưa tải được cuộc trò chuyện. " + str(history_error))
        else:
            _render_composer(conversation_id, alert_id)
        with st.expander("Thông tin nguồn và cách bot hoạt động", expanded=False):
            st.caption(_source_note(health))
            st.caption("Tin mới ở cuối · Lưu tối đa 50 cảnh báo trong khung này · Chỉ cập nhật từ dữ liệu đã lưu. Thông báo tự động không gọi AI hoặc gửi ra ngoài ứng dụng.")
