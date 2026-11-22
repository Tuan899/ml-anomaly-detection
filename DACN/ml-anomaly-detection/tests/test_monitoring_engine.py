"""Exercise persistent train/score separation and auditable operational votes."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import numpy as np
import pandas as pd

from src.dbms_monitoring import MYSQL_METRICS
from src.models import fit_models
from src.monitoring_engine import MonitoringEngine, vote_level


def observations(rows=100):
    rng = np.random.default_rng(423)
    return pd.DataFrame({"timestamp": pd.date_range("2026-11-01", periods=rows, freq="min", tz="UTC"),
        "queries_per_second": 50 + rng.uniform(-2, 2, rows),
        "connections": 30 + rng.integers(-2, 3, rows),
        "response_time_ms": 15 + rng.uniform(-.5, .5, rows),
        "slow_queries": np.zeros(rows), "connection_errors": np.zeros(rows),
        "label": np.ones(rows, dtype=int), "scenario": ["K1"] * rows})


class MonitoringEngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "monitor.sqlite3"
        self.engine = MonitoringEngine(self.path)
        self.addCleanup(self.engine.close)
        self.frame = observations()

    def test_requires_explicit_training_and_rejects_contaminated_baseline(self):
        with self.assertRaisesRegex(ValueError, "Train a normal baseline"):
            self.engine.ingest(self.frame.iloc[80:81])
        bad = self.frame.copy()
        bad.loc[10, "label"] = -1
        with self.assertRaisesRegex(ValueError, "labeled anomalies"):
            self.engine.train_baseline(bad, end_index=60)
        with self.assertRaisesRegex(ValueError, "at least 30"):
            self.engine.train_baseline(self.frame.iloc[:20])
        self.assertIsNone(self.engine.baseline())

    def test_same_estimators_as_batch_pipeline_and_no_refitting_on_score(self):
        baseline = self.engine.train_baseline(self.frame, end_index=60)
        test = self.frame.iloc[60:].copy()
        test.loc[65, "queries_per_second"] = 350
        test.loc[65, "label"] = -1
        expected = fit_models(self.frame.iloc[:60][list(MYSQL_METRICS)], test[list(MYSQL_METRICS)])
        actual = self.engine.ingest(test, source="K2", session_id="replay-one")
        for name, result in expected.items():
            np.testing.assert_array_equal(result.predictions, [row["raw_predictions"][name] for row in actual])
            np.testing.assert_allclose(result.scores, [row["scores"][name] for row in actual], rtol=1e-12)
        self.assertEqual(baseline, self.engine.baseline())
        self.assertEqual(["K1"] * len(test), [row["scenario"] for row in actual])
        json.dumps(actual, allow_nan=False)

    def test_unselected_test_values_and_labels_cannot_affect_fitted_reference(self):
        first = self.engine.train_baseline(self.frame, end_index=60)
        changed = self.frame.astype({metric: float for metric in MYSQL_METRICS}).copy()
        changed.loc[60:, list(MYSQL_METRICS)] = np.inf
        changed.loc[60:, "label"] = -1
        second = self.engine.train_baseline(changed, end_index=60)
        for key in ("scaler", "baselines", "parameters", "features"):
            self.assertEqual(first[key], second[key])

    def test_voting_and_material_deviation_match_each_prediction(self):
        constant = self.frame.copy()
        constant.loc[:, list(MYSQL_METRICS)] = 50.
        constant.loc[:, "connection_errors"] = 0.
        self.engine.train_baseline(constant.iloc[:60])
        test = constant.iloc[60:62].copy()
        test.loc[60, "queries_per_second"] = 51.
        test.loc[61, "connection_errors"] = 3.
        records = self.engine.ingest(test)
        small, large = records
        self.assertEqual(-1, small["raw_predictions"]["mad"])
        self.assertEqual(0, small["votes"])
        self.assertEqual("normal", small["level"])
        self.assertGreater(large["votes"], 0)
        errors = next(item for item in large["evidence"] if item["metric"] == "connection_errors")
        self.assertTrue(errors["material"])
        self.assertEqual(3., errors["delta"])
        self.assertIsNone(errors["relative_change"])
        for record in records:
            self.assertEqual(record["votes"], sum(value == -1 for value in record["predictions"].values()))
            self.assertEqual(vote_level(record["votes"]), record["level"])
        self.assertEqual(["normal", "watch", "warning", "critical", "critical"], [vote_level(v) for v in range(5)])

    def test_restart_restores_artifact_history_and_feedback_audit(self):
        reference = self.engine.train_baseline(self.frame.iloc[:60])
        first = self.engine.ingest(self.frame.iloc[60:61], source="live", session_id="one")[0]
        updated = self.engine.feedback(first["id"], "false_alarm", "DBA verified scheduled work")
        self.assertEqual("false_alarm", updated["feedback"]["verdict"])
        other = MonitoringEngine(self.path)
        self.addCleanup(other.close)
        self.assertEqual(reference, other.baseline())
        self.assertEqual("false_alarm", other.history()[0]["feedback"]["verdict"])
        scored = other.ingest(self.frame.iloc[61:62], source="live")[0]
        self.assertEqual(first["baseline_id"], scored["baseline_id"])
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM engine_feedback_events").fetchone()[0])

    def test_retraining_keeps_old_history_and_evaluation_versions_separate(self):
        first = self.engine.train_baseline(self.frame.iloc[:60])
        self.engine.ingest(self.frame.iloc[60:65], source="K1")
        second = self.engine.train_baseline(self.frame.iloc[:50])
        self.engine.ingest(self.frame.iloc[65:67], source="K2")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(7, len(self.engine.history()))
        self.assertEqual(5, self.engine.evaluation(baseline_id=first["id"])["labeled_rows"])
        current = self.engine.evaluation()
        self.assertEqual(2, current["labeled_rows"])
        self.assertEqual([second["id"]], current["baseline_ids"])
        for scope in ("raw", "guarded"):
            self.assertEqual(4, len(current[scope]))
            for result in current[scope].values():
                self.assertEqual(2, sum(sum(row) for row in result["confusion_matrix"]))

    def test_unlabeled_observations_and_feedback_do_not_create_ground_truth(self):
        self.engine.train_baseline(self.frame.iloc[:60])
        record = self.engine.ingest(self.frame.iloc[60:61].drop(columns=["label"]))[0]
        self.engine.feedback(record["id"], "true_incident")
        result = self.engine.evaluation()
        self.assertEqual(0, result["labeled_rows"])
        self.assertEqual({}, result["raw"])
        self.assertIsNone(self.engine.history()[0]["label"])

    def test_invalid_batch_is_atomic_and_baseline_cannot_be_scored_as_test(self):
        self.engine.train_baseline(self.frame.iloc[:60])
        with self.assertRaisesRegex(ValueError, "after the baseline"):
            self.engine.ingest(self.frame.iloc[59:61])
        for invalid in (np.inf, np.nan, -1, True):
            bad = self.frame.iloc[60:62].copy().astype({"queries_per_second": object})
            bad.loc[61, "queries_per_second"] = invalid
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                self.engine.ingest(bad)
        self.assertEqual([], self.engine.history())

    def test_concurrent_writers_preserve_all_rows_and_monotonic_ids(self):
        self.engine.train_baseline(self.frame.iloc[:60])
        with ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(lambda i: self.engine.ingest(self.frame.iloc[60+i:61+i], source=f"source-{i % 2}"), range(9)))
        history = self.engine.history(limit=100)
        self.assertEqual(9, len(history))
        self.assertEqual(list(range(1, 10)), [row["id"] for row in history])
        self.assertEqual(4, len(self.engine.history(source="source-1")))
        self.assertEqual([7, 8, 9], [row["id"] for row in self.engine.history(after_id=6)])

    def test_collector_retries_are_idempotent_and_changed_retries_are_rejected(self):
        self.engine.train_baseline(self.frame.iloc[:60])
        records = self.frame.iloc[60:62].copy()
        records["event_id"] = ["collector:60", "collector:61"]
        first = self.engine.ingest(records, source="live", session_id="collector-one")
        self.engine.feedback(first[0]["id"], "false_alarm", "reviewed")
        other = MonitoringEngine(self.path)
        self.addCleanup(other.close)
        retried = other.ingest(records, source="live", session_id="collector-one")
        self.assertEqual([row["id"] for row in first], [row["id"] for row in retried])
        self.assertEqual("false_alarm", retried[0]["feedback"]["verdict"])
        self.assertEqual(2, len(other.history()))
        records.loc[60, "queries_per_second"] = 999
        with self.assertRaisesRegex(ValueError, "different measurements"):
            other.ingest(records, source="live", session_id="collector-one")
        self.assertEqual(2, len(other.history()))

    def test_independent_engine_instances_cannot_duplicate_the_same_event(self):
        self.engine.train_baseline(self.frame.iloc[:60])
        other = MonitoringEngine(self.path)
        self.addCleanup(other.close)
        record = self.frame.iloc[60:61].copy()
        record["event_id"] = ["stable-event"]
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(engine.ingest, record, source="live", session_id="collector")
                       for engine in (self.engine, other)]
            outputs = [future.result()[0] for future in futures]
        self.assertEqual(outputs[0]["id"], outputs[1]["id"])
        self.assertEqual(1, len(self.engine.history()))

    def test_evidence_exports_full_scope_and_the_selected_baseline_metadata(self):
        frame = observations(rows=1300)
        old = self.engine.train_baseline(frame.iloc[:60], source="normal-reference-old")
        heldout = frame.iloc[60:1280].copy()
        heldout.loc[80:90, "queries_per_second"] = 350.
        heldout.loc[80:90, "label"] = -1
        self.engine.ingest(heldout, source="K2", session_id="long-replay")
        current = self.engine.train_baseline(frame.iloc[:50], source="normal-reference-new")
        self.engine.ingest(frame.iloc[1280:1300], source="K1")
        export = self.engine.evidence(baseline_id=old["id"], source="K2")
        self.assertEqual(old, export["baseline"])
        self.assertEqual(1220, len(export["samples"]))
        self.assertEqual(1220, export["evaluation"]["rows"])
        self.assertEqual(1220, export["evaluation"]["labeled_rows"])
        self.assertEqual(11, export["evaluation"]["anomaly_rows"])
        self.assertEqual([old["id"]], export["evaluation"]["baseline_ids"])
        self.assertEqual("K2", export["evaluation"]["source"])
        self.assertTrue(all(row["baseline_id"] == old["id"] for row in export["samples"]))
        for scope in ("raw", "guarded"):
            for metrics in export["evaluation"][scope].values():
                self.assertEqual(1220, sum(sum(row) for row in metrics["confusion_matrix"]))
        self.assertEqual(current, self.engine.baseline())
        self.assertEqual(current, self.engine.evidence()["baseline"])
        self.assertEqual(20, len(self.engine.evidence()["samples"]))
        self.assertIn("+00:00", export["exported_at"])
        json.dumps(export, allow_nan=False)
        with self.assertRaisesRegex(ValueError, "not found"):
            self.engine.evidence(baseline_id=99999)

    def test_catalog_keeps_old_scopes_after_more_than_a_thousand_new_samples(self):
        frame = observations(rows=1300)
        old = self.engine.train_baseline(frame.iloc[:60], source="old-reference")
        self.engine.ingest(frame.iloc[60:65], source="old-source")
        recent = self.engine.train_baseline(frame.iloc[:50], source="recent-reference")
        self.engine.ingest(frame.iloc[65:1265], source="recent-source")
        empty = self.engine.train_baseline(frame.iloc[:40], source="unscored-reference")
        self.assertEqual({recent["id"]}, {row["baseline_id"] for row in self.engine.history(limit=1000)})
        # Deny access to the artifact column so even a hidden baseline() call or
        # SELECT * regression cannot silently load a large fitted bundle.
        self.engine._connection.set_authorizer(lambda action, table, column, *_:
            sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and table == "engine_baselines" and column == "artifact"
            else sqlite3.SQLITE_OK)
        try:
            catalog = self.engine.catalog()
        finally:
            # Python 3.10 does not yet support disabling this callback with None.
            self.engine._connection.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
        self.assertEqual([empty["id"], recent["id"], old["id"]], [item["id"] for item in catalog["baselines"]])
        self.assertEqual([0, 1200, 5], [item["sample_count"] for item in catalog["baselines"]])
        self.assertEqual(old, {key: value for key, value in catalog["baselines"][-1].items() if key != "sample_count"})
        self.assertEqual([
            {"baseline_id": recent["id"], "source": "recent-source", "sample_count": 1200},
            {"baseline_id": old["id"], "source": "old-source", "sample_count": 5},
        ], catalog["sources"])
        export = self.engine.evidence(source="old-source", baseline_id=old["id"])
        self.assertEqual(5, len(export["samples"]))
        self.assertEqual(5, export["evaluation"]["labeled_rows"])
        self.assertEqual(old, export["baseline"])


if __name__ == "__main__":
    unittest.main()
