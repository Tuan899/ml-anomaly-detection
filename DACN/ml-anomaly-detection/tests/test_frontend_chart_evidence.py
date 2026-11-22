"""Preserve measured data and distinguish a model alert from metric evidence."""
from copy import deepcopy
import unittest

from frontend.live_charts import METRICS, MODELS, activity_figure, comparison_figure


def stored_samples() -> list[dict]:
    """Representative stored records, including a suppressed raw model flag."""
    reference = dict(zip(METRICS, (50.125, 12.0, 14.25, 0.0, 0.0)))
    samples = []
    for index, qps in enumerate((50.125, 325.75, 320.125)):
        raw = {name: (-1 if index == 1 or (index == 0 and name == "mad") else 1)
               for name in MODELS}
        guarded = {name: (-1 if index == 1 else 1) for name in MODELS}
        values = {**reference, "queries_per_second": qps}
        samples.append({
            **values,
            "timestamp": f"2026-11-21T09:00:0{index}+07:00",
            "received_at": f"2026-11-21T02:01:0{index}+00:00",
            "source": "replay",
            "votes": sum(value == -1 for value in guarded.values()),
            "raw_votes": sum(value == -1 for value in raw.values()),
            "voters": [name for name, value in guarded.items() if value == -1],
            "raw_voters": [name for name, value in raw.items() if value == -1],
            "level": "critical" if index == 1 else "normal",
            "predictions": guarded, "raw_predictions": raw,
            "evidence": [
                {"metric": metric, "actual": values[metric], "baseline": reference[metric],
                 "allowed_deviation": 5.0,
                 "material": metric == "queries_per_second" and index > 0}
                for metric in METRICS
            ],
        })
    return samples


class FrontendChartEvidenceTests(unittest.TestCase):
    def test_qps_only_alert_does_not_mark_other_channels_or_unvoted_drift(self):
        samples = stored_samples()
        for dark in (False, True):
            with self.subTest(dark=dark):
                figure = activity_figure(samples, dark)
                self.assertEqual(10, len(figure.data))
                self.assertEqual([samples[1]["received_at"]], list(figure.data[1].x))
                self.assertEqual([samples[1]["queries_per_second"]], list(figure.data[1].y))
                for trace in figure.data[3::2]:
                    self.assertEqual([], list(trace.x))
                    self.assertEqual([], list(trace.y))

    def test_missing_metric_evidence_never_claims_a_specific_channel_is_abnormal(self):
        for missing in (True, False):
            with self.subTest(missing_field=missing):
                samples = stored_samples()
                for sample in samples:
                    if missing:
                        sample.pop("evidence")
                    else:
                        sample["evidence"] = []
                figure = activity_figure(samples)
                self.assertEqual(10, len(figure.data))
                for trace in figure.data[1::2]:
                    self.assertEqual([], list(trace.x))
                self.assertEqual(4, samples[1]["votes"])

    def test_exact_measurements_and_raw_guarded_decisions_survive_chart_rendering(self):
        samples = stored_samples()
        original = deepcopy(samples)
        received = [sample["received_at"] for sample in samples]
        for dark in (False, True):
            activity = activity_figure(samples, dark)
            for index, metric in enumerate(METRICS):
                trace = activity.data[index * 2]
                self.assertEqual(received, list(trace.x))
                self.assertEqual([sample[metric] for sample in samples], list(trace.y))
                self.assertEqual(samples[0]["timestamp"], trace.customdata[0][5])
            for raw in (False, True):
                field = "raw_predictions" if raw else "predictions"
                comparison = comparison_figure(samples, raw, dark).data[0]
                self.assertEqual(received, list(comparison.x))
                self.assertEqual(list(MODELS.values()), list(comparison.y))
                self.assertEqual(
                    [[int(sample[field][name] == -1) for sample in samples] for name in MODELS],
                    [list(row) for row in comparison.z],
                )
                votes = "raw_votes" if raw else "votes"
                self.assertEqual([sample[votes] for sample in samples],
                                 [entry[7] for entry in comparison.customdata[0]])
        self.assertEqual(original, samples)


if __name__ == "__main__":
    unittest.main()
