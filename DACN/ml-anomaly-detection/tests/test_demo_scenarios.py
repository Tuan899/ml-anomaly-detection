from datetime import datetime
import unittest

from src.demo_scenarios import METRICS, baseline_records, inject_record, scenario_catalog, scenario_records


class ReplayScenarioTests(unittest.TestCase):
    def test_scenarios_share_the_normal_reference_but_not_the_training_rows(self):
        baseline = baseline_records()
        normal = scenario_records("K1")
        self.assertTrue(all(row["label"] == 1 for row in baseline + normal))
        self.assertLess(datetime.fromisoformat(baseline[-1]["timestamp"]), datetime.fromisoformat(normal[0]["timestamp"]))
        affected = {"K2": {"queries_per_second"}, "K3": {"connections", "connection_errors"},
                    "K4": {"response_time_ms", "slow_queries"}}
        for scenario, metrics in affected.items():
            records = scenario_records(scenario)
            self.assertEqual(30, sum(row["label"] == -1 for row in records))
            for index, row in enumerate(records):
                changed = {name for name in METRICS if row[name] != normal[index][name]}
                self.assertEqual(metrics if 60 <= index < 90 else set(), changed)
                self.assertEqual(-1 if changed else 1, row["label"])
        self.assertEqual(["K1", "K2", "K3", "K4"], [item["id"] for item in scenario_catalog()])

    def test_injection_copies_input_and_cannot_choose_a_real_workload(self):
        original = scenario_records("K1", 1)[0]
        copied = dict(original)
        self.assertEqual(-1, inject_record(original, "K2")["label"])
        self.assertEqual(copied, original)
        with self.assertRaises(ValueError):
            inject_record(original, "SQL")


if __name__ == "__main__":
    unittest.main()
