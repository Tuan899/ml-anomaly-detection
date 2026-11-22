"""The public entrypoint stays focused on MySQL, including older sessions."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import httpx
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

APP_PATH = ROOT / "frontend" / "app.py"


class MySQLPublicAppTests(unittest.TestCase):
    def setUp(self):
        # Exercise the actual renderer and HTTP error handling. A failed
        # connection must not be disguised as a successful monitoring session.
        self.http = patch("frontend.monitoring_client.httpx.request",
                          side_effect=httpx.ConnectError("backend unavailable"))
        self.requests = self.http.start()
        self.addCleanup(self.http.stop)

    def app(self, **state):
        app = AppTest.from_file(APP_PATH, default_timeout=60)
        for key, value in state.items():
            app.session_state[key] = value
        return app.run()

    def assert_monitor_only(self, app):
        self.assertEqual([], [item.message for item in app.exception])
        self.assertTrue(any(item.value == "Giám sát MySQL" for item in app.header))
        keys = {item.key for element in (app.radio, app.selectbox, app.multiselect,
                                         app.file_uploader, app.button) for item in element}
        self.assertFalse({"interface_mode", "workspace_mode", "selected_models", "dbms_models",
                          "basic_csv_upload", "dbms_csv_upload", "csv_upload",
                          "basic_start", "dbms_run", "run_analysis"} & keys)
        self.assertIn("admin_assistant_open", keys)
        self.assertTrue(any("[Bot cảnh báo](#bot-canh-bao)" == item.value for item in app.markdown))
        self.assertFalse(any(item.label in {"Phân tích CSV & nghiên cứu", "Công cụ phân tích"}
                             for item in app.expander))
        captions = " ".join(item.value for item in app.caption)
        for name in ("MAD", "Isolation Forest", "LOF", "One-Class SVM"):
            self.assertIn(name, captions)

    def test_default_public_page_shows_connection_failure_without_offline_menu(self):
        app = self.app()
        self.assert_monitor_only(app)
        self.assertGreater(self.requests.call_count, 0)
        self.assertTrue(app.error)
        self.assertEqual(0, len(app.success))

    def test_older_research_session_cannot_restore_removed_menu(self):
        for mode in ("Cơ bản", "Nâng cao"):
            with self.subTest(mode=mode):
                app = self.app(interface_mode=mode, workspace_mode="CSV một chỉ số / notebook NAB")
                self.assert_monitor_only(app)
                self.assertEqual(0, len(app.success))

    def test_theme_toggle_keeps_public_monitoring_entrypoint(self):
        app = self.app()
        app.toggle(key="dark_mode").set_value(True).run()
        self.assert_monitor_only(app)
        self.assertTrue(app.toggle(key="dark_mode").value)


if __name__ == "__main__":
    unittest.main()
