"""Messenger presentation must preserve chronology, HTML safety and explicit actions."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT, Path(__file__).resolve().parent):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from test_alert_chat import FakeBotBackend, point
from frontend import alert_chat


P = "alert_chat_"
APP = "from frontend.alert_chat import render_alert_chat\nrender_alert_chat()\n"


class MessengerTimelineTests(unittest.TestCase):
    def test_received_time_orders_alerts_with_chat_and_preserves_equal_time_turn_order(self):
        first_alert = {**point(42), "timestamp": "2026-11-01T00:00:00+00:00",
                       "received_at": "2026-11-21T01:02:00+00:00"}
        earlier_alert = {**point(41), "timestamp": "2026-12-01T00:00:00+00:00",
                         "received_at": "2026-11-21T08:00:00+07:00"}
        user = {"role": "user", "content": "Tôi cần kiểm tra gì?", "created_at": "2026-11-21T01:01:00Z"}
        assistant = {"role": "assistant", "content": "Đối chiếu nhật ký.", "created_at": user["created_at"]}
        events = alert_chat._timeline_events([first_alert, earlier_alert], [user, assistant])
        self.assertEqual(["alert", "message", "message", "alert"], [event["kind"] for event in events])
        for actual, expected in zip(events, [earlier_alert, user, assistant, first_alert]):
            self.assertIs(expected, actual["item"], "Presentation must retain the original evidence")

    def test_source_time_is_only_fallback_and_missing_times_remain_stably_at_end(self):
        fallback_alert = {**point(42), "received_at": None, "timestamp": "2026-11-21T01:00:00Z"}
        untimed_alert = {**point(43), "received_at": "not-a-time", "timestamp": None}
        user = {"role": "user", "content": "Question with no timestamp"}
        assistant = {"role": "assistant", "content": "Answer with no timestamp"}
        timed_answer = {"role": "assistant", "content": "Saved answer", "created_at": "2026-11-21T01:01:00Z"}
        first = alert_chat._timeline_events([untimed_alert, fallback_alert], [timed_answer, user, assistant])
        second = alert_chat._timeline_events([untimed_alert, fallback_alert], [timed_answer, user, assistant])
        self.assertEqual(first, second)
        self.assertIs(fallback_alert, first[0]["item"])
        self.assertIs(timed_answer, first[1]["item"])
        unknown = [event["item"] for event in first[2:]]
        self.assertEqual(3, len(unknown))
        self.assertIn(untimed_alert, unknown)
        self.assertLess(unknown.index(user), unknown.index(assistant))
        # Partial timestamps must never reverse the server's turn ordering.
        partial = alert_chat._timeline_events([fallback_alert], [user, assistant, timed_answer])
        messages = [event["item"] for event in partial if event["kind"] == "message"]
        self.assertEqual([user, assistant, timed_answer], messages)

    def test_message_html_escapes_user_and_provider_text_and_keeps_role_classes(self):
        attack = '<script>alert("secret")</script><img src=x onerror="run()"> & "quoted"'
        for role, expected_class in (("user", "bubble-user"), ("assistant", "bubble-bot")):
            with self.subTest(role=role):
                html = alert_chat._message_html({"role": role, "content": attack, "mode": "ai",
                                                 "created_at": "2026-11-21T01:00:00Z", "sources": [42]})
                self.assertIn("messenger-bubble", html)
                self.assertIn(expected_class, html)
                self.assertIn("&lt;script&gt;", html)
                self.assertIn("&lt;img", html)
                self.assertNotIn("<script", html.lower())
                self.assertNotIn("<img", html.lower())
                self.assertIn("&amp;", html)

    def test_alert_html_escapes_untrusted_source_time_and_model_names(self):
        malicious = point()
        malicious.update(source="<script>source()</script>", scenario=None,
                         timestamp='<img src=x onerror="sourceTime()">',
                         received_at="<script>receiptTime()</script>",
                         voters=["mad", '<img src=x onerror="model()">'])
        original = deepcopy(malicious)
        html = alert_chat._alert_html(malicious, new=True)
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("<img", html.lower())
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img", html)
        self.assertIn("#42", html)
        self.assertIn("MAD", html)
        self.assertEqual(original, malicious)


class MessengerActionsTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBotBackend()
        for name, action in (("monitor_get", self.backend.get), ("monitor_post", self.backend.post)):
            boundary = patch("frontend.alert_chat." + name, side_effect=action)
            boundary.start()
            self.addCleanup(boundary.stop)
        address = patch("frontend.alert_chat.get_backend_url", side_effect=lambda: self.backend.url)
        address.start()
        self.addCleanup(address.stop)

    def ui(self):
        app = AppTest.from_string(APP, default_timeout=30).run()
        self.assert_clean(app)
        return app

    def assert_clean(self, app):
        self.assertEqual([], [item.message for item in app.exception])

    def posts(self):
        return [(path, payload) for method, path, payload in self.backend.calls if method == "POST"]

    @staticmethod
    def visible(app):
        return "\n".join(str(item.value) for kind in ("markdown", "caption", "error", "warning", "success", "info")
                         for item in getattr(app, kind))

    def test_summary_button_is_explicit_and_keeps_the_selected_alert_and_conversation(self):
        app = self.ui()
        self.assertEqual([], self.posts())
        conversation = app.session_state[P + "conversation_id"]
        app.selectbox(key=P + "alert").set_value(42).run()
        self.assertEqual([], self.posts())
        app.button(key=P + "quick_summary").click().run()
        self.assert_clean(app)
        self.assertEqual([("/assistant/chat", {
            "question": "Tóm tắt tình trạng nguồn giám sát và các cảnh báo gần đây.",
            "conversation_id": conversation, "alert_id": 42,
        })], self.posts())
        self.assertIn("Đã đọc số liệu kết nối của bản ghi #42", self.visible(app))
        self.assertNotIn("THIS RESPONSE MUST NOT BE RENDERED DIRECTLY", self.visible(app))

    def test_quick_question_failure_does_not_add_a_fabricated_message(self):
        app = self.ui()
        before = len(app.chat_message)
        self.backend.fail_chat = True
        app.button(key=P + "quick_check").click().run()
        self.assert_clean(app)
        self.assertEqual(1, len(self.posts()))
        self.assertIn("Trợ lý chưa trả lời", self.visible(app))
        self.assertEqual(before, len(app.chat_message))
        self.assertEqual([], self.backend.messages)
        self.assertEqual(0, len(app.success))

    def test_jump_to_latest_changes_display_without_posting_a_question(self):
        app = self.ui()
        conversation = app.session_state[P + "conversation_id"]
        app.button(key=P + "jump_latest").click().run()
        self.assert_clean(app)
        self.assertEqual([], self.posts())
        self.assertEqual([], self.backend.messages)
        self.assertEqual(conversation, app.session_state[P + "conversation_id"])

    def test_history_failure_keeps_alert_but_exposes_no_chat_or_quick_send_controls(self):
        self.backend.fail_history = True
        app = self.ui()
        self.assertIn("Chưa tải được cuộc trò chuyện", self.visible(app))
        self.assertEqual(1, len(app.chat_message))
        self.assertEqual(0, len(app.chat_input))
        keys = {button.key for button in app.button}
        self.assertTrue({P + "quick_summary", P + "quick_why", P + "quick_check"}.isdisjoint(keys))
        self.assertEqual([], self.posts())


if __name__ == "__main__":
    unittest.main()
