"""Check three visible practice files and CSV upload validation.

Invalid upload fixtures are constructed in memory instead of filling data/.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = PROJECT_ROOT / "data"
APP_PATH = PROJECT_ROOT / "frontend" / "research_app.py"
for directory in (PROJECT_ROOT, Path(__file__).resolve().parent):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from frontend.demo_data import ANOMALOUS_SAMPLES, NORMAL_SAMPLE
from http_transport import APITransport
from src.dbms_monitoring import MYSQL_METRICS, run_dbms_detection
from src.pipeline import run_detection


def practice_frame() -> pd.DataFrame:
    """A single-metric fixture with two held-out spikes and recovery."""
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-10-01 09:00", periods=10, freq="min"),
        "value": [50., 52., 49., 51., 48., 53., 50., 300., 350., 52.],
        "is_anomaly": [1] * 7 + [-1, -1, 1],
    })


def csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")


class DeliveredSamplePipelineTests(unittest.TestCase):
    def test_data_contains_only_three_ten_row_examples(self) -> None:
        expected = {NORMAL_SAMPLE, *ANOMALOUS_SAMPLES.values()}
        self.assertEqual(3, len(expected))
        self.assertEqual(expected, {path.name for path in SAMPLE_DIR.iterdir()})
        for filename in expected:
            with self.subTest(filename=filename):
                frame = pd.read_csv(SAMPLE_DIR / filename)
                self.assertEqual(10, len(frame))
                times = pd.to_datetime(frame["timestamp"])
                self.assertTrue(times.is_unique)
                self.assertTrue(times.is_monotonic_increasing)
                self.assertTrue(times.diff().dropna().eq(pd.Timedelta(minutes=1)).all())
                self.assertTrue(np.isfinite(frame[list(MYSQL_METRICS)]).all().all())
                self.assertTrue(frame["label"].isin([1, -1]).all())

    def test_normal_example_has_no_events_or_operational_alerts(self) -> None:
        result = run_dbms_detection(SAMPLE_DIR / NORMAL_SAMPLE, label_col="label")
        self.assertTrue(result.frame["label"].eq(1).all())
        self.assertEqual(int(len(result.frame) * .7), result.metadata["train_rows"])
        self.assertEqual(len(result.frame) - result.metadata["train_rows"], len(result.predictions))
        for name in result.metadata["model_names"]:
            self.assertTrue(result.predictions[f"{name}_prediction"].eq(1).all())
        self.assertTrue(any("Small dataset" in item for item in result.metadata["warnings"]))

    def test_anomaly_examples_share_train_and_show_two_events_then_recovery(self) -> None:
        normal = pd.read_csv(SAMPLE_DIR / NORMAL_SAMPLE)
        for filename, changed in (
            ("mysql_query_spike.csv", ["queries_per_second"]),
            ("mysql_latency_spike.csv", ["response_time_ms", "slow_queries"]),
        ):
            with self.subTest(filename=filename):
                frame = pd.read_csv(SAMPLE_DIR / filename)
                pd.testing.assert_frame_equal(normal.iloc[:7], frame.iloc[:7])
                self.assertEqual([7, 8], frame.index[frame["label"].eq(-1)].tolist())
                self.assertEqual(["09:07", "09:08"], pd.to_datetime(frame.loc[frame["label"].eq(-1), "timestamp"]).dt.strftime("%H:%M").tolist())
                pd.testing.assert_series_equal(normal.iloc[-1], frame.iloc[-1])
                unchanged = [metric for metric in MYSQL_METRICS if metric not in changed]
                pd.testing.assert_frame_equal(normal[unchanged], frame[unchanged])
                for metric in changed:
                    self.assertTrue(frame.loc[[7, 8], metric].gt(normal.loc[[7, 8], metric]).all())
                result = run_dbms_detection(frame, label_col="label", model_names=["mad"])
                truth = result.predictions["label"].eq(-1)
                flags = result.predictions["mad_prediction"].eq(-1)
                np.testing.assert_array_equal(truth, flags)
                self.assertTrue(result.frame.iloc[:result.metadata["train_rows"]]["label"].eq(1).all())


class InMemoryCSVValidationTests(unittest.TestCase):
    def test_invalid_timestamps_duplicates_and_small_split_are_rejected(self) -> None:
        invalid_time = practice_frame()
        invalid_time["timestamp"] = invalid_time["timestamp"].astype(str)
        invalid_time.loc[2, "timestamp"] = "not a date"
        duplicate_time = practice_frame()
        duplicate_time.loc[2, "timestamp"] = duplicate_time.loc[1, "timestamp"]
        for frame, message in (
            (invalid_time, "invalid timestamps"),
            (duplicate_time, "Duplicate timestamps"),
            (practice_frame().iloc[:3], "at least 3 training rows"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                run_detection(BytesIO(csv_bytes(frame)), model_names=["mad"])

    def test_bad_metric_rows_are_removed_before_splitting(self) -> None:
        frame = practice_frame()
        frame.loc[[1, 3], "value"] = np.nan
        result = run_detection(BytesIO(csv_bytes(frame)), model_names=["mad"])
        self.assertEqual(2, result.metadata["cleaning"]["dropped_rows"])
        self.assertEqual(len(frame) - 2, len(result.frame))
        self.assertEqual(int(len(result.frame) * .7), result.metadata["train_rows"])
        self.assertTrue(any("removed before" in item for item in result.metadata["warnings"]))

    def test_zero_one_labels_are_rejected_only_when_selected(self) -> None:
        frame = practice_frame()
        frame["is_anomaly"] = frame["is_anomaly"].eq(-1).astype(int)
        result = run_detection(BytesIO(csv_bytes(frame)), model_names=["mad"])
        self.assertEqual({}, result.metrics)
        self.assertEqual(len(frame), len(result.frame))
        with self.assertRaisesRegex(ValueError, "explicit -1"):
            run_detection(BytesIO(csv_bytes(frame)), label_col="is_anomaly", model_names=["mad"])


class CSVUploadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = APITransport().__enter__()
        self.addCleanup(self.transport.__exit__, None, None, None)
        self.app = AppTest.from_file(APP_PATH, default_timeout=60)
        self.app.session_state["interface_mode"] = "Cơ bản"
        self.app.run()
        self.assert_no_exception()
        self.app.radio(key="interface_mode").set_value("Nâng cao").run()
        self.app.radio(key="workspace_mode").set_value("CSV một chỉ số / notebook NAB").run()
        self.assert_no_exception()

    def assert_no_exception(self) -> None:
        self.assertEqual([], [item.message for item in self.app.exception])

    def upload(self, frame: pd.DataFrame) -> None:
        source = self.app.radio(key="data_source")
        source.set_value(source.options[1]).run()
        self.app.file_uploader(key="csv_upload").set_value(("practice.csv", csv_bytes(frame), "text/csv")).run()
        self.app.multiselect(key="selected_models").set_value(["mad"]).run()
        self.app.slider(key="train_fraction").set_value(70).run()
        self.app.slider(key="contamination").set_value(1.0).run()
        self.app.checkbox(key="include_time").set_value(False).run()
        self.assert_no_exception()

    def select_label(self) -> None:
        control = next(item for item in self.app.selectbox if (item.key or "").startswith("label_"))
        control.set_value("is_anomaly").run()
        self.assert_no_exception()

    def run_analysis(self) -> None:
        self.assertFalse(self.app.button(key="run_analysis").proto.disabled)
        self.app.button(key="run_analysis").click().run()
        self.assert_no_exception()

    def test_labeled_upload_reports_current_predictions_and_exports(self) -> None:
        original = practice_frame()
        self.upload(original)
        self.select_label()
        self.run_analysis()
        self.transport.mock_post.assert_called_once()
        self.assertEqual("is_anomaly", self.transport.requests[0].url.params["label_col"])
        self.assertEqual("/detect", self.transport.requests[0].url.path)
        self.assertEqual([], list(self.app.error))
        result = self.app.session_state["detection_run"]
        self.assertEqual(int(len(original) * .7), result.metadata["train_rows"])
        self.assertEqual(len(original) - result.metadata["train_rows"], result.metadata["test_rows"])
        truth = result.predictions["is_anomaly"].eq(-1)
        flagged = result.predictions["mad_prediction"].eq(-1)
        np.testing.assert_array_equal(truth, flagged)
        confusion = next(item.value for item in self.app.dataframe if "Cảnh báo đúng" in item.value.columns)
        self.assertEqual([int((truth & flagged).sum())], confusion["Cảnh báo đúng"].tolist())
        self.assertEqual([int((~truth & flagged).sum())], confusion["Cảnh báo nhầm"].tolist())
        self.assertEqual([int((truth & ~flagged).sum())], confusion["Bỏ sót"].tolist())
        self.assertEqual(2, len(self.app.download_button))

    def test_bad_value_upload_explains_cleaning_and_runs(self) -> None:
        frame = practice_frame()
        frame.loc[[1, 3], "value"] = np.nan
        self.upload(frame)
        self.assertEqual([], list(self.app.error))
        self.assertTrue(any("Có 2 dòng" in item.value for item in self.app.warning))
        self.assertTrue(any("5 dòng đầu huấn luyện, 3 dòng cuối kiểm tra" in item.value for item in self.app.caption))
        self.run_analysis()
        result = self.app.session_state["detection_run"]
        self.assertEqual(2, result.metadata["cleaning"]["dropped_rows"])
        self.assertEqual(len(frame) - 2, len(result.frame))
        self.assertTrue(any("Đã loại dòng" in item.value for item in self.app.warning))
        self.assertEqual(2, len(self.app.download_button))

    def test_invalid_label_upload_explains_opt_in_error_and_removes_exports(self) -> None:
        frame = practice_frame()
        frame["is_anomaly"] = frame["is_anomaly"].eq(-1).astype(int)
        self.upload(frame)
        self.run_analysis()
        self.assertEqual([], list(self.app.error))
        self.assertEqual({}, self.app.session_state["detection_run"].metrics)
        self.assertEqual(2, len(self.app.download_button))
        self.select_label()
        self.assertEqual(0, len(self.app.download_button))
        self.run_analysis()
        self.assertTrue(any("Nhãn phải dùng 1" in item.value for item in self.app.error))
        self.assertEqual(0, len(self.app.download_button))


if __name__ == "__main__":
    unittest.main()
