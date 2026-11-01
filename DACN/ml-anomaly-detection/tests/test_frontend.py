"""Exercise the actual Streamlit workflow without a browser or network access.

Run with ``python -m unittest discover -s tests -p test_frontend.py -v``.
The CSV fixtures are deliberately small; these checks validate the interface and
data flow, not the detection quality of the algorithms.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "app.py"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.helpers import metric_candidates


def csv_fixture(
    *, timestamp: str = "timestamp", value: str = "value", invalid_labels: bool = False
) -> bytes:
    """Provide chronological data with explicit labels in both train/test parts."""
    rows = [f"{timestamp},{value},label"]
    start = datetime(2026, 1, 1)
    for index in range(30):
        observed = start + timedelta(hours=index)
        anomaly = index in (8, 24, 28)
        measurement = 95 if anomaly else 30 + index % 5
        label = 0 if invalid_labels else (-1 if anomaly else 1)
        rows.append(f"{observed.isoformat()},{measurement},{label}")
    return ("\n".join(rows) + "\n").encode("utf-8")


class FrontendWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = AppTest.from_file(APP_PATH, default_timeout=60).run()
        self.assert_no_exception()

    def assert_no_exception(self) -> None:
        self.assertEqual([], [item.message for item in self.app.exception])

    def assert_no_export(self) -> None:
        self.assertEqual(0, len(self.app.download_button))

    def upload(self, data: bytes, filename: str = "measurements.csv") -> None:
        if not self.app.file_uploader:
            source = self.app.radio(key="data_source")
            source.set_value(source.options[1]).run()
        self.app.file_uploader(key="csv_upload").set_value((filename, data, "text/csv")).run()
        self.assert_no_exception()

    def select_label(self, name: str | None) -> None:
        control = next(item for item in self.app.selectbox if (item.key or "").startswith("label_"))
        control.set_value(name).run()
        self.assert_no_exception()

    def run_analysis(self, *, mad_only: bool = True) -> None:
        if mad_only:
            self.app.multiselect(key="selected_models").set_value(["mad"]).run()
        self.app.button(key="run_analysis").click().run()
        self.assert_no_exception()

    def test_initial_screen_has_guidance_and_no_previous_export(self) -> None:
        self.assertEqual([], list(self.app.error))
        self.assert_no_export()
        self.assertFalse(self.app.button(key="run_analysis").proto.disabled)
        self.assertTrue(any("Hướng dẫn sử dụng" in item.label for item in self.app.expander))
        self.assertTrue(any("1. Chọn dữ liệu" == item.value for item in self.app.subheader))
        self.assertTrue(any("2. Cấu hình phân tích" == item.value for item in self.app.header))

    def test_default_sample_runs_all_models_and_shows_current_results(self) -> None:
        self.run_analysis(mad_only=False)
        self.assertEqual([], list(self.app.error))
        self.assertEqual(2, len(self.app.download_button))
        self.assertEqual(["Tổng quan", "Chi tiết", "Đánh giá", "Hướng dẫn"], [tab.label for tab in self.app.tabs])
        result = self.app.session_state["detection_run"]
        self.assertEqual(4, len(result.metadata["model_names"]))
        self.assertEqual(result.metadata["test_rows"], len(result.predictions))
        self.assertEqual(len(result.frame), result.metadata["train_rows"] + result.metadata["test_rows"])
        self.assertGreater(len(result.predictions), 0)
        self.assertEqual({}, result.metrics)
        self.assertTrue(any("chưa thể tính Precision" in item.value for item in self.app.info))
        for item in self.app.warning:
            self.assertNotIn("Small dataset:", item.value)
            self.assertNotIn("No ground-truth labels", item.value)

    def test_no_algorithm_disables_analysis_and_explains_next_step(self) -> None:
        self.app.multiselect(key="selected_models").set_value([]).run()
        self.assert_no_exception()
        self.assertTrue(self.app.button(key="run_analysis").proto.disabled)
        self.assertTrue(any("chọn ít nhất một thuật toán" in item.value for item in self.app.warning))
        self.assert_no_export()

    def test_labels_are_optional_and_only_used_when_selected(self) -> None:
        self.upload(csv_fixture())
        label = next(item for item in self.app.selectbox if (item.key or "").startswith("label_"))
        self.assertIsNone(label.value)
        self.run_analysis()
        self.assertEqual({}, self.app.session_state["detection_run"].metrics)
        self.select_label("label")
        self.assert_no_export()
        self.run_analysis()
        self.assertEqual([], list(self.app.error))
        result = self.app.session_state["detection_run"]
        self.assertEqual("label", result.metadata["label_col"])
        self.assertEqual({"mad"}, set(result.metrics))
        for score in result.metrics["mad"].values():
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 1)
        self.assertEqual(2, len(self.app.download_button))

    def test_invalid_label_values_show_vietnamese_error_without_export(self) -> None:
        self.upload(csv_fixture(invalid_labels=True))
        self.select_label("label")
        self.run_analysis()
        self.assert_no_export()
        self.assertTrue(self.app.error)
        messages = " ".join(item.value for item in self.app.error)
        self.assertIn("Nhãn phải dùng 1", messages)
        self.assertNotIn("Labels must", messages)
        self.assertNotIn("Traceback", messages)

    def test_invalid_csv_is_actionable_and_cannot_run(self) -> None:
        self.upload(b"one_column\n1\n2\n")
        self.assertTrue(self.app.error)
        self.assertIn("ít nhất hai cột", self.app.error[0].value)
        self.assertTrue(self.app.button(key="run_analysis").proto.disabled)
        self.assert_no_export()

    def test_duplicate_csv_headers_are_rejected_before_running(self) -> None:
        self.upload(b"timestamp,value,value\n2026-01-01,10,20\n2026-01-02,12,22\n")
        self.assertTrue(any("Tên cột bị trùng" in item.value for item in self.app.error))
        self.assertTrue(self.app.button(key="run_analysis").proto.disabled)
        self.assert_no_export()

    def test_extra_csv_fields_are_rejected_before_running(self) -> None:
        self.upload(b"timestamp,value\n2026-01-01,10,extra\n2026-01-02,12,extra\n")
        self.assertTrue(any("Số trường trên các dòng CSV không khớp" in item.value for item in self.app.error))
        self.assertTrue(self.app.button(key="run_analysis").proto.disabled)
        self.assert_no_export()

    def test_config_change_hides_export_until_run_is_updated(self) -> None:
        self.run_analysis()
        self.assertEqual(2, len(self.app.download_button))
        self.app.slider(key="contamination").set_value(2.0).run()
        self.assert_no_exception()
        self.assert_no_export()
        self.assertTrue(any("Dữ liệu hoặc cấu hình đã thay đổi" in item.value for item in self.app.info))
        self.run_analysis()
        self.assertEqual(2, len(self.app.download_button))
        self.assertAlmostEqual(0.02, self.app.session_state["detection_run"].metadata["contamination"])

    def test_switching_to_upload_hides_previous_source_results(self) -> None:
        self.run_analysis()
        source = self.app.radio(key="data_source")
        source.set_value(source.options[1]).run()
        self.assert_no_exception()
        self.assert_no_export()
        self.assertTrue(self.app.button(key="run_analysis").proto.disabled)
        self.assertEqual(0, len(self.app.metric))

    def test_replacing_upload_resets_column_choices_and_hides_export(self) -> None:
        self.upload(csv_fixture())
        self.select_label("label")
        self.run_analysis()
        self.assertEqual(2, len(self.app.download_button))
        self.upload(csv_fixture(timestamp="observed_at", value="cpu_load"), filename="other.csv")
        self.assert_no_export()
        timestamp = next(item for item in self.app.selectbox if (item.key or "").startswith("timestamp_"))
        value = next(item for item in self.app.selectbox if (item.key or "").startswith("value_"))
        label = next(item for item in self.app.selectbox if (item.key or "").startswith("label_"))
        self.assertEqual("observed_at", timestamp.value)
        self.assertEqual("cpu_load", value.value)
        self.assertIsNone(label.value)
        self.run_analysis()
        self.assertEqual([], list(self.app.error))
        self.assertEqual("cpu_load", self.app.session_state["detection_run"].metadata["value_col"])

    def test_clearing_upload_hides_results_and_disables_analysis(self) -> None:
        self.upload(csv_fixture())
        self.run_analysis()
        self.assertEqual(2, len(self.app.download_button))
        self.app.file_uploader(key="csv_upload").clear().run()
        self.assert_no_exception()
        self.assert_no_export()
        self.assertTrue(self.app.button(key="run_analysis").proto.disabled)

    def test_details_filter_changes_only_display_and_keeps_export(self) -> None:
        self.upload(csv_fixture())
        self.run_analysis()
        result = self.app.session_state["detection_run"]
        predictions = result.predictions.copy()
        control = self.app.radio(key="detail_filter")
        control.set_value("Tất cả").run()
        self.assert_no_exception()
        self.assertTrue(any(len(item.value) == len(predictions) and "Kết luận" in item.value.columns for item in self.app.dataframe))
        self.assertEqual(2, len(self.app.download_button))
        self.assertTrue(predictions.equals(self.app.session_state["detection_run"].predictions))

    def test_dark_mode_preserves_current_analysis_and_exports(self) -> None:
        self.run_analysis()
        signature = self.app.session_state["detection_signature"]
        predictions = self.app.session_state["detection_run"].predictions.copy()
        self.app.toggle(key="dark_mode").set_value(True).run()
        self.assert_no_exception()
        self.assertEqual(2, len(self.app.download_button))
        self.assertEqual(signature, self.app.session_state["detection_signature"])
        self.assertTrue(predictions.equals(self.app.session_state["detection_run"].predictions))


class MetricCandidateTests(unittest.TestCase):
    def test_boolean_columns_and_case_insensitive_labels_are_excluded(self) -> None:
        frame = pd.DataFrame({
            "timestamp": [1, 2, 3], "cpu_load": [20, 30, 40],
            "boolean": [True, False, True],
            "nullable_boolean": pd.Series([True, None, False], dtype="boolean"),
            "IS_ANOMALY": [1, -1, 1], "Anomaly": [1, -1, 1],
            "Label": [1, -1, 1], "LABELS": [1, -1, 1],
            "TARGET": [1, -1, 1], "Ground_Truth": [1, -1, 1], "Y_TRUE": [1, -1, 1],
        })
        self.assertEqual(["cpu_load"], metric_candidates(frame, "timestamp"))

    def test_numeric_text_can_be_selected_but_text_and_infinity_cannot(self) -> None:
        frame = pd.DataFrame({
            "timestamp": [1, 2, 3], "numeric_text": ["12.5", None, "17"],
            "notes": ["start", "pause", "stop"],
            "nonfinite": [float("inf"), float("nan"), -float("inf")],
        })
        self.assertEqual(["numeric_text"], metric_candidates(frame, "timestamp"))


if __name__ == "__main__":
    unittest.main()
