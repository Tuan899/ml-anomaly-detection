"""Stored decisions stay separate from filtered alerts and unrelated sessions."""
from copy import deepcopy
import unittest

from frontend.algorithm_status import (build_algorithm_details, build_algorithm_table,
                                       scoped_samples)
from frontend.live_charts import MODELS


def point(sample_id=1, **changes):
    record = {
        "id": sample_id, "baseline_id": 7, "source": "mysql-prod", "session_id": "collector-a",
        "predictions": {name: 1 for name in MODELS},
        "raw_predictions": {name: 1 for name in MODELS},
        "scores": dict(zip(MODELS, (3.123456789123, 0.123456789, 0.4321098765, 1.234567891))),
    }
    record.update(changes)
    return record


class AlgorithmStatusTests(unittest.TestCase):
    def test_raw_flags_suppressed_by_filter_are_not_reported_as_guarded_flags(self):
        latest = point()
        latest["raw_predictions"]["mad"] = -1
        latest["raw_predictions"]["lof"] = -1
        latest["predictions"]["lof"] = -1
        table = build_algorithm_table(latest, [latest]).set_index("Thuật toán")
        self.assertEqual((4, 2), table.shape)
        self.assertEqual("Đã lọc dao động", table.loc["MAD", "Mẫu mới nhất"])
        self.assertEqual("0 / 1", table.loc["MAD", "Gắn cờ / N mẫu"])
        self.assertEqual("Gắn cờ", table.loc["LOF", "Mẫu mới nhất"])
        self.assertEqual("1 / 1", table.loc["LOF", "Gắn cờ / N mẫu"])
        raw = build_algorithm_details(latest).set_index("Thuật toán")
        self.assertEqual("Gắn cờ", raw.loc["MAD", "Dự đoán gốc"])

    def test_counts_use_only_the_same_baseline_source_and_session(self):
        latest = point(6)
        earlier = point(5)
        earlier["predictions"]["mad"] = -1
        other_scope = [point(1, baseline_id=6), point(2, source="replay"),
                       point(3, session_id="collector-b"), point(4, session_id=None)]
        for unrelated in other_scope:
            unrelated["predictions"] = {name: -1 for name in MODELS}
        samples = [*other_scope, earlier, latest]
        self.assertEqual([earlier, latest], scoped_samples(latest, samples))
        table = build_algorithm_table(latest, samples).set_index("Thuật toán")
        self.assertEqual("1 / 2", table.loc["MAD", "Gắn cờ / N mẫu"])
        self.assertEqual("0 / 2", table.loc["LOF", "Gắn cờ / N mẫu"])

    def test_original_score_precision_and_records_are_preserved(self):
        latest = point()
        original = deepcopy(latest)
        details = build_algorithm_details(latest)
        self.assertEqual(list(MODELS.values()), details["Thuật toán"].tolist())
        self.assertEqual(list(latest["scores"].values()), details["Điểm gốc"].tolist())
        build_algorithm_table(latest, [latest])
        self.assertEqual(original, latest)

    def test_missing_and_invalid_predictions_are_explicit_in_status_and_counts(self):
        latest = point(predictions={"mad": True, "lof": None}, raw_predictions={}, scores={})
        table = build_algorithm_table(latest, [latest])
        self.assertEqual(4, len(table))
        self.assertEqual({"Chưa có kết quả"}, set(table["Mẫu mới nhất"]))
        self.assertTrue(all("thiếu 1 kết quả" in value for value in table["Gắn cờ / N mẫu"]))
        details = build_algorithm_details(latest)
        self.assertEqual({"Chưa có kết quả"}, set(details["Dự đoán gốc"]))
        self.assertTrue(all(value is None for value in details["Điểm gốc"]))
        latest["scores"] = dict(zip(MODELS, (True, float("nan"), float("inf"), "0.5")))
        self.assertTrue(all(value is None for value in build_algorithm_details(latest)["Điểm gốc"]))

    def test_no_latest_or_unknown_scope_cannot_appear_as_four_normal_results(self):
        table = build_algorithm_table(None, [point()])
        self.assertEqual(4, len(table))
        self.assertEqual({"Chưa có kết quả"}, set(table["Mẫu mới nhất"]))
        self.assertEqual({"Chưa có mẫu"}, set(table["Gắn cờ / N mẫu"]))
        self.assertEqual([], scoped_samples({"source": "mysql-prod"}, [point()]))

    def test_stale_view_identifies_results_as_stored_without_a_healthy_claim(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string('''
import streamlit as st
from frontend.algorithm_status import render_algorithm_status
from frontend.live_charts import MODELS
latest = {"id": 2, "baseline_id": 1, "source": "mysql", "session_id": "a",
          "predictions": {name: 1 for name in MODELS},
          "raw_predictions": {name: 1 for name in MODELS},
          "scores": {name: 0.123456789 for name in MODELS}}
def show_table(frame, dark, **options):
    st.dataframe(frame, hide_index=True, **options)
render_algorithm_status(latest, [latest], fresh=False, dark=False, show_table=show_table)
''').run()
        self.assertEqual([], [item.message for item in app.exception])
        self.assertEqual([4, 4], [len(item.value) for item in app.dataframe])
        self.assertTrue(any("đã lưu" in item.value for item in app.markdown))
        self.assertTrue(any("chưa xác nhận" in item.value for item in app.caption))
        self.assertEqual(0, len(app.success))


if __name__ == "__main__":
    unittest.main()
