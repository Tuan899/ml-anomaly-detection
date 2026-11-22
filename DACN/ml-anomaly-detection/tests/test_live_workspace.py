"""Exercise live UI actions through the real API, fitted engine and SQLite."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.monitoring_api import get_controller, router
from frontend.api_client import BackendError
from frontend.live_workspace import (METRICS, MODELS, SCREENS, activity_figure,
                                     comparison_figure, flatten_history, health_presentation)
from frontend.monitoring_client import monitor_get, monitor_post
from src.demo_scenarios import baseline_records, inject_record, scenario_records
from src.monitoring_controller import MonitoringController


APP = '''
from pathlib import Path
import streamlit as st
from frontend.live_workspace import render_live_workspace
def show_table(frame, dark, **kwargs):
    st.dataframe(frame)
render_live_workspace(Path.cwd(), False, show_table)
'''


class LiveWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "monitor.sqlite3"
        self.controller = MonitoringController(self.path)
        self.addCleanup(self.close_controller)
        api = FastAPI()
        api.include_router(router)
        api.dependency_overrides[get_controller] = lambda: self.controller
        self.client = TestClient(api)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.requests = []
        self.boundary = patch("frontend.monitoring_client.httpx.request", side_effect=self.request)
        self.boundary.start()
        self.addCleanup(self.boundary.stop)

    def close_controller(self):
        self.controller.stop()
        self.controller.engine.close()

    def request(self, method, url, **kwargs):
        kwargs.pop("timeout", None)
        kwargs.pop("trust_env", None)
        result = self.client.request(method, urlsplit(url).path, **kwargs)
        self.requests.append(result.request)
        return result

    def ui(self):
        app = AppTest.from_string(APP, default_timeout=60).run()
        self.assertEqual([], [item.message for item in app.exception])
        return app

    def ready(self):
        baseline = monitor_post("/train", {"source": "K1"})["baseline"]
        monitor_post("/source/live", {"interval_seconds": 1, "stale_after_seconds": 5})
        normal = scenario_records("K1", 30)[0]
        incident = inject_record(scenario_records("K1", 30)[1], "K3")
        result = monitor_post("/samples", {"records": [normal, incident], "source": "live"})["samples"]
        return baseline, result

    def test_no_baseline_does_not_create_models_or_claim_normal_operation(self):
        app = self.ui()
        self.assertIsNone(self.controller.engine.baseline())
        self.assertTrue(any("Chưa học mức nền" in item.value for item in app.warning))
        self.assertEqual(0, len(app.success))
        self.assertEqual(["/monitor/health"], [request.url.path for request in self.requests])

    def test_explicit_training_action_persists_only_chosen_normal_interval(self):
        app = self.ui()
        app.radio(key="monitor_screen").set_value(SCREENS[1]).run()
        app.number_input(key="monitor_baseline_end_K1_300").set_value(120).run()
        self.assertIsNone(self.controller.engine.baseline())
        app.button(key="monitor_train").click().run()
        self.assertEqual([], [item.message for item in app.exception])
        baseline = self.controller.engine.baseline()
        self.assertEqual(120, baseline["rows"])
        self.assertEqual(120, baseline["scaler"]["fit_rows"])
        training = next(request for request in self.requests if request.url.path == "/monitor/train")
        self.assertEqual(120, json.loads(training.content)["end_index"])
        self.assertFalse(any(request.url.path == "/monitor/replay/start" for request in self.requests))

    def test_alert_feedback_from_form_survives_controller_and_page_reload(self):
        _, points = self.ready()
        incident = points[-1]
        self.assertGreaterEqual(incident["votes"], 2)
        app = self.ui()
        app.radio(key=f"monitor_verdict_{incident['id']}").set_value("Xác nhận sự cố thật")
        app.text_input(key=f"monitor_note_{incident['id']}").set_value("Đã đối chiếu nhật ký kết nối.")
        app.button(key=f"monitor_save_{incident['id']}").click().run()
        self.assertEqual([], [item.message for item in app.exception])
        self.controller.stop()
        self.controller.engine.close()
        self.controller = MonitoringController(self.path)
        reopened = self.ui()
        self.assertEqual("Xác nhận sự cố thật", reopened.radio(key=f"monitor_verdict_{incident['id']}").value)
        self.assertEqual("Đã đối chiếu nhật ký kết nối.", reopened.text_input(key=f"monitor_note_{incident['id']}").value)
        self.assertTrue(any(request.url.path.endswith("/feedback") for request in self.requests))

    def test_uploaded_anomaly_outside_chosen_baseline_is_not_silently_filtered_or_trained(self):
        records = baseline_records(60) + [inject_record(scenario_records("K1", 30)[0], "K2")]
        app = self.ui()
        app.radio(key="monitor_screen").set_value(SCREENS[1]).run()
        app.radio(key="monitor_baseline_source").set_value("CSV của bạn").run()
        app.file_uploader(key="monitor_baseline_csv").set_value(("reference.csv", pd.DataFrame(records).to_csv(index=False).encode(), "text/csv")).run()
        self.assertTrue(app.button(key="monitor_train").disabled)
        self.assertIsNone(self.controller.engine.baseline())
        app.number_input(key="monitor_baseline_end_reference.csv_61").set_value(60).run()
        self.assertFalse(app.button(key="monitor_train").disabled)
        app.button(key="monitor_train").click().run()
        self.assertEqual([], [item.message for item in app.exception])
        self.assertEqual(60, self.controller.engine.baseline()["rows"])
        training = next(request for request in self.requests if request.url.path == "/monitor/train")
        payload = json.loads(training.content)
        self.assertEqual(61, len(payload["records"]))
        self.assertEqual(-1, payload["records"][-1]["label"])
        self.assertEqual(60, payload["end_index"])

    def test_stale_source_overrides_latest_zero_vote_measurement(self):
        self.ready()
        latest = monitor_post("/samples", {"records": [scenario_records("K1", 30)[2]], "source": "live"})["samples"][-1]
        self.assertEqual(0, latest["votes"])
        with patch("src.monitoring_controller._utcnow", return_value=datetime.now(timezone.utc) + timedelta(seconds=20)):
            app = self.ui()
        self.assertTrue(any("Mất tín hiệu" in item.value for item in app.error))
        self.assertFalse(any("Mẫu gần nhất:" in item.value for item in app.success))

    def test_recorded_alert_is_prominent_before_chart_when_source_is_stopped(self):
        _, points = self.ready()
        self.controller.stop()
        app = self.ui()
        self.assertTrue(any("NGHIÊM TRỌNG" in item.value and "Đã ghi nhận" in item.value for item in app.error))
        headings = [item.value for item in app.markdown]
        alert_index = next(index for index, text in enumerate(headings) if "Cảnh báo đã ghi nhận" in text)
        chart_index = next(index for index, text in enumerate(headings) if "Diễn biến hoạt động" in text)
        self.assertLess(alert_index, chart_index)
        self.assertTrue(any("Đây là cảnh báo đã lưu" in item.value for item in app.caption))
        self.assertIsNotNone(app.radio(key=f"monitor_verdict_{points[-1]['id']}"))
        self.assertEqual(5, len(app.metric))
        self.assertFalse(any("Mẫu gần nhất:" in item.value for item in app.success))

    def test_new_normal_sample_does_not_hide_recorded_critical_alert(self):
        self.ready()
        latest = monitor_post("/samples", {"records": [scenario_records("K1", 30)[2]], "source": "live"})["samples"][-1]
        self.assertEqual(0, latest["votes"])
        app = self.ui()
        self.assertTrue(any("NGHIÊM TRỌNG" in item.value for item in app.error))
        self.assertTrue(any("Mẫu gần nhất: Chưa có cảnh báo" in item.value for item in app.success))
        self.assertTrue(any("Đây là cảnh báo đã lưu" in item.value for item in app.caption))

    def test_one_click_demo_produces_visible_model_scored_alert(self):
        app = self.ui()
        app.button(key="monitor_demo_alert").click().run()
        self.assertEqual([], [item.message for item in app.exception])
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not self.controller.engine.alerts():
            time.sleep(.05)
        self.assertTrue(any(point["votes"] >= 2 and point["scenario"] == "K3" for point in self.controller.engine.alerts()))
        app.run()
        self.assertTrue(any("NGHIÊM TRỌNG" in item.value or "CẢNH BÁO" in item.value for item in [*app.error, *app.warning]))
        self.assertTrue(any(request.url.path == "/monitor/demo/alert" for request in self.requests))

    def test_comparison_switch_changes_only_decisions_and_reports_actual_metrics(self):
        baseline, points = self.ready()
        app = self.ui()
        app.radio(key="monitor_screen").set_value(SCREENS[2]).run()
        self.assertEqual([], [item.message for item in app.exception])
        guarded_spec = json.loads(app.get("plotly_chart")[0].proto.spec)
        expected_guarded = [[int(point["predictions"][name] == -1) for point in points] for name in MODELS]
        self.assertEqual(expected_guarded, guarded_spec["data"][0]["z"])
        app.toggle(key="monitor_raw_predictions").set_value(True).run()
        self.assertEqual([], [item.message for item in app.exception])
        raw_spec = json.loads(app.get("plotly_chart")[0].proto.spec)
        expected_raw = [[int(point["raw_predictions"][name] == -1) for point in points] for name in MODELS]
        self.assertEqual(expected_raw, raw_spec["data"][0]["z"])
        self.assertEqual(guarded_spec["data"][0]["x"], raw_spec["data"][0]["x"])
        self.assertEqual(1, sum(request.url.path == "/monitor/evidence" for request in self.requests))
        self.assertEqual(baseline["id"], self.controller.engine.baseline()["id"])
        measured = self.controller.engine.evaluation(baseline_id=baseline["id"])["raw"]
        displayed = next(item.value for item in app.dataframe if "Precision" in item.value)
        for _, row in displayed.iterrows():
            name = next(name for name, label in MODELS.items() if label == row["Thuật toán"])
            self.assertAlmostEqual(measured[name]["precision"], row["Precision"])
            self.assertEqual(measured[name]["fp"], row["FP"])
            self.assertEqual(measured[name]["fn"], row["FN"])
        self.assertEqual({"monitor_export_csv", "monitor_export_json"}, {item.key for item in app.download_button})

    def test_backend_failure_is_not_replaced_by_old_green_health(self):
        self.ready()
        with patch("frontend.monitoring_client.httpx.request", side_effect=httpx.ConnectError("offline")):
            app = self.ui()
        self.assertTrue(any("Mất kết nối Backend" in item.value for item in app.error))
        self.assertEqual(0, len(app.success))
        self.assertEqual(0, len(app.metric))

    def test_old_baseline_remains_selectable_beyond_latest_thousand_observations(self):
        old_baseline, old_points = self.ready()
        new_baseline = monitor_post("/train", {"source": "K1"})["baseline"]
        monitor_post("/source/live", {"interval_seconds": 1, "stale_after_seconds": 5})
        monitor_post("/samples", {"records": scenario_records("K1", 1000), "source": "new-live"})
        latest = monitor_get("/history", limit=1000)["samples"]
        self.assertTrue(all(point["baseline_id"] == new_baseline["id"] for point in latest))
        app = self.ui()
        app.radio(key="monitor_screen").set_value(SCREENS[2]).run()
        self.assertIn(f"Mức nền #{old_baseline['id']}", app.selectbox(key="monitor_comparison_baseline").options)
        app.selectbox(key="monitor_comparison_baseline").set_value(old_baseline["id"]).run()
        self.assertEqual([], [item.message for item in app.exception])
        snapshot = app.session_state["monitor_evidence_snapshot"]["data"]
        self.assertEqual(old_baseline["id"], snapshot["baseline"]["id"])
        self.assertEqual([point["id"] for point in old_points], [point["id"] for point in snapshot["samples"]])
        self.assertEqual(len(old_points), snapshot["evaluation"]["rows"])
        self.assertIn("live", app.selectbox(key=f"monitor_comparison_source_{old_baseline['id']}").options)

    def test_exports_and_tooltips_preserve_all_observations_and_both_vote_sets(self):
        _, points = self.ready()
        frame = flatten_history(points)
        self.assertEqual([point["votes"] for point in points], frame["votes"].tolist())
        for metric in METRICS:
            self.assertEqual([point[metric] for point in points], frame[metric].tolist())
        self.assertEqual([point.get("scenario") for point in points], frame["scenario"].tolist())
        for name in MODELS:
            self.assertEqual([point["raw_predictions"][name] for point in points], frame[f"{name}_raw_prediction"].tolist())
            self.assertEqual([point["predictions"][name] for point in points], frame[f"{name}_prediction"].tolist())
        chart = activity_figure(points)
        self.assertEqual(10, len(chart.data))
        for index, metric in enumerate(METRICS):
            self.assertEqual([point[metric] for point in points], list(chart.data[index * 2].y))
            self.assertEqual([point["received_at"] for point in points], list(chart.data[index * 2].x))
        self.assertEqual(points[0]["timestamp"], chart.data[0].customdata[0][5])
        raw = comparison_figure(points, raw=True)
        self.assertEqual(points[-1]["raw_votes"], raw.data[0].customdata[0][-1][7])
        self.assertIn("Đồng thuận gốc", raw.data[0].hovertemplate)


class MonitoringPresentationTests(unittest.TestCase):
    def test_stale_and_stopped_states_never_return_success(self):
        for state in ("stale", "stopped", "completed", "waiting", "idle", "error"):
            with self.subTest(state=state):
                health = {"baseline": {"id": 1}, "collector": {"status": state, "last_received_at": "2026-01-01"}}
                self.assertNotEqual("success", health_presentation(health)[0])

    def test_unknown_or_malformed_liveness_fails_closed_even_with_last_sample(self):
        source = {"status": "running", "last_received_at": "2026-01-01T00:00:00Z", "age_seconds": 1., "stale_after_seconds": 5.}
        self.assertEqual("success", health_presentation({"baseline": {"id": 1}, "collector": source})[0])
        for change in ({"status": "restarting"}, {"age_seconds": None}, {"age_seconds": float("nan")},
                       {"age_seconds": -1}, {"age_seconds": True}, {"age_seconds": 10},
                       {"stale_after_seconds": 0}, {"stale_after_seconds": float("inf")}):
            with self.subTest(change=change):
                self.assertNotEqual("success", health_presentation({"baseline": {"id": 1}, "collector": {**source, **change}})[0])

    def test_nonfinite_payload_rejected_before_network(self):
        with patch("frontend.monitoring_client.httpx.request") as request:
            with self.assertRaises(BackendError):
                monitor_post("/samples", {"records": [{"queries_per_second": float("nan")}]})
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
