"""Real-load endpoints are exercised through a fake runner, never a database."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.monitoring_api import get_controller, router
from src.demo_scenarios import scenario_records
from src.monitoring_controller import MonitoringController


TARGET = 'a' * 64


class FakeFaultRunner:
    def __init__(self):
        self.value = {'enabled': True, 'configured': True, 'target': {'target_id': TARGET},
                      'configuration_message': '', 'limits': {}, 'job': None}
        self.started = []
        self.stop_calls = 0
        self.close_calls = 0
        self.on_stop = None
        self.stop_error = None

    def status(self):
        return deepcopy(self.value)

    def start(self, **options):
        self.started.append(options)
        self.value['job'] = dict(options, id=len(self.started), status='running')
        return self.status()

    def stop(self):
        self.stop_calls += 1
        if self.on_stop:
            self.on_stop()
        if self.stop_error:
            raise RuntimeError(self.stop_error)
        if self.value['job'] and self.value['job']['status'] == 'running':
            self.value['job']['status'] = 'stopped'
        return self.status()

    def close(self):
        self.close_calls += 1


class LiveFaultAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runner = FakeFaultRunner()
        self.controller = MonitoringController(Path(self.temp.name) / 'monitor.sqlite3', fault_runner=self.runner)
        self.addCleanup(self.controller.close)
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_controller] = lambda: self.controller
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        response = self.client.post('/monitor/train', json={})
        self.assertEqual(200, response.status_code, response.text)

    def fresh_source(self, target=TARGET):
        body = {'session_id': 'producer-current', 'interval_seconds': 1}
        if target is not None:
            body['target_id'] = target
        response = self.client.post('/monitor/source/live', json=body)
        self.assertEqual(200, response.status_code, response.text)
        row = scenario_records('K1', rows=30)[0]
        row['event_id'] = 'measured-point'
        response = self.client.post('/monitor/samples', json={
            'source': 'live', 'session_id': 'producer-current', 'records': [row]})
        self.assertEqual(200, response.status_code, response.text)
        return response.json()['samples'][0]

    def start_fault(self, **changes):
        return self.client.post('/monitor/faults/live', json={'scenario': 'K2', **changes})

    def test_read_status_does_not_start_workload(self):
        response = self.client.get('/monitor/faults/live')
        self.assertEqual(200, response.status_code)
        self.assertEqual(TARGET, response.json()['target']['target_id'])
        self.assertEqual([], self.runner.started)

    def test_start_requires_fresh_live_collector_and_matching_target(self):
        self.assertEqual(409, self.start_fault().status_code)
        self.client.post('/monitor/source/live', json={'session_id': 'producer-current', 'target_id': TARGET})
        self.assertEqual(409, self.start_fault().status_code)  # no sample yet
        self.fresh_source(target=None)
        self.assertEqual(409, self.start_fault().status_code)
        self.fresh_source(target='b' * 64)
        self.assertEqual(409, self.start_fault().status_code)
        self.assertEqual([], self.runner.started)

    def test_live_start_is_gated_by_age_even_before_status_changes(self):
        point = self.fresh_source()
        future = datetime.fromisoformat(point['received_at']).replace(tzinfo=timezone.utc) + timedelta(seconds=20)
        with patch('src.monitoring_controller._utcnow', return_value=future):
            self.assertEqual(409, self.start_fault().status_code)
        self.assertEqual([], self.runner.started)

    def test_runner_opt_in_and_configuration_are_required(self):
        self.fresh_source()
        self.runner.value['enabled'] = False
        self.assertEqual(409, self.start_fault().status_code)
        self.runner.value['enabled'] = True
        self.runner.value['configured'] = False
        self.assertEqual(409, self.start_fault().status_code)
        self.assertEqual([], self.runner.started)

    def test_strict_bounds_reject_boolean_credentials_and_arbitrary_scenarios(self):
        self.fresh_source()
        for changes in ({'scenario': 'K1'}, {'duration_seconds': True}, {'duration_seconds': 1.5},
                        {'duration_seconds': 61}, {'connections': 21}, {'connections': True},
                        {'auth_failures': 4}, {'rate_per_second': 501}, {'password': 'do-not-send'}):
            response = self.start_fault(**changes)
            self.assertEqual(422, response.status_code, (changes, response.text))
        self.assertEqual(422, self.client.post('/monitor/source/live', json={'target_id': 'not-a-sha256'}).status_code)
        self.assertEqual([], self.runner.started)

    def test_valid_start_and_explicit_stop_use_bounded_runner_parameters(self):
        self.fresh_source()
        response = self.start_fault(scenario='K3', duration_seconds=4, connections=3, auth_failures=1)
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual('running', response.json()['job']['status'])
        self.assertEqual({'scenario': 'K3', 'duration_seconds': 4, 'rate_per_second': 100,
                          'connections': 3, 'auth_failures': 1}, self.runner.started[0])
        response = self.client.post('/monitor/faults/live/stop')
        self.assertEqual('stopped', response.json()['job']['status'])
        self.assertEqual('running', self.controller.collector_status()['status'])

    def test_changing_source_stops_load_before_replay_and_old_sender_cannot_stop_new_load(self):
        self.fresh_source()
        self.assertEqual(200, self.start_fault().status_code)
        before = self.runner.stop_calls
        response = self.client.post('/monitor/source/stop', json={'session_id': 'producer-old'})
        self.assertEqual(before, self.runner.stop_calls)
        self.assertEqual('running', self.runner.status()['job']['status'])
        observed_modes = []
        self.runner.on_stop = lambda: observed_modes.append(self.controller.collector_status()['mode'])
        response = self.client.post('/monitor/replay/start', json={'scenario': 'K1', 'rows': 30, 'interval_seconds': .1})
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(['live'], observed_modes)
        self.assertEqual('stopped', self.runner.status()['job']['status'])
        self.assertEqual('replay', self.controller.collector_status()['mode'])

    def test_training_and_source_stop_end_current_load_without_changing_old_evidence(self):
        point = self.fresh_source()
        self.assertEqual(200, self.start_fault().status_code)
        response = self.client.post('/monitor/train', json={})
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual('stopped', self.runner.status()['job']['status'])
        old = self.controller.engine.history(baseline_id=point['baseline_id'])[0]
        self.assertEqual(point['raw_predictions'], old['raw_predictions'])
        self.assertEqual(point['scores'], old['scores'])

    def test_incomplete_workload_cleanup_prevents_source_transition(self):
        self.fresh_source()
        self.assertEqual(200, self.start_fault().status_code)
        self.runner.stop_error = 'Cleanup is still pending'
        try:
            response = self.client.post('/monitor/replay/start', json={})
            self.assertEqual(409, response.status_code, response.text)
            self.assertEqual('live', self.controller.collector_status()['mode'])
            self.assertEqual('running', self.runner.status()['job']['status'])
        finally:
            self.runner.stop_error = None


if __name__ == '__main__':
    unittest.main()
