"""Verify real CSV -> HTTP -> DBMS estimators and dashboard workflows.

Synthetic labels describe injected scenarios. These tests verify that reported
results come from current predictions; they do not establish production quality.
"""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import httpx
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "app.py"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.api import app
from frontend.api_client import BackendError, detect_via_api
from http_transport import APITransport


METRICS = ["queries_per_second", "connections", "response_time_ms", "slow_queries", "connection_errors"]
MODELS = ["mad", "isolation_forest", "lof", "one_class_svm"]


def expected_matrix(truth: pd.Series, prediction: pd.Series) -> list[list[int]]:
    return [[int((truth.eq(actual) & prediction.eq(predicted)).sum())
             for predicted in (1, -1)] for actual in (1, -1)]


def expected_metrics(truth: pd.Series, prediction: pd.Series) -> dict[str, float]:
    true_positive = int((truth.eq(-1) & prediction.eq(-1)).sum())
    false_positive = int((truth.eq(1) & prediction.eq(-1)).sum())
    false_negative = int((truth.eq(-1) & prediction.eq(1)).sum())
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.
    return {"precision": precision, "recall": recall, "f1": f1}


def small_change_csv() -> bytes:
    """A one-unit change in query load has no independent incident evidence."""
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=80, freq="min"),
        "queries_per_second": [50.] * 60 + [51.] * 20,
        "connections": 50., "response_time_ms": 50.,
        "slow_queries": 0., "connection_errors": 0., "label": 1,
    })
    return frame.to_csv(index=False).encode("utf-8")


class DBMSApiWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.content = (PROJECT_ROOT / "data" / "mysql_anomalous.csv").read_bytes()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def post(self, content: bytes | None = None, **changes):
        params = {"analysis_mode": "dbms", "value_col": "queries_per_second",
                  "label_col": "label", "include_context": True,
                  "train_fraction": .7, "models": ",".join(MODELS)}
        params.update(changes)
        params = {key: value for key, value in params.items() if value is not None}
        return self.client.post("/detect", params=params,
                                files={"file": ("mysql.csv", self.content if content is None else content, "text/csv")})

    def test_all_metrics_and_observations_survive_actual_http_analysis(self) -> None:
        response = self.post()
        self.assertEqual(200, response.status_code, response.text)
        payload = response.json()
        metadata = payload["metadata"]
        original = pd.read_csv(BytesIO(self.content))
        context, predicted = pd.DataFrame(payload["context"]), pd.DataFrame(payload["predictions"])
        self.assertEqual(METRICS, metadata["metric_cols"])
        self.assertEqual(MODELS, metadata["model_names"])
        self.assertEqual("dbms", metadata["analysis_mode"])
        self.assertEqual(len(original), len(context))
        self.assertEqual(len(context) - metadata["train_rows"], len(predicted))
        for metric in METRICS:
            np.testing.assert_allclose(context[metric], original[metric], rtol=1e-12)
            np.testing.assert_allclose(predicted[metric], original[metric].iloc[metadata["train_rows"]:], rtol=1e-12)
        self.assertEqual(original["label"].iloc[metadata["train_rows"]:].tolist(), predicted["label"].tolist())

    def test_raw_and_effective_evaluations_match_current_prediction_rows(self) -> None:
        response = self.post()
        self.assertEqual(200, response.status_code, response.text)
        payload = response.json()
        metadata, predicted = payload["metadata"], pd.DataFrame(payload["predictions"])
        truth = predicted["label"]
        self.assertTrue(truth.eq(-1).any())
        for name in MODELS:
            with self.subTest(model=name):
                raw, effective = predicted[f"{name}_raw_prediction"], predicted[f"{name}_prediction"]
                self.assertEqual(expected_matrix(truth, raw), metadata["raw_confusion_matrices"][name])
                self.assertEqual(expected_matrix(truth, effective), metadata["confusion_matrices"][name])
                self.assertEqual(int(raw.eq(-1).sum()), metadata["raw_anomaly_counts"][name])
                for score, value in expected_metrics(truth, effective).items():
                    self.assertAlmostEqual(value, payload["metrics"][name][score])
                for score, value in expected_metrics(truth, raw).items():
                    self.assertAlmostEqual(value, metadata["raw_metrics"][name][score])
                expected = np.where(raw.eq(-1) & predicted["activity_deviation"], -1, 1)
                np.testing.assert_array_equal(effective, expected)

    def test_missing_metric_fails_without_returning_fabricated_results(self) -> None:
        frame = pd.read_csv(BytesIO(self.content)).drop(columns=["connection_errors"])
        response = self.post(frame.to_csv(index=False).encode("utf-8"))
        self.assertEqual(422, response.status_code)
        self.assertIn("connection_errors", response.json()["detail"])
        self.assertNotIn("predictions", response.json())
        self.assertNotIn("metrics", response.json())

    def test_dbms_api_infers_qps_display_metric_when_value_column_is_omitted(self) -> None:
        response = self.post(value_col=None)
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual("queries_per_second", response.json()["metadata"]["value_col"])

    def test_unselected_labels_never_create_quality_metrics(self) -> None:
        response = self.post(label_col=None)
        self.assertEqual(200, response.status_code, response.text)
        payload = response.json()
        self.assertEqual({}, payload["metrics"])
        self.assertEqual({}, payload["metadata"]["raw_metrics"])
        self.assertEqual({}, payload["metadata"]["confusion_matrices"])
        self.assertEqual({}, payload["metadata"]["raw_confusion_matrices"])
        self.assertIsNone(payload["metadata"]["label_col"])
        self.assertTrue(all("label" not in row for row in payload["predictions"]))

    def test_disabling_noise_guard_exposes_unmodified_model_predictions(self) -> None:
        response = self.post(noise_guard=False)
        self.assertEqual(200, response.status_code, response.text)
        payload = response.json()
        predicted, metadata = pd.DataFrame(payload["predictions"]), payload["metadata"]
        self.assertFalse(metadata["noise_guard"]["enabled"])
        for name in MODELS:
            np.testing.assert_array_equal(predicted[f"{name}_prediction"], predicted[f"{name}_raw_prediction"])
            self.assertEqual(metadata["raw_metrics"][name], payload["metrics"][name])
            self.assertEqual(metadata["raw_confusion_matrices"][name], metadata["confusion_matrices"][name])

    def test_50_to_51_is_not_automatically_an_operational_alert(self) -> None:
        response = self.post(small_change_csv(), split_index=60)
        self.assertEqual(200, response.status_code, response.text)
        payload = response.json()
        predicted = pd.DataFrame(payload["predictions"])
        self.assertFalse(predicted["activity_deviation"].any())
        self.assertGreater(payload["metadata"]["raw_anomaly_counts"]["mad"], 0)
        for name in MODELS:
            self.assertTrue(predicted[f"{name}_prediction"].eq(1).all())


class DBMSHttpClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = (PROJECT_ROOT / "data" / "mysql_anomalous.csv").read_bytes()
        self.transport = APITransport().__enter__()
        self.addCleanup(self.transport.__exit__, None, None, None)

    def detect(self, **changes):
        settings = {"analysis_mode": "dbms", "label_col": "label"}
        settings.update(changes)
        return detect_via_api(self.content, "mysql_anomalous.csv", **settings)

    def test_client_keeps_five_metrics_and_actual_test_predictions(self) -> None:
        result = self.detect()
        self.transport.mock_post.assert_called_once()
        request = self.transport.requests[0]
        self.assertEqual("dbms", request.url.params["analysis_mode"])
        self.assertEqual("true", request.url.params["include_context"])
        for metric in METRICS:
            self.assertIn(metric, result.frame)
            self.assertIn(metric, result.predictions)
        self.assertEqual(MODELS, result.metadata["model_names"])
        self.assertEqual(set(MODELS), set(result.metrics))
        self.assertEqual(result.metadata["test_rows"], len(result.predictions))

    def test_requested_guard_and_threshold_are_sent_and_verified(self) -> None:
        result = self.detect(noise_guard=False, deviation_threshold=4.5, model_names=["mad", "lof"])
        request = self.transport.requests[0]
        self.assertEqual("false", request.url.params["noise_guard"])
        self.assertEqual("4.5", request.url.params["deviation_threshold"])
        self.assertFalse(result.metadata["noise_guard"]["enabled"])
        self.assertEqual(["mad", "lof"], result.metadata["model_names"])

    def test_incomplete_or_inconsistent_backend_evidence_is_rejected(self) -> None:
        self.detect()
        original = self.transport.client.post("/detect", params={
            "analysis_mode": "dbms", "value_col": "queries_per_second",
            "label_col": "label", "include_context": True,
        }, files={"file": ("mysql.csv", self.content, "text/csv")}).json()
        cases = []
        incomplete = deepcopy(original)
        incomplete["predictions"][0].pop("response_time_ms")
        cases.append(incomplete)
        bad_matrix = deepcopy(original)
        bad_matrix["metadata"]["confusion_matrices"]["mad"][0][0] += 1
        cases.append(bad_matrix)
        bad_raw = deepcopy(original)
        bad_raw["predictions"][0]["mad_raw_prediction"] = 0
        cases.append(bad_raw)
        bad_policy = deepcopy(original)
        bad_policy["metadata"]["noise_guard"]["enabled"] = False
        cases.append(bad_policy)
        bad_raw_metrics = deepcopy(original)
        bad_raw_metrics["metadata"]["raw_metrics"]["mad"]["precision"] = .123456789
        cases.append(bad_raw_metrics)
        bad_effective_metrics = deepcopy(original)
        bad_effective_metrics["metrics"]["mad"]["f1"] = .123456789
        cases.append(bad_effective_metrics)
        for index, payload in enumerate(cases):
            with self.subTest(case=index):
                self.transport.mock_post.side_effect = None
                self.transport.mock_post.return_value = httpx.Response(
                    200, json=payload, request=httpx.Request("POST", "http://testserver/detect"))
                with self.assertRaises(BackendError):
                    self.detect()


class DBMSDashboardWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = APITransport().__enter__()
        self.addCleanup(self.transport.__exit__, None, None, None)
        self.app = AppTest.from_file(APP_PATH, default_timeout=60).run()
        self.assert_no_exception()
        self.app.radio(key="interface_mode").set_value("Nâng cao").run()
        self.assert_no_exception()

    def assert_no_exception(self) -> None:
        self.assertEqual([], [item.message for item in self.app.exception])

    def run_analysis(self, *, anomalous: bool = False) -> None:
        if anomalous:
            self.app.selectbox(key="dbms_sample").set_value("Hoạt động bất thường").run()
        self.app.selectbox(key="dbms_label").set_value("label").run()
        self.app.button(key="dbms_run").click().run()
        self.assert_no_exception()
        self.assertEqual([], list(self.app.error))

    def assert_no_prediction_export(self) -> None:
        keys = {item.key for item in self.app.download_button}
        self.assertNotIn("dbms_download_csv", keys)
        self.assertNotIn("dbms_download_json", keys)

    def test_default_dbms_workspace_previews_data_without_training(self) -> None:
        self.assertEqual("Giám sát hệ quản trị CSDL MySQL", self.app.radio(key="workspace_mode").value)
        self.assertEqual("Hoạt động bình thường", self.app.selectbox(key="dbms_sample").value)
        self.assertFalse(self.app.button(key="dbms_run").proto.disabled)
        self.assertEqual({"dbms_download_source"}, {item.key for item in self.app.download_button})
        self.assertNotIn("dbms_result", self.app.session_state)
        self.assertEqual(0, len(self.app.metric))
        self.transport.mock_post.assert_not_called()

    def test_normal_operation_reports_stable_without_inventing_recall(self) -> None:
        self.run_analysis()
        self.transport.mock_post.assert_called_once()
        result = self.app.session_state["dbms_result"]
        self.assertTrue(any("Hoạt động ổn định" in item.value for item in self.app.success))
        self.assertTrue(any("không có nhãn bất thường" in item.value for item in self.app.warning))
        for name in MODELS:
            self.assertTrue(result.predictions[f"{name}_prediction"].eq(1).all())
            self.assertEqual(0., result.metrics[name]["recall"])
            self.assertEqual(0., result.metrics[name]["f1"])
        self.assertEqual({"dbms_download_source", "dbms_download_csv", "dbms_download_json"},
                         {item.key for item in self.app.download_button})

    def test_anomalous_sample_shows_actual_values_charts_and_computed_evaluations(self) -> None:
        self.run_analysis(anomalous=True)
        result = self.app.session_state["dbms_result"]
        data = result.predictions
        self.assertTrue(any("Phát hiện dấu hiệu bất thường" in item.value for item in self.app.warning))
        displayed = next(item.value for item in self.app.dataframe if "mad_raw_prediction" in item.value.columns)
        expected = data.loc[data["mad_prediction"].eq(-1)].reset_index(drop=True)
        self.assertGreater(len(expected), 0)
        for metric in METRICS:
            np.testing.assert_allclose(displayed[metric], expected[metric])
        evidence = next(item.value for item in self.app.dataframe if "Giá trị thực tế" in item.value.columns)
        np.testing.assert_allclose(evidence["Giá trị thực tế"], expected.iloc[0][METRICS].astype(float))
        comparison = next(item.value for item in self.app.dataframe if "Cảnh báo sau lọc" in item.value.columns)
        self.assertEqual(4, len(comparison))
        for index, name in enumerate(MODELS):
            self.assertEqual(int(data[f"{name}_prediction"].eq(-1).sum()), comparison.iloc[index]["Cảnh báo sau lọc"])
            self.assertAlmostEqual(result.metrics[name]["f1"], comparison.iloc[index]["f1 sau lọc"])
            self.assertAlmostEqual(result.metadata["raw_metrics"][name]["f1"], comparison.iloc[index]["f1 gốc"])
        figures = [json.loads(chart.proto.spec) for chart in self.app.get("plotly_chart")]
        trends = [figure for figure in figures if figure["data"][0]["type"] == "scatter"]
        self.assertEqual(6, len(trends))
        self.assertEqual(4, sum(figure["data"][0]["type"] == "heatmap" for figure in figures))
        self.assertTrue(all("customdata[4]" in figure["data"][1]["hovertemplate"] for figure in trends))
        self.app.radio(key="dbms_eval_scope").set_value("Dự đoán mô hình gốc").run()
        self.assert_no_exception()
        self.transport.mock_post.assert_called_once()
        evaluated = next(item.value for item in self.app.dataframe if {"TP", "FP", "FN", "TN"} <= set(item.value.columns))
        for index, name in enumerate(MODELS):
            self.assertAlmostEqual(result.metadata["raw_metrics"][name]["f1"], evaluated.iloc[index]["f1"])

    def test_changed_configuration_hides_results_until_a_new_run(self) -> None:
        self.run_analysis(anomalous=True)
        self.app.slider(key="dbms_contamination").set_value(2.).run()
        self.assert_no_exception()
        self.assert_no_prediction_export()
        self.assertEqual(0, len(self.app.metric))
        self.assertTrue(any("Dữ liệu hoặc cấu hình đã thay đổi" in item.value for item in self.app.info))
        self.transport.mock_post.assert_called_once()
        self.app.button(key="dbms_run").click().run()
        self.assert_no_exception()
        self.assertEqual(2, self.transport.mock_post.call_count)
        self.assertEqual(.02, self.app.session_state["dbms_result"].metadata["contamination"])

    def test_failed_retry_clears_results_and_never_falls_back_to_local_fitting(self) -> None:
        self.run_analysis(anomalous=True)
        self.transport.mock_post.side_effect = httpx.ConnectError("connection refused")
        self.app.button(key="dbms_run").click().run()
        self.assert_no_exception()
        self.assertTrue(any("Không kết nối được BE" in item.value for item in self.app.error))
        self.assertNotIn("dbms_result", self.app.session_state)
        self.assertNotIn("dbms_result_signature", self.app.session_state)
        self.assert_no_prediction_export()
        self.assertEqual(0, len(self.app.metric))
        self.app.toggle(key="dark_mode").set_value(True).run()
        self.assert_no_exception()
        self.assert_no_prediction_export()
        self.assertEqual(2, self.transport.mock_post.call_count)

    def test_switching_source_hides_previous_analysis_and_does_not_collect_automatically(self) -> None:
        self.run_analysis(anomalous=True)
        self.app.radio(key="dbms_source").set_value("Tải CSV MySQL").run()
        self.assert_no_exception()
        self.assert_no_prediction_export()
        self.assertEqual(0, len(self.app.metric))
        self.assertEqual(1, len(self.app.file_uploader))
        with patch("frontend.dbms_dashboard.collect_mysql_metrics") as collector:
            self.app.radio(key="dbms_source").set_value("Kết nối MySQL").run()
            self.assert_no_exception()
            collector.assert_not_called()
        self.assert_no_prediction_export()
        self.assertEqual(0, len(self.app.metric))
        self.assertEqual(0, len(self.app.get("plotly_chart")))
        self.transport.mock_post.assert_called_once()

    def test_csv_upload_without_selected_labels_runs_without_quality_metrics(self) -> None:
        content = (PROJECT_ROOT / "data" / "mysql_anomalous.csv").read_bytes()
        self.app.radio(key="dbms_source").set_value("Tải CSV MySQL").run()
        self.app.file_uploader(key="dbms_csv_upload").set_value(("mysql.csv", content, "text/csv")).run()
        self.app.selectbox(key="dbms_label").select_index(0).run()
        self.app.button(key="dbms_run").click().run()
        self.assert_no_exception()
        self.assertEqual({}, self.app.session_state["dbms_result"].metrics)
        self.assertTrue(any("Chưa có nhãn tham chiếu" in item.value for item in self.app.info))
        self.assertTrue(any(item.key == "dbms_download_csv" for item in self.app.download_button))
        self.assertFalse(any(json.loads(chart.proto.spec)["data"][0]["type"] == "heatmap"
                             for chart in self.app.get("plotly_chart")))

    def test_missing_csv_metric_shows_actionable_error_without_analysis(self) -> None:
        content = (PROJECT_ROOT / "data" / "mysql_anomalous.csv").read_bytes()
        invalid = pd.read_csv(BytesIO(content)).drop(columns=["connections"]).to_csv(index=False).encode("utf-8")
        self.app.radio(key="dbms_source").set_value("Tải CSV MySQL").run()
        self.app.file_uploader(key="dbms_csv_upload").set_value(("invalid.csv", invalid, "text/csv")).run()
        self.assert_no_exception()
        self.assertTrue(any("connections" in item.value for item in self.app.error))
        self.assert_no_prediction_export()
        self.assertNotIn("dbms_result", self.app.session_state)
        self.transport.mock_post.assert_not_called()

    def test_explicit_live_collection_preserves_returned_measurements_through_api(self) -> None:
        collected = pd.read_csv(PROJECT_ROOT / "data" / "mysql_normal.csv").iloc[:60][["timestamp", *METRICS]].copy()
        with patch("frontend.dbms_dashboard.collect_mysql_metrics", return_value=collected) as collector:
            self.app.radio(key="dbms_source").set_value("Kết nối MySQL").run()
            self.app.text_input(key="mysql_host").set_value("mysql.example.test")
            self.app.text_input(key="mysql_password").set_value("TEST_ONLY_PASSWORD")
            collector.assert_not_called()
            self.app.button(key="mysql_collect").click().run()
            self.assert_no_exception()
            collector.assert_called_once()
            self.assertEqual("mysql.example.test", collector.call_args.kwargs["host"])
            self.assertEqual("TEST_ONLY_PASSWORD", collector.call_args.kwargs["password"])
            self.transport.mock_post.assert_not_called()
            self.app.button(key="dbms_run").click().run()
        self.assert_no_exception()
        self.assertEqual([], list(self.app.error))
        result = self.app.session_state["dbms_result"]
        self.assertEqual({}, result.metrics)
        self.assertEqual(60, len(result.frame))
        for metric in METRICS:
            np.testing.assert_allclose(collected[metric], result.frame[metric], rtol=1e-12)
        request = self.transport.requests[0]
        self.assertNotIn(b"TEST_ONLY_PASSWORD", request.content)
        self.assertNotIn(b"mysql.example.test", request.content)
        self.assertNotIn("password", request.url.params)


if __name__ == "__main__":
    unittest.main()
