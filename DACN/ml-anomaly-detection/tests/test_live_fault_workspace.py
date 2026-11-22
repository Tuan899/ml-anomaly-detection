"""Exercise the real-load controls without connecting to a database."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.api_client import BackendError

APP = "from frontend.live_workspace import _live_fault_panel\n_live_fault_panel()"


class LiveFaultWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.health = {"baseline": {"id": 1}, "collector": {
            "mode": "live", "status": "running", "target_id": "a" * 64,
            "last_received_at": "2026-11-21T00:00:00Z", "age_seconds": 1., "stale_after_seconds": 5.,
        }}
        self.state = {"enabled": True, "configured": True,
                      "target": {"host": "127.0.0.1", "port": 3306, "target_id": "a" * 64},
                      "job": None}
        self.posts = []
        get_patch = patch("frontend.live_workspace.monitor_get", side_effect=self.get)
        post_patch = patch("frontend.live_workspace.monitor_post", side_effect=self.post)
        get_patch.start()
        post_patch.start()
        self.addCleanup(get_patch.stop)
        self.addCleanup(post_patch.stop)

    def get(self, path, **kwargs):
        return deepcopy(self.health if path == "/health" else self.state)

    def post(self, path, payload):
        self.posts.append((path, payload))
        if path.endswith("/stop"):
            self.state["job"]["status"] = "stopped"
        else:
            self.state["job"] = {"scenario": payload["scenario"], "status": "running", "counters": {}}
        return deepcopy(self.state)

    def ui(self):
        app = AppTest.from_string(APP, default_timeout=30).run()
        self.assertEqual([], [item.message for item in app.exception])
        return app

    def test_load_requires_configured_matching_fresh_live_source(self):
        for mutation in ("disabled", "mismatch", "stale", "replay"):
            with self.subTest(mutation=mutation):
                with patch.object(self, "health", deepcopy(self.health)), patch.object(self, "state", deepcopy(self.state)):
                    if mutation == "disabled":
                        self.state["enabled"] = False
                    elif mutation == "mismatch":
                        self.health["collector"]["target_id"] = "b" * 64
                    else:
                        self.health["collector"]["status" if mutation == "stale" else "mode"] = mutation
                    app = self.ui()
                    for scenario in ("K2", "K3", "K4"):
                        self.assertTrue(app.button(key=f"monitor_live_fault_{scenario}").disabled)
                    self.assertEqual([], self.posts)

    def test_start_forwards_selected_limits_once_and_blocks_second_job(self):
        app = self.ui()
        app.slider(key="monitor_fault_duration").set_value(8)
        app.slider(key="monitor_fault_rate").set_value(150)
        app.slider(key="monitor_fault_connections").set_value(6)
        app.number_input(key="monitor_fault_auth_failures").set_value(2)
        app.button(key="monitor_live_fault_K3").click().run()
        self.assertEqual([], [item.message for item in app.exception])
        self.assertEqual([("/faults/live", {"scenario": "K3", "duration_seconds": 8,
                          "rate_per_second": 150, "connections": 6, "auth_failures": 2})], self.posts)
        self.assertTrue(app.button(key="monitor_live_fault_K2").disabled)
        self.assertFalse(app.button(key="monitor_live_fault_stop").disabled)

    def test_stop_calls_backend_and_preserves_measurement_health(self):
        self.state["job"] = {"scenario": "K2", "status": "running", "counters": {"successful_queries": 123}}
        original = deepcopy(self.health)
        app = self.ui()
        app.button(key="monitor_live_fault_stop").click().run()
        self.assertEqual([], [item.message for item in app.exception])
        self.assertEqual([("/faults/live/stop", {})], self.posts)
        self.assertEqual(original, self.health)
        self.assertTrue(app.button(key="monitor_live_fault_stop").disabled)

    def test_backend_failure_does_not_leave_load_controls_available(self):
        with patch("frontend.live_workspace.monitor_get", side_effect=BackendError("Mất kết nối Backend")):
            app = self.ui()
        self.assertTrue(any("Mất kết nối Backend" in item.value for item in app.error))
        self.assertFalse(any(item.key.startswith("monitor_live_fault_K") for item in app.button))
        self.assertEqual([], self.posts)


if __name__ == "__main__":
    unittest.main()
