"""Assistant HTTP contracts, exact selection and private config validation."""
from __future__ import annotations

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import admin_api
from backend.monitoring_api import get_controller
from tests.test_admin_assistant import FakeController, KEY, PRIVATE_NOTE, DB_PASSWORD


class FakeNotifier:
    def __init__(self):
        self.settings = {}
        self.previews = []
        self.test_calls = 0

    def status(self):
        return {"enabled": self.settings.get("enabled", False), "configured": bool(self.settings),
                "jobs": [], "sent_count": 0, "pending_count": 0, "failed_count": 0}

    def configure(self, **settings):
        self.settings = settings
        return self.status()

    def preview(self, point):
        self.previews.append(point["id"])
        return {"subject": "Xem trước cảnh báo", "body": f"Bản ghi #{point['id']}"}

    def test_email(self):
        self.test_calls += 1
        return {"id": "test-job", "status": "queued"}


class AdminAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(admin_api.shutdown_admin)
        self.controller = FakeController()
        self.controller.db_path = Path(self.temp.name) / "monitor.sqlite3"
        self.controller.notifier = FakeNotifier()
        self.app = FastAPI()
        self.app.include_router(admin_api.router)
        self.app.dependency_overrides[get_controller] = lambda: self.controller
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_status_briefing_and_rules_chat_work_before_configuration(self):
        status = self.client.get("/monitor/assistant/status")
        self.assertEqual(200, status.status_code, status.text)
        self.assertEqual("openai", status.json()["ai"]["provider"])
        self.assertFalse(status.json()["ai"]["configured"])
        briefing = self.client.get("/monitor/assistant/briefing")
        self.assertEqual(200, briefing.status_code)
        self.assertEqual("rules", briefing.json()["mode"])
        response = self.client.post("/monitor/assistant/chat", json={"question": "Giải thích cảnh báo"})
        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual("rules", body["mode"])
        self.assertEqual(32, len(body["conversation_id"]))
        history = self.client.get("/monitor/assistant/history", params={"conversation_id": body["conversation_id"]})
        self.assertEqual(200, history.status_code)
        self.assertEqual(["user", "assistant"], [item["role"] for item in history.json()["messages"]])
        self.assertNotIn(PRIVATE_NOTE, response.text)
        self.assertNotIn(DB_PASSWORD, response.text)
        self.assertEqual(0, self.controller.notifier.test_calls)

    def test_exact_historical_alert_and_missing_identifier(self):
        response = self.client.post("/monitor/assistant/chat", json={"question": "Xem bản cũ", "alert_id": 2})
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual([2], response.json()["sources"])
        self.assertIn("khác mức nền hiện tại", response.json()["answer"])
        missing = self.client.post("/monitor/assistant/chat", json={"question": "Xem", "alert_id": 999})
        self.assertEqual(404, missing.status_code)
        preview = self.client.get("/monitor/assistant/email/preview", params={"alert_id": 2})
        self.assertEqual(200, preview.status_code)
        self.assertEqual([2], self.controller.notifier.previews)
        self.assertEqual(404, self.client.get("/monitor/assistant/email/preview", params={"alert_id": 999}).status_code)

    def test_ai_config_never_echoes_key_and_blank_keeps_in_memory_configuration(self):
        response = self.client.post("/monitor/assistant/config/ai", json={
            "enabled": True, "api_key": KEY, "model": "gpt-6.2-sol"})
        self.assertEqual(200, response.status_code, response.text)
        self.assertTrue(response.json()["configured"])
        self.assertNotIn(KEY, response.text)
        response = self.client.post("/monitor/assistant/config/ai", json={"enabled": False, "api_key": ""})
        self.assertTrue(response.json()["configured"])
        self.assertFalse(response.json()["enabled"])
        self.assertNotIn(KEY, self.client.get("/monitor/assistant/status").text)
        self.assertNotIn(KEY, repr(admin_api.AIConfigRequest(enabled=True, api_key=KEY)))

    def test_malformed_secret_fields_and_other_validation_never_echo_raw_values(self):
        payloads = [("/config/ai", {"enabled": True, "api_key": {"secret": KEY}}),
                    ("/config/ai", {"enabled": True, "api_key": [KEY]}),
                    ("/config/ai", {"enabled": 1, "api_key": KEY}),
                    ("/config/email", {"enabled": True, "password": {"secret": KEY}}),
                    ("/config/email", {"enabled": True, "password": [KEY]}),
                    ("/config/email", {"enabled": True, "password": KEY, "port": True})]
        for path, payload in payloads:
            with self.subTest(path=path, payload_type=type(payload.get("password", payload.get("api_key"))).__name__):
                response = self.client.post("/monitor/assistant" + path, json=payload)
                self.assertEqual(422, response.status_code, response.text)
                self.assertNotIn(KEY, response.text)
                self.assertNotIn('"input"', response.text)
        self.assertFalse(self.client.get("/monitor/assistant/status").json()["ai"]["configured"])

    def test_chat_and_query_schema_boundaries_reject_invalid_ids_and_input(self):
        for payload in ({"question": ""}, {"question": " "}, {"question": "x" * 2001},
                        {"question": True}, {"question": "Xem", "alert_id": -1},
                        {"question": "Xem", "alert_id": 0}, {"question": "Xem", "alert_id": True},
                        {"question": "Xem", "alert_id": 2**63},
                        {"question": "Xem", "conversation_id": "f" * 31},
                        {"question": "Xem", "conversation_id": "F" * 32},
                        {"question": "Xem", "unknown": "x"}):
            with self.subTest(payload=str(payload)[:70]):
                self.assertEqual(422, self.client.post("/monitor/assistant/chat", json=payload).status_code)
        for value in (-1, 0, "true", 2**63):
            self.assertEqual(422, self.client.get("/monitor/assistant/email/preview", params={"alert_id": value}).status_code)
        for value in ("f" * 31, "F" * 32, "../../private"):
            self.assertEqual(422, self.client.get("/monitor/assistant/history", params={"conversation_id": value}).status_code)
        self.assertEqual(200, self.client.get("/monitor/assistant/history", params={"conversation_id": "a" * 32}).status_code)

    def test_email_config_preview_and_test_are_separate_explicit_calls(self):
        payload = {"enabled": True, "host": "smtp.example.test", "port": 587, "security": "starttls",
                   "username": "smtp-private", "password": KEY, "sender": "monitor@example.test",
                   "recipients": ["admin@example.test"], "cooldown_seconds": 300}
        configured = self.client.post("/monitor/assistant/config/email", json=payload)
        self.assertEqual(200, configured.status_code, configured.text)
        self.assertNotIn(KEY, configured.text)
        self.assertEqual(KEY, self.controller.notifier.settings["password"])
        self.assertEqual(0, self.controller.notifier.test_calls)
        self.client.get("/monitor/assistant/status")
        self.client.get("/monitor/assistant/briefing")
        self.client.get("/monitor/assistant/email/preview", params={"alert_id": 12})
        self.assertEqual(0, self.controller.notifier.test_calls)
        response = self.client.post("/monitor/assistant/email/test")
        self.assertEqual(200, response.status_code)
        self.assertEqual("queued", response.json()["status"])
        self.assertEqual(1, self.controller.notifier.test_calls)
        self.assertNotIn(KEY, repr(admin_api.EmailConfigRequest(**payload)))
        for cooldown in (59, 3601, True):
            payload["cooldown_seconds"] = cooldown
            self.assertEqual(422, self.client.post("/monitor/assistant/config/email", json=payload).status_code)

    def test_shutdown_closes_services_and_router_is_registered(self):
        self.client.get("/monitor/assistant/briefing")
        service = admin_api._assistant(self.controller)
        admin_api.shutdown_admin()
        with self.assertRaises(RuntimeError):
            service.status()
        from backend.api import app
        self.assertIn("/monitor/assistant/chat", app.openapi()["paths"])


if __name__ == "__main__":
    unittest.main()
