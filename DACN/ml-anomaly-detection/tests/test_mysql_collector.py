"""Collector contract and failure checks with a fake protocol, not a live server."""

from types import SimpleNamespace
import ssl
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from src import mysql_collector as collector


def snapshots():
    return [
        {"Questions": str(q), "Threads_connected": str(c), "Slow_queries": str(s),
         "Aborted_connects": str(e), "Uptime": str(u)}
        for q, c, s, e, u in (
            (1000, 8, 80, 40, 100), (1100, 9, 82, 41, 102),
            (1250, 8, 83, 41, 105), (1450, 20, 83, 42, 109), (1700, 8, 87, 42, 114),
        )
    ]


class FakeCursor:
    def __init__(self, values, *, error=None):
        self.values = iter(values)
        self.error = error
        self.sql = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    def execute(self, sql):
        self.sql.append(sql)
        if self.error:
            raise self.error

    def fetchone(self):
        return (1,)

    def fetchall(self):
        return list(next(self.values).items())


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def close(self):
        self.closed = True


class MySQLCollectorTests(unittest.TestCase):
    def setUp(self):
        self.cursor = FakeCursor(snapshots())
        self.connection = FakeConnection(self.cursor)
        self.connect = Mock(return_value=self.connection)
        self.driver = SimpleNamespace(VERSION=(1, 2, 3, "final"), connect=self.connect)
        self.patches = [
            patch.object(collector, "pymysql", self.driver),
            patch.object(collector.time, "sleep"),
            patch.object(collector.time, "monotonic", side_effect=[100, 102, 105, 109, 114]),
            patch.object(collector.time, "perf_counter", side_effect=[v for _ in range(5) for v in (0, .002)]),
        ]
        for active in self.patches:
            active.start()
            self.addCleanup(active.stop)

    def collect(self, **overrides):
        kwargs = {"host": "localhost", "user": "monitor", "password": "test-secret",
                  "samples": 4, "interval_seconds": 1., "ssl_disabled": True}
        kwargs.update(overrides)
        return collector.collect_mysql_metrics(**kwargs)

    def test_rates_use_actual_elapsed_and_preexisting_counts_are_excluded(self):
        frame = self.collect()
        self.assertEqual(list(frame.columns), list(collector.METRIC_COLUMNS))
        self.assertEqual(frame["queries_per_second"].tolist(), [50., 50., 50., 50.])
        self.assertEqual(frame["slow_queries"].tolist(), [2, 1, 0, 4])
        self.assertEqual(frame["connection_errors"].tolist(), [1, 0, 1, 0])
        self.assertEqual(frame["connections"].tolist(), [9, 8, 20, 8])
        self.assertEqual(frame["response_time_ms"].tolist(), [2., 2., 2., 2.])
        self.assertIsNotNone(pd.to_datetime(frame["timestamp"], utc=True).dt.tz)
        self.assertNotIn("label", frame)
        self.assertTrue(frame.attrs["sampling"]["initial_snapshot_excluded"])
        self.assertNotIn("test-secret", str(frame.attrs))
        self.assertTrue(self.connection.closed)
        self.assertTrue(self.cursor.closed)

    def test_read_only_sql_allowlist_and_connection_options(self):
        injection_like_name = "db`; DROP TABLE example; --"
        self.collect(database=injection_like_name, user="monitor'; --")
        self.assertEqual(set(self.cursor.sql), {
            "SET SESSION TRANSACTION READ ONLY", "SHOW GLOBAL STATUS", "SELECT 1",
        })
        self.assertEqual(self.cursor.sql[0], "SET SESSION TRANSACTION READ ONLY")
        self.assertEqual(self.cursor.sql.count("SHOW GLOBAL STATUS"), 5)
        options = self.connect.call_args.kwargs
        self.assertEqual(options["database"], injection_like_name)
        self.assertEqual(options["user"], "monitor'; --")
        self.assertTrue(options["autocommit"])
        self.assertFalse(options["local_infile"])
        self.assertEqual(options["read_timeout"], 5)
        self.assertNotIn("init_command", options)

    def test_progress_runs_after_each_emitted_sample(self):
        callback = Mock()
        self.collect(progress_callback=callback)
        self.assertEqual([call.args for call in callback.call_args_list], [(1, 4), (2, 4), (3, 4), (4, 4)])

    def test_verified_tls_is_default(self):
        self.collect(ssl_disabled=False)
        options = self.connect.call_args.kwargs
        context = options["ssl"]
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertFalse(options["ssl_disabled"])

    def test_custom_ca_is_loaded_without_disabling_verification(self):
        context = ssl.create_default_context()
        with patch.object(collector.ssl, "create_default_context", return_value=context) as create:
            self.collect(ssl_disabled=False, ssl_ca="test-ca.pem")
        create.assert_called_once_with(cafile="test-ca.pem")
        self.assertIs(self.connect.call_args.kwargs["ssl"], context)

    def test_every_required_missing_counter_fails_without_zero_substitution(self):
        for name in collector._REQUIRED_COUNTERS:
            with self.subTest(counter=name):
                values = snapshots()
                del values[0][name]
                self.connection.fake_cursor = FakeCursor(values)
                with self.assertRaisesRegex(collector.MySQLCollectionError, name):
                    self.collect()
                self.assertTrue(self.connection.closed)

    def test_resets_fail_entire_batch_instead_of_returning_negative_deltas(self):
        for name in collector._CUMULATIVE_COUNTERS:
            with self.subTest(counter=name):
                values = snapshots()
                values[1][name] = "0"
                self.connection.fake_cursor = FakeCursor(values)
                with patch.object(collector.time, "monotonic", side_effect=[100, 102]), \
                        patch.object(collector.time, "perf_counter", side_effect=[0, .002, 1, 1.002]), \
                        self.assertRaisesRegex(collector.MySQLCollectionError, "đặt lại"):
                    self.collect()
                self.assertTrue(self.connection.closed)

    def test_decreasing_connection_gauge_is_allowed(self):
        self.assertEqual(self.collect()["connections"].iloc[-1], 8)

    def test_invalid_counter_values_fail(self):
        for value in ("NaN", "-1", "1.5", "password=test-secret", "１２"):
            with self.subTest(value=value):
                values = snapshots()
                values[0]["Questions"] = value
                self.connection.fake_cursor = FakeCursor(values)
                with self.assertRaisesRegex(collector.MySQLCollectionError, "số nguyên") as raised:
                    self.collect()
                self.assertNotIn("test-secret", str(raised.exception))

    def test_no_elapsed_time_fails_instead_of_inventing_qps(self):
        with patch.object(collector.time, "monotonic", return_value=100), \
                self.assertRaisesRegex(collector.MySQLCollectionError, "khoảng thời gian"):
            self.collect()

    def test_invalid_probe_fails(self):
        self.cursor.fetchone = lambda: (0,)
        with self.assertRaisesRegex(collector.MySQLCollectionError, "SELECT 1"):
            self.collect()
        self.assertTrue(self.connection.closed)

    def test_access_errors_do_not_expose_raw_driver_or_credentials(self):
        self.cursor.error = RuntimeError(1045, "password=test-secret, user=private-account")
        with self.assertRaisesRegex(collector.MySQLCollectionError, "từ chối") as raised:
            self.collect()
        self.assertNotIn("test-secret", str(raised.exception))
        self.assertNotIn("private-account", str(raised.exception))
        self.assertTrue(raised.exception.__suppress_context__)
        self.assertTrue(self.connection.closed)
        self.assertTrue(self.cursor.closed)

    def test_connect_errors_are_sanitized(self):
        self.connect.side_effect = RuntimeError("password=test-secret")
        with self.assertRaises(collector.MySQLCollectionError) as raised:
            self.collect()
        self.assertNotIn("test-secret", str(raised.exception))

    def test_missing_or_old_driver_produces_actionable_error(self):
        for driver in (None, SimpleNamespace(VERSION=(1, 1, 2), connect=Mock())):
            with self.subTest(driver=driver), patch.object(collector, "pymysql", driver), \
                    self.assertRaisesRegex(collector.MySQLCollectionError, "PyMySQL"):
                self.collect()
        self.connect.assert_not_called()

    def test_invalid_configuration_is_rejected_before_connecting(self):
        for overrides in (
            {"host": ""}, {"user": " "}, {"password": None}, {"database": 42},
            {"port": True}, {"port": 0}, {"port": 65536},
            {"samples": 3}, {"samples": 601}, {"samples": True}, {"samples": 4.0},
            {"interval_seconds": 0.099}, {"interval_seconds": 61},
            {"interval_seconds": float("nan")}, {"interval_seconds": True},
            {"connect_timeout": 0}, {"connect_timeout": float("inf")},
            {"ssl_disabled": "yes"}, {"ssl_ca": ""}, {"ssl_ca": "ca.pem"},
            {"progress_callback": "invalid"},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(collector.MySQLCollectionError):
                self.collect(**overrides)
        self.connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
