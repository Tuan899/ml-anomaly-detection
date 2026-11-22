"""Administrator chat and email settings, opened explicitly from the dashboard.

The backend owns the evidence, conversation history and mail queue. Merely
rendering the launcher performs no request and never starts an AI or mail call.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import streamlit as st

from frontend.api_client import BackendError
from frontend.monitoring_client import monitor_get, monitor_post


PREFIX = "admin_assistant_"
DEFAULT_MODEL = "gpt-6.2-sol"


def _key(name: str) -> str:
    return PREFIX + name


def _close() -> None:
    st.session_state[_key("dialog_open")] = False


def _notice(name: str) -> None:
    notice = st.session_state.pop(_key(name + "_notice"), None)
    if notice:
        kind, message = notice
        getattr(st, kind)(message)


def _redacted_error(exc: BackendError, secrets: list[str]) -> str:
    message = str(exc)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[đã ẩn]")
    return message


def _save_ai() -> None:
    secret = st.session_state.get(_key("api_key"), "")
    payload = {
        "enabled": st.session_state[_key("ai_enabled")],
        "model": st.session_state[_key("ai_model")].strip(),
        "api_key": secret,
    }
    try:
        monitor_post("/assistant/config/ai", payload)
        st.session_state[_key("ai_notice")] = ("success", "Đã lưu cấu hình AI.")
    except BackendError as exc:
        st.session_state[_key("ai_notice")] = ("error", _redacted_error(exc, [secret]))
    finally:
        # A submit callback runs before widgets are instantiated on the next run.
        st.session_state[_key("api_key")] = ""


def _save_email() -> None:
    secret = st.session_state.get(_key("smtp_password"), "")
    recipients = st.session_state[_key("recipients")].replace("\n", ",")
    payload = {
        "enabled": st.session_state[_key("email_enabled")],
        "host": st.session_state[_key("smtp_host")].strip(),
        "port": int(st.session_state[_key("smtp_port")]),
        "security": st.session_state[_key("smtp_security")],
        "username": st.session_state[_key("smtp_username")].strip(),
        "password": secret,
        "sender": st.session_state[_key("sender")].strip(),
        "recipients": [value.strip() for value in recipients.split(",") if value.strip()],
        "cooldown_seconds": int(st.session_state[_key("cooldown")]),
    }
    try:
        monitor_post("/assistant/config/email", payload)
        st.session_state[_key("email_notice")] = ("success", "Đã lưu cấu hình email.")
    except BackendError as exc:
        st.session_state[_key("email_notice")] = ("error", _redacted_error(exc, [secret]))
    finally:
        st.session_state[_key("smtp_password")] = ""


def _gmail_preset() -> None:
    st.session_state[_key("smtp_host")] = "smtp.gmail.com"
    st.session_state[_key("smtp_port")] = 587
    st.session_state[_key("smtp_security")] = "starttls"


def _sources(sources: list | None) -> None:
    if sources:
        st.caption("Chứng cứ: " + ", ".join(f"#{value}" for value in sources))


def _mode_label(mode: str | None) -> str:
    return "AI · OpenAI" if mode == "ai" else "Giải thích theo quy tắc"


def _alert_label(point: dict) -> str:
    identifier = point.get("id", point.get("sample_id"))
    details = [f"#{identifier}"]
    if point.get("timestamp"):
        timestamp = str(point["timestamp"])
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone(timedelta(hours=7)))
                timestamp = parsed.strftime("%d/%m/%Y %H:%M:%S") + " · giờ Việt Nam"
        except ValueError:
            pass
        details.append(timestamp)
    if point.get("votes") is not None:
        details.append(f"{point['votes']}/4 thuật toán")
    if point.get("source"):
        source = str(point["source"])
        if source.startswith("replay:"):
            source = "Mô phỏng · " + source.partition(":")[2]
        elif source == "live":
            source = "Bộ thu trực tiếp"
        details.append(source)
    return " · ".join(details)


def _alert_options(alerts: list[dict], key: str, *, optional: bool) -> tuple[list, dict]:
    labels = {point.get("id", point.get("sample_id")): _alert_label(point) for point in alerts}
    labels.pop(None, None)
    options = ([None] if optional else []) + list(labels)
    previous = st.session_state.get(key)
    # A selected record remains usable when a newer alert leaves the recent five.
    if previous is not None and previous not in options:
        options.append(previous)
        labels[previous] = f"#{previous} · Cảnh báo đã chọn trước đó"
    return options, labels


def _ask(question: str, conversation_id: str, alert_id: int | None) -> None:
    payload = {"question": question, "conversation_id": conversation_id}
    if alert_id is not None:
        payload["alert_id"] = alert_id
    try:
        with st.spinner("Đang đọc dữ liệu cảnh báo…"):
            monitor_post("/assistant/chat", payload)
    except BackendError as exc:
        st.error(str(exc))
        return
    # Reload authoritative history; no locally invented answer or success mode.
    st.rerun()


def _render_chat(status: dict, briefing: dict | None) -> None:
    conversation_id = st.session_state.setdefault(_key("conversation_id"), uuid4().hex)
    ai = status.get("ai", {})
    ready = ai.get("enabled") and ai.get("configured")
    st.markdown("### Hiểu cảnh báo, biết bước tiếp theo")
    st.caption("Đã bật AI · mỗi câu trả lời ghi rõ chế độ thực tế được sử dụng."
               if ready else "Giải thích theo quy tắc · bạn có thể hỏi ngay. Kết nối OpenAI tại tab Cấu hình AI khi cần.")
    if briefing:
        with st.container(border=True):
            st.markdown("**Tình hình từ dữ liệu đã ghi nhận**")
            st.caption("Giải thích theo quy tắc · không thay thế trạng thái nguồn giám sát hiện tại")
            st.write(briefing.get("summary", "Chưa có bản tin."))
            _sources(briefing.get("sources"))
    alerts = (briefing or {}).get("alerts", [])
    options, labels = _alert_options(alerts, _key("chat_alert"), optional=True)
    alert_id = st.selectbox(
        "Cảnh báo muốn trao đổi", options, key=_key("chat_alert"),
        format_func=lambda value: "Tổng quan hoạt động" if value is None else labels[value],
        help="Chọn một cảnh báo để câu trả lời bám sát số liệu của bản ghi đó. Chọn Tổng quan hoạt động để hỏi về tình hình chung.",
    )
    try:
        with st.spinner("Đang tải cuộc trò chuyện…"):
            history = monitor_get("/assistant/history", conversation_id=conversation_id).get("messages", [])
    except BackendError as exc:
        st.error(str(exc))
        return
    with st.container(height=340, border=True, key=_key("chat_history")):
        if not history:
            st.markdown("**Bạn muốn tìm hiểu điều gì?**")
            st.write("Chọn một câu hỏi gợi ý bên dưới hoặc nhập câu hỏi của bạn.")
            st.caption("Trợ lý giải thích chỉ số lệch nền, thuật toán phát hiện và gợi ý bước kiểm tra dựa trên dữ liệu đã lưu. Khi chưa đủ chứng cứ, câu trả lời cần phân biệt giả thuyết với kết luận.")
        for message in history:
            role = "user" if message.get("role") == "user" else "assistant"
            with st.chat_message(role):
                if role == "assistant":
                    st.caption(_mode_label(message.get("mode")))
                st.write(message.get("content", ""))
                if role == "assistant":
                    _sources(message.get("sources"))
    st.caption("Hỏi nhanh")
    columns = st.columns(3)
    questions = (
        ("why", "Vì sao cảnh báo?", "Vì sao xuất hiện cảnh báo này? Hãy giải thích bằng số liệu và phiếu của các thuật toán."),
        ("check", "Cần kiểm tra gì?", "Tôi cần kiểm tra gì trước với cảnh báo này? Phân biệt bằng chứng và giả thuyết."),
        ("summary", "Tóm tắt tình hình", "Tóm tắt tình trạng nguồn giám sát và các cảnh báo gần đây."),
    )
    for column, (name, label, question) in zip(columns, questions):
        if column.button(label, key=_key("ask_" + name), width="stretch"):
            _ask(question, conversation_id, alert_id)
    question = st.chat_input("Hỏi trợ lý về cảnh báo…", key=_key("question"), max_chars=4000)
    if question:
        _ask(question, conversation_id, alert_id)
    st.caption("Câu trả lời có mã chứng cứ để đối chiếu. Lịch sử được lưu trên máy chủ ứng dụng; cuộc trò chuyện này được giữ trong phiên giao diện.")


def _render_ai(settings: dict) -> None:
    _notice("ai")
    st.markdown("### Kết nối trợ lý AI")
    st.write("Trợ lý vẫn giải thích theo quy tắc khi chưa kết nối OpenAI. Nếu muốn dùng AI, nhập thông tin, bật tùy chọn rồi lưu.")
    st.caption(str(settings.get("message", "Chưa có cấu hình AI.")))
    with st.form(_key("ai_form")):
        st.checkbox("Bật giải thích bằng AI", value=bool(settings.get("enabled")), key=_key("ai_enabled"))
        st.text_input("Tên mô hình OpenAI", value=settings.get("model") or DEFAULT_MODEL, key=_key("ai_model"),
                      help="Dùng tên mô hình mà tài khoản API của bạn có quyền truy cập. Lưu cấu hình không đồng nghĩa với kiểm tra kết nối thành công.")
        st.text_input("Khóa API OpenAI", type="password", key=_key("api_key"),
                      help="Để trống để giữ khóa đã cấu hình. Không nhập khóa vào câu hỏi chat.")
        st.caption("Khi dùng AI, câu hỏi và số liệu cảnh báo cần thiết được gửi đến OpenAI.")
        st.form_submit_button("Lưu cấu hình AI", on_click=_save_ai, type="primary", width="stretch")
    st.caption("Khóa nhập qua biểu mẫu chỉ giữ trong bộ nhớ Backend. Sau khi Backend khởi động lại cần cấu hình lại.")
    st.caption("Khi AI chưa sẵn sàng hoặc gọi dịch vụ lỗi, câu trả lời được ghi rõ là giải thích theo quy tắc.")


def _job_status(value: str | None) -> str:
    return {
        "queued": "Đang chờ", "pending": "Đang chờ", "sending": "Đang gửi",
        "sent": "SMTP đã nhận", "failed": "Gửi lỗi", "unknown": "Chưa xác định",
        "skipped": "Đã bỏ qua", "cancelled": "Đã hủy",
    }.get(value, value or "Chưa xác định")


def _render_email(settings: dict, briefing: dict | None) -> None:
    _notice("email")
    st.markdown("### Nhận cảnh báo qua email")
    st.write("Điền thông tin dịch vụ email, lưu cấu hình rồi gửi một thư kiểm tra. Lịch sử bên dưới cho biết yêu cầu đang chờ, đã được máy chủ nhận hay gặp lỗi.")
    st.caption(str(settings.get("message", "Chưa cấu hình gửi email.")))
    st.button("Dùng cấu hình Gmail", key=_key("gmail_preset"), on_click=_gmail_preset,
              help="Chỉ điền máy chủ, cổng và kiểu bảo mật. Bạn vẫn cần nhập tài khoản, mật khẩu ứng dụng và người nhận.")
    with st.form(_key("email_form")):
        st.checkbox("Bật gửi email cảnh báo", value=bool(settings.get("enabled")), key=_key("email_enabled"))
        st.text_input("Máy chủ SMTP", value=settings.get("host") or "", placeholder="smtp.example.com", key=_key("smtp_host"))
        port, security = st.columns(2)
        # The Gmail preset writes the port before rendering. Let that stored
        # widget value take precedence without also supplying a default.
        port_default = {} if _key("smtp_port") in st.session_state else {"value": int(settings.get("port") or 587)}
        port.number_input("Cổng SMTP", min_value=1, max_value=65535, key=_key("smtp_port"), **port_default)
        security.selectbox("Bảo mật", ["starttls", "ssl"],
                           index=1 if settings.get("security") == "ssl" else 0, key=_key("smtp_security"),
                           format_func=lambda value: {"starttls": "STARTTLS · thường dùng cổng 587", "ssl": "SSL/TLS · thường dùng cổng 465"}[value],
                           help="Chọn theo hướng dẫn của dịch vụ email bạn sử dụng.")
        st.text_input("Tài khoản SMTP", key=_key("smtp_username"), help="Để trống để giữ tài khoản đã cấu hình.")
        st.text_input("Mật khẩu SMTP / mật khẩu ứng dụng", type="password", key=_key("smtp_password"),
                      help="Để trống để giữ mật khẩu đã cấu hình.")
        st.text_input("Email người gửi", value=settings.get("sender") or "", key=_key("sender"))
        st.text_input("Email người nhận", value=", ".join(settings.get("recipients") or []),
                      placeholder="admin@example.com, oncall@example.com", key=_key("recipients"),
                      help="Có thể nhập nhiều địa chỉ, cách nhau bằng dấu phẩy.")
        st.number_input("Khoảng chờ giữa các thông báo (giây)", min_value=60, max_value=3600,
                        value=int(settings.get("cooldown_seconds") or 300), step=60, key=_key("cooldown"),
                        help="Giới hạn tần suất gửi để tránh nhận quá nhiều thư khi liên tiếp xuất hiện cảnh báo.")
        st.form_submit_button("Lưu cấu hình email", on_click=_save_email, type="primary", width="stretch")
    st.caption("Chỉ tự gửi cho cảnh báo mới từ 2/4 phiếu sau khi bật; không gửi lại toàn bộ lịch sử. Email từ dữ liệu mô phỏng có nhãn mô phỏng.")
    st.caption("Tài khoản và mật khẩu nhập qua biểu mẫu giữ trong bộ nhớ Backend; cần cấu hình lại sau khi Backend khởi động lại. Với Gmail, dùng mật khẩu ứng dụng nếu tài khoản hỗ trợ.")
    st.divider()
    st.markdown("**Kiểm tra trước khi sử dụng**")
    st.caption("Xem trước chỉ đọc nội dung. Gửi email kiểm tra sẽ tạo yêu cầu gửi đến các địa chỉ đã lưu.")
    recipients = settings.get("recipients") or []
    st.caption("Người nhận đã lưu: " + (", ".join(recipients) if recipients else "Chưa có"))
    options, labels = _alert_options((briefing or {}).get("alerts", []), _key("preview_alert"), optional=False)
    alert_id = st.selectbox("Cảnh báo để xem trước email", options, format_func=lambda value: labels[value],
                            key=_key("preview_alert"), disabled=not options,
                            placeholder="Chưa có cảnh báo đã lưu")
    preview_column, test_column = st.columns(2)
    if preview_column.button("Xem trước email", key=_key("email_preview"), disabled=alert_id is None, width="stretch"):
        try:
            with st.spinner("Đang chuẩn bị nội dung email…"):
                preview = monitor_get("/assistant/email/preview", alert_id=alert_id)
            st.session_state[_key("email_preview_result")] = {"alert_id": alert_id, **preview}
        except BackendError as exc:
            st.session_state.pop(_key("email_preview_result"), None)
            st.error(str(exc))
    can_send = bool(settings.get("enabled") and settings.get("configured"))
    if test_column.button("Gửi email kiểm tra", key=_key("email_test"), disabled=not can_send, width="stretch"):
        try:
            with st.spinner("Đang gửi yêu cầu kiểm tra email…"):
                result = monitor_post("/assistant/email/test", {})
            job = result.get("job", result)
            state = job.get("status")
            if state == "sent":
                st.success("Máy chủ SMTP đã nhận email kiểm tra; chưa xác nhận thư đã vào Inbox.")
            elif state in {"queued", "pending", "sending"}:
                st.info("Email kiểm tra đã được xếp hàng. Xem kết quả tại Lịch sử gửi email.")
            elif state in {"failed", "unknown"}:
                st.error("Chưa xác nhận gửi email kiểm tra. Xem trạng thái tại Lịch sử gửi email.")
            else:
                st.info("Backend đã nhận yêu cầu kiểm tra. Xem trạng thái tại Lịch sử gửi email.")
        except BackendError as exc:
            st.error(str(exc))
    if not can_send:
        st.caption("Bật và lưu cấu hình email hợp lệ để gửi thư kiểm tra.")
    preview = st.session_state.get(_key("email_preview_result"))
    if preview and preview.get("alert_id") == alert_id:
        with st.expander("Nội dung email xem trước", expanded=True):
            st.write(preview.get("subject", ""))
            st.text(preview.get("body", ""))
    st.markdown("**Lịch sử gửi email**")
    counts = st.columns(3)
    for column, label, field in zip(counts, ["SMTP đã nhận", "Đang chờ", "Gửi lỗi"],
                                    ["sent_count", "pending_count", "failed_count"]):
        column.metric(label, settings.get(field, 0))
    if st.button("Làm mới trạng thái email", key=_key("refresh_email")):
        st.rerun()
    jobs = settings.get("jobs") or []
    if jobs:
        rows = [{"Mã": job.get("id"), "Cảnh báo": job.get("alert_id", job.get("sample_id")),
                 "Thời điểm": job.get("created_at", ""), "Trạng thái": _job_status(job.get("status")),
                 "Chi tiết": job.get("error") or job.get("message") or ""} for job in jobs[:20]]
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.caption("Chưa có tác vụ gửi email. Sau khi cấu hình và gửi thư kiểm tra, trạng thái sẽ xuất hiện tại đây.")


@st.dialog(title="Trợ lý quản trị viên", width="large", on_dismiss=_close)
def _assistant_dialog() -> None:
    try:
        with st.spinner("Đang kết nối trợ lý…"):
            status = monitor_get("/assistant/status")
    except BackendError as exc:
        st.error(str(exc))
        st.caption("Chưa đọc được cấu hình. Kiểm tra Backend rồi mở lại trợ lý.")
        return
    try:
        briefing = monitor_get("/assistant/briefing")
    except BackendError as exc:
        briefing = None
        st.warning(str(exc))
    chat, ai, email = st.tabs(["Trò chuyện", "Cấu hình AI", "Email cảnh báo"])
    with chat:
        _render_chat(status, briefing)
    with ai:
        _render_ai(status.get("ai", {}))
    with email:
        _render_email(status.get("email", {}), briefing)


def render_assistant_entry() -> None:
    """Render a quiet launcher; API requests start only after an explicit click."""
    launcher, description = st.columns([1, 2], vertical_alignment="center")
    if launcher.button("Trợ lý AI & Email", key=_key("open"), icon=":material/support_agent:", width="stretch"):
        st.session_state[_key("dialog_open")] = True
    description.caption("Giải thích cảnh báo · Cấu hình thông báo email")
    if st.session_state.get(_key("dialog_open"), False):
        _assistant_dialog()
