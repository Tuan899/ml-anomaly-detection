"""Read-only protocol, reset rebasing, retry identity and credential isolation."""
from __future__ import annotations

from pathlib import Path
import ssl
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import live_collector as live
from src.live_faults import database_target_id


def snapshot(q, uptime, at, *, slow=0, errors=0, connections=30):
    return ({'Questions': q, 'Uptime': uptime, 'Threads_connected': connections,
             'Slow_queries': slow, 'Aborted_connects': errors}, at,
            f'2026-11-21T00:00:{int(at):02d}+00:00', 2.0)


class FakeCursor:
    def __init__(self):
        self.sql = []
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass
    def execute(self, sql):
        self.sql.append(sql)


class FakeConnection:
    def __init__(self):
        self.current = FakeCursor()
        self.closed = False
    def cursor(self):
        return self.current
    def close(self):
        self.closed = True


class LiveCollectorTests(unittest.TestCase):
    def config(self, **changes):
        values = dict(host='db.internal.test', user='readonly-monitor', password='DO_NOT_LOG_THIS', ssl_disabled=True)
        values.update(changes)
        return live.CollectorConfig(**values)

    def test_interval_rates_use_elapsed_time_and_reset_is_not_zero_sample(self):
        before = snapshot(1000, 100, 1, slow=10, errors=2)
        after = snapshot(1200, 102, 3, slow=12, errors=3, connections=28)
        observation = live.interval_observation(before, after)
        self.assertEqual(100, observation['queries_per_second'])
        self.assertEqual(2, observation['slow_queries'])
        self.assertEqual(1, observation['connection_errors'])
        self.assertEqual(28, observation['connections'])
        self.assertIsNone(live.interval_observation(after, snapshot(10, 1, 4)))

    def test_continuous_sampling_skips_reset_then_uses_new_reference(self):
        connection = FakeConnection()
        driver = SimpleNamespace(VERSION=(1, 2, 3), connect=Mock(return_value=connection))
        values = [snapshot(1000, 100, 0), snapshot(10, 1, 1),
                  snapshot(30, 2, 2, slow=1), snapshot(45, 3, 3, slow=1)]
        statuses = []
        with patch.object(live.protocol, 'pymysql', driver), \
             patch.object(live.protocol, '_status_snapshot', side_effect=values):
            collector = live.LiveCollector(self.config(), wait=lambda _: False, status_callback=statuses.append)
            records = list(collector.samples(max_samples=2))
        self.assertEqual([20, 15], [row['queries_per_second'] for row in records])
        self.assertEqual([1, 0], [row['slow_queries'] for row in records])
        self.assertEqual(['connected', 'counter_reset'], statuses)
        self.assertEqual(['SET SESSION TRANSACTION READ ONLY'], connection.current.sql)
        self.assertTrue(connection.closed)
        self.assertTrue(all('label' not in row for row in records))

    def test_connection_is_read_only_with_verified_tls_and_redacted_config(self):
        connection = FakeConnection()
        driver = SimpleNamespace(VERSION=(1, 2, 3), connect=Mock(return_value=connection))
        with patch.object(live.protocol, 'pymysql', driver), \
             patch.object(live.protocol, '_status_snapshot', side_effect=[snapshot(10, 1, 1), snapshot(20, 2, 2)]):
            config = self.config(ssl_disabled=False)
            self.assertNotIn('DO_NOT_LOG_THIS', repr(config))
            list(live.LiveCollector(config, wait=lambda _: False).samples(max_samples=1))
        options = driver.connect.call_args.kwargs
        self.assertFalse(options['local_infile'])
        self.assertTrue(options['autocommit'])
        self.assertEqual(ssl.CERT_REQUIRED, options['ssl'].verify_mode)
        self.assertTrue(options['ssl'].check_hostname)
        self.assertFalse(options['ssl_disabled'])

    def test_driver_error_is_not_exposed_in_status_events(self):
        driver = SimpleNamespace(VERSION=(1, 2, 3), connect=Mock(side_effect=RuntimeError('password=DO_NOT_LOG_THIS')))
        events = []
        with patch.object(live.protocol, 'pymysql', driver):
            rows = list(live.LiveCollector(self.config(), wait=lambda _: True, status_callback=events.append).samples(max_samples=1))
        self.assertEqual([], rows)
        self.assertEqual(['connection_error'], events)
        self.assertNotIn('DO_NOT_LOG_THIS', str(events))

    def test_http_retry_reuses_event_id_and_sends_no_connection_credentials(self):
        requests = []
        sample_attempts = 0
        def post(url, *, json=None):
            nonlocal sample_attempts
            requests.append((url, json))
            if url.endswith('/samples'):
                sample_attempts += 1
                status = 500 if sample_attempts == 1 else 200
            else:
                status = 200
            return httpx.Response(status, json={}, request=httpx.Request('POST', url))
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.post.side_effect = post
        stop = Mock()
        stop.is_set.return_value = False
        stop.wait.return_value = False
        record = live.interval_observation(snapshot(10, 1, 1), snapshot(20, 2, 2))
        with patch.object(live.httpx, 'Client', return_value=client), \
             patch.object(live.LiveCollector, 'samples', return_value=(dict(record) for _ in range(1))):
            count = live.run_collector(self.config(), max_samples=1, stop_event=stop)
        self.assertEqual(1, count)
        posts = [body for url, body in requests if url.endswith('/samples')]
        self.assertEqual(2, len(posts))
        self.assertEqual(posts[0]['records'][0]['event_id'], posts[1]['records'][0]['event_id'])
        self.assertNotIn('DO_NOT_LOG_THIS', str(requests))
        self.assertNotIn('db.internal.test', str(requests))
        self.assertNotIn('readonly-monitor', str(requests))
        self.assertEqual(database_target_id('db.internal.test', 3306), requests[0][1]['target_id'])
        self.assertEqual(64, len(requests[0][1]['target_id']))
        self.assertTrue(requests[-1][0].endswith('/monitor/source/stop'))
        self.assertEqual(posts[0]['session_id'], requests[-1][1]['session_id'])
        self.assertFalse(any(url.endswith('/replay/stop') for url, _ in requests))


if __name__ == '__main__':
    unittest.main()
