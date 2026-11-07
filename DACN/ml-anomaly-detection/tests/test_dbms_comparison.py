"""Shared-reference comparison: one fit, honest held-outs and HTTP failures."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from sklearn.metrics import confusion_matrix

from backend.api import MAX_UPLOAD_BYTES, app
from frontend.api_client import BackendError, compare_via_api
from src.dbms_comparison import compare_dbms_datasets
from src.dbms_monitoring import MYSQL_METRICS, run_dbms_detection
from src.models import evaluate_predictions, fit_models


ROOT = Path(__file__).resolve().parents[1]


def observations(rows=40, start="2026-01-01", anomalous=False):
    trend = np.sin(np.arange(rows) * .45)
    frame = pd.DataFrame({"timestamp": pd.date_range(start, periods=rows, freq="min"),
                          **{metric: 50 + trend for metric in MYSQL_METRICS},
                          "label": np.ones(rows, dtype=int), "scenario": "normal"})
    if anomalous:
        frame.loc[rows - 3:, ["queries_per_second", "connections", "response_time_ms"]] *= 8
        frame.loc[rows - 3:, "label"] = -1
        frame.loc[rows - 3:, "scenario"] = "test spike"
    return frame


def csv_bytes(frame):
    return frame.to_csv(index=False).encode("utf-8")


class DBMSComparisonTests(unittest.TestCase):
    def test_one_fit_uses_only_normal_prefix_and_concatenates_features(self):
        normal, anomalous = observations(), observations(50, anomalous=True)
        # A different reference prefix must not affect training in any way.
        anomalous.loc[:34, list(MYSQL_METRICS)] = 9000
        original_normal, original_anomalous = normal.copy(deep=True), anomalous.copy(deep=True)
        with patch("src.dbms_comparison.fit_models", wraps=fit_models) as fit:
            runs = compare_dbms_datasets(normal, anomalous, label_col="label")
        fit.assert_called_once()
        train, test = fit.call_args.args
        pd.testing.assert_frame_equal(train, normal.iloc[:28][list(MYSQL_METRICS)])
        expected_test = pd.concat([normal.iloc[28:][list(MYSQL_METRICS)], anomalous.iloc[35:][list(MYSQL_METRICS)]], ignore_index=True)
        pd.testing.assert_frame_equal(test, expected_test)
        self.assertNotIn("label", train)
        self.assertNotIn("timestamp", train)
        self.assertEqual(runs["normal"].metadata["parameters"], runs["anomalous"].metadata["parameters"])
        self.assertEqual(runs["normal"].metadata["train_baselines"], runs["anomalous"].metadata["train_baselines"])
        for run in runs.values():
            self.assertEqual(run.metadata["comparison"]["reference_train_rows"], 28)
            self.assertEqual(run.metadata["comparison"]["prediction_batch_rows"], 27)
            for parameters in run.metadata["parameters"].values():
                self.assertEqual(parameters["preprocessing"]["fit_rows"], 28)
                np.testing.assert_allclose(parameters["preprocessing"]["mean"], train.mean())
        self.assertEqual(runs["anomalous"].metadata["train_rows"], 35)
        self.assertEqual(runs["anomalous"].metadata["test_rows"], 15)
        pd.testing.assert_frame_equal(normal, original_normal)
        pd.testing.assert_frame_equal(anomalous, original_anomalous)

    def test_matches_single_normal_run_and_preserves_original_held_outs(self):
        normal = observations()
        anomalous = observations(50, "2026-02-01", anomalous=True)
        baseline = run_dbms_detection(normal, label_col="label", include_time=True)
        runs = compare_dbms_datasets(normal.iloc[::-1], anomalous.iloc[::-1], label_col="label", include_time=True)
        for name in baseline.metadata["model_names"]:
            for suffix in ("raw_prediction", "prediction", "score"):
                np.testing.assert_allclose(baseline.predictions[f"{name}_{suffix}"], runs["normal"].predictions[f"{name}_{suffix}"])
        for role, original in (("normal", normal), ("anomalous", anomalous)):
            run = runs[role]
            columns = ["timestamp", *MYSQL_METRICS, "label", "scenario"]
            pd.testing.assert_frame_equal(run.predictions[columns], original.iloc[run.metadata["train_rows"]:][columns].reset_index(drop=True))
            self.assertNotIn("label", run.metadata["features"])
            self.assertIn("hour_sin", run.metadata["features"])

    def test_changing_held_outs_or_labels_cannot_change_training(self):
        normal, anomalous = observations(), observations(anomalous=True)
        first = compare_dbms_datasets(normal, anomalous, label_col="label")
        normal.loc[28:, list(MYSQL_METRICS)] *= 100
        anomalous.loc[:, list(MYSQL_METRICS)] *= 500
        normal["label"] = anomalous["label"] = -1
        second = compare_dbms_datasets(normal, anomalous, label_col="label")
        for role in first:
            self.assertEqual(first[role].metadata["parameters"], second[role].metadata["parameters"])
            self.assertEqual(first[role].metadata["train_baselines"], second[role].metadata["train_baselines"])
            self.assertTrue(any(warning.startswith("Training labels contain anomalies") for warning in second[role].metadata["warnings"]))

    def test_raw_and_guarded_metrics_and_counts_rederive_exactly(self):
        for guard in (True, False):
            runs = compare_dbms_datasets(observations(), observations(anomalous=True), label_col="label", noise_guard=guard)
            for run in runs.values():
                for name in run.metadata["model_names"]:
                    for raw in (True, False):
                        predictions = run.predictions[f"{name}_{'raw_prediction' if raw else 'prediction'}"]
                        metrics = run.metadata["raw_metrics"][name] if raw else run.metrics[name]
                        matrix_key = "raw_confusion_matrices" if raw else "confusion_matrices"
                        count_key = "raw_anomaly_counts" if raw else "anomaly_counts"
                        self.assertEqual(metrics, evaluate_predictions(run.predictions.label, predictions))
                        self.assertEqual(run.metadata[matrix_key][name], confusion_matrix(run.predictions.label, predictions, labels=[1, -1]).tolist())
                        self.assertEqual(run.metadata[count_key][name], int(predictions.eq(-1).sum()))

    def test_unlabeled_does_not_infer_scenario_labels(self):
        runs = compare_dbms_datasets(observations(), observations(anomalous=True), model_names="mad")
        for run in runs.values():
            self.assertEqual(run.metrics, {})
            self.assertEqual(run.metadata["raw_metrics"], {})
            self.assertEqual(run.metadata["confusion_matrices"], {})
            self.assertNotIn("label", run.predictions)
            self.assertNotIn("scenario", run.metadata["features"])

    def test_strict_validation_in_either_source_happens_before_fitting(self):
        for role in (0, 1):
            for invalid in ("missing", "negative", "duplicate time", "invalid label"):
                pair = [observations(), observations()]
                if invalid == "missing":
                    pair[role] = pair[role].drop(columns=["connection_errors"])
                elif invalid == "negative":
                    pair[role].loc[0, "response_time_ms"] = -1
                elif invalid == "duplicate time":
                    pair[role].loc[1, "timestamp"] = pair[role].loc[0, "timestamp"]
                else:
                    pair[role].loc[0, "label"] = 0
                with self.subTest(role=role, invalid=invalid), patch("src.dbms_comparison.fit_models") as fit:
                    with self.assertRaises(ValueError):
                        compare_dbms_datasets(*pair, label_col="label")
                    fit.assert_not_called()
        for kwargs in ({"split_index": True}, {"split_index": 40}, {"train_fraction": 1},
                       {"contamination": 0}, {"model_names": ["mad", "mad"]},
                       {"value_col": "label"}, {"noise_guard": "yes"},
                       {"include_time": 1}, {"deviation_threshold": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                compare_dbms_datasets(observations(), observations(), **kwargs)

    def test_bundled_demo_uses_1008_reference_and_two_432_heldouts(self):
        runs = compare_dbms_datasets(ROOT / "data/mysql_normal.csv", ROOT / "data/mysql_anomalous.csv", label_col="label")
        for run in runs.values():
            self.assertEqual(run.metadata["train_rows"], 1008)
            self.assertEqual(run.metadata["test_rows"], 432)
            self.assertEqual(run.metadata["comparison"]["reference_train_rows"], 1008)
            self.assertEqual(run.metadata["comparison"]["prediction_batch_rows"], 864)


class ComparisonHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = TestClient(app)
        cls.normal = csv_bytes(observations())
        cls.anomalous = csv_bytes(observations(50, anomalous=True))
        cls.params = {"models": "mad,lof", "label_col": "label"}
        cls.files = {"normal_file": ("normal.csv", cls.normal, "text/csv"),
                     "anomalous_file": ("anomalous.csv", cls.anomalous, "text/csv")}
        cls.payload = cls.api.post("/compare", params=cls.params, files=cls.files).json()

    @classmethod
    def tearDownClass(cls):
        cls.api.close()

    def forward(self, url, **kwargs):
        kwargs.pop("trust_env")
        kwargs.pop("timeout")
        return self.api.post(url, **kwargs)

    def call_client(self):
        return compare_via_api(self.normal, self.anomalous, model_names=["mad", "lof"], label_col="label")

    def test_client_round_trip_uses_real_compare_endpoint(self):
        with patch("frontend.api_client.httpx.post", side_effect=self.forward) as post:
            runs = self.call_client()
        post.assert_called_once()
        self.assertTrue(post.call_args.args[0].endswith("/compare"))
        self.assertTrue(post.call_args.kwargs["params"]["include_context"])
        self.assertFalse(post.call_args.kwargs["trust_env"])
        self.assertEqual(set(post.call_args.kwargs["files"]), {"normal_file", "anomalous_file"})
        self.assertEqual(len(runs["normal"].predictions), 12)
        self.assertEqual(len(runs["anomalous"].predictions), 15)
        self.assertEqual(runs["normal"].metadata["parameters"], runs["anomalous"].metadata["parameters"])
        self.assertEqual(len(pd.read_csv(BytesIO(runs["anomalous"].export_csv()))), 15)

    def test_api_uses_threadpool_once_and_context_can_be_omitted(self):
        async def execute(function, *args, **kwargs):
            return function(*args, **kwargs)

        with patch("backend.api.run_in_threadpool", side_effect=execute) as worker:
            response = self.api.post("/compare", params={**self.params, "include_context": False}, files=self.files)
        self.assertEqual(response.status_code, 200)
        worker.assert_called_once()
        self.assertNotIn("context", response.json()["normal"])

    def test_both_uploads_are_size_limited_empty_and_invalid_are_rejected(self):
        for key in self.files:
            for content, status in ((b"", 422), (b"x" * (MAX_UPLOAD_BYTES + 1), 413), (b"timestamp,queries_per_second\n2026-01-01,1\n", 422)):
                files = {**self.files, key: ("bad.csv", content, "text/csv")}
                with self.subTest(key=key, size=len(content)):
                    response = self.api.post("/compare", params=self.params, files=files)
                    self.assertEqual(response.status_code, status)
        for params in ({"models": "bad"}, {"models": "mad,mad"}, {"train_fraction": 1}, {"contamination": 0}, {"split_index": 100}):
            with self.subTest(params=params):
                self.assertEqual(self.api.post("/compare", params=params, files=self.files).status_code, 422)

    def test_client_rejects_bad_size_before_upload(self):
        with patch("frontend.api_client.httpx.post") as post:
            for normal, anomalous in ((b"", self.anomalous), (self.normal, b""), (b"x" * (MAX_UPLOAD_BYTES + 1), self.anomalous), (self.normal, b"x" * (MAX_UPLOAD_BYTES + 1))):
                with self.assertRaises(BackendError):
                    compare_via_api(normal, anomalous)
            post.assert_not_called()

    def test_http_failure_messages_are_actionable_and_sanitized(self):
        for status in (400, 413, 422, 500, 404):
            with self.subTest(status=status), patch("frontend.api_client.httpx.post", return_value=httpx.Response(status, json={"detail": "secret traceback"})):
                with self.assertRaises(BackendError) as caught:
                    self.call_client()
                self.assertNotIn("secret", str(caught.exception))
                self.assertNotIn("traceback", str(caught.exception))
        for error in (httpx.ConnectError("secret"), httpx.ReadTimeout("secret")):
            with patch("frontend.api_client.httpx.post", side_effect=error):
                with self.assertRaises(BackendError) as caught:
                    self.call_client()
                self.assertNotIn("secret", str(caught.exception))

    def test_client_rejects_mismatched_shared_reference_or_tampered_evaluation(self):
        for path, value in (
            (("anomalous", "metadata", "comparison", "reference_source"), "anomalous"),
            (("anomalous", "metadata", "comparison", "shared_model_fit_calls"), 2),
            (("anomalous", "metadata", "comparison", "shared_scaler_fit_calls"), True),
            (("anomalous", "metadata", "comparison", "reference_train_rows"), 35),
            (("anomalous", "metadata", "parameters", "mad", "preprocessing", "fit_rows"), 35),
            (("anomalous", "metadata", "train_baselines", "connections", "median"), 9000),
            (("anomalous", "metadata", "confusion_matrices", "mad"), [[15, 0], [0, 0]]),
            (("anomalous", "metrics", "mad", "precision"), .123),
            (("normal", "predictions", 0, "timestamp"), "2000-01-01"),
        ):
            payload = deepcopy(self.payload)
            target = payload
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), patch("frontend.api_client.httpx.post", return_value=httpx.Response(200, json=payload)):
                with self.assertRaisesRegex(BackendError, "không đúng định dạng"):
                    self.call_client()
        with patch("frontend.api_client.httpx.post", return_value=httpx.Response(200, text="<html>wrong service</html>")):
            with self.assertRaisesRegex(BackendError, "không đúng định dạng"):
                self.call_client()


if __name__ == "__main__":
    unittest.main()
