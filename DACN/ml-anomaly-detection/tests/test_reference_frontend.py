"""Verify the notebook workflow through the real frontend/API boundary.

The two evaluation scopes deliberately have different sizes and positive-label
counts. These checks ensure that the interface preserves that distinction and
does not substitute local results when the backend is unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import httpx
import pandas as pd
from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "app.py"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from http_transport import APITransport


class NotebookReferenceFrontendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = APITransport().__enter__()
        self.addCleanup(self.transport.__exit__, None, None, None)
        self.app = AppTest.from_file(APP_PATH, default_timeout=60).run()
        self.assert_no_exception()
        self.app.radio(key="interface_mode").set_value("Nâng cao").run()
        self.assert_no_exception()
        self.app.radio(key="workspace_mode").set_value("CSV một chỉ số / notebook NAB").run()
        self.assert_no_exception()

    def assert_no_exception(self) -> None:
        self.assertEqual([], [item.message for item in self.app.exception])

    def run_analysis(self) -> None:
        self.assertFalse(self.app.button(key="run_analysis").proto.disabled)
        self.app.button(key="run_analysis").click().run()
        self.assert_no_exception()

    def test_default_opens_complete_nab_profile_without_starting_training(self) -> None:
        self.assertEqual("NAB CPU đầy đủ · 4.032 điểm", self.app.selectbox(key="sample_dataset").value)
        self.assertTrue(self.app.checkbox(key="use_reference").value)
        self.assertFalse(self.app.button(key="run_analysis").proto.disabled)
        self.assertEqual([], list(self.app.error))
        self.assertEqual(0, len(self.app.download_button))
        self.assertNotIn("detection_run", self.app.session_state)
        self.transport.mock_post.assert_not_called()

    def test_reference_configuration_and_complete_source_reach_the_backend(self) -> None:
        self.run_analysis()
        self.transport.mock_post.assert_called_once()
        request = self.transport.requests[0]
        self.assertEqual("/detect", request.url.path)
        self.assertEqual("notebook_reference", request.url.params["analysis_mode"])
        self.assertEqual("mad,isolation_forest,lof", request.url.params["models"])
        self.assertEqual("is_anomaly", request.url.params["label_col"])
        self.assertEqual("false", request.url.params["include_time"])
        self.assertEqual("true", request.url.params["include_context"])
        self.assertAlmostEqual(1 / 3550, float(request.url.params["contamination"]))
        self.assertIn((PROJECT_ROOT / "data" / "nab_cpu_labeled.csv").read_bytes(), request.content)

        result = self.app.session_state["detection_run"]
        self.assertEqual(4032, len(result.frame))
        self.assertEqual(3550, result.metadata["train_rows"])
        self.assertEqual(482, result.metadata["test_rows"])
        self.assertEqual(482, len(result.predictions))
        self.assertEqual(["mad", "isolation_forest", "lof"], result.metadata["model_names"])
        self.assertEqual(["value"], result.metadata["features"])
        self.assertEqual(2, int(result.frame["is_anomaly"].eq(-1).sum()))
        self.assertEqual(1, int(result.predictions["is_anomaly"].eq(-1).sum()))
        self.assertEqual("2014-02-27 17:15:00", str(result.predictions.loc[result.predictions["is_anomaly"].eq(-1), "timestamp"].iloc[0]))
        self.assertEqual([], list(self.app.error))
        self.assertEqual(3, len(self.app.download_button))
        self.assertEqual("Tải CSV MAD toàn chuỗi (4.032 điểm)", self.app.download_button(key="download_full_mad").label)

    def test_full_series_mad_and_test_evaluations_keep_their_own_counts(self) -> None:
        self.run_analysis()
        result = self.app.session_state["detection_run"]
        baseline = result.metadata["reference_baseline"]
        self.assertEqual("full_series_descriptive", baseline["scope"])
        self.assertEqual(4032, baseline["fit_rows"])
        self.assertEqual(4032, baseline["rows"])
        self.assertAlmostEqual(.134, baseline["median"])
        self.assertAlmostEqual(.002, baseline["mad"])
        self.assertEqual([[2964, 1066], [0, 2]], baseline["confusion_matrix"])
        full_predictions = pd.DataFrame(baseline["predictions"])
        self.assertEqual(4032, len(full_predictions))
        self.assertEqual(1068, int(full_predictions["mad_prediction"].eq(-1).sum()))
        self.assertEqual(2, int(full_predictions["is_anomaly"].eq(-1).sum()))

        # Unlike a copied screenshot, these figures come back from the actual
        # backend run and must agree with the current displayed test table.
        self.assertEqual({
            "mad": [[357, 124], [0, 1]],
            "isolation_forest": [[481, 0], [1, 0]],
            "lof": [[481, 0], [0, 1]],
        }, result.metadata["confusion_matrices"])
        confusion = next(item.value for item in self.app.dataframe if "Cảnh báo đúng" in item.value.columns and len(item.value) == 3)
        self.assertEqual([1, 0, 1], confusion["Cảnh báo đúng"].tolist())
        self.assertEqual([124, 0, 0], confusion["Cảnh báo nhầm"].tolist())
        self.assertEqual([0, 1, 0], confusion["Bỏ sót"].tolist())
        self.assertEqual(1.0, result.metrics["lof"]["f1"])
        self.assertEqual(0.0, result.metrics["isolation_forest"]["f1"])
        self.assertIn("Theo notebook", [tab.label for tab in self.app.tabs])
        known_labels = next(item.value for item in self.app.dataframe if "Thời điểm bất thường (UTC)" in item.value.columns)
        self.assertEqual(["Huấn luyện IF/LOF", "Kiểm tra IF/LOF"], known_labels["Phạm vi"].tolist())
        self.assertTrue(any("MAD dùng cả 4.032 điểm" in item.value for item in self.app.info))
        self.assertTrue(any("Không so sánh F1 MAD toàn chuỗi" in item.value for item in self.app.caption))
        heatmaps = {}
        for chart in self.app.get("plotly_chart"):
            figure = json.loads(chart.proto.spec)
            if figure["data"][0]["type"] == "heatmap":
                heatmaps[figure["layout"]["title"]["text"]] = figure["data"][0]["z"]
        self.assertEqual({
            "MAD · toàn chuỗi 4.032 điểm": [[2964, 1066], [0, 2]],
            "mad · 482 điểm": [[357, 124], [0, 1]],
            "isolation_forest · 482 điểm": [[481, 0], [1, 0]],
            "lof · 482 điểm": [[481, 0], [0, 1]],
        }, heatmaps)

    def test_disabling_reference_invalidates_exports_and_unlocks_configuration(self) -> None:
        self.run_analysis()
        self.assertEqual(3, len(self.app.download_button))
        self.app.checkbox(key="use_reference").set_value(False).run()
        self.assert_no_exception()
        self.assertEqual(0, len(self.app.download_button))
        self.assertFalse(self.app.multiselect(key="selected_models").proto.disabled)
        self.assertFalse(self.app.slider(key="train_fraction").proto.disabled)
        self.assertFalse(self.app.slider(key="contamination").proto.disabled)
        self.transport.mock_post.assert_called_once()

    def test_restoring_reference_resets_invalid_generic_column_selection(self) -> None:
        self.app.checkbox(key="use_reference").set_value(False).run()
        time_column = next(item for item in self.app.selectbox if item.label == "Cột thời gian")
        time_column.set_value("is_anomaly").run()
        self.assert_no_exception()
        self.assertTrue(self.app.button(key="run_analysis").proto.disabled)
        self.transport.mock_post.assert_not_called()

        self.app.checkbox(key="use_reference").set_value(True).run()
        self.assert_no_exception()
        for label, expected in (
            ("Cột thời gian", "timestamp"),
            ("Cột giá trị", "value"),
            ("Nhãn tham chiếu (tùy chọn)", "is_anomaly"),
        ):
            control = next(item for item in self.app.selectbox if item.label == label)
            self.assertEqual(expected, control.value)
            self.assertTrue(control.proto.disabled)
        self.assertEqual([], list(self.app.error))
        self.run_analysis()
        self.transport.mock_post.assert_called_once()
        self.assertEqual("timestamp", self.transport.requests[0].url.params["timestamp_col"])
        self.assertEqual("value", self.transport.requests[0].url.params["value_col"])
        self.assertEqual("is_anomaly", self.transport.requests[0].url.params["label_col"])
        self.assertEqual(482, len(self.app.session_state["detection_run"].predictions))

    def test_failed_reference_retry_clears_old_results_and_never_uses_local_detection(self) -> None:
        self.run_analysis()
        self.assertEqual(3, len(self.app.download_button))
        self.transport.mock_post.side_effect = httpx.ConnectError("connection refused")
        self.run_analysis()
        self.assertEqual(2, self.transport.mock_post.call_count)
        self.assertTrue(any("Không kết nối được BE" in item.value for item in self.app.error))
        self.assertEqual(0, len(self.app.download_button))
        self.assertNotIn("detection_run", self.app.session_state)
        self.assertNotIn("detection_signature", self.app.session_state)
        self.assertEqual(0, len(self.app.metric))
        self.app.toggle(key="dark_mode").set_value(True).run()
        self.assert_no_exception()
        self.assertEqual(0, len(self.app.download_button))
        self.assertEqual(2, self.transport.mock_post.call_count)


if __name__ == "__main__":
    unittest.main()
