"""Keep measured values intact when CSV names overlap calendar feature names."""

import unittest

import numpy as np
import pandas as pd

from src.eda import seasonality_figure, trend_figure


class EdaTests(unittest.TestCase):
    def frame(self, metric_name: str, timestamp_name: str = "timestamp") -> pd.DataFrame:
        return pd.DataFrame({
            timestamp_name: pd.to_datetime([
                "2026-01-05 08:00", "2026-01-05 08:30",
                "2026-01-06 08:00", "2026-01-06 09:00",
            ]),
            metric_name: [100., 300., 500., 900.],
        })

    def test_trend_preserves_calendar_named_measurements_and_custom_timestamps(self):
        for metric_name in ("hour", "day_of_week", "hour_sin"):
            with self.subTest(metric_name=metric_name):
                frame = self.frame(metric_name, "observed_at")
                original = frame.copy(deep=True)
                figure = trend_figure(frame, metric_name, "observed_at")
                np.testing.assert_array_equal(figure.data[0].y, [100, 300, 500, 900])
                np.testing.assert_array_equal(
                    pd.to_datetime(figure.data[0].x), frame["observed_at"],
                )
                pd.testing.assert_frame_equal(frame, original)

    def test_seasonality_aggregates_source_values_with_calendar_named_metrics(self):
        for metric_name in ("hour", "day_of_week", "hour_sin"):
            with self.subTest(metric_name=metric_name):
                frame = self.frame(metric_name, "observed_at")
                original = frame.copy(deep=True)
                figure = seasonality_figure(frame, metric_name, "observed_at")
                np.testing.assert_array_equal(figure.data[0].x, [8, 9])
                np.testing.assert_array_equal(figure.data[0].y, [300, 900])
                np.testing.assert_array_equal(figure.data[1].x, [0, 1])
                np.testing.assert_array_equal(figure.data[1].y, [200, 700])
                pd.testing.assert_frame_equal(frame, original)

    def test_timestamp_named_hour_retains_time_axis_and_correct_groups(self):
        frame = self.frame("value", "hour")
        trend = trend_figure(frame, "value", "hour")
        np.testing.assert_array_equal(pd.to_datetime(trend.data[0].x), frame["hour"])
        seasonality = seasonality_figure(frame, "value", "hour")
        np.testing.assert_array_equal(seasonality.data[0].y, [300, 900])
        np.testing.assert_array_equal(seasonality.data[1].y, [200, 700])


if __name__ == "__main__":
    unittest.main()
