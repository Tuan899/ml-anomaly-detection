"""Actual monitoring routes, fitted estimators, persisted evidence and liveness."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.monitoring_api import get_controller, router
from src.demo_scenarios import inject_record, scenario_records
from src.monitoring_controller import MonitoringController


class MonitoringAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'monitor.sqlite3'
        self.controller = MonitoringController(self.path)
        self.addCleanup(lambda: self.controller.close())
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_controller] = lambda: self.controller
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def train(self):
        response = self.client.post('/monitor/train', json={})
        self.assertEqual(200, response.status_code, response.text)
        return response.json()['baseline']

    def sample(self, *, event_id='point-1'):
        row = inject_record(scenario_records('K1', rows=30)[0], 'K2')
        row['event_id'] = event_id
        return row

    def ingest(self, row=None, *, session='collector-1'):
        response = self.client.post('/monitor/samples', json={
            'records': [row or self.sample()], 'source': 'live', 'session_id': session})
        self.assertEqual(200, response.status_code, response.text)
        return response.json()['samples'][0]

    def test_cold_start_never_claims_healthy_collector_and_requires_training(self):
        health = self.client.get('/monitor/health').json()
        self.assertEqual('ok', health['backend'])
        self.assertIsNone(health['baseline'])
        self.assertEqual('idle', health['collector']['status'])
        self.assertIsNone(health['latest'])
        for path, body in [('/monitor/source/live', {}), ('/monitor/replay/start', {}),
                           ('/monitor/inject', {'scenario': 'K2'})]:
            self.assertEqual(409, self.client.post(path, json=body).status_code)

    def test_training_is_separate_from_shared_four_model_scoring(self):
        baseline = self.train()
        self.assertEqual(300, baseline['rows'])
        self.assertEqual(300, baseline['scaler']['fit_rows'])
        self.assertEqual([], self.client.get('/monitor/history').json()['samples'])
        point = self.ingest()
        self.assertEqual(baseline['id'], point['baseline_id'])
        self.assertEqual({'mad', 'isolation_forest', 'lof', 'one_class_svm'}, set(point['predictions']))
        self.assertEqual(sum(value == -1 for value in point['predictions'].values()), point['votes'])
        self.assertEqual(point['votes'], len(point['voters']))
        self.assertEqual(5, len(point['evidence']))
        qps = next(item for item in point['evidence'] if item['metric'] == 'queries_per_second')
        self.assertAlmostEqual(point['queries_per_second'] - qps['baseline'], qps['delta'])
        self.assertTrue(qps['material'])
        self.assertEqual(-1, point['label'])
        self.assertEqual(baseline['scaler'], self.client.get('/monitor/health').json()['baseline']['scaler'])
        evaluation = self.client.get('/monitor/evaluation').json()
        self.assertEqual(1, evaluation['labeled_rows'])
        self.assertEqual(1, evaluation['anomaly_rows'])
        for result in evaluation['raw'].values():
            self.assertEqual(1, sum(sum(row) for row in result['confusion_matrix']))

    def test_duplicate_retries_do_not_renew_stale_liveness(self):
        self.train()
        self.client.post('/monitor/source/live', json={'stale_after_seconds': 1, 'session_id': 'collector-1'})
        first = self.ingest()
        future = datetime.fromisoformat(first['received_at']).replace(tzinfo=timezone.utc) + timedelta(seconds=20)
        with patch('src.monitoring_controller._utcnow', return_value=future):
            retry = self.ingest()
            health = self.client.get('/monitor/health').json()
        self.assertEqual(first['id'], retry['id'])
        self.assertEqual(first['received_at'], health['collector']['last_received_at'])
        self.assertEqual('stale', health['collector']['status'])
        self.assertGreaterEqual(health['collector']['age_seconds'], 20)
        self.assertEqual(1, len(self.client.get('/monitor/history').json()['samples']))

    def test_feedback_and_baseline_survive_backend_reconstruction(self):
        baseline = self.train()
        point = self.ingest()
        response = self.client.post(f"/monitor/alerts/{point['id']}/feedback", json={
            'verdict': 'true_incident', 'note': 'Đã đối chiếu log vận hành.'})
        self.assertEqual(200, response.status_code, response.text)
        # Simulate process loss without graceful source-stop metadata.
        self.controller.engine.close()
        self.controller = MonitoringController(self.path)
        health = self.client.get('/monitor/health').json()
        self.assertEqual(baseline['id'], health['baseline']['id'])
        self.assertEqual('stale', health['collector']['status'])
        restored = self.client.get('/monitor/history').json()['samples'][0]
        self.assertEqual('true_incident', restored['feedback']['verdict'])
        self.assertEqual(point['raw_predictions'], restored['raw_predictions'])

    def test_validation_rejects_bad_data_and_credentials_instead_of_storing_it(self):
        self.train()
        bad = self.sample()
        bad['connections'] = -1
        self.assertEqual(422, self.client.post('/monitor/samples', json={'records': [bad]}).status_code)
        self.assertEqual(422, self.client.post('/monitor/samples', json={'records': [self.sample()], 'password': 'secret'}).status_code)
        for path, body in [('/monitor/train', {'deviation_threshold': True}),
                           ('/monitor/source/live', {'interval_seconds': True}),
                           ('/monitor/replay/start', {'rows': True}),
                           ('/monitor/inject', {'scenario': 'K1'}),
                           ('/monitor/replay/start', {'interval_seconds': 0})]:
            self.assertEqual(422, self.client.post(path, json=body).status_code, (path, body))
        self.assertEqual([], self.client.get('/monitor/history').json()['samples'])

    def test_replay_injection_records_real_scores_and_old_collector_stop_cannot_stop_it(self):
        self.train()
        self.client.post('/monitor/source/live', json={'session_id': 'old-collector'})
        started = self.client.post('/monitor/replay/start', json={'scenario': 'K1', 'rows': 30, 'interval_seconds': .1})
        self.assertEqual(200, started.status_code, started.text)
        injected = self.client.post('/monitor/inject', json={'scenario': 'K3', 'duration_samples': 2})
        self.assertTrue(injected.json()['synthetic'])
        stopped = self.client.post('/monitor/source/stop', json={'session_id': 'old-collector'}).json()
        self.assertEqual('replay', stopped['collector']['mode'])
        self.assertNotEqual('stopped', stopped['collector']['status'])
        deadline = time.monotonic() + 4
        points = []
        while time.monotonic() < deadline:
            points = self.client.get('/monitor/history').json()['samples']
            if sum(point.get('scenario') == 'K3' for point in points) >= 2:
                break
            time.sleep(.03)
        self.assertEqual(2, sum(point.get('scenario') == 'K3' for point in points))
        self.assertTrue(all(point['source'] == 'K1' for point in points))
        faults = [point for point in points if point['scenario'] == 'K3']
        self.assertTrue(all(point['label'] == -1 and point['connections'] >= 120 for point in faults))
        self.assertTrue(all(len(point['raw_predictions']) == 4 for point in faults))
        self.client.post('/monitor/replay/stop')
        self.assertEqual('stopped', self.client.get('/monitor/health').json()['collector']['status'])

    def test_explicit_stop_blocks_old_live_sender_until_source_reenabled(self):
        self.train()
        self.ingest()
        self.client.post('/monitor/replay/stop')
        response = self.client.post('/monitor/samples', json={
            'records': [self.sample(event_id='point-2')], 'source': 'live', 'session_id': 'collector-1'})
        self.assertEqual(409, response.status_code)
        self.assertEqual('stopped', self.client.get('/monitor/health').json()['collector']['status'])
        self.client.post('/monitor/source/live', json={'session_id': 'collector-1'})
        self.ingest(self.sample(event_id='point-2'))

    def test_new_baseline_does_not_show_an_old_point_as_its_latest_measurement(self):
        first = self.train()
        self.ingest()
        second = self.train()
        self.assertNotEqual(first['id'], second['id'])
        self.assertIsNone(self.client.get('/monitor/health').json()['latest'])
        self.assertEqual(1, len(self.client.get('/monitor/history').json()['samples']))

    def test_evidence_uses_exact_matching_samples_and_matrices(self):
        self.train()
        self.ingest()
        exported = self.client.get('/monitor/evidence').json()
        self.assertEqual(1, len(exported['samples']))
        self.assertEqual(1, exported['evaluation']['rows'])
        self.assertEqual(exported['samples'][0]['baseline_id'], exported['baseline']['id'])
        self.assertTrue(exported['exported_at'])


if __name__ == '__main__':
    unittest.main()
