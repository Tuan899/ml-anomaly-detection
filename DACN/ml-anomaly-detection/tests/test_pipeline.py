"""Regression checks for chronological evaluation and user-supplied CSV data."""

from io import BytesIO
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from src.anomaly_detection import run_nab_analysis
from src.data_prep import load_timeseries, read_csv_frame
from src.models import build_feature_matrix, evaluate_predictions
from src.pipeline import run_detection


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=12, freq="h"),
        "value": [1, 2, 3, 2, 1, 3, 100, 2, 1, 3, 2, 100],
        "label": [1, 1, 1, 1, 1, 1, -1, 1, 1, 1, 1, -1],
    })


class PipelineTests(unittest.TestCase):
    def test_training_statistics_do_not_depend_on_held_out_values(self):
        frame = sample_frame()
        first = run_detection(frame, split_index=6, model_names="mad")
        frame.loc[6:, "value"] *= 1000
        second = run_detection(frame, split_index=6, model_names="mad")
        self.assertEqual(first.metadata["parameters"], second.metadata["parameters"])
        self.assertEqual(first.metadata["parameters"]["mad"]["preprocessing"]["fit_rows"], 6)
        self.assertEqual(first.predictions["mad_prediction"].iloc[0], -1)
        self.assertEqual(first.metadata["train_rows"], 6)
        self.assertEqual(len(first.predictions), 6)

    def test_sorting_and_metrics_use_only_held_out_labels(self):
        frame = sample_frame().iloc[::-1]
        result = run_detection(frame, split_index=6, label_col="label", model_names=["mad"])
        self.assertEqual(result.predictions["timestamp"].iloc[0], pd.Timestamp("2026-01-01 06:00"))
        expected = evaluate_predictions(result.predictions["label"], result.predictions["mad_prediction"])
        self.assertEqual(result.metrics["mad"], expected)
        unlabeled = run_detection(frame, split_index=6, model_names=["mad"])
        self.assertEqual(unlabeled.metrics, {})

    def test_output_names_cannot_overwrite_ground_truth_or_metric(self):
        for column in ("mad_prediction", "mad_score"):
            with self.subTest(column=column):
                frame = sample_frame().rename(columns={"label": column})
                with self.assertRaisesRegex(ValueError, "conflict"):
                    run_detection(frame, split_index=6, label_col=column, model_names="mad")
                frame = sample_frame().rename(columns={"value": column})
                with self.assertRaisesRegex(ValueError, "conflict"):
                    run_detection(frame, split_index=6, value_col=column, model_names="mad")

    def test_calendar_features_preserve_selected_source_metric(self):
        frame = sample_frame().rename(columns={"value": "hour_sin"})
        features = build_feature_matrix(frame, "hour_sin", include_time=True)
        np.testing.assert_array_equal(features["hour_sin"], frame["hour_sin"])
        self.assertIn("dow_cos", features)

    def test_metric_cleaning_is_counted_before_splitting(self):
        frame = sample_frame().astype({"value": object})
        frame.loc[1, "value"] = "not a number"
        frame.loc[2, "value"] = np.inf
        result = run_detection(frame, split_index=6, model_names="mad")
        self.assertEqual(result.metadata["cleaning"]["dropped_rows"], 2)
        self.assertEqual(result.metadata["test_rows"], 4)
        self.assertTrue(any("removed" in warning for warning in result.metadata["warnings"]))

    def test_invalid_labels_are_rejected(self):
        for invalid in (0, np.nan, "unknown", True):
            with self.subTest(invalid=invalid):
                frame = sample_frame().astype({"label": object})
                frame.loc[9, "label"] = invalid
                with self.assertRaisesRegex(ValueError, "Labels must"):
                    run_detection(frame, split_index=6, label_col="label", model_names="mad")

    def test_invalid_split_and_numeric_settings_are_rejected(self):
        for kwargs in ({"split_index": 2}, {"split_index": True}, {"split_index": 6.5},
                       {"contamination": True}, {"contamination": 0}, {"contamination": float("nan")},
                       {"train_fraction": "0.7"}, {"train_fraction": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_detection(sample_frame(), model_names="mad", **kwargs)

    def test_bad_timestamps_and_duplicate_timestamps_are_rejected(self):
        frame = sample_frame()
        frame.loc[1, "timestamp"] = frame.loc[0, "timestamp"]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_timeseries(frame)
        with self.assertRaisesRegex(ValueError, "invalid timestamps"):
            load_timeseries(BytesIO(b"timestamp,value\nnot-a-date,1\n"))

    def test_ambiguous_csv_headers_and_extra_fields_are_rejected(self):
        for reader in (read_csv_frame, load_timeseries):
            with self.subTest(reader=reader.__name__):
                with self.assertRaisesRegex(ValueError, "Column names must be unique"):
                    reader(BytesIO(b"timestamp,value,value\n2026-01-01,1,2\n"))
                with self.assertRaisesRegex(ValueError, "fields do not match"):
                    reader(BytesIO(b"timestamp,value\n2026-01-01,1,2\n2026-01-02,2,3\n"))

    def test_raw_parser_preserves_unselected_columns_and_input_order(self):
        content = b"timestamp,metric,label\n2026-01-02,bad,unknown\n2026-01-01,3,-1\n"
        frame = read_csv_frame(BytesIO(content))
        self.assertEqual(list(frame.columns), ["timestamp", "metric", "label"])
        self.assertEqual(frame["timestamp"].tolist(), ["2026-01-02", "2026-01-01"])
        self.assertEqual(frame["metric"].tolist(), ["bad", "3"])
        self.assertEqual(frame["label"].tolist(), ["unknown", "-1"])
        copied = read_csv_frame(frame)
        copied.loc[0, "metric"] = "changed"
        self.assertEqual(frame.loc[0, "metric"], "bad")

    def test_export_has_test_rows_and_utf8_bom(self):
        result = run_detection(sample_frame(), split_index=6, model_names="mad")
        exported = pd.read_csv(BytesIO(result.export_csv()))
        self.assertTrue(result.export_csv().startswith(b"\xef\xbb\xbf"))
        self.assertEqual(len(exported), result.metadata["test_rows"])
        summary = result.summary()
        self.assertEqual(len(summary["predictions"]), 6)
        self.assertTrue(all(row["mad_prediction"] == -1 for row in summary["anomalies"]["mad"]))

    def test_bundled_cli_sample_runs_with_automatic_split(self):
        source = Path(__file__).parents[1] / "data" / "cpu_0.csv"
        frame, metrics = run_nab_analysis(source)
        self.assertGreater(len(frame), 3)
        self.assertEqual(set(metrics), {"mad", "isolation_forest", "lof", "one_class_svm"})
        with self.assertRaises(ValueError):
            run_nab_analysis(source, contamination=0)


if __name__ == "__main__":
    unittest.main()
