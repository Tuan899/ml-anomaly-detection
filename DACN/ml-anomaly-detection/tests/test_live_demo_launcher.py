"""Verify live-demo setup boundaries without contacting a database."""
from __future__ import annotations

from contextlib import redirect_stderr
from datetime import datetime, timezone
from io import StringIO
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_live_demo as launcher


class LiveDemoLauncherTests(unittest.TestCase):
    def test_check_never_prompts_or_starts_services(self):
        with patch.object(launcher, "_check_dependencies"), patch.object(launcher, "_run") as run:
            self.assertEqual(0, launcher.main(["--check"]))
        run.assert_not_called()

    def test_bounds_reject_invalid_sampling_configuration(self):
        for flags in (["--baseline-samples", "29"], ["--baseline-samples", "301"],
                      ["--interval", "nan"], ["--interval", "0"], ["--port", "65536"]):
            with self.subTest(flags=flags), redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit):
                    launcher.arguments(flags)

    def test_unencrypted_remote_is_rejected_before_password_prompt(self):
        args = launcher.arguments(["--host", "remote.internal", "--port", "3306", "--user", "reader",
                                   "--fault-user", "demo", "--no-tls"])
        with patch.object(launcher, "getpass") as password:
            with self.assertRaisesRegex(launcher.DemoError, "loopback"):
                launcher._run(args)
        password.assert_not_called()

    def test_child_credentials_are_separated(self):
        base = {"PATH": "safe", "MYSQL_HOST": "db", "MYSQL_PASSWORD": "read-secret",
                "FAULT_MYSQL_HOST": "db", "FAULT_MYSQL_PASSWORD": "load-secret",
                "ANOMALY_FAULT_ENABLED": "1", "ANOMALY_API_URL": "http://127.0.0.1:8002",
                "OPENAI_API_KEY": "ai-secret", "SMTP_PASSWORD": "mail-secret", "SMTP_USER": "sender@example.com"}
        backend = launcher._child_environment(base, "backend")
        collector = launcher._child_environment(base, "collector")
        frontend = launcher._child_environment(base, "frontend")
        self.assertEqual("load-secret", backend["FAULT_MYSQL_PASSWORD"])
        self.assertEqual("ai-secret", backend["OPENAI_API_KEY"])
        self.assertEqual("mail-secret", backend["SMTP_PASSWORD"])
        self.assertNotIn("MYSQL_PASSWORD", backend)
        self.assertEqual("read-secret", collector["MYSQL_PASSWORD"])
        self.assertNotIn("FAULT_MYSQL_PASSWORD", collector)
        self.assertNotIn("OPENAI_API_KEY", collector)
        self.assertNotIn("SMTP_PASSWORD", collector)
        self.assertNotIn("ANOMALY_FAULT_ENABLED", collector)
        self.assertNotIn("MYSQL_PASSWORD", frontend)
        self.assertNotIn("FAULT_MYSQL_PASSWORD", frontend)
        self.assertNotIn("OPENAI_API_KEY", frontend)
        self.assertNotIn("SMTP_PASSWORD", frontend)
        self.assertEqual("http://127.0.0.1:8002", frontend["ANOMALY_API_URL"])
        self.assertEqual("read-secret", base["MYSQL_PASSWORD"])

    def test_finished_child_is_never_signalled(self):
        child = MagicMock()
        child.poll.return_value = 0
        launcher._stop_owned(child)
        child.send_signal.assert_not_called()
        child.wait.assert_not_called()

    def test_measured_baseline_precedes_services_and_secrets_stay_out_of_commands(self):
        args = launcher.arguments(["--host", "127.0.0.1", "--port", "3306", "--user", "reader",
            "--fault-user", "loader", "--baseline-samples", "30", "--interval", ".1", "--no-tls", "--no-browser"])
        frame = pd.DataFrame([{"timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "queries_per_second": 2.2, "connections": 1, "response_time_ms": .4,
            "slow_queries": 0, "connection_errors": 0}])
        children = [MagicMock() for _ in range(3)]
        for child in children:
            child.poll.return_value = None
        client = MagicMock()
        client.get.return_value.status_code = 200
        client.post.return_value.raise_for_status.return_value = None
        boundary = MagicMock()
        boundary.__enter__.return_value = client
        events = []
        def measured(**kwargs):
            events.append("baseline")
            self.assertEqual(30, kwargs["samples"])
            self.assertEqual("reader-password", kwargs["password"])
            return frame
        def start(command, environment, log_file):
            self.assertEqual("baseline", events[0])
            self.assertNotIn("reader-password", " ".join(command))
            self.assertNotIn("loader-password", " ".join(command))
            events.append((command, environment))
            return children[len(events) - 2]
        with tempfile.TemporaryDirectory() as directory, patch.object(launcher, "ROOT", Path(directory)), \
             patch.object(launcher, "getpass", side_effect=["reader-password", "loader-password"]), \
             patch("src.mysql_collector.collect_mysql_metrics", side_effect=measured), \
             patch("httpx.Client", return_value=boundary), patch.object(launcher, "_wait_backend"), \
             patch.object(launcher, "_free_port", side_effect=[8002, 8504]), \
             patch.object(launcher, "_start", side_effect=start), patch.object(launcher, "_stop_owned") as stop, \
             patch.object(launcher.time, "sleep", side_effect=KeyboardInterrupt), \
             patch.dict(os.environ, {"MYSQL_PASSWORD": "inherited-secret", "FAULT_MYSQL_NO_TLS": "bad"}):
            with self.assertRaises(KeyboardInterrupt):
                launcher._run(args)
            self.assertEqual([children[2], children[1], children[0]], [call.args[0] for call in stop.call_args_list])
            trained = client.post.call_args.kwargs["json"]
            self.assertEqual("live-baseline", trained["source"])
            self.assertEqual(2.2, trained["records"][0]["queries_per_second"])
            self.assertTrue(trained["records"][0]["timestamp"].startswith("2026-01-01T00:00:00"))
            self.assertNotIn("label", trained["records"][0])
            self.assertTrue((Path(directory) / ".runtime" / "live_baseline.csv").is_file())
        backend_env, collector_env, frontend_env = [event[1] for event in events[1:]]
        self.assertEqual("1", backend_env["FAULT_MYSQL_NO_TLS"])
        self.assertEqual("loader-password", backend_env["FAULT_MYSQL_PASSWORD"])
        self.assertNotIn("MYSQL_PASSWORD", backend_env)
        self.assertEqual("reader-password", collector_env["MYSQL_PASSWORD"])
        self.assertNotIn("FAULT_MYSQL_PASSWORD", collector_env)
        self.assertNotIn("MYSQL_PASSWORD", frontend_env)
        self.assertNotIn("FAULT_MYSQL_PASSWORD", frontend_env)


if __name__ == "__main__":
    unittest.main()
