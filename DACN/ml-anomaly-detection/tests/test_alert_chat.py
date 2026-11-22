"""The bot polls saved evidence; only an explicit question can create chat."""
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

from frontend.alert_chat import FEED_LIMIT, _snapshot
from frontend.api_client import BackendError


P = "alert_chat_"
APP = "from frontend.alert_chat import render_alert_chat\nrender_alert_chat()\n"


def point(identifier=42, *, baseline_id=5, votes=3, source="live", scenario=None):
    return {"id": identifier, "baseline_id": baseline_id, "votes": votes,
            "source": source, "scenario": scenario,
            "timestamp": "2026-11-21T01:00:00+00:00", "received_at": "2026-11-21T01:00:01+00:00",
            "connections": 150., "voters": ["mad", "isolation_forest", "lof"][:votes],
            "evidence": [{"metric": "connections", "actual": 150., "baseline": 30.,
                          "delta": 120., "allowed_deviation": 4., "material": True}]}


class FeedCursorTests(unittest.TestCase):
    def test_initial_snapshot_is_bounded_deduplicated_scoped_history(self):
        points = [point(index) for index in range(1, FEED_LIMIT + 21)]
        points.extend([point(70), point(71, votes=1), point(72, baseline_id=99)])
        state, arrived = _snapshot(None, ("api-a", 5), list(reversed(points)), latest_id=72)
        self.assertEqual([], arrived)
        self.assertEqual([], state["new_ids"])
        self.assertEqual(list(range(21, 71)), [item["id"] for item in state["points"]])
        self.assertEqual(72, state["last_id"])

    def test_only_new_ids_advance_cursor_and_scope_or_recovery_reseeds_history(self):
        state, _ = _snapshot(None, ("api-a", 5), [point(42)])
        updated, arrived = _snapshot(state, ("api-a", 5), [point(43), point(42), point(43)])
        self.assertEqual([43], arrived)
        same, repeated = _snapshot(updated, ("api-a", 5), [point(43), point(42)])
        self.assertEqual([], repeated)
        self.assertEqual([43], same["new_ids"])
        for scope, previous in [(("api-b", 5), updated), (("api-a", 6), updated),
                                (("api-a", 5), {**updated, "disconnected": True})]:
            with self.subTest(scope=scope, disconnected=previous.get("disconnected")):
                reset, arrived = _snapshot(previous, scope, [point(44, baseline_id=scope[1])])
                self.assertEqual([], arrived)
                self.assertEqual([], reset["new_ids"])

    def test_source_session_change_resets_new_markers_without_rewriting_evidence(self):
        initial = point(42, source="K3", scenario="K3")
        state, _ = _snapshot(None, ("api", 5), [initial], context=("replay", "K3", "session-a"))
        changed, arrived = _snapshot(state, ("api", 5), [initial, point(43)], context=("live", "live", "session-b"))
        self.assertEqual([], arrived)
        self.assertEqual([], changed["new_ids"])
        self.assertEqual(initial, changed["points"][0])


class FakeBotBackend:
    def __init__(self):
        self.calls = []
        self.points = [point()]
        self.messages = []
        self.fail_health = False
        self.fail_alerts = False
        self.fail_history = False
        self.fail_chat = False
        self.url = "http://qa-api-a"
        self.health = {"baseline": {"id": 5}, "latest": {"id": 42},
                       "collector": {"mode": "live", "source": "live", "session_id": "session-a",
                                     "status": "stopped", "last_received_at": "2026-11-21T01:00:01+00:00",
                                     "age_seconds": 20., "stale_after_seconds": 5.}}

    def get(self, path, **params):
        self.calls.append(("GET", path, deepcopy(params)))
        if path == "/health":
            if self.fail_health:
                raise BackendError("Mất kết nối Backend.")
            return deepcopy(self.health)
        if path == "/alerts":
            if self.fail_alerts:
                raise BackendError("Chưa đọc được cảnh báo.")
            return {"alerts": deepcopy(self.points)}
        if path == "/assistant/history":
            if self.fail_history:
                raise BackendError("Lịch sử chat chưa phản hồi.")
            return {"conversation_id": params["conversation_id"], "messages": deepcopy(self.messages)}
        raise AssertionError("Unexpected GET " + path)

    def post(self, path, payload=None):
        self.calls.append(("POST", path, deepcopy(payload)))
        if path != "/assistant/chat":
            raise AssertionError("Unexpected POST " + path)
        if self.fail_chat:
            raise BackendError("Trợ lý chưa trả lời.")
        answer = "Đã đọc số liệu kết nối của bản ghi #42; chưa xác định nguyên nhân."
        self.messages.extend([{"role": "user", "content": payload["question"]},
                              {"role": "assistant", "content": answer, "mode": "rules", "sources": [42]}])
        return {"answer": "THIS RESPONSE MUST NOT BE RENDERED DIRECTLY", "mode": "ai"}


class AlertChatFrontendTests(unittest.TestCase):
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

    @staticmethod
    def visible(app):
        return "\n".join(str(item.value) for kind in ("markdown", "caption", "text", "error", "warning", "info", "success")
                         for item in getattr(app, kind))

    def posts(self):
        return [payload for method, path, payload in self.backend.calls if method == "POST"]

    def test_initial_and_duplicate_alerts_are_history_without_toast_or_automatic_chat(self):
        self.backend.points = [point(), point(), point(43, votes=1), point(44, baseline_id=6)]
        app = self.ui()
        self.assertEqual(1, len(app.chat_message))
        self.assertEqual(0, len(app.get("toast")))
        self.assertEqual([], self.posts())
        visible = self.visible(app)
        self.assertIn("Lịch sử đã lưu", visible)
        self.assertIn("chưa thể kết luận tình trạng MySQL hiện tại", visible)
        self.assertIn("150 kết nối · nền 30 · chênh 120", visible)
        self.assertIn("MAD, Isolation Forest, LOF", visible)
        self.assertNotIn("#43", visible)
        self.assertNotIn("#44", visible)
        self.assertFalse(any("/email" in path or "/config" in path or "/status" in path for _, path, _ in self.backend.calls))

    def test_new_alert_gets_one_toast_and_does_not_repeat_on_poll(self):
        app = self.ui()
        self.backend.points.insert(0, point(45, source="K3", scenario="K3"))
        self.backend.health["latest"] = {"id": 45}
        app.run()
        self.assert_clean(app)
        self.assertEqual(1, len(app.get("toast")))
        self.assertEqual([45], app.session_state[P + "feed_state"]["new_ids"])
        self.assertIn("Dữ liệu mô phỏng · K3", self.visible(app))
        self.assertIn("Mới trong phiên này", self.visible(app))
        app.run()
        self.assertEqual(0, len(app.get("toast")))
        self.assertEqual([], self.posts())

    def test_baseline_switch_resets_selection_new_markers_and_keeps_conversation(self):
        app = self.ui()
        conversation = app.session_state[P + "conversation_id"]
        app.selectbox(key=P + "alert").set_value(42).run()
        self.backend.health["baseline"] = {"id": 6}
        self.backend.health["latest"] = {"id": 55}
        self.backend.points = [point(55, baseline_id=6)]
        app.run()
        self.assert_clean(app)
        self.assertIsNone(app.selectbox(key=P + "alert").value)
        self.assertEqual(conversation, app.session_state[P + "conversation_id"])
        self.assertEqual([], app.session_state[P + "feed_state"]["new_ids"])
        self.assertEqual(0, len(app.get("toast")))
        self.assertNotIn("#42", self.visible(app))

    def test_connection_failure_keeps_labeled_history_and_recovery_does_not_replay_alerts(self):
        app = self.ui()
        self.backend.fail_alerts = True
        app.run()
        self.assert_clean(app)
        self.assertIn("Bot chưa cập nhật được cảnh báo", self.visible(app))
        self.assertIn("Lịch sử đã lưu", self.visible(app))
        self.assertEqual(0, len(app.chat_input))
        self.assertEqual(0, len(app.success))
        self.backend.fail_alerts = False
        self.backend.points.insert(0, point(46))
        self.backend.health["latest"] = {"id": 46}
        app.run()
        self.assert_clean(app)
        self.assertIn("Đã kết nối lại", self.visible(app))
        self.assertEqual(0, len(app.get("toast")))
        self.assertEqual([], app.session_state[P + "feed_state"]["new_ids"])

    def test_backend_change_clears_other_backend_cache_even_while_offline(self):
        app = self.ui()
        conversation = app.session_state[P + "conversation_id"]
        app.selectbox(key=P + "alert").set_value(42).run()
        self.backend.url = "http://qa-api-b"
        self.backend.fail_health = True
        app.run()
        self.assert_clean(app)
        self.assertNotIn("#42", self.visible(app))
        self.assertEqual(0, len(app.chat_message))
        self.backend.fail_health = False
        app.run()
        self.assertNotEqual(conversation, app.session_state[P + "conversation_id"])
        self.assertIsNone(app.selectbox(key=P + "alert").value)
        self.assertEqual(0, len(app.get("toast")))

    def test_question_uses_selected_alert_and_only_saved_backend_messages_are_rendered(self):
        app = self.ui()
        conversation = app.session_state[P + "conversation_id"]
        self.assertTrue(re.fullmatch("[0-9a-f]{32}", conversation))
        app.selectbox(key=P + "alert").set_value(42).run()
        app.chat_input(key=P + "question").set_value("Tôi cần kiểm tra chỉ số nào?").run()
        self.assert_clean(app)
        self.assertEqual([{"question": "Tôi cần kiểm tra chỉ số nào?", "conversation_id": conversation, "alert_id": 42}], self.posts())
        visible = self.visible(app)
        self.assertIn("Đã đọc số liệu kết nối của bản ghi #42", visible)
        self.assertIn("Giải thích theo quy tắc", visible)
        self.assertIn("Chứng cứ: #42", visible)
        self.assertNotIn("THIS RESPONSE MUST NOT BE RENDERED DIRECTLY", visible)
        self.assertEqual(conversation, app.session_state[P + "conversation_id"])

    def test_question_failure_never_invents_messages_or_success(self):
        app = self.ui()
        self.backend.fail_chat = True
        app.chat_input(key=P + "question").set_value("Vì sao cảnh báo?").run()
        self.assert_clean(app)
        self.assertIn("Trợ lý chưa trả lời", self.visible(app))
        self.assertEqual(1, len(app.chat_message), "Only the saved alert should remain")
        self.assertEqual(0, len(app.success))
        self.assertEqual([], self.backend.messages)

    def test_history_failure_preserves_feed_and_disables_questions_until_recovered(self):
        self.backend.fail_history = True
        app = self.ui()
        self.assertIn("Chưa tải được cuộc trò chuyện", self.visible(app))
        self.assertEqual(1, len(app.chat_message))
        self.assertEqual(0, len(app.chat_input))
        self.assertEqual([], self.posts())

    def test_without_baseline_bot_does_not_query_unscoped_alerts_or_claim_healthy(self):
        self.backend.health["baseline"] = None
        self.backend.health["latest"] = None
        app = self.ui()
        self.assertIn("Chưa có mức nền", self.visible(app))
        self.assertFalse(any(path == "/alerts" for _, path, _ in self.backend.calls))
        self.assertEqual(0, len(app.chat_message))
        self.assertEqual(0, len(app.success))


if __name__ == "__main__":
    unittest.main()
