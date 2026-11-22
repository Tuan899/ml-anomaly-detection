"""Real controller/API notification wiring, with every SMTP worker disabled."""
from __future__ import annotations

from datetime import datetime, timedelta
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import admin_api, monitoring_api
from src.admin_notifications import EmailNotifier
from src.demo_scenarios import baseline_records, inject_record, scenario_records
from src.monitoring_controller import MonitoringController


class NotificationControllerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "monitor.sqlite3"
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        worker = patch.object(EmailNotifier, "_ensure_worker", return_value=None)
        worker.start()
        self.addCleanup(worker.stop)
        delivery = patch.object(EmailNotifier, "_deliver", side_effect=AssertionError("SMTP must not run"))
        self.delivery = delivery.start()
        self.addCleanup(delivery.stop)
        self.controller = MonitoringController(self.path)
        self.addCleanup(lambda: self.controller.close())
        self.addCleanup(admin_api.shutdown_admin)
        app = FastAPI()
        app.include_router(monitoring_api.router)
        app.include_router(admin_api.router)
        app.dependency_overrides[monitoring_api.get_controller] = lambda: self.controller
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def configure(self):
        response = self.client.post("/monitor/assistant/config/email", json={
            "enabled": True, "host": "smtp.example.test", "port": 587,
            "security": "starttls", "username": "qa@example.test",
            "password": "QA_SECRET_MUST_NOT_PERSIST", "sender": "qa@example.test",
            "recipients": ["admin@example.test"], "cooldown_seconds": 300,
        })
        self.assertEqual(200, response.status_code, response.text)
        self.assertTrue(response.json()["configured"])

    def train(self):
        self.controller.train(baseline_records(), source="K1")

    @staticmethod
    def record(event_id="incident-1", seconds=0):
        record = inject_record(scenario_records("K1", rows=30)[0], "K3")
        record["timestamp"] = (datetime.fromisoformat(record["timestamp"]) + timedelta(seconds=seconds)).isoformat()
        record["event_id"] = event_id
        return record

    def ingest(self, record=None):
        response = self.client.post("/monitor/samples", json={
            "records": [record or self.record()], "source": "live", "session_id": "qa-collector",
        })
        self.assertEqual(200, response.status_code, response.text)
        return response.json()["samples"][0]

    def test_real_status_exposes_disabled_notifier_and_reading_does_not_send(self):
        self.assertIsNone(self.controller._notifier)
        self.controller.health()
        self.assertIsNone(self.controller._notifier)
        response = self.client.get("/monitor/assistant/status")
        self.assertEqual(200, response.status_code, response.text)
        self.assertFalse(response.json()["email"]["enabled"])
        self.assertFalse(response.json()["email"]["configured"])
        self.assertEqual([], response.json()["email"]["jobs"])
        self.assertEqual(409, self.client.post("/monitor/assistant/email/test").status_code)
        self.delivery.assert_not_called()

    def test_live_samples_queue_once_and_apply_existing_durable_cooldown(self):
        self.train()
        self.configure()
        point = self.ingest()
        self.assertGreaterEqual(point["votes"], 2)
        retry = self.ingest()
        self.assertEqual(point, retry)
        second = self.ingest(self.record("incident-2", seconds=1))
        self.assertNotEqual(point["id"], second["id"])
        self.assertEqual(point["votes"], second["votes"])
        jobs = self.controller.notifier.status()["jobs"]
        self.assertEqual(1, len(jobs))
        self.assertEqual(point["id"], jobs[0]["sample_id"])
        self.assertEqual("queued", jobs[0]["status"])
        with sqlite3.connect(self.path) as connection:
            seen = connection.execute("SELECT sample_id,outcome FROM email_seen_samples ORDER BY sample_id").fetchall()
            self.assertEqual([(point["id"], "queued"), (second["id"], "cooldown")], seen)
            public = connection.execute("SELECT payload FROM email_settings").fetchone()[0]
            self.assertNotIn("QA_SECRET_MUST_NOT_PERSIST", public)
        preview = self.client.get("/monitor/assistant/email/preview", params={"alert_id": point["id"]})
        self.assertEqual(200, preview.status_code)
        self.assertIn("[MÔ PHỎNG]", preview.json()["subject"])
        self.assertEqual(point, self.controller.engine.get_sample(point["id"]))
        self.delivery.assert_not_called()

    def test_environment_configuration_queues_first_new_live_alert(self):
        self.train()
        self.assertIsNone(self.controller._notifier)
        with patch.dict(os.environ, {
            "ANOMALY_EMAIL_ENABLED": "1", "SMTP_HOST": "smtp.example.test",
            "SMTP_FROM": "qa@example.test", "ALERT_EMAIL_TO": "admin@example.test",
        }):
            point = self.ingest()
        jobs = self.controller.notifier.status()["jobs"]
        self.assertEqual(1, len(jobs))
        self.assertEqual(point["id"], jobs[0]["sample_id"])
        self.delivery.assert_not_called()

    def test_enabling_email_does_not_resend_saved_history_or_duplicate_after_restart(self):
        self.train()
        old = self.ingest()
        self.configure()
        self.ingest()
        self.assertEqual([], self.controller.notifier.status()["jobs"])
        new = self.ingest(self.record("incident-2", seconds=1))
        job_ids = [job["id"] for job in self.controller.notifier.status()["jobs"]]
        self.assertEqual(1, len(job_ids))
        self.controller.close()
        self.controller = MonitoringController(self.path)
        self.controller.start_live(session_id="qa-collector")
        restarted = self.controller.notifier.status()
        self.assertFalse(restarted["configured"], "SMTP credentials must stay only in process memory")
        self.assertEqual(job_ids, [job["id"] for job in restarted["jobs"]])
        self.assertEqual(old["id"], self.ingest()["id"])
        self.assertEqual(new["id"], self.ingest(self.record("incident-2", seconds=1))["id"])
        self.assertEqual(job_ids, [job["id"] for job in self.controller.notifier.status()["jobs"]])
        self.delivery.assert_not_called()

    def test_replay_committed_alerts_reach_same_queue_with_simulation_label(self):
        self.train()
        self.configure()
        self.controller.start_replay(scenario="K3", interval_seconds=.1, rows=30)
        deadline = time.monotonic() + 5
        jobs = []
        while time.monotonic() < deadline:
            jobs = self.controller.notifier.status()["jobs"]
            if jobs:
                break
            time.sleep(.03)
        self.controller.stop()
        self.assertTrue(jobs, "Replay scored alerts never reached the notification queue")
        point = self.controller.engine.get_sample(jobs[0]["sample_id"])
        self.assertGreaterEqual(point["votes"], 2)
        self.assertEqual("K3", point["source"])
        self.assertIn("[MÔ PHỎNG]", jobs[0]["subject"])
        self.assertNotEqual("error", self.controller.collector_status()["status"])
        self.delivery.assert_not_called()

    def test_notifier_failure_never_changes_committed_scoring_or_liveness(self):
        self.train()
        with patch.object(self.controller.notifier, "enqueue", side_effect=RuntimeError("QA_SECRET_ERROR")):
            with self.assertLogs("src.monitoring_controller", level="WARNING") as messages:
                point = self.ingest()
        self.assertNotIn("QA_SECRET_ERROR", "\n".join(messages.output))
        self.assertEqual(point, self.controller.engine.get_sample(point["id"]))
        self.assertEqual("running", self.controller.collector_status()["status"])

    def test_shutdown_closes_the_same_notifier_and_does_not_recreate_it(self):
        notifier = self.controller.notifier
        self.assertIs(notifier, self.controller.notifier)
        self.controller.close()
        self.assertTrue(notifier._closed)
        self.controller.close()
        with self.assertRaises(RuntimeError):
            _ = self.controller.notifier
        self.delivery.assert_not_called()


if __name__ == "__main__":
    unittest.main()
