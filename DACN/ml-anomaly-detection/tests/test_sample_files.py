"""Verify the delivered CSV practice files and their documented UI workflows.

Run with ``python -m unittest discover -s tests -p test_sample_files.py -v``.
These synthetic files demonstrate validation and known anomalies; they do not
establish performance on real measurements.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = PROJECT_ROOT / "data" / "kiem_thu"
APP_PATH = PROJECT_ROOT / "frontend" / "app.py"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_prep import read_csv_frame
from src.pipeline import run_detection


def load_contract() -> dict:
    return json.loads((SAMPLE_DIR / "ket_qua_mong_doi.json").read_text(encoding="utf-8"))


def sample_run(filename: str, *, use_labels: bool = True):
    settings = load_contract()["settings"].copy()
    settings["label_col"] = "is_anomaly" if use_labels else None
    return run_detection(SAMPLE_DIR / filename, **settings)


class DeliveredSamplePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_contract()
        cls.expected = {item["file"]: item for item in cls.contract["files"]}

    def test_delivered_files_have_the_documented_input_counts(self) -> None:
        self.assertEqual(9, len(self.expected))
        self.assertEqual(
            set(self.expected), {path.name for path in SAMPLE_DIR.glob("*.csv")}
        )
        for filename, expected in self.expected.items():
            with self.subTest(filename=filename):
                with (SAMPLE_DIR / filename).open(encoding="utf-8-sig", newline="") as source:
                    rows = list(csv.reader(source))
                self.assertEqual(expected["input_rows"], len(rows) - 1)

    def test_normal_sample_has_no_mad_alerts(self) -> None:
        expected = self.expected["01_binh_thuong.csv"]
        result = sample_run(expected["file"])
        self.assertEqual(expected["clean_rows"], len(result.frame))
        self.assertEqual(expected["train_rows"], result.metadata["train_rows"])
        self.assertEqual(expected["test_rows"], result.metadata["test_rows"])
        self.assertEqual(expected["mad_alerts"], result.predictions["mad_prediction"].eq(-1).sum())
        self.assertTrue(result.frame["is_anomaly"].eq(1).all())
        self.assertTrue(any("no anomalies" in item for item in result.metadata["warnings"]))

    def test_labeled_sample_detects_exactly_the_documented_spikes(self) -> None:
        expected = self.expected["02_bat_thuong_co_nhan.csv"]
        raw = read_csv_frame(SAMPLE_DIR / expected["file"])
        known = self.contract["known_anomalies"]
        known_positions = [item["csv_line"] - 2 for item in known]
        self.assertEqual([151, 172, 185], known_positions)
        self.assertEqual(known_positions, raw.index[raw["is_anomaly"].eq(-1)].tolist())
        for item in known:
            with self.subTest(timestamp=item["timestamp"]):
                position = item["csv_line"] - 2
                self.assertEqual(position + 1, item["observation"])
                self.assertEqual(pd.Timestamp(item["timestamp"]), pd.Timestamp(raw.iloc[position]["timestamp"]))
                self.assertEqual(item["value"], raw.iloc[position]["value"])

        result = sample_run(expected["file"])
        self.assertEqual(expected["clean_rows"], len(result.frame))
        self.assertEqual(expected["train_rows"], result.metadata["train_rows"])
        self.assertEqual(expected["test_rows"], result.metadata["test_rows"])
        self.assertTrue(result.frame.iloc[:expected["train_rows"]]["is_anomaly"].eq(1).all())
        truth = result.predictions["is_anomaly"].eq(-1)
        flagged = result.predictions["mad_prediction"].eq(-1)
        self.assertEqual(expected["true_test_anomalies"], int(truth.sum()))
        self.assertEqual(expected["mad_alerts"], int(flagged.sum()))
        self.assertEqual(expected["mad_true_positives"], int((truth & flagged).sum()))
        self.assertEqual(expected["mad_false_positives"], int((~truth & flagged).sum()))
        self.assertEqual(expected["mad_false_negatives"], int((truth & ~flagged).sum()))
        self.assertEqual({"precision": 1.0, "recall": 1.0, "f1": 1.0}, result.metrics["mad"])

    def test_invalid_time_structure_and_split_samples_are_rejected(self) -> None:
        for expected in self.expected.values():
            if expected["outcome"] != "reject":
                continue
            with self.subTest(filename=expected["file"]):
                with self.assertRaises(ValueError) as caught:
                    sample_run(expected["file"], use_labels=False)
                self.assertIn(expected["error_contains"], str(caught.exception))

    def test_bad_metric_values_are_counted_and_removed_before_splitting(self) -> None:
        expected = self.expected["05_gia_tri_loi.csv"]
        result = sample_run(expected["file"], use_labels=False)
        self.assertEqual(expected["clean_rows"], len(result.frame))
        self.assertEqual(expected["input_rows"], result.metadata["cleaning"]["input_rows"])
        self.assertEqual(expected["dropped_rows"], result.metadata["cleaning"]["dropped_rows"])
        self.assertEqual(expected["train_rows"], result.metadata["train_rows"])
        self.assertEqual(expected["test_rows"], result.metadata["test_rows"])
        self.assertTrue(any("removed before" in item for item in result.metadata["warnings"]))

    def test_zero_one_labels_are_rejected_only_if_selected(self) -> None:
        expected = self.expected["06_nhan_sai.csv"]
        without_labels = sample_run(expected["file"], use_labels=False)
        self.assertEqual({}, without_labels.metrics)
        self.assertEqual(expected["input_rows"], len(without_labels.frame))
        with self.assertRaises(ValueError) as caught:
            sample_run(expected["file"])
        self.assertIn(expected["error_contains"], str(caught.exception))


class DeliveredSampleUploadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = AppTest.from_file(APP_PATH, default_timeout=60).run()
        self.assert_no_exception()

    def assert_no_exception(self) -> None:
        self.assertEqual([], [item.message for item in self.app.exception])

    def upload(self, filename: str) -> None:
        source = self.app.radio(key="data_source")
        source.set_value(source.options[1]).run()
        self.app.file_uploader(key="csv_upload").set_value(
            (filename, (SAMPLE_DIR / filename).read_bytes(), "text/csv")
        ).run()
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

    def test_labeled_spike_upload_shows_three_correct_alerts_and_exports(self) -> None:
        self.upload("02_bat_thuong_co_nhan.csv")
        self.select_label()
        self.run_analysis()
        self.assertEqual([], list(self.app.error))
        result = self.app.session_state["detection_run"]
        self.assertEqual(140, result.metadata["train_rows"])
        self.assertEqual(60, result.metadata["test_rows"])
        self.assertEqual(3, int(result.predictions["mad_prediction"].eq(-1).sum()))
        confusion = next(item.value for item in self.app.dataframe if "Cảnh báo đúng" in item.value.columns)
        self.assertEqual([3], confusion["Cảnh báo đúng"].tolist())
        self.assertEqual([0], confusion["Cảnh báo nhầm"].tolist())
        self.assertEqual([0], confusion["Bỏ sót"].tolist())
        self.assertEqual(2, len(self.app.download_button))

    def test_bad_value_upload_warns_about_six_removed_rows_then_runs(self) -> None:
        self.upload("05_gia_tri_loi.csv")
        self.assertEqual([], list(self.app.error))
        self.assertTrue(any("Có 6 dòng" in item.value for item in self.app.warning))
        self.assertTrue(any("9 dòng đầu huấn luyện, 5 dòng cuối kiểm tra" in item.value for item in self.app.caption))
        self.run_analysis()
        result = self.app.session_state["detection_run"]
        self.assertEqual(6, result.metadata["cleaning"]["dropped_rows"])
        self.assertEqual(14, len(result.frame))
        self.assertEqual(9, result.metadata["train_rows"])
        self.assertEqual(5, result.metadata["test_rows"])
        self.assertTrue(any("Đã loại dòng" in item.value for item in self.app.warning))
        self.assertEqual(2, len(self.app.download_button))

    def test_zero_one_label_upload_runs_without_label_but_explains_opt_in_error(self) -> None:
        self.upload("06_nhan_sai.csv")
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
