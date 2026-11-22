"""Keep source provenance and current liveness separate from stored model votes."""
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
from frontend.live_workspace import _time_label, source_presentation


class SourcePresentationTests(unittest.TestCase):
    def health(self, mode="live", status="running"):
        return {"backend": "ok", "baseline": {"id": 1},
                "collector": {"mode": mode, "status": status, "last_received_at": "2026-11-21T09:00:00Z",
                              "age_seconds": 1, "stale_after_seconds": 5},
                "latest": {"votes": 0, "level": "normal"}}

    def test_replay_never_claims_live_mysql_even_when_all_votes_are_normal(self):
        health = self.health(mode="replay")
        before = deepcopy(health)
        tone, title, detail = source_presentation(health)
        self.assertEqual("simulated", tone)
        self.assertIn("mô phỏng", title)
        self.assertIn("không phản ánh MySQL thật", detail)
        self.assertEqual(before, health)

    def test_stale_stopped_or_invalid_live_signal_cannot_get_live_badge(self):
        for status in ("stale", "stopped", "waiting", "completed", "error", "restarting"):
            with self.subTest(status=status):
                self.assertEqual("waiting", source_presentation(self.health(status=status))[0])
        health = self.health()
        for age in (None, float("nan"), -1, True, 6):
            health["collector"]["age_seconds"] = age
            with self.subTest(age=age):
                self.assertEqual("waiting", source_presentation(health)[0])

    def test_live_badge_requires_fresh_signal_but_is_independent_of_anomaly_votes(self):
        health = self.health()
        for level, votes in (("normal", 0), ("critical", 4)):
            health["latest"] = {"level": level, "votes": votes}
            self.assertEqual("live", source_presentation(health)[0])
        self.assertEqual("unknown", source_presentation({})[0])

    def test_local_time_is_only_a_display_conversion_of_the_same_instant(self):
        utc = "2026-11-21T20:30:00Z"
        local = "2026-11-22T03:30:00+07:00"
        self.assertEqual("03:30:00 · 22/11/2026", _time_label(utc))
        self.assertEqual(_time_label(utc), _time_label(local))
        self.assertEqual("—", _time_label(None))

    def test_history_failure_does_not_leave_green_status_or_old_measurements(self):
        health = self.health()

        def request(path, **params):
            if path == "/health":
                return health
            raise BackendError("Mất kết nối Backend khi đọc lịch sử.")

        with patch("frontend.live_workspace.monitor_get", side_effect=request):
            app = AppTest.from_string("""
import streamlit as st
from frontend.live_workspace import _monitor_panel
_monitor_panel(False, lambda frame, dark, **kwargs: st.dataframe(frame))
""", default_timeout=30).run()
        self.assertEqual([], [item.message for item in app.exception])
        self.assertEqual(0, len(app.metric))
        self.assertEqual(0, len(app.success))
        self.assertTrue(any("Mất kết nối" in item.value for item in app.error))


if __name__ == "__main__":
    unittest.main()
