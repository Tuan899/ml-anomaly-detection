"""Validate operational monitoring without changing original estimator behavior."""
from io import BytesIO
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from scripts.generate_mysql_demo import build_demo_frames
from src.dbms_monitoring import MYSQL_METRICS, load_mysql_metrics, run_dbms_detection
from src.models import evaluate_predictions


ROOT = Path(__file__).resolve().parents[1]


def constant_frame():
    return pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=20, freq="min"),
                         **{metric: np.full(20, 50.0) for metric in MYSQL_METRICS},
                         "label": np.ones(20, dtype=int)})


class DBMSMonitoringTests(unittest.TestCase):
    def test_small_change_is_suppressed_and_raw_predictions_retained(self):
        frame = constant_frame()
        frame.loc[14:, list(MYSQL_METRICS)] = 51.0
        result = run_dbms_detection(frame, split_index=14, model_names="mad", label_col="label")
        self.assertTrue((result.predictions["mad_raw_prediction"] == -1).all())
        self.assertTrue((result.predictions["mad_prediction"] == 1).all())
        self.assertFalse(result.predictions["activity_deviation"].any())
        self.assertEqual(result.metadata["raw_anomaly_counts"]["mad"], 6)
        self.assertEqual(result.metadata["anomaly_counts"]["mad"], 0)
        unguarded = run_dbms_detection(frame, split_index=14, model_names="mad", noise_guard=False)
        np.testing.assert_array_equal(unguarded.predictions["mad_prediction"], result.predictions["mad_raw_prediction"])
        np.testing.assert_array_equal(unguarded.predictions["mad_score"], result.predictions["mad_score"])

    def test_large_changes_have_numeric_evidence_and_all_actual_metrics(self):
        frame = constant_frame()
        frame.loc[14, "connections"] = 250
        result = run_dbms_detection(frame, split_index=14, model_names="mad")
        self.assertEqual(result.predictions.loc[0, "mad_prediction"], -1)
        self.assertIn("connections: actual=250", result.predictions.loc[0, "suspected_indicators"])
        for metric in MYSQL_METRICS:
            self.assertIn(metric, result.predictions)
        self.assertEqual(result.metadata["features"], list(MYSQL_METRICS))
        self.assertEqual(result.metrics, {})
        self.assertEqual(result.metadata["confusion_matrices"], {})

    def test_zero_error_baseline_has_an_explicit_count_scaled_score(self):
        frame = constant_frame()
        frame["connection_errors"] = 0
        frame.loc[14, "connection_errors"] = 1
        result = run_dbms_detection(frame, split_index=14, model_names="mad")
        self.assertEqual(result.predictions.loc[0, "connection_errors_deviation_score"], 3.5)
        self.assertTrue(result.predictions.loc[0, "activity_deviation"])
        self.assertEqual(result.metadata["noise_guard"]["zero_tolerance_score"]["one_event_score"], 3.5)
        self.assertIn("not robust z-scores", result.metadata["noise_guard"]["score_policy"])

    def test_training_statistics_and_preprocessing_do_not_use_test_or_labels(self):
        frame = constant_frame()
        frame["scenario"] = "must not be used as feature"
        first = run_dbms_detection(frame, split_index=14, label_col="label")
        frame.loc[14:, list(MYSQL_METRICS)] *= 1000
        frame.loc[:, "label"] = -1
        second = run_dbms_detection(frame, split_index=14, label_col="label")
        self.assertEqual(first.metadata["train_baselines"], second.metadata["train_baselines"])
        self.assertEqual(first.metadata["parameters"], second.metadata["parameters"])
        self.assertNotIn("label", second.metadata["features"])
        self.assertNotIn("scenario", second.metadata["features"])
        for name in first.metadata["model_names"]:
            self.assertEqual(first.metadata["parameters"][name]["preprocessing"]["fit_rows"], 14)

    def test_strict_metric_and_timestamp_validation(self):
        for metric in MYSQL_METRICS:
            for invalid in (np.nan, np.inf, -1, "bad", True, 1 + 2j):
                with self.subTest(metric=metric, invalid=invalid):
                    frame = constant_frame().astype({metric: object})
                    frame.loc[4, metric] = invalid
                    with self.assertRaises(ValueError):
                        load_mysql_metrics(frame)
            with self.assertRaisesRegex(ValueError, "Missing MySQL activity"):
                load_mysql_metrics(constant_frame().drop(columns=[metric]))
        for value in ("invalid-date", None):
            frame = constant_frame().astype({"timestamp": object})
            frame.loc[3, "timestamp"] = value
            with self.assertRaisesRegex(ValueError, "invalid timestamps"):
                load_mysql_metrics(frame)
        frame = constant_frame()
        frame.loc[3, "timestamp"] = frame.loc[2, "timestamp"]
        with self.assertRaisesRegex(ValueError, "Duplicate timestamps"):
            load_mysql_metrics(frame)

    def test_invalid_labels_settings_and_output_collisions(self):
        for label in (0, None, np.inf, "bad", True, -1 + 0j):
            frame = constant_frame().astype({"label": object})
            frame.loc[3, "label"] = label
            with self.assertRaisesRegex(ValueError, "Labels must"):
                run_dbms_detection(frame, split_index=14, label_col="label", model_names="mad")
        for kwargs in ({"split_index": True}, {"split_index": 2}, {"split_index": 20},
                       {"train_fraction": 1}, {"train_fraction": np.nan}, {"contamination": 0},
                       {"noise_guard": "yes"}, {"include_time": 1}, {"deviation_threshold": 0},
                       {"value_col": "label"}, {"model_names": []}, {"model_names": ["mad", "mad"]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_dbms_detection(constant_frame(), **kwargs)
        frame = constant_frame().rename(columns={"label": "mad_raw_prediction"})
        with self.assertRaisesRegex(ValueError, "conflict"):
            run_dbms_detection(frame, label_col="mad_raw_prediction", model_names="mad")

    def test_evaluations_recompute_from_exact_held_out_predictions(self):
        frame = pd.read_csv(ROOT / "data" / "mysql_anomalous.csv")
        result = run_dbms_detection(frame.iloc[::-1], label_col="label")
        truth = result.predictions["label"]
        self.assertEqual(len(result.predictions), 432)
        self.assertTrue(result.predictions["timestamp"].is_monotonic_increasing)
        for name in result.metadata["model_names"]:
            for raw in (False, True):
                col = f"{name}_{'raw_prediction' if raw else 'prediction'}"
                key = "raw_metrics" if raw else None
                metrics = result.metadata[key][name] if key else result.metrics[name]
                self.assertEqual(metrics, evaluate_predictions(truth, result.predictions[col]))
                matrix_key = "raw_confusion_matrices" if raw else "confusion_matrices"
                self.assertEqual(result.metadata[matrix_key][name], confusion_matrix(truth, result.predictions[col], labels=[1, -1]).tolist())
        json.dumps(result.summary())
        exported = pd.read_csv(BytesIO(result.export_csv()))
        self.assertEqual(len(exported), len(result.predictions))

    def test_demo_baseline_reproducibility_and_test_only_incidents(self):
        normal, anomalous, incidents = build_demo_frames()
        again, _, _ = build_demo_frames()
        pd.testing.assert_frame_equal(normal, again)
        self.assertGreater(len(normal), 1000)
        split = 1008
        pd.testing.assert_frame_equal(normal.iloc[:split], anomalous.iloc[:split])
        self.assertTrue((normal["label"] == 1).all())
        self.assertTrue((anomalous.iloc[:split]["label"] == 1).all())
        self.assertEqual({incident["scenario"] for incident in incidents},
                         {"query_spike", "connection_spike", "latency_spike", "combined_pressure"})
        manifest = json.loads((ROOT / "data" / "mysql_demo_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["recommended_split_index"], split)


if __name__ == "__main__":
    unittest.main()
