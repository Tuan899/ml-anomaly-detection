"""Exercise the beginner workflow against the actual HTTP analysis pipeline.

Only the network boundary is replaced by ASGI. Counts, charts and reports must
still come from the current backend predictions, never from scenario names.
"""

from __future__ import annotations

from base64 import b64decode
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import httpx
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "app.py"
for directory in (PROJECT_ROOT, Path(__file__).resolve().parent):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from http_transport import APITransport


MODELS = ["mad", "isolation_forest", "lof", "one_class_svm"]
METRICS = ["queries_per_second", "connections", "response_time_ms", "slow_queries", "connection_errors"]


def values(encoded):
    """Read both ordinary Plotly arrays and Plotly 6 typed-array JSON."""
    if isinstance(encoded, dict) and "bdata" in encoded:
        return np.frombuffer(b64decode(encoded["bdata"]), dtype=encoded["dtype"])
    return np.asarray(encoded)


def operational_flags(run):
    return run.predictions[[f"{name}_prediction" for name in run.metadata["model_names"]]].eq(-1).any(axis=1)


class MonitoringWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = APITransport().__enter__()
        self.addCleanup(self.transport.__exit__, None, None, None)
        self.app = AppTest.from_file(APP_PATH, default_timeout=60).run()
        self.assert_no_exception()

    def assert_no_exception(self) -> None:
        self.assertEqual([], [item.message for item in self.app.exception])

    def assert_no_results(self) -> None:
        self.assertEqual(0, len(self.app.metric))
        self.assertFalse({"basic_report", "basic_csv", "basic_json"} & {item.key for item in self.app.download_button})

    def analyze(self, *, anomalous=False):
        if anomalous:
            self.app.button(key="basic_anomalous").click().run()
        self.app.button(key="basic_start").click().run()
        self.assert_no_exception()
        return self.app.session_state["basic_result"]

    def upload(self, content: bytes) -> None:
        self.app.radio(key="basic_source").set_value("Tải tệp CSV").run()
        self.app.file_uploader(key="basic_csv_upload").set_value(("mysql.csv", content, "text/csv")).run()
        self.assert_no_exception()

    def test_default_is_three_step_basic_without_training_or_model_controls(self) -> None:
        self.assertEqual("Cơ bản", self.app.radio(key="interface_mode").value)
        self.assertEqual("Dùng dữ liệu mẫu", self.app.radio(key="basic_source").value)
        self.assertEqual("normal", self.app.session_state["basic_scenario"])
        for key in ("basic_normal", "basic_anomalous", "basic_compare", "basic_start"):
            self.assertFalse(self.app.button(key=key).proto.disabled)
        self.assertEqual(0, len(self.app.multiselect))
        self.assertEqual(0, len(self.app.slider))
        self.assertNotIn("workspace_mode", {item.key for item in self.app.radio})
        self.assert_no_results()
        self.assertNotIn("basic_result", self.app.session_state)
        self.transport.mock_post.assert_not_called()

    def test_normal_result_uses_real_holdout_and_reports_no_operational_alerts(self) -> None:
        result = self.analyze()
        self.transport.mock_post.assert_called_once()
        self.assertEqual("/detect", self.transport.requests[0].url.path)
        self.assertEqual(MODELS, result.metadata["model_names"])
        self.assertEqual(1008, result.metadata["train_rows"])
        self.assertEqual(432, len(result.predictions))
        self.assertEqual(0, int(operational_flags(result).sum()))
        self.assertEqual(4, len(self.app.metric))
        self.assertTrue(any("Bình thường" in item.value for item in self.app.metric))
        self.assertTrue({"basic_report", "basic_csv", "basic_json"} <= {item.key for item in self.app.download_button})
        self.assertNotIn("label", result.metadata["features"])
        self.assertNotIn("scenario", result.metadata["features"])

    def test_anomalous_result_charts_and_notable_table_match_current_predictions(self) -> None:
        result = self.analyze(anomalous=True)
        flags = operational_flags(result)
        self.assertGreater(int(flags.sum()), 0)
        self.assertEqual(4, len(self.app.metric))
        figures = [json.loads(item.proto.spec) for item in self.app.get("plotly_chart")]
        count_chart = next(figure for figure in figures if figure["data"][0]["type"] == "bar")
        np.testing.assert_array_equal([len(flags) - int(flags.sum()), int(flags.sum())], values(count_chart["data"][0]["y"]))
        self.assertGreaterEqual(sum(figure["data"][0]["type"] == "scatter" for figure in figures), 2)
        notable = next(item.value for item in self.app.dataframe if {"Thời gian", "Giá trị quan sát", "Giá trị tham chiếu"} <= set(item.value.columns))
        self.assertGreater(len(notable), 0)
        self.assertTrue(pd.to_datetime(notable["Thời gian"]).isin(result.predictions.loc[flags, "timestamp"]).all())
        evidence = next(item.value for item in self.app.dataframe if {"Chỉ số", "Giá trị quan sát", "Mức tham chiếu"} <= set(item.value.columns))
        self.assertFalse({"actual", "reference", "deviation_ratio", "material"} & set(evidence.columns))
        first_alert = result.predictions.loc[flags].iloc[0]
        np.testing.assert_allclose(first_alert[METRICS].astype(float), evidence["Giá trị quan sát"])
        np.testing.assert_allclose([result.metadata["train_baselines"][metric]["median"] for metric in METRICS], evidence["Mức tham chiếu"])
        self.assertTrue(any("Vì sao hệ thống" in item.value for item in self.app.markdown))

    def test_new_data_returns_to_selection_without_automatically_training(self) -> None:
        self.analyze(anomalous=True)
        self.app.button(key="basic_other_data").click().run()
        self.assert_no_exception()
        self.assert_no_results()
        self.assertNotIn("basic_result", self.app.session_state)
        self.app.button(key="basic_normal").click().run()
        self.assert_no_exception()
        self.assert_no_results()
        self.transport.mock_post.assert_called_once()

    def test_navigation_to_comparison_hides_previous_single_run_results(self) -> None:
        self.analyze(anomalous=True)
        self.app.radio(key="basic_navigation").set_value("So sánh dữ liệu").run()
        self.assert_no_exception()
        self.assertEqual("compare", self.app.session_state["basic_scenario"])
        self.assert_no_results()
        self.assertTrue(any("thay đổi" in item.value.lower() for item in self.app.info))
        self.transport.mock_post.assert_called_once()

    def test_backend_failure_never_shows_previous_results_or_local_fallback(self) -> None:
        self.analyze(anomalous=True)
        self.app.button(key="basic_other_data").click().run()
        self.transport.mock_post.side_effect = httpx.ConnectError("connection refused")
        self.app.button(key="basic_start").click().run()
        self.assert_no_exception()
        self.assertTrue(any("Không kết nối được BE" in item.value for item in self.app.error))
        self.assertNotIn("basic_result", self.app.session_state)
        self.assertNotIn("basic_result_signature", self.app.session_state)
        self.assert_no_results()
        self.assertEqual(2, self.transport.mock_post.call_count)

    def test_csv_aliases_preserve_measurements_without_fabricating_quality_metrics(self) -> None:
        original = pd.read_csv(PROJECT_ROOT / "data" / "mysql_anomalous.csv").drop(columns=["label", "scenario"])
        renamed = original.rename(columns=dict(zip(
            ["timestamp", *METRICS],
            ["time", "qps", "active_connections", "latency_ms", "slow_query_count", "failed_connections"],
        )))
        self.upload(renamed.to_csv(index=False).encode("utf-8"))
        result = self.analyze()
        self.assertEqual({}, result.metrics)
        self.assertIsNone(result.metadata["label_col"])
        for column in METRICS:
            np.testing.assert_allclose(original[column], result.frame[column])
        self.assertNotIn("label_col", self.transport.requests[0].url.params)

    def test_missing_csv_metric_is_actionable_and_never_sent_for_analysis(self) -> None:
        original = pd.read_csv(PROJECT_ROOT / "data" / "mysql_normal.csv").drop(columns=["connections"])
        self.upload(original.to_csv(index=False).encode("utf-8"))
        self.assertTrue(any("connections" in item.value for item in self.app.error))
        self.assertTrue(self.app.button(key="basic_start").proto.disabled)
        self.assert_no_results()
        self.transport.mock_post.assert_not_called()

    def test_mysql_collects_only_on_start_then_analyzes_the_returned_measurements(self) -> None:
        collected = pd.read_csv(PROJECT_ROOT / "data" / "mysql_normal.csv").iloc[:60][["timestamp", *METRICS]].copy()
        with patch("frontend.monitoring_workspace.collect_mysql_metrics", return_value=collected) as collector:
            self.app.radio(key="basic_source").set_value("Kết nối MySQL").run()
            self.app.text_input(key="basic_mysql_host").set_value("mysql.example.test")
            self.app.text_input(key="basic_mysql_password").set_value("TEST_ONLY_PASSWORD").run()
            self.assert_no_exception()
            collector.assert_not_called()
            self.transport.mock_post.assert_not_called()
            result = self.analyze()
            collector.assert_called_once()
            self.assertEqual("mysql.example.test", collector.call_args.kwargs["host"])
            self.assertEqual("TEST_ONLY_PASSWORD", collector.call_args.kwargs["password"])
        self.assertEqual(60, len(result.frame))
        self.assertEqual({}, result.metrics)
        for metric in METRICS:
            np.testing.assert_allclose(collected[metric], result.frame[metric], rtol=1e-12)
        request = self.transport.requests[0]
        self.assertNotIn(b"TEST_ONLY_PASSWORD", request.content)
        self.assertNotIn(b"mysql.example.test", request.content)
        self.assertNotIn("label_col", request.url.params)

    def test_mysql_collection_failure_has_no_api_request_or_stale_results(self) -> None:
        from src.mysql_collector import MySQLCollectionError

        self.analyze(anomalous=True)
        self.app.button(key="basic_other_data").click().run()
        self.app.radio(key="basic_source").set_value("Kết nối MySQL").run()
        with patch("frontend.monitoring_workspace.collect_mysql_metrics",
                   side_effect=MySQLCollectionError("Không kết nối được MySQL. Kiểm tra địa chỉ và quyền tài khoản.")):
            self.app.button(key="basic_start").click().run()
        self.assert_no_exception()
        self.assertTrue(any("Không kết nối được MySQL" in item.value for item in self.app.error))
        self.assertNotIn("basic_result", self.app.session_state)
        self.assertNotIn("basic_result_signature", self.app.session_state)
        self.assert_no_results()
        self.transport.mock_post.assert_called_once()

    def test_advanced_manual_mapping_blocks_duplicates_then_preserves_measurements(self) -> None:
        original = pd.read_csv(PROJECT_ROOT / "data" / "mysql_anomalous.csv")
        source_names = ["observed_when", "application_query_rate", "open_sessions", "round_trip_ms", "slow_events", "failed_connect_events"]
        mapping = dict(zip(["timestamp", *METRICS], source_names))
        content = original.rename(columns=mapping).to_csv(index=False).encode("utf-8")
        self.app.radio(key="interface_mode").set_value("Nâng cao").run()
        self.app.radio(key="dbms_source").set_value("Tải CSV MySQL").run()
        self.app.file_uploader(key="dbms_csv_upload").set_value(("custom_mysql.csv", content, "text/csv")).run()
        self.app.checkbox(key="dbms_manual_columns").set_value(True).run()
        for canonical, source in mapping.items():
            self.app.selectbox(key="dbms_mapping_" + canonical).set_value(source)
        self.app.selectbox(key="dbms_mapping_connections").set_value(mapping["queries_per_second"]).run()
        self.assert_no_exception()
        self.assertTrue(any("Mỗi cột nguồn chỉ được ánh xạ một lần" in item.value for item in self.app.error))
        self.transport.mock_post.assert_not_called()
        self.app.selectbox(key="dbms_mapping_connections").set_value(mapping["connections"]).run()
        self.assert_no_exception()
        self.assertEqual([], list(self.app.error))
        self.app.button(key="dbms_run").click().run()
        self.assert_no_exception()
        self.assertEqual([], list(self.app.error))
        self.transport.mock_post.assert_called_once()
        result = self.app.session_state["dbms_result"]
        self.assertEqual(METRICS, result.metadata["features"])
        self.assertFalse(set(source_names) & set(result.metadata["features"]))
        self.assertNotIn("label", result.metadata["features"])
        self.assertEqual(len(original), len(result.frame))
        for metric in METRICS:
            np.testing.assert_allclose(original[metric], result.frame[metric], rtol=1e-12)
        self.assertEqual(content, original.rename(columns=mapping).to_csv(index=False).encode("utf-8"))

    def test_compare_reuses_one_normal_reference_and_original_measurements(self) -> None:
        self.app.button(key="basic_compare").click().run()
        self.app.button(key="basic_start").click().run()
        self.assert_no_exception()
        self.transport.mock_post.assert_called_once()
        self.assertEqual("/compare", self.transport.requests[0].url.path)
        results = self.app.session_state["basic_result"]
        self.assertEqual({"normal", "anomalous"}, set(results))
        for role, result in results.items():
            comparison = result.metadata["comparison"]
            self.assertEqual(role, comparison["role"])
            self.assertEqual("normal", comparison["reference_source"])
            self.assertEqual(1, comparison["shared_model_fit_calls"])
            self.assertEqual(1, comparison["shared_scaler_fit_calls"])
            self.assertEqual(results["normal"].metadata["train_baselines"], result.metadata["train_baselines"])
            original = pd.read_csv(PROJECT_ROOT / "data" / f"mysql_{role}.csv")
            for metric in METRICS:
                np.testing.assert_allclose(original[metric], result.frame[metric])
        self.assertLess(int(operational_flags(results["normal"]).sum()), int(operational_flags(results["anomalous"]).sum()))
        self.assertTrue({"basic_report", "basic_csv", "basic_json"} <= {item.key for item in self.app.download_button})


if __name__ == "__main__":
    unittest.main()
