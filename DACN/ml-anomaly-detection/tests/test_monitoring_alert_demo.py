"""The explicit alert demo must produce real model votes without replacing live data."""
from pathlib import Path
from datetime import datetime
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
from src.demo_scenarios import baseline_records, scenario_records
from src.monitoring_controller import MonitoringController


class AlertDemoAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'monitor.sqlite3'
        self.controller = MonitoringController(self.path)
        self.addCleanup(lambda: self.controller.close())
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_controller] = lambda: self.controller
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def start_fast_demo(self):
        original = self.controller.start_replay
        def fast_replay(**options):
            self.assertEqual({'scenario': 'K1', 'interval_seconds': 1.0, 'rows': 180, 'loop': False}, options)
            options['interval_seconds'] = .1  # only the test clock is accelerated
            return original(**options)
        with patch.object(self.controller, 'start_replay', new=fast_replay):
            response = self.client.post('/monitor/demo/alert')
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def wait_for_alert(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            alarms = self.controller.engine.alerts(limit=100)
            if alarms:
                self.assertGreaterEqual(alarms[0]['votes'], 2)
                self.assertEqual(alarms[0]['votes'], len(alarms[0]['voters']))
                return alarms[0]
            time.sleep(.03)
        self.fail('K3 replay did not produce an actual model-voted alert')

    def test_cold_demo_trains_only_normal_k1_then_creates_a_scored_k3_alert(self):
        result = self.start_fast_demo()
        self.assertTrue(result['simulated'])
        self.assertEqual('K3', result['scenario'])
        baseline = result['baseline']
        self.assertEqual('K1', baseline['source'])
        self.assertEqual(300, baseline['scaler']['fit_rows'])
        # Stored timestamps are UTC, so compare instants rather than date text.
        self.assertEqual(datetime.fromisoformat(baseline_records()[0]['timestamp']),
                         datetime.fromisoformat(baseline['source_start']))
        alert = self.wait_for_alert()
        self.assertEqual('K3', alert['scenario'])
        self.assertEqual(-1, alert['label'])
        self.assertEqual(baseline['id'], alert['baseline_id'])
        self.assertEqual(4, len(alert['raw_predictions']))
        self.assertTrue(any(item['material'] for item in alert['evidence']))

    def test_existing_k1_models_and_history_remain_unchanged_and_persist(self):
        baseline = self.controller.train(baseline_records(), source='K1', contamination=.02)
        old = self.controller.engine.ingest([scenario_records('K1', rows=30)[0]], source='K1')[0]
        result = self.start_fast_demo()
        self.wait_for_alert()
        self.controller.stop()
        self.assertEqual(baseline['id'], result['baseline']['id'])
        self.assertEqual(baseline['scaler'], self.controller.engine.baseline()['scaler'])
        self.assertEqual(.02, self.controller.engine.baseline()['contamination'])
        self.assertEqual(1, len(self.controller.engine.catalog()['baselines']))
        self.controller.close()
        self.controller = MonitoringController(self.path)
        stored = self.controller.engine.history(limit=1000)
        previous = next(point for point in stored if point['id'] == old['id'])
        self.assertEqual(old['scores'], previous['scores'])
        self.assertTrue(any(point.get('scenario') == 'K3' and point['votes'] >= 2 for point in stored))

    def test_demo_refuses_custom_baseline_without_overwriting_it(self):
        baseline = self.controller.train(baseline_records(), source='operator.csv')
        response = self.client.post('/monitor/demo/alert')
        self.assertEqual(409, response.status_code)
        self.assertEqual(baseline['id'], self.controller.engine.baseline()['id'])
        self.assertEqual(1, len(self.controller.engine.catalog()['baselines']))
        self.assertEqual([], self.controller.engine.history())

    def test_demo_refuses_live_context_even_after_live_source_has_stopped(self):
        baseline = self.controller.train(baseline_records(), source='K1')
        self.controller.start_live(session_id='producer')
        self.assertEqual(409, self.client.post('/monitor/demo/alert').status_code)
        self.controller.stop()
        self.assertEqual('stopped', self.controller.collector_status()['status'])
        self.assertEqual(409, self.client.post('/monitor/demo/alert').status_code)
        self.assertEqual('live', self.controller.collector_status()['mode'])
        self.assertEqual(baseline['id'], self.controller.engine.baseline()['id'])
        self.assertEqual([], self.controller.engine.history())

    def test_incompatible_k1_time_window_is_rejected_before_source_changes(self):
        # A label/source name alone must not bypass the held-out time check.
        baseline = self.controller.train(scenario_records('K1', rows=30), source='K1')
        before = self.controller.collector_status()
        response = self.client.post('/monitor/demo/alert')
        self.assertEqual(422, response.status_code)
        self.assertEqual(before, self.controller.collector_status())
        self.assertEqual(baseline['id'], self.controller.engine.baseline()['id'])
        self.assertEqual([], self.controller.engine.history())


if __name__ == '__main__':
    unittest.main()
