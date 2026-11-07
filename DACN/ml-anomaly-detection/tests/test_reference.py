"""Verify notebook reproduction against independent raw-value estimators."""

from io import BytesIO
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from scipy.stats import median_abs_deviation
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix
from sklearn.neighbors import LocalOutlierFactor

from backend.api import app
from src.models import evaluate_predictions
from src.notebook_reference import REFERENCE_DATA, REFERENCE_MODELS, run_notebook_reference


class NotebookReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = REFERENCE_DATA.read_bytes()
        cls.frame = pd.read_csv(BytesIO(cls.content))
        cls.reference_run = run_notebook_reference(BytesIO(cls.content))

    def test_raw_estimators_match_notebook_predictions_and_scores(self):
        values = self.frame["value"].to_numpy().reshape(-1, 1)
        estimators = {
            "isolation_forest": IsolationForest(contamination=1 / 3550, random_state=42),
            "lof": LocalOutlierFactor(contamination=1 / 3550, novelty=True),
        }
        for name, model in estimators.items():
            with self.subTest(model=name):
                model.fit(values[:3550])
                np.testing.assert_array_equal(self.reference_run.predictions[f"{name}_prediction"], model.predict(values[3550:]))
                np.testing.assert_array_equal(self.reference_run.predictions[f"{name}_score"], model.decision_function(values[3550:]))

    def test_full_series_mad_matches_notebook_and_keeps_distinct_scope(self):
        values = self.frame["value"].to_numpy()
        median, mad = np.median(values), median_abs_deviation(values)
        z_score = .6745 * (values - median) / mad
        expected = np.where(np.abs(z_score) >= 3.5, -1, 1)
        baseline = self.reference_run.metadata["reference_baseline"]
        self.assertEqual(baseline["scope"], "full_series_descriptive")
        self.assertEqual(baseline["rows"], 4032)
        self.assertEqual(baseline["fit_rows"], 4032)
        self.assertEqual(baseline["median"], .134)
        self.assertEqual(baseline["mad"], mad)
        records = pd.DataFrame(baseline["predictions"])
        np.testing.assert_array_equal(records["mad_prediction"], expected)
        np.testing.assert_allclose(records["z_score"], z_score, atol=1e-14)
        np.testing.assert_array_equal(self.reference_run.predictions["mad_prediction"], expected[3550:])
        self.assertEqual(baseline["metrics"], evaluate_predictions(self.reference_run.frame["is_anomaly"], expected))
        self.assertEqual(baseline["confusion_matrix"], confusion_matrix(self.reference_run.frame["is_anomaly"], expected, labels=[1, -1]).tolist())

    def test_main_metrics_and_matrices_cover_identical_test_rows(self):
        run = self.reference_run
        self.assertEqual((len(run.frame), len(run.predictions)), (4032, 482))
        self.assertEqual(run.metadata["train_rows"], 3550)
        self.assertEqual(run.predictions["timestamp"].iloc[0], pd.Timestamp("2014-02-26 22:20:00"))
        self.assertEqual(int(run.frame["is_anomaly"].iloc[:3550].eq(-1).sum()), 1)
        self.assertEqual(int(run.predictions["is_anomaly"].eq(-1).sum()), 1)
        self.assertEqual(run.frame.index[run.frame["is_anomaly"].eq(-1)].tolist(), [3547, 3777])
        for name in REFERENCE_MODELS:
            self.assertEqual(run.metrics[name], evaluate_predictions(run.predictions["is_anomaly"], run.predictions[f"{name}_prediction"]))
            matrix = run.metadata["confusion_matrices"][name]
            self.assertEqual(matrix, confusion_matrix(run.predictions["is_anomaly"], run.predictions[f"{name}_prediction"], labels=[1, -1]).tolist())
            self.assertEqual(np.asarray(matrix).sum(), 482)

    def test_fixed_profile_uses_no_scaler_calendar_features_or_svm(self):
        with patch("src.models.StandardScaler", side_effect=AssertionError("must use raw values")), patch("src.models.OneClassSVM", side_effect=AssertionError("not in notebook")):
            run = run_notebook_reference(BytesIO(self.content))
        self.assertEqual(run.metadata["model_names"], ["mad", "isolation_forest", "lof"])
        self.assertEqual(run.metadata["features"], ["value"])
        self.assertEqual(run.metadata["contamination"], 1 / 3550)
        self.assertTrue(all(params["preprocessing"]["name"] == "none" for params in run.metadata["parameters"].values()))
        self.assertTrue(any("including test" in message for message in run.metadata["warnings"]))

    def test_invalid_or_modified_series_are_rejected(self):
        cases = []
        cases.append(self.frame.iloc[:-1])
        cases.append(self.frame.iloc[::-1])
        changed_value = self.frame.copy()
        changed_value.loc[30, "value"] += .001
        cases.append(changed_value)
        invalid_value = self.frame.copy()
        invalid_value.loc[30, "value"] = np.nan
        cases.append(invalid_value)
        invalid_time = self.frame.copy()
        invalid_time.loc[30, "timestamp"] = "2014-02-14 14:31:00"
        cases.append(invalid_time)
        for frame in cases:
            with self.subTest(rows=len(frame)), self.assertRaisesRegex(ValueError, "Notebook reference"):
                run_notebook_reference(frame)

    def test_labels_are_derived_and_csv_round_trip_with_custom_columns_is_supported(self):
        frame = self.frame.rename(columns={"timestamp": "observed_at", "value": "cpu"})
        frame["is_anomaly"] = 0  # Invalid supplied labels are not trusted.
        run = run_notebook_reference(BytesIO(frame.to_csv(index=False).encode()), timestamp_col="observed_at", value_col="cpu")
        self.assertEqual(run.metadata["timestamp_col"], "observed_at")
        self.assertEqual(run.metadata["value_col"], "cpu")
        self.assertEqual(run.metadata["label_col"], "is_anomaly")
        self.assertEqual(int(run.frame["is_anomaly"].eq(-1).sum()), 2)
        self.assertEqual(run.metadata["reference_baseline"]["predictions"][0]["observed_at"], "2014-02-14T14:30:00.000000000")
        np.testing.assert_array_equal(run.predictions["lof_prediction"], self.reference_run.predictions["lof_prediction"])

    def test_float_round_trip_tolerance_keeps_canonical_neighbor_ties(self):
        frame = self.frame.copy()
        frame["value"] = np.nextafter(frame["value"].to_numpy(), np.inf)
        run = run_notebook_reference(frame)
        np.testing.assert_array_equal(run.frame["value"], self.reference_run.frame["value"])
        for name in REFERENCE_MODELS:
            np.testing.assert_array_equal(run.predictions[f"{name}_prediction"], self.reference_run.predictions[f"{name}_prediction"])

    def test_api_preserves_test_contract_and_exposes_separate_full_mad_baseline(self):
        with TestClient(app) as client:
            response = client.post(
                "/detect", params={"analysis_mode": "notebook_reference", "include_context": True,
                                   "train_fraction": .7, "contamination": .01,
                                   "models": "one_class_svm", "label_col": "ignored", "include_time": True},
                files={"file": ("nab.csv", self.content, "text/csv")},
            )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["metadata"]["analysis_mode"], "notebook_reference")
        self.assertEqual(payload["metadata"]["model_names"], list(REFERENCE_MODELS))
        self.assertEqual(payload["metadata"]["label_col"], "is_anomaly")
        self.assertEqual(len(payload["context"]), 4032)
        self.assertEqual(len(payload["predictions"]), 482)
        self.assertEqual(len(payload["metadata"]["reference_baseline"]["predictions"]), 4032)
        self.assertEqual(payload["models"], payload["anomalies"])
        self.assertEqual(payload["metrics"], self.reference_run.metrics)
        self.assertEqual(payload["predictions"][0]["timestamp"], payload["context"][3550]["timestamp"])

    def test_api_rejects_unknown_mode_and_unrelated_data(self):
        with TestClient(app) as client:
            for mode, content in (("unknown", self.content), ("notebook_reference", b"timestamp,value\n2026-01-01,1\n")):
                with self.subTest(mode=mode):
                    response = client.post("/detect", params={"analysis_mode": mode},
                                           files={"file": ("data.csv", content, "text/csv")})
                    self.assertEqual(response.status_code, 422, response.text)


if __name__ == "__main__":
    unittest.main()
