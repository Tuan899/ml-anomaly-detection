"""Exercise explicit chat/configuration actions without AI, SMTP or network."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.api_client import BackendError


APP = '''
from frontend.admin_assistant import render_assistant_entry
render_assistant_entry()
'''
P = "admin_assistant_"


class FakeAssistant:
    def __init__(self):
        self.calls = []
        self.messages = []
        self.fail_chat = False
        self.fail_config = False
        self.fail_status = False
        self.ai_mode = "rules"
        self.status = {
            "ai": {"enabled": False, "configured": False, "provider": "openai",
                   "model": "gpt-6.2-sol", "message": "AI chưa được cấu hình."},
            "email": {"enabled": False, "configured": False, "host": "", "port": 587,
                      "security": "starttls", "sender": "", "recipients": [],
                      "cooldown_seconds": 300, "message": "Chưa cấu hình email.",
                      "jobs": [], "sent_count": 0, "pending_count": 0, "failed_count": 0},
        }
        self.briefing = {
            "health": {"collector": {"status": "stopped"}}, "baseline_id": 5,
            "alerts": [{"id": 42, "votes": 3, "source": "replay:K3",
                        "timestamp": "2026-11-21T01:00:00+00:00"}],
            "summary": "Nguồn đã dừng; cảnh báo #42 là dữ liệu lịch sử mô phỏng.",
            "mode": "rules", "sources": [42],
        }

    def get(self, path, **params):
        self.calls.append(("GET", path, deepcopy(params)))
        if path == "/assistant/status":
            if self.fail_status:
                raise BackendError("Không kết nối được Backend.")
            return deepcopy(self.status)
        if path == "/assistant/briefing":
            return deepcopy(self.briefing)
        if path == "/assistant/history":
            return {"conversation_id": params["conversation_id"], "messages": deepcopy(self.messages)}
        if path == "/assistant/email/preview":
            return {"subject": "[MÔ PHỎNG] Cảnh báo #42", "body": "Phiếu 3/4. Bản ghi đã lưu #42."}
        raise AssertionError(f"Unexpected GET {path}")

    def post(self, path, payload=None):
        payload = deepcopy(payload or {})
        self.calls.append(("POST", path, payload))
        if path == "/assistant/chat":
            if self.fail_chat:
                raise BackendError("Dịch vụ chat chưa phản hồi.")
            answer = "Đã đọc bản ghi #42 từ Backend; chưa xác định nguyên nhân."
            common = {"mode": self.ai_mode, "created_at": "2026-11-21T01:02:00+00:00", "sources": [42]}
            self.messages.extend([
                {"role": "user", "content": payload["question"], **common},
                {"role": "assistant", "content": answer, **common},
            ])
            return {"conversation_id": payload["conversation_id"], "answer": answer, **common}
        if path == "/assistant/config/ai":
            if self.fail_config:
                raise BackendError("Không thể lưu khóa " + payload["api_key"])
            self.status["ai"].update(enabled=payload["enabled"], model=payload["model"])
            self.status["ai"]["configured"] |= bool(payload["api_key"])
            return deepcopy(self.status["ai"])
        if path == "/assistant/config/email":
            if self.fail_config:
                raise BackendError("Không thể lưu mật khẩu " + payload["password"])
            for field in ("enabled", "host", "port", "security", "sender", "recipients", "cooldown_seconds"):
                self.status["email"][field] = payload[field]
            self.status["email"]["configured"] = bool(payload["host"] and payload["recipients"])
            return deepcopy(self.status["email"])
        if path == "/assistant/email/test":
            job = {"id": 9, "status": "queued", "created_at": "2026-11-21T01:02:00+00:00"}
            self.status["email"]["jobs"].append(job)
            self.status["email"]["pending_count"] += 1
            return deepcopy(job)
        raise AssertionError(f"Unexpected POST {path}")


class AdminAssistantFrontendTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeAssistant()
        for name, action in (("monitor_get", self.backend.get), ("monitor_post", self.backend.post)):
            boundary = patch("frontend.admin_assistant." + name, side_effect=action)
            boundary.start()
            self.addCleanup(boundary.stop)

    def ui(self, *, opened=True):
        app = AppTest.from_string(APP, default_timeout=30).run()
        self.assert_clean(app)
        self.assertEqual([], self.backend.calls, "The launcher must make no API request.")
        if opened:
            app.button(key=P + "open").click().run()
            self.assert_clean(app)
        return app

    def assert_clean(self, app):
        self.assertEqual([], [item.message for item in app.exception])

    def visible(self, app):
        return "\n".join(str(item.value) for kind in ("markdown", "caption", "text", "error", "warning", "success", "info")
                         for item in getattr(app, kind))

    def posts(self, path):
        return [data for method, route, data in self.backend.calls if method == "POST" and route == path]

    def test_launcher_is_quiet_and_dialog_reads_actual_evidence(self):
        app = self.ui()
        self.assertIn("dữ liệu lịch sử mô phỏng", self.visible(app))
        self.assertIn("Giải thích theo quy tắc", self.visible(app))
        self.assertEqual(["Trò chuyện", "Cấu hình AI", "Email cảnh báo"], [tab.label for tab in app.tabs])
        self.assertFalse(self.posts("/assistant/chat"))
        self.assertTrue(app.button(key=P + "email_test").disabled)
        conversation = app.session_state[P + "conversation_id"]
        self.assertTrue(re.fullmatch("[0-9a-f]{32}", conversation))

    def test_chat_uses_selected_alert_and_backend_history_with_stable_conversation(self):
        app = self.ui()
        conversation = app.session_state[P + "conversation_id"]
        app.selectbox(key=P + "chat_alert").set_value(42).run()
        app.chat_input(key=P + "question").set_value("Chỉ số nào lệch nền?").run()
        self.assert_clean(app)
        payload = self.posts("/assistant/chat")[-1]
        self.assertEqual({"question": "Chỉ số nào lệch nền?", "conversation_id": conversation, "alert_id": 42}, payload)
        self.assertIn("Đã đọc bản ghi #42 từ Backend", self.visible(app))
        self.assertIn("Chứng cứ: #42", self.visible(app))
        self.assertEqual(2, len(app.chat_message))
        app.button(key=P + "ask_check").click().run()
        self.assert_clean(app)
        self.assertEqual(conversation, self.posts("/assistant/chat")[-1]["conversation_id"])

    def test_chat_failure_does_not_fabricate_success_and_ai_mode_is_explicit(self):
        app = self.ui()
        self.backend.fail_chat = True
        app.button(key=P + "ask_why").click().run()
        self.assert_clean(app)
        self.assertIn("Dịch vụ chat chưa phản hồi", self.visible(app))
        self.assertEqual(0, len(app.chat_message))
        self.assertEqual(0, len(app.success))
        self.backend.fail_chat = False
        self.backend.ai_mode = "ai"
        app.button(key=P + "ask_summary").click().run()
        self.assertIn("AI · OpenAI", self.visible(app))

    def test_ai_config_clears_secret_even_when_backend_rejects_it(self):
        app = self.ui()
        secret = "test-private-api-key"
        app.checkbox(key=P + "ai_enabled").set_value(True)
        app.text_input(key=P + "ai_model").set_value("gpt-6.2-sol")
        app.text_input(key=P + "api_key").set_value(secret)
        app.button(key="FormSubmitter:" + P + "ai_form-Lưu cấu hình AI").click().run()
        self.assert_clean(app)
        self.assertEqual({"enabled": True, "model": "gpt-6.2-sol", "api_key": secret}, self.posts("/assistant/config/ai")[-1])
        self.assertEqual("", app.text_input(key=P + "api_key").value)
        self.assertNotIn(secret, self.visible(app))
        self.assertIn("Đã lưu cấu hình AI", self.visible(app))
        self.backend.fail_config = True
        app.text_input(key=P + "api_key").set_value(secret)
        app.button(key="FormSubmitter:" + P + "ai_form-Lưu cấu hình AI").click().run()
        self.assert_clean(app)
        self.assertEqual("", app.session_state[P + "api_key"])
        self.assertNotIn(secret, self.visible(app))
        self.assertIn("[đã ẩn]", self.visible(app))

    def test_email_config_gmail_preset_parsed_recipients_and_no_implicit_send(self):
        app = self.ui()
        app.button(key=P + "gmail_preset").click().run()
        self.assert_clean(app)
        self.assertEqual("smtp.gmail.com", app.text_input(key=P + "smtp_host").value)
        self.assertEqual(587, app.number_input(key=P + "smtp_port").value)
        self.assertEqual("starttls", app.selectbox(key=P + "smtp_security").value)
        app.checkbox(key=P + "email_enabled").set_value(True)
        app.text_input(key=P + "smtp_username").set_value("sender@example.com")
        app.text_input(key=P + "smtp_password").set_value("private-smtp-password")
        app.text_input(key=P + "sender").set_value("sender@example.com")
        app.text_input(key=P + "recipients").set_value(" admin@example.com, oncall@example.com ")
        app.number_input(key=P + "cooldown").set_value(600)
        app.button(key="FormSubmitter:" + P + "email_form-Lưu cấu hình email").click().run()
        self.assert_clean(app)
        payload = self.posts("/assistant/config/email")[-1]
        self.assertEqual({"enabled": True, "host": "smtp.gmail.com", "port": 587, "security": "starttls",
                          "username": "sender@example.com", "password": "private-smtp-password",
                          "sender": "sender@example.com", "recipients": ["admin@example.com", "oncall@example.com"],
                          "cooldown_seconds": 600}, payload)
        self.assertEqual("", app.text_input(key=P + "smtp_password").value)
        self.assertNotIn("private-smtp-password", self.visible(app))
        self.assertFalse(self.posts("/assistant/email/test"))
        self.assertFalse(app.button(key=P + "email_test").disabled)

    def test_email_preview_is_read_only_and_test_is_explicit_queued_not_sent(self):
        self.backend.status["email"].update(enabled=True, configured=True, recipients=["admin@example.com"])
        app = self.ui()
        app.button(key=P + "email_preview").click().run()
        self.assert_clean(app)
        self.assertIn("[MÔ PHỎNG] Cảnh báo #42", self.visible(app))
        self.assertFalse(self.posts("/assistant/email/test"))
        self.assertIn("Người nhận đã lưu: admin@example.com", self.visible(app))
        app.button(key=P + "email_test").click().run()
        self.assert_clean(app)
        self.assertEqual([{}], self.posts("/assistant/email/test"))
        self.assertTrue(any("đã được xếp hàng" in item.value for item in app.info))
        self.assertEqual(0, len(app.success))
        app.button(key=P + "refresh_email").click().run()
        self.assert_clean(app)
        self.assertEqual(1, len(app.dataframe))
        self.assertEqual("Đang chờ", app.dataframe[0].value.iloc[0]["Trạng thái"])

    def test_backend_failure_is_visible_without_configuration_or_chat(self):
        self.backend.fail_status = True
        app = self.ui()
        self.assertIn("Không kết nối được Backend", self.visible(app))
        self.assertEqual(0, len(app.chat_input))
        self.assertEqual(0, len(app.success))
        self.assertFalse(any(method == "POST" for method, _, _ in self.backend.calls))


if __name__ == "__main__":
    unittest.main()
