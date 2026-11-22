"""Regressions for demo selection and honest, actionable result presentation."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "research_app.py"
for directory in (PROJECT_ROOT, Path(__file__).resolve().parent):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from frontend.demo_data import ANOMALOUS_SAMPLES, DEFAULT_ANOMALOUS_SAMPLE
from frontend.dbms_charts import MYSQL_METRICS
from frontend.reporting import build_report_markdown
from http_transport import APITransport


class DashboardUXRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = APITransport().__enter__()
        self.addCleanup(self.transport.__exit__, None, None, None)
        self.app = AppTest.from_file(APP_PATH, default_timeout=60)
        self.app.session_state["interface_mode"] = "Cơ bản"
        self.app.run()
        self.assert_no_exception()

    def assert_no_exception(self) -> None:
        self.assertEqual([], [item.message for item in self.app.exception])

    def test_basic_anomalous_demo_uses_the_current_isolated_scenario(self) -> None:
        self.app.button(key="basic_anomalous").click().run()
        self.app.button(key="basic_start").click().run()
        self.assert_no_exception()
        result = self.app.session_state["basic_result"]
        self.assertEqual(DEFAULT_ANOMALOUS_SAMPLE, self.app.session_state["basic_result_sources"]["single"])
        self.assertEqual("synthetic", result.metadata["source_kind"])
        original = pd.read_csv(PROJECT_ROOT / "data" / DEFAULT_ANOMALOUS_SAMPLE)
        np.testing.assert_allclose(original[list(MYSQL_METRICS)], result.frame[list(MYSQL_METRICS)])

    def test_advanced_exposes_only_the_delivered_anomaly_scenarios(self) -> None:
        self.app.radio(key="interface_mode").set_value("Nâng cao").run()
        self.app.selectbox(key="dbms_sample").set_value("Hoạt động bất thường").run()
        self.app.multiselect(key="dbms_models").set_value(["mad"]).run()
        self.assertEqual(list(ANOMALOUS_SAMPLES), self.app.selectbox(key="dbms_sample_scenario").options)
        self.assertEqual({"mysql_query_spike.csv", "mysql_latency_spike.csv"}, set(ANOMALOUS_SAMPLES.values()))
        for scenario, filename in ANOMALOUS_SAMPLES.items():
            with self.subTest(scenario=scenario):
                self.app.selectbox(key="dbms_sample_scenario").set_value(scenario).run()
                self.app.button(key="dbms_run").click().run()
                self.assert_no_exception()
                self.assertEqual([], list(self.app.error))
                result = self.app.session_state["dbms_result"]
                self.assertEqual("synthetic", result.metadata["source_kind"])
                original = pd.read_csv(PROJECT_ROOT / "data" / filename)
                np.testing.assert_allclose(original[list(MYSQL_METRICS)], result.frame[list(MYSQL_METRICS)])

    def test_mixed_labels_are_explained_and_upload_names_do_not_claim_provenance(self) -> None:
        labeled = pd.read_csv(PROJECT_ROOT / "data" / "mysql_normal.csv")
        unlabeled = labeled.drop(columns=["label"])
        self.app.button(key="basic_compare").click().run()
        self.app.radio(key="basic_source").set_value("Tải tệp CSV").run()
        for key, frame, filename in (
            ("normal", labeled, "mysql_normal.csv"),
            ("anomalous", unlabeled, DEFAULT_ANOMALOUS_SAMPLE),
        ):
            self.app.file_uploader(key=f"basic_{key}_upload").set_value(
                (filename, frame.to_csv(index=False).encode("utf-8"), "text/csv")
            ).run()
        self.assert_no_exception()
        self.assertTrue(any("Chỉ một tệp có nhãn" in item.value for item in self.app.info))
        self.app.button(key="basic_start").click().run()
        self.assert_no_exception()
        self.assertEqual([], list(self.app.error))
        self.assertTrue(any("Chỉ một tệp có nhãn" in item.value for item in self.app.info))
        for result in self.app.session_state["basic_result"].values():
            self.assertEqual("upload", result.metadata["source_kind"])
            self.assertIsNone(result.metadata["label_col"])
            self.assertEqual({}, result.metrics)
            report = build_report_markdown(result, source_name="mysql_normal.csv").decode("utf-8-sig")
            self.assertIn("Nguồn và nhãn do người dùng cung cấp", report)
            self.assertNotIn("Dữ liệu mẫu tổng hợp phục vụ kiểm thử", report)
        comparison = json.loads(self.app.get("plotly_chart")[0].proto.spec)
        self.assertEqual("Dữ liệu tham chiếu", comparison["data"][0]["name"])
        self.assertEqual("Dữ liệu cần đối chiếu", comparison["data"][2]["name"])
        self.assertTrue(any("Hoạt động tham chiếu" in item.value for item in self.app.markdown))
        self.assertFalse(any("#### Hoạt động bình thường" == item.value for item in self.app.markdown))


class AlertFilterUXRegressionTests(unittest.TestCase):
    def test_empty_severity_filter_explains_how_to_restore_alerts(self) -> None:
        app = AppTest.from_string("""
import pandas as pd
import streamlit as st
from frontend.monitoring_workspace import _notable

summary = {"notable": pd.DataFrame({"Mức cảnh báo": ["Cần chú ý"], "Thời gian": ["2026-01-01"]})}
_notable(summary, lambda frame, dark: st.dataframe(frame), False)
""", default_timeout=60).run()
        self.assertEqual(1, len(app.dataframe))
        app.radio(key="basic_level_filter").set_value("Cảnh báo cao").run()
        self.assertEqual([], [item.message for item in app.exception])
        self.assertEqual(0, len(app.dataframe))
        self.assertTrue(any("Chọn Tất cả" in item.value for item in app.info))
        app.radio(key="basic_level_filter").set_value("Tất cả").run()
        self.assertEqual(1, len(app.dataframe))


if __name__ == "__main__":
    unittest.main()
