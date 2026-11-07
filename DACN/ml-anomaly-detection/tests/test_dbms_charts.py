"""Check chart evidence and visibility without fitting estimators or UI mocks."""
from copy import deepcopy
import unittest

import numpy as np
import pandas as pd

from frontend.dbms_charts import build_trend_figure, MYSQL_METRICS, METRIC_UNITS
from src.contracts import DetectionRun


def sample_run() -> DetectionRun:
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-10-01", periods=8, freq="min"),
        **{metric: np.arange(8, dtype=float) + 20 + index for index, metric in enumerate(MYSQL_METRICS)},
        "label": [1, 1, 1, 1, 1, -1, 1, -1],
    })
    data = frame.iloc[4:].reset_index(drop=True).copy()
    data["mad_prediction"] = [1, -1, 1, 1]
    return DetectionRun(frame, data, {}, {
        "timestamp_col": "timestamp", "label_col": "label", "model_names": ["mad"],
        "train_baselines": {metric: {"median": 21.5 + index, "lower_bound": 18 + index,
                                     "upper_bound": 25 + index}
                            for index, metric in enumerate(MYSQL_METRICS)},
    })


class DBMSChartTests(unittest.TestCase):
    def test_default_shows_exact_holdout_and_alert_evidence(self):
        run = sample_run()
        figure = build_trend_figure(run, "mad", "queries_per_second")
        actual, alerts = figure.data[:2]
        self.assertEqual(list(run.predictions.timestamp), list(actual.x))
        np.testing.assert_array_equal(run.predictions.queries_per_second, actual.y)
        flags = run.predictions.loc[run.predictions.mad_prediction.eq(-1)]
        self.assertEqual(list(flags.timestamp), list(alerts.x))
        np.testing.assert_array_equal(flags.queries_per_second, alerts.y)
        np.testing.assert_array_equal(flags[list(MYSQL_METRICS)], alerts.customdata)
        for index in range(5):
            self.assertIn(f"customdata[{index}]", alerts.hovertemplate)
        self.assertEqual(2, len(figure.data))
        self.assertFalse(any(shape.xref == "x" for shape in figure.layout.shapes))
        self.assertEqual(0, len(figure.layout.annotations))

    def test_full_history_keeps_alerts_in_holdout_and_labels_boundary(self):
        run = sample_run()
        figure = build_trend_figure(run, "mad", "connections", full_history=True)
        self.assertEqual(list(run.frame.timestamp), list(figure.data[0].x))
        np.testing.assert_array_equal(run.frame.connections, figure.data[0].y)
        self.assertEqual([run.predictions.timestamp.iloc[1]], list(figure.data[1].x))
        boundary = run.predictions.timestamp.iloc[0].isoformat()
        split = next(shape for shape in figure.layout.shapes if shape.type == "line" and shape.xref == "x")
        self.assertEqual(boundary, split.x0)
        self.assertEqual(boundary, split.x1)
        self.assertTrue(any(note.text == "Bắt đầu kiểm tra" for note in figure.layout.annotations))

    def test_reference_band_uses_stored_training_bounds_even_with_test_extreme(self):
        run = sample_run()
        run.predictions.loc[0, "response_time_ms"] = 100000.0
        figure = build_trend_figure(run, "mad", "response_time_ms")
        band = next(shape for shape in figure.layout.shapes if shape.type == "rect")
        baseline = run.metadata["train_baselines"]["response_time_ms"]
        self.assertEqual(baseline["lower_bound"], band.y0)
        self.assertEqual(baseline["upper_bound"], band.y1)
        self.assertEqual("Vùng tham chiếu từ dữ liệu học", band.name)
        median = next(shape for shape in figure.layout.shapes if shape.type == "line")
        self.assertEqual(baseline["median"], median.y0)
        self.assertEqual(baseline["median"], median.y1)
        self.assertEqual("dot", median.line.dash)

    def test_palette_and_units_are_explicit_for_both_page_modes(self):
        for dark, ink, background, line in (
            (False, "#17233b", "#ffffff", "#2563eb"),
            (True, "#e5edf9", "#111c2e", "#38bdf8"),
        ):
            for metric in MYSQL_METRICS:
                with self.subTest(dark=dark, metric=metric):
                    figure = build_trend_figure(sample_run(), "mad", metric, dark=dark)
                    self.assertEqual(ink, figure.layout.font.color)
                    self.assertGreaterEqual(figure.layout.font.size, 13)
                    self.assertEqual(background, figure.layout.paper_bgcolor)
                    self.assertEqual(background, figure.layout.plot_bgcolor)
                    self.assertEqual(ink, figure.layout.legend.font.color)
                    for axis in (figure.layout.xaxis, figure.layout.yaxis):
                        self.assertEqual(ink, axis.tickfont.color)
                        self.assertEqual(ink, axis.title.font.color)
                    self.assertEqual(METRIC_UNITS[metric], figure.layout.yaxis.title.text)
                    self.assertEqual(line, figure.data[0].line.color)
                    self.assertEqual("#dc2626", figure.data[1].marker.color)
                    self.assertEqual(6, figure.layout.xaxis.nticks)

    def test_optional_truth_marks_preserve_labels_and_input(self):
        run = sample_run()
        original_frame, original_predictions = run.frame.copy(deep=True), run.predictions.copy(deep=True)
        original_meta = deepcopy(run.metadata)
        figure = build_trend_figure(run, "mad", "slow_queries", show_labels=True, full_history=True)
        truth = run.predictions.loc[run.predictions.label.eq(-1)]
        self.assertEqual(list(truth.timestamp), list(figure.data[2].x))
        np.testing.assert_array_equal(truth.slow_queries, figure.data[2].y)
        pd.testing.assert_frame_equal(original_frame, run.frame)
        pd.testing.assert_frame_equal(original_predictions, run.predictions)
        self.assertEqual(original_meta, run.metadata)
        run.metadata["label_col"] = None
        self.assertEqual(2, len(build_trend_figure(run, "mad", "slow_queries", show_labels=True).data))

    def test_no_alerts_and_zero_width_band_do_not_invent_measurements(self):
        run = sample_run()
        run.predictions["mad_prediction"] = 1
        run.metadata["train_baselines"]["connection_errors"] = {
            "median": 0.0, "lower_bound": 0.0, "upper_bound": 0.0,
        }
        figure = build_trend_figure(run, "mad", "connection_errors")
        self.assertEqual(0, len(figure.data[1].x))
        self.assertEqual(len(run.predictions), len(figure.data[0].x))
        self.assertTrue(any(shape.type == "rect" and shape.y0 == shape.y1 == 0 for shape in figure.layout.shapes))


if __name__ == "__main__":
    unittest.main()
