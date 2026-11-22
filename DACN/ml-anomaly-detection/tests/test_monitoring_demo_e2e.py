"""Exercise the shipped HTTP demo, persistent scoring and exported evidence.

The scenarios are synthetic and fixed before model fitting. Tests reconcile
reported counts against real predictions; they do not prescribe a model rank or
promise a particular accuracy on these or production workloads.
"""
from __future__ import annotations

from collections import Counter
from io import BytesIO
import json
import math
from pathlib import Path
import tempfile
import unittest

import pandas as pd
from fastapi.testclient import TestClient

from backend.api import app
from backend.monitoring_api import get_controller
from frontend.live_workspace import flatten_history
from src.dbms_monitoring import MYSQL_METRICS
from src.demo_scenarios import scenario_records
from src.models import MODEL_NAMES
from src.monitoring_controller import MonitoringController


def independent_counts(samples, name, field):
    selected = [sample for sample in samples if sample["label"] in (-1, 1)]
    tn = sum(sample["label"] == 1 and sample[field][name] == 1 for sample in selected)
    fp = sum(sample["label"] == 1 and sample[field][name] == -1 for sample in selected)
    fn = sum(sample["label"] == -1 and sample[field][name] == 1 for sample in selected)
    tp = sum(sample["label"] == -1 and sample[field][name] == -1 for sample in selected)
    precision = tp / (tp + fp) if tp + fp else 0.
    recall = tp / (tp + fn) if tp + fn else 0.
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.
    return {"tn": tn, "fp": fp, "fn": fn, "tp": tp, "precision": precision,
            "recall": recall, "f1": f1, "confusion_matrix": [[tn, fp], [fn, tp]]}


class MonitoringDemoEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temporary.name) / "demo.sqlite3"
        self.controller = MonitoringController(self.db_path)
        self.previous_overrides = dict(app.dependency_overrides)
        app.dependency_overrides[get_controller] = lambda: self.controller
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        try:
            self.client.__exit__(None, None, None)
            self.controller.close()
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(self.previous_overrides)
            self.temporary.cleanup()

    def post(self, path, payload):
        response = self.client.post("/monitor" + path, json=payload)
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def get(self, path, **params):
        response = self.client.get("/monitor" + path, params=params)
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def assert_counts(self, samples, evaluation):
        self.assertEqual(len(samples), evaluation["rows"])
        self.assertEqual(sum(sample["label"] in (-1, 1) for sample in samples), evaluation["labeled_rows"])
        for scope, field in (("raw", "raw_predictions"), ("guarded", "predictions")):
            self.assertEqual(set(MODEL_NAMES), set(evaluation[scope]))
            for name in MODEL_NAMES:
                expected = independent_counts(samples, name, field)
                for key in ("tn", "fp", "fn", "tp", "confusion_matrix"):
                    self.assertEqual(expected[key], evaluation[scope][name][key])
                for key in ("precision", "recall", "f1"):
                    self.assertAlmostEqual(expected[key], evaluation[scope][name][key], places=12)

    def test_k1_through_k4_share_one_fitted_reference_and_report_actual_votes(self):
        baseline = self.post("/train", {})["baseline"]
        self.assertEqual(300, baseline["rows"])
        self.assertEqual(300, baseline["scaler"]["fit_rows"])
        self.assertEqual(list(MYSQL_METRICS), baseline["features"])
        levels = {0: "normal", 1: "watch", 2: "warning", 3: "critical", 4: "critical"}
        all_samples = []
        for scenario in ("K1", "K2", "K3", "K4"):
            observations = scenario_records(scenario)
            for index, record in enumerate(observations):
                record["event_id"] = f"{scenario}:{index}"
            samples = self.post("/samples", {"records": observations, "source": scenario,
                                            "session_id": "e2e-common-reference"})["samples"]
            self.assertEqual(len(observations), len(samples))
            for original, sample in zip(observations, samples):
                self.assertEqual(baseline["id"], sample["baseline_id"])
                self.assertEqual(original["label"], sample["label"])
                self.assertEqual(original["scenario"], sample["scenario"])
                self.assertEqual(original["event_id"], sample["event_id"])
                for metric in MYSQL_METRICS:
                    self.assertAlmostEqual(original[metric], sample[metric], places=12)
                evidence = {item["metric"]: item for item in sample["evidence"]}
                self.assertEqual(set(MYSQL_METRICS), set(evidence))
                for metric, item in evidence.items():
                    reference = baseline["baselines"][metric]
                    self.assertEqual(sample[metric], item["actual"])
                    self.assertEqual(reference["median"], item["baseline"])
                    self.assertAlmostEqual(sample[metric] - reference["median"], item["delta"], places=12)
                    self.assertEqual(abs(item["delta"]) > item["allowed_deviation"], item["material"])
                material = any(item["material"] for item in evidence.values())
                for name in MODEL_NAMES:
                    self.assertTrue(math.isfinite(sample["scores"][name]))
                    expected = -1 if sample["raw_predictions"][name] == -1 and material else 1
                    self.assertEqual(expected, sample["predictions"][name])
                for prefix, field in (("raw_", "raw_predictions"), ("", "predictions")):
                    voters = [name for name in MODEL_NAMES if sample[field][name] == -1]
                    self.assertEqual(voters, sample[prefix + "voters"])
                    self.assertEqual(len(voters), sample[prefix + "votes"])
                    self.assertEqual(levels[len(voters)], sample[prefix + "level"])
            evaluation = self.get("/evaluation", source=scenario, baseline_id=baseline["id"])
            self.assert_counts(samples, evaluation)
            vote_counts = Counter(sample["votes"] for sample in samples)
            print(json.dumps({"scenario": scenario, "samples": len(samples),
                "reference_anomalies": sum(sample["label"] == -1 for sample in samples),
                "guarded_votes": {str(vote): vote_counts[vote] for vote in range(5)},
                "raw_alerts": {name: sum(row["raw_predictions"][name] == -1 for row in samples) for name in MODEL_NAMES},
                "guarded_alerts": {name: sum(row["predictions"][name] == -1 for row in samples) for name in MODEL_NAMES},
                "guarded_fp_fn": {name: {key: evaluation["guarded"][name][key] for key in ("fp", "fn")} for name in MODEL_NAMES}}))
            all_samples.extend(samples)
        self.assertEqual(baseline, self.get("/health")["baseline"])
        snapshot = self.get("/evidence", baseline_id=baseline["id"])
        self.assertEqual(baseline, snapshot["baseline"])
        self.assertEqual(all_samples, snapshot["samples"])
        self.assert_counts(snapshot["samples"], snapshot["evaluation"])

    def test_feedback_survives_restart_and_csv_json_keep_complete_raw_and_guarded_scope(self):
        baseline = self.post("/train", {})["baseline"]
        records = scenario_records("K2", rows=1200)
        for index, record in enumerate(records):
            record["event_id"] = f"long-replay:{index}"
        stored = []
        for start in range(0, len(records), 700):
            stored.extend(self.post("/samples", {"records": records[start:start + 700],
                "source": "K2", "session_id": "persistent-e2e"})["samples"])
        incident = next(sample for sample in stored if sample["label"] == -1)
        before = self.get("/evaluation", source="K2", baseline_id=baseline["id"])
        reviewed = self.post(f"/alerts/{incident['id']}/feedback", {
            "verdict": "false_alarm", "note": "DBA confirmed a scheduled test workload"})["alert"]
        self.assertEqual("false_alarm", reviewed["feedback"]["verdict"])
        self.assertEqual(-1, reviewed["label"])
        self.assertEqual(before, self.get("/evaluation", source="K2", baseline_id=baseline["id"]))
        self.controller.close()
        self.controller = MonitoringController(self.db_path)
        self.assertEqual("stopped", self.get("/health")["collector"]["status"])
        self.assertEqual(1000, len(self.get("/history", limit=1000, baseline_id=baseline["id"])["samples"]))
        export = self.get("/evidence", source="K2", baseline_id=baseline["id"])
        self.assertEqual(1200, len(export["samples"]))
        self.assertEqual(baseline, export["baseline"])
        self.assert_counts(export["samples"], export["evaluation"])
        restored = next(sample for sample in export["samples"] if sample["id"] == incident["id"])
        self.assertEqual(reviewed["feedback"], restored["feedback"])
        self.assertEqual(-1, restored["label"])
        encoded = json.dumps(export, allow_nan=False).encode("utf-8")
        decoded = json.loads(encoded)
        self.assertEqual(1200, decoded["evaluation"]["labeled_rows"])
        table = flatten_history(export["samples"])
        csv = pd.read_csv(BytesIO(table.to_csv(index=False).encode("utf-8-sig")))
        self.assertEqual(1200, len(csv))
        self.assertEqual([sample["id"] for sample in export["samples"]], csv["id"].tolist())
        for name in MODEL_NAMES:
            for suffix, field in (("raw_prediction", "raw_predictions"), ("prediction", "predictions")):
                self.assertEqual([sample[field][name] for sample in export["samples"]], csv[f"{name}_{suffix}"].tolist())
        self.assertEqual("false_alarm", csv.loc[csv["id"] == incident["id"], "feedback_verdict"].iloc[0])
        self.assertEqual(-1, csv.loc[csv["id"] == incident["id"], "label"].iloc[0])


if __name__ == "__main__":
    unittest.main()
