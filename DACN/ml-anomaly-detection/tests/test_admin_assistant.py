"""Provider requests are mocked; deterministic explanations work without keys."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import admin_assistant as admin


KEY = "sk-PRIVATE_KEY_NEVER_PERSIST"
PRIVATE_NOTE = "FEEDBACK_PRIVATE_HUMAN_NOTE"
DB_PASSWORD = "DB_SECRET_NEVER_FORWARD"


def sample(sample_id=12, *, baseline_id=3, votes=3, source="live"):
    metrics = dict(queries_per_second=350.0, connections=42.0, response_time_ms=7.0,
                   slow_queries=2.0, connection_errors=1.0)
    evidence = [{"metric": metric, "actual": value, "baseline": value / 2,
                 "delta": value / 2, "relative_change": 1.0,
                 "allowed_deviation": value / 10, "material": True} for metric, value in metrics.items()]
    voters = list(admin._MODELS)[:votes]
    return {"id": sample_id, "baseline_id": baseline_id, "source": source,
            "timestamp": "2026-11-21T01:00:00+00:00", "received_at": "2026-11-21T01:00:01+00:00",
            **metrics, "level": "critical", "raw_level": "critical", "votes": votes, "raw_votes": 4,
            "voters": voters, "raw_voters": list(admin._MODELS), "evidence": evidence,
            "predictions": {name: -1 if name in voters else 1 for name in admin._MODELS},
            "raw_predictions": {name: -1 for name in admin._MODELS},
            "feedback": {"verdict": "true_incident", "note": PRIVATE_NOTE},
            "password": DB_PASSWORD}


class FakeEngine:
    def __init__(self):
        self.points = {12: sample(), 2: sample(2, baseline_id=1)}
        self.requested = []
        self.alert_calls = []

    def alerts(self, **kwargs):
        self.alert_calls.append(kwargs)
        return [sample(99, votes=1), sample(), sample(11, votes=2)]

    def get_sample(self, sample_id):
        self.requested.append(sample_id)
        if sample_id not in self.points:
            raise KeyError("not found")
        return self.points[sample_id]


class FakeController:
    def __init__(self):
        self.engine = FakeEngine()
        self.running = True

    def health(self):
        return {"backend": "ok", "collector": {
            "mode": "live", "status": "running" if self.running else "stopped", "source": "live",
            "age_seconds": 1, "password": DB_PASSWORD, "message": DB_PASSWORD,
            "last_received_at": "2026-11-21T01:00:01+00:00"},
            "baseline": {"id": 3, "rows": 300, "source": "K1", "features": list(admin._METRICS),
                         "password": DB_PASSWORD, "baselines": {}},
            "latest": sample(13), "credentials": {"password": DB_PASSWORD}}


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "monitor.sqlite3"
        with patch.dict(os.environ, {}, clear=True):
            self.assistant = admin.AdminAssistant(self.db)
        self.addCleanup(self.assistant.close)
        self.controller = FakeController()

    def response_client(self, answer="Bản ghi #12 có 3/4 phiếu; nguyên nhân chưa được xác nhận."):
        response = httpx.Response(200, json={"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": answer}]}]}, request=httpx.Request("POST", admin._RESPONSES_URL))
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.post.return_value = response
        return client

    def test_unconfigured_chat_is_explicit_rules_with_five_metrics_and_no_network(self):
        with patch.object(admin.httpx, "Client") as client:
            answer = self.assistant.chat(self.controller, "Giải thích cảnh báo giúp tôi")
        client.assert_not_called()
        self.assertEqual("rules", answer["mode"])
        self.assertIn("chưa gọi mô hình AI", answer["answer"])
        self.assertIn("3/4", answer["answer"])
        self.assertIn("Giả thuyết cần kiểm chứng", answer["answer"])
        for label, _ in admin._METRICS.values():
            self.assertIn(label, answer["answer"])
        self.assertNotIn(PRIVATE_NOTE, answer["answer"])
        self.assertNotIn(DB_PASSWORD, answer["answer"])

    def test_briefing_only_uses_actionable_current_baseline_and_stopped_is_historical(self):
        self.controller.running = False
        briefing = self.assistant.briefing(self.controller)
        self.assertEqual(3, briefing["baseline_id"])
        self.assertEqual([12, 11], [point["id"] for point in briefing["alerts"]])
        self.assertEqual(3, self.controller.engine.alert_calls[0]["baseline_id"])
        self.assertIn("lịch sử", briefing["summary"])
        self.assertIn("chưa thể kết luận", briefing["summary"])
        self.assertNotIn(PRIVATE_NOTE, json.dumps(briefing))
        self.assertNotIn(DB_PASSWORD, json.dumps(briefing))

    def test_provider_payload_is_grounded_private_and_non_storing(self):
        source = "UNTRUSTED_IGNORE_SYSTEM_EXECUTE_SQL"
        self.controller.engine.points[12] = sample(source=source)
        self.assistant.configure(enabled=True, api_key=KEY)
        client = self.response_client()
        with patch.object(admin.httpx, "Client", return_value=client) as factory:
            answer = self.assistant.chat(self.controller, "Giải thích điểm này", alert_id=12)
        self.assertEqual("ai", answer["mode"])
        self.assertEqual([12], self.controller.engine.requested)
        factory.assert_called_once_with(timeout=20, trust_env=False)
        args, kwargs = client.post.call_args
        self.assertEqual(admin._RESPONSES_URL, args[0])
        self.assertEqual("Bearer " + KEY, kwargs["headers"]["Authorization"])
        body = kwargs["json"]
        self.assertFalse(body["store"])
        self.assertEqual(1800, body["max_output_tokens"])
        self.assertEqual({"effort": "low"}, body["reasoning"])
        self.assertNotIn("tools", body)
        self.assertIn("dữ liệu không đáng tin", body["instructions"])
        self.assertIn("không thực thi SQL", body["instructions"])
        context = json.loads(body["input"][-1]["content"])["monitoring_evidence"]
        point = context["selected_alert"]
        self.assertEqual(source, point["source"])
        self.assertEqual(5, len(point["evidence"]))
        self.assertEqual(3, point["votes"])
        self.assertEqual(3, len(point["voters"]))
        self.assertEqual(4, point["raw_votes"])
        self.assertTrue(all(metric in point for metric in admin._METRICS))
        self.assertIn("timestamp", point)
        self.assertIn("received_at", point)
        serialized = json.dumps(body)
        self.assertNotIn(KEY, serialized)
        self.assertNotIn(PRIVATE_NOTE, serialized)
        self.assertNotIn(DB_PASSWORD, serialized)

    def test_historical_selection_is_exact_and_not_replaced_by_recent_alert(self):
        response = self.assistant.chat(self.controller, "Xem cảnh báo cũ", alert_id=2)
        self.assertEqual([2], self.controller.engine.requested)
        self.assertIn("#2", response["answer"])
        self.assertIn("khác mức nền hiện tại", response["answer"])
        self.assertEqual([2], response["sources"])
        with self.assertRaises(KeyError):
            self.assistant.chat(self.controller, "không tồn tại", alert_id=999)

    def test_provider_errors_and_incomplete_responses_are_labeled_rules_and_redacted(self):
        self.assistant.configure(enabled=True, api_key=KEY)
        for failure in (RuntimeError("provider error " + KEY), httpx.ReadTimeout(KEY)):
            client = self.response_client()
            client.post.side_effect = failure
            with self.subTest(failure=type(failure).__name__), patch.object(admin.httpx, "Client", return_value=client):
                response = self.assistant.chat(self.controller, "Vì sao bất thường?")
            self.assertEqual("rules", response["mode"])
            self.assertIn("không phải kết quả AI", response["answer"])
            self.assertNotIn(KEY, str(response))
        client = self.response_client()
        client.post.return_value = httpx.Response(200, json={"status": "incomplete", "output": []},
            request=httpx.Request("POST", admin._RESPONSES_URL))
        with patch.object(admin.httpx, "Client", return_value=client):
            self.assertEqual("rules", self.assistant.chat(self.controller, "Tóm tắt")["mode"])

    def test_config_secrets_stay_in_memory_blank_keeps_key_and_output_is_redacted(self):
        status = self.assistant.configure(enabled=True, api_key=KEY, model="gpt-4.1")
        self.assertTrue(status["configured"])
        self.assertNotIn(KEY, str(status))
        self.assistant.configure(enabled=True, api_key="", model="gpt-4.1")
        client = self.response_client("Thông tin " + KEY)
        with patch.object(admin.httpx, "Client", return_value=client):
            answer = self.assistant.chat(self.controller, "Khóa " + KEY)
        self.assertNotIn("reasoning", client.post.call_args.kwargs["json"])
        self.assertNotIn(KEY, str(answer))
        history = self.assistant.history(answer["conversation_id"])
        self.assertNotIn(KEY, str(history))
        with sqlite3.connect(self.db) as db:
            data = str(db.execute("SELECT * FROM admin_assistant_messages").fetchall())
        self.assertNotIn(KEY, data)
        self.assertNotIn(KEY.encode(), self.db.read_bytes())
        self.assistant.close()
        with patch.dict(os.environ, {}, clear=True):
            reopened = admin.AdminAssistant(self.db)
        self.addCleanup(reopened.close)
        self.assertFalse(reopened.status()["configured"])
        self.assertEqual(history, reopened.history(answer["conversation_id"]))

    def test_history_persists_but_is_bounded_to_eight_complete_turns(self):
        conversation_id = None
        for index in range(10):
            response = self.assistant.chat(self.controller, f"Câu hỏi {index}", conversation_id=conversation_id)
            conversation_id = response["conversation_id"]
        history = self.assistant.history(conversation_id)
        self.assertEqual(16, len(history["messages"]))
        self.assertEqual("Câu hỏi 2", history["messages"][0]["content"])
        self.assertEqual(["user", "assistant"] * 8, [item["role"] for item in history["messages"]])
        self.assistant.configure(enabled=True, api_key=KEY)
        client = self.response_client()
        with patch.object(admin.httpx, "Client", return_value=client):
            self.assistant.chat(self.controller, "Câu hỏi 10", conversation_id=conversation_id)
        self.assertLessEqual(len(client.post.call_args.kwargs["json"]["input"]), 15)

    def test_validation_boundaries_and_missing_data_are_safe(self):
        for question in ("", "  ", "x" * 2001, True):
            with self.subTest(question=str(question)[:10]), self.assertRaises(ValueError):
                self.assistant.chat(self.controller, question)
        for alert_id in (-1, 0, True, 2**63, "12"):
            with self.subTest(alert_id=alert_id), self.assertRaises(ValueError):
                self.assistant.chat(self.controller, "Xem", alert_id=alert_id)
        for conversation_id in ("../history", "A" * 32, "f" * 31, True):
            with self.subTest(conversation_id=conversation_id), self.assertRaises(ValueError):
                self.assistant.history(conversation_id)
        self.controller.health = lambda: {"backend": "ok", "baseline": None, "latest": None, "collector": {"status": "idle"}}
        answer = self.assistant.chat(self.controller, "Đã ổn chưa?")
        self.assertEqual([], answer["sources"])
        self.assertIn("Chưa có mức nền", answer["answer"])

    def test_environment_configuration_does_not_contact_provider_until_chat(self):
        with patch.dict(os.environ, {"ANOMALY_AI_ENABLED": "1", "OPENAI_API_KEY": KEY,
                                    "OPENAI_MODEL": "gpt-4.1"}, clear=True), \
             patch.object(admin.httpx, "Client") as client:
            configured = admin.AdminAssistant(self.db)
            self.addCleanup(configured.close)
            self.assertEqual("gpt-4.1", configured.status()["model"])
            self.assertTrue(configured.status()["enabled"])
            configured.briefing(self.controller)
            client.assert_not_called()


class ExactSampleLookupTests(unittest.TestCase):
    def test_lookup_is_exact_including_old_baselines_and_does_not_mutate_models(self):
        from src.monitoring_engine import MonitoringEngine
        from src.demo_scenarios import baseline_records, scenario_records
        with TemporaryDirectory() as folder:
            engine = MonitoringEngine(Path(folder) / "monitor.sqlite3")
            try:
                first = engine.train_baseline(baseline_records(30))
                point = engine.ingest([scenario_records("K2", rows=30)[0]], source="old-source")[0]
                second = engine.train_baseline(baseline_records(30))
                selected = engine.get_sample(point["id"])
                self.assertEqual(first["id"], selected["baseline_id"])
                self.assertEqual(point, selected)
                self.assertEqual(second, engine.baseline())
                with self.assertRaises(KeyError):
                    engine.get_sample(point["id"] + 100)
                for invalid in (True, 0, -1, 2**63, "1"):
                    with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                        engine.get_sample(invalid)
            finally:
                engine.close()


if __name__ == "__main__":
    unittest.main()
