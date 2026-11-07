"""Validate user-facing conclusions against explicit measured evidence."""
from copy import deepcopy
import unittest

import numpy as np
import pandas as pd

from frontend.monitoring_charts import build_comparison_figure, build_count_figure, build_score_figure
from frontend.reporting import build_report_markdown
from src.contracts import DetectionRun
from src.monitoring_summary import alert_mask, evaluation_table, summarize_run


def run_fixture(rows=20, models=("mad",)):
    reference = {"queries_per_second": 50.0, "connections": 20.0,
                 "response_time_ms": 10.0, "slow_queries": 2.0, "connection_errors": 0.0}
    tolerances = dict(zip(reference, (5.0, 3.0, 5.0, 2.0, 0.0)))
    frame = pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=5 + rows, freq="min"),
                          **{metric: [value] * (5 + rows) for metric, value in reference.items()}})
    data = frame.iloc[5:].reset_index(drop=True).copy()
    for model in models:
        data[f"{model}_prediction"] = 1
        data[f"{model}_raw_prediction"] = 1
        data[f"{model}_score"] = 3.0
    metadata = {"model_names": list(models), "timestamp_col": "timestamp", "label_col": None,
                "train_rows": 5, "test_rows": rows,
                "train_baselines": {metric: {"median": value, "allowed_deviation": tolerances[metric]}
                                    for metric, value in reference.items()},
                "noise_guard": {"enabled": True, "deviation_threshold": 3.5}, "timings": {}}
    return DetectionRun(frame, data, {}, metadata)


def flag(run, positions=(0,), model="mad", value=56.0):
    run.predictions.loc[list(positions), "queries_per_second"] = value
    run.predictions.loc[list(positions), f"{model}_prediction"] = -1
    run.predictions.loc[list(positions), f"{model}_raw_prediction"] = -1
    run.predictions.loc[list(positions), f"{model}_score"] = -12.0


class MonitoringSummaryTests(unittest.TestCase):
    def test_stable_count_does_not_label_small_changes_as_alerts(self):
        run = run_fixture()
        run.predictions["queries_per_second"] = 51.0
        summary = summarize_run(run)
        self.assertEqual("Bình thường", summary["status"])
        self.assertEqual("normal", summary["status_level"])
        self.assertEqual(0, summary["alert_count"])
        self.assertEqual(0.0, summary["alert_rate"])
        self.assertEqual(20, summary["rows_analyzed"])
        self.assertEqual(25, summary["total_rows"])
        self.assertTrue(summary["notable"].empty)
        self.assertIn("không bảo đảm", summary["explanation"])

    def test_raw_and_operational_alerts_are_separate_and_union_not_double_counted(self):
        run = run_fixture(models=("mad", "lof"))
        flag(run, positions=(0,))
        flag(run, positions=(0, 1), model="lof")
        run.predictions.loc[2, "mad_raw_prediction"] = -1
        summary = summarize_run(run)
        self.assertEqual(2, summary["alert_count"])
        self.assertEqual(3, summary["raw_count"])
        self.assertEqual(1, summary["model_counts"]["mad"]["alerts"])
        self.assertEqual(2, summary["model_counts"]["lof"]["alerts"])
        self.assertEqual([True, True, False], alert_mask(run).iloc[:3].tolist())
        self.assertEqual([True, True, True], alert_mask(run, raw=True).iloc[:3].tolist())

    def test_one_mild_alert_is_attention_with_exact_evidence(self):
        run = run_fixture()
        flag(run)
        summary = summarize_run(run)
        self.assertEqual("attention", summary["status_level"])
        self.assertEqual("Cần chú ý", summary["notable"].iloc[0]["Mức cảnh báo"])
        self.assertEqual(56.0, summary["notable"].iloc[0]["Giá trị quan sát"])
        self.assertEqual(50.0, summary["notable"].iloc[0]["Giá trị tham chiếu"])
        self.assertEqual(12.0, summary["notable"].iloc[0]["Điểm bất thường"])
        self.assertEqual(5, len(summary["evidence"]))
        evidence = summary["evidence"].query("metric == 'queries_per_second'").iloc[0]
        self.assertEqual(6.0, evidence["delta"])
        self.assertEqual(5.0, evidence["allowed_deviation"])
        self.assertIn("truy vấn", " ".join(summary["next_checks"]))
        self.assertIn("chưa xác nhận", summary["notable"].iloc[0]["Giải thích ngắn"])

    def test_severe_point_rules_require_an_actual_model_alert(self):
        # Changing measurements alone cannot create a model alert or high status.
        unflagged = run_fixture()
        unflagged.predictions.loc[0, ["queries_per_second", "connections", "connection_errors"]] = [900, 900, 99]
        self.assertEqual("normal", summarize_run(unflagged)["status_level"])
        cases = [({"queries_per_second": 61.0}, "large deviation"),
                 ({"queries_per_second": 56.0, "connections": 24.0}, "two changed metrics"),
                 ({"connection_errors": 1.0}, "connection errors above zero reference")]
        for changes, reason in cases:
            with self.subTest(reason=reason):
                run = run_fixture()
                flag(run)
                for metric, value in changes.items():
                    run.predictions.loc[0, metric] = value
                summary = summarize_run(run)
                self.assertEqual("high", summary["status_level"])
                self.assertEqual(1, summary["high_point_count"])
                self.assertEqual("Cảnh báo cao", summary["notable"].iloc[0]["Mức cảnh báo"])

    def test_rate_rule_is_explicit_overall_policy_not_point_severity(self):
        run = run_fixture()
        flag(run, positions=(0, 1))
        summary = summarize_run(run)
        self.assertEqual(0.1, summary["alert_rate"])
        self.assertEqual("high", summary["status_level"])
        self.assertEqual(0, summary["high_point_count"])
        self.assertTrue(summary["notable"]["Mức cảnh báo"].eq("Cần chú ý").all())
        self.assertIn("10%", summary["severity_rule"])
        self.assertIn("không phải giới hạn MySQL", summary["severity_rule"])

    def test_model_score_is_from_a_detecting_model_not_average_or_largest_other_score(self):
        run = run_fixture(models=("lof", "mad"))
        flag(run, model="lof")
        flag(run, model="mad")
        run.predictions.loc[0, "lof_score"] = -8000
        row = summarize_run(run)["notable"].iloc[0]
        self.assertEqual("MAD", row["Thuật toán (điểm)"])
        self.assertEqual(12.0, row["Điểm bất thường"])
        run.predictions.loc[0, "mad_prediction"] = 1
        row = summarize_run(run)["notable"].iloc[0]
        self.assertEqual("LOF", row["Thuật toán (điểm)"])
        self.assertEqual(8000, row["Điểm bất thường"])

    def test_intervals_group_consecutive_observations_without_filling_gaps(self):
        run = run_fixture()
        flag(run, positions=(0, 1, 4))
        intervals = summarize_run(run)["intervals"]
        self.assertEqual([2, 1], [part["count"] for part in intervals])
        self.assertEqual(run.predictions.timestamp.iloc[0], intervals[0]["start"])
        self.assertEqual(run.predictions.timestamp.iloc[1], intervals[0]["end"])
        self.assertEqual(run.predictions.timestamp.iloc[4], intervals[1]["start"])

    def test_no_label_leakage_or_source_mutation_by_summary(self):
        run = run_fixture()
        flag(run)
        original = run.predictions.copy(deep=True)
        metadata = deepcopy(run.metadata)
        before = summarize_run(run)
        run.predictions["label"] = -1
        run.metadata["label_col"] = "label"
        after = summarize_run(run)
        self.assertEqual(before["status"], after["status"])
        self.assertEqual(before["explanation"], after["explanation"])
        pd.testing.assert_frame_equal(before["notable"], after["notable"])
        pd.testing.assert_frame_equal(original, run.predictions.drop(columns="label"))
        del run.metadata["label_col"]
        del metadata["label_col"]
        self.assertEqual(metadata, run.metadata)

    def test_invalid_or_absent_labels_do_not_make_metrics(self):
        run = run_fixture()
        self.assertTrue(evaluation_table(run).empty)
        run.metadata["label_col"] = "label"
        for value in (True, "normal", 0, np.nan):
            with self.subTest(value=value):
                run.predictions["label"] = value
                self.assertTrue(evaluation_table(run).empty)

    def test_actual_evaluation_includes_accuracy_and_confusion_counts(self):
        run = run_fixture(rows=4)
        run.metadata["label_col"] = "label"
        run.predictions["label"] = [-1, 1, -1, 1]
        run.predictions["mad_prediction"] = [-1, -1, 1, 1]
        run.predictions["mad_raw_prediction"] = [-1, 1, -1, 1]
        # Deliberately stale backend values must not become user-facing metrics.
        run.metrics = {"mad": {"precision": 0.99, "recall": 0.99}}
        metric = evaluation_table(run).iloc[0]
        for key in ("Precision", "Recall", "F1-score", "Accuracy"):
            self.assertEqual(.5, metric[key])
        for key in ("TN", "FP", "FN", "TP"):
            self.assertEqual(1, metric[key])
        self.assertEqual(1.0, evaluation_table(run, raw=True).iloc[0]["Accuracy"])

    def test_unguarded_multivariate_alert_is_explained_without_claiming_exceeded_tolerance(self):
        run = run_fixture()
        flag(run, value=51.0)
        summary = summarize_run(run)
        self.assertEqual("attention", summary["status_level"])
        self.assertIn("Chưa chỉ số riêng lẻ", summary["notable"].iloc[0]["Giải thích ngắn"])
        self.assertIn("chưa có số truy vấn lỗi", summary["indicator_note"])


class MonitoringChartsAndReportTests(unittest.TestCase):
    def test_score_chart_keeps_exact_negated_margin_and_two_alert_sets(self):
        run = run_fixture()
        flag(run)
        run.predictions.loc[1, "mad_raw_prediction"] = -1
        run.predictions.loc[1, "mad_score"] = -1.5
        figure = build_score_figure(run, "mad")
        np.testing.assert_array_equal(-run.predictions.mad_score, figure.data[0].y)
        self.assertEqual(list(run.predictions.timestamp), list(figure.data[0].x))
        self.assertEqual(list(run.predictions.timestamp.iloc[:2]), list(figure.data[1].x))
        self.assertEqual([run.predictions.timestamp.iloc[0]], list(figure.data[2].x))
        self.assertEqual(0, figure.layout.shapes[0].y0)
        self.assertEqual("#17233b", figure.layout.font.color)
        self.assertEqual("#ffffff", figure.layout.paper_bgcolor)

    def test_count_chart_uses_union_and_does_not_count_training_or_model_votes(self):
        run = run_fixture(models=("mad", "lof"))
        flag(run)
        flag(run, model="lof")
        figure = build_count_figure(run)
        self.assertEqual([19, 1], list(figure.data[0].y))

    def test_comparison_chart_does_not_change_or_align_source_measurements(self):
        left, right = run_fixture(), run_fixture()
        flag(right)
        right.predictions["timestamp"] += pd.Timedelta(days=2)
        original = right.predictions.copy(deep=True)
        figure = build_comparison_figure(left, right, "queries_per_second")
        np.testing.assert_array_equal(left.predictions.queries_per_second, figure.data[0].y)
        np.testing.assert_array_equal(right.predictions.queries_per_second, figure.data[2].y)
        self.assertEqual(list(right.predictions.timestamp), list(figure.data[2].x))
        pd.testing.assert_frame_equal(original, right.predictions)

    def test_unlabeled_report_has_real_counts_source_and_no_invented_metrics(self):
        run = run_fixture()
        flag(run)
        report = build_report_markdown(run, source_name="Dữ liệu mẫu demo").decode("utf-8-sig")
        self.assertIn("dữ liệu mẫu demo", report.lower())
        self.assertIn("không xác nhận hiệu quả trên máy chủ thật", report)
        self.assertIn("1 (5.00%)", report)
        self.assertIn("không tính Precision", report)
        self.assertIn("56", report)
        self.assertIn("Trung vị học", report)

    def test_labeled_report_contains_recomputed_accuracy_and_explicit_matrix_layout(self):
        run = run_fixture(rows=4)
        run.metadata["label_col"] = "label"
        run.predictions["label"] = [-1, 1, -1, 1]
        run.predictions["mad_prediction"] = [-1, -1, 1, 1]
        run.predictions["mad_raw_prediction"] = [-1, 1, -1, 1]
        run.metrics = {"mad": {"accuracy": .999}}
        report = build_report_markdown(run).decode("utf-8-sig")
        self.assertIn("| MAD | 0.5 | 0.5 | 0.5 | 0.5 | 1 | 1 | 1 | 1 |", report)
        self.assertIn("[[TN, FP], [FN, TP]]", report)
        self.assertNotIn("0.999", report)
        self.assertIn("Dự đoán gốc", report)

    def test_comparison_report_distinguishes_shared_training_from_excluded_prefix(self):
        run = run_fixture()
        run.metadata["comparison"] = {"role": "anomalous", "reference_train_rows": 37,
                                       "local_excluded_prefix_rows": 12}
        report = build_report_markdown(run).decode("utf-8-sig")
        self.assertIn("Mô hình chung học 37 bản ghi", report)
        self.assertIn("12 bản ghi đầu của bộ đang báo cáo không được chấm", report)
        self.assertIn("Phần đầu bộ đối chiếu không tham gia huấn luyện", report)
        self.assertIn("không cộng thời gian lặp lại", report)


if __name__ == "__main__":
    unittest.main()
