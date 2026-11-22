"""Reject ambiguous inputs before fitting and keep chronological splits exact."""

import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.data_prep import load_timeseries, summarize_seasonality
from src.dbms_monitoring import MYSQL_METRICS, run_dbms_detection
from src.models import build_feature_matrix, fit_models
from src.pipeline import run_detection


def sample_frame(rows=10):
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=rows, freq="min"),
        "value": np.arange(rows, dtype=float),
    })


class ValidationRegressionTests(unittest.TestCase):
    def test_numeric_and_boolean_timestamps_are_rejected_before_fitting(self):
        cases = [np.arange(10), np.arange(10, dtype=float), [True] * 10,
                 ["2026-01-01"] * 9 + [42], ["2026-01-01"] * 9 + [np.bool_(True)]]
        for timestamps in cases:
            with self.subTest(timestamps=timestamps):
                frame = sample_frame().assign(timestamp=timestamps)
                with patch("src.pipeline.fit_models") as fitting:
                    with self.assertRaisesRegex(ValueError, "invalid timestamps"):
                        run_detection(frame, model_names="mad")
                    fitting.assert_not_called()

    def test_mixed_boolean_and_complex_metrics_are_never_cast_to_real_values(self):
        for invalid in (True, np.bool_(False), 3 + 2j, np.complex128(3 + 2j)):
            with self.subTest(invalid=invalid):
                frame = sample_frame().astype({"value": object})
                frame.loc[3, "value"] = invalid
                original = frame.copy(deep=True)
                for loader in (load_timeseries, build_feature_matrix):
                    with self.subTest(loader=loader.__name__):
                        with self.assertRaisesRegex(ValueError, "real numeric"):
                            loader(frame, value_col="value")
                pd.testing.assert_frame_equal(frame, original)

    def test_complex_labels_are_rejected_before_integer_conversion(self):
        for invalid in (-1 + 0j, np.complex128(1 + 0j)):
            with self.subTest(invalid=invalid):
                frame = sample_frame().assign(label=pd.Series([1] * 10, dtype=object))
                frame.loc[8, "label"] = invalid
                with patch("src.pipeline.fit_models") as fitting:
                    with self.assertRaisesRegex(ValueError, "Labels must be explicit"):
                        run_detection(frame, label_col="label", model_names="mad")
                    fitting.assert_not_called()

    def test_automatic_metric_selection_skips_boolean_and_complex_candidates(self):
        frame = sample_frame().rename(columns={"value": "valid_metric"})
        frame.insert(1, "mixed_boolean", pd.Series([True] + list(range(1, 10)), dtype=object))
        frame.insert(2, "complex_metric", np.arange(10) + 2j)
        loaded = load_timeseries(frame)
        self.assertEqual("valid_metric", loaded.attrs["value_col"])
        np.testing.assert_array_equal(loaded["valid_metric"], frame["valid_metric"])

    def test_calendar_option_requires_a_boolean_in_both_entry_points(self):
        frame = sample_frame()
        for invalid in ("false", "true", 0, 1, None):
            with self.subTest(include_time=invalid):
                with self.assertRaisesRegex(ValueError, "include_time must be a boolean"):
                    run_detection(frame, model_names="mad", include_time=invalid)
                with self.assertRaisesRegex(ValueError, "include_time must be a boolean"):
                    build_feature_matrix(frame, "value", include_time=invalid)
        self.assertEqual(["value"], list(build_feature_matrix(frame, "value", include_time=np.bool_(False))))
        self.assertIn("hour_sin", build_feature_matrix(frame, "value", include_time=np.bool_(True)))

    def test_invalid_model_selectors_raise_actionable_value_errors(self):
        frame = sample_frame()
        for invalid in (42, True, [["mad"]], ["mad", "mad"], [], [None]):
            with self.subTest(model_names=invalid):
                with self.assertRaisesRegex(ValueError, "algorithms"):
                    run_detection(frame, model_names=invalid)
                with self.assertRaisesRegex(ValueError, "model_names"):
                    fit_models(frame[["value"]].iloc[:7], frame[["value"]].iloc[7:], model_names=invalid)

    def test_exact_percentage_split_matches_dbms_and_preserves_test_boundary(self):
        frame = sample_frame(1440)
        single = run_detection(frame, model_names="mad", train_fraction=.7)
        mysql = frame.drop(columns="value").copy()
        for metric in MYSQL_METRICS:
            mysql[metric] = 10.0
        multivariate = run_dbms_detection(mysql, model_names="mad", train_fraction=.7)
        self.assertEqual(1008, single.metadata["train_rows"])
        self.assertEqual(432, single.metadata["test_rows"])
        self.assertEqual(single.metadata["split_index"], multivariate.metadata["split_index"])
        self.assertEqual(frame["timestamp"].iloc[1008], single.predictions["timestamp"].iloc[0])

    def test_explicit_split_and_numeric_text_metric_remain_supported(self):
        frame = sample_frame().assign(value=lambda data: data["value"].astype(str))
        original = frame.copy(deep=True)
        run = run_detection(frame, model_names="mad", split_index=6)
        self.assertEqual((6, 4), (run.metadata["train_rows"], run.metadata["test_rows"]))
        np.testing.assert_array_equal(run.frame["value"], np.arange(10, dtype=float))
        pd.testing.assert_frame_equal(frame, original)

    def test_seasonality_summary_preserves_calendar_named_measurements(self):
        timestamps = pd.to_datetime(["2026-01-05 08:00", "2026-01-05 08:30",
                                     "2026-01-06 08:00", "2026-01-06 09:00"])
        for metric in ("hour", "day_of_week", "month", "hour_sin"):
            with self.subTest(metric=metric):
                frame = pd.DataFrame({"observed_at": timestamps, metric: [100., 300., 500., 900.]},
                                     index=[4, 8, 12, 16])
                original = frame.copy(deep=True)
                summary = summarize_seasonality(frame, metric, "observed_at")
                self.assertEqual([8, 9], summary["hourly"]["hour"].tolist())
                self.assertEqual([300., 900.], summary["hourly"]["mean"].tolist())
                self.assertEqual([200., 700.], summary["weekday"]["mean"].tolist())
                self.assertEqual([450.], summary["monthly"]["mean"].tolist())
                pd.testing.assert_frame_equal(frame, original)

    def test_seasonality_summary_supports_calendar_named_timestamp(self):
        frame = pd.DataFrame({"hour": pd.date_range("2026-01-01", periods=4, freq="h"),
                              "value": [100., 300., 500., 900.]})
        summary = summarize_seasonality(frame, "value", "hour")
        self.assertEqual(frame["value"].tolist(), summary["hourly"]["mean"].tolist())


if __name__ == "__main__":
    unittest.main()
