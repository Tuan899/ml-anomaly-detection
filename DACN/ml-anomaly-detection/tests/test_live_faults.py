"""Bounded real-workload orchestration tested without a database connection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import ssl
import sys
from tempfile import TemporaryDirectory
from threading import Event, Lock, Thread
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import live_faults as live


SECRET = "NEVER_STORE_FAULT_PASSWORD"
USERNAME = "private-fault-account"


class FakeClock:
    def __init__(self):
        self.value = 0.0
        self.waits = []
        self.lock = Lock()

    def __call__(self):
        with self.lock:
            return self.value

    def advance(self, seconds):
        with self.lock:
            self.value += seconds

    def wait(self, seconds):
        self.waits.append(seconds)
        self.advance(seconds)
        return False


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.last_sql = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def execute(self, sql):
        self.last_sql = sql
        self.connection.statements.append((self.connection.clock(), sql))
        if self.connection.execute_error:
            raise self.connection.execute_error
        if sql == "SELECT SLEEP(0.2)" and self.connection.slow_clock:
            self.connection.clock.advance(0.2)

    def fetchone(self):
        return (0,) if self.last_sql == "SELECT SLEEP(0.2)" else (1,)


class FakeConnection:
    def __init__(self, clock, *, execute_error=None, close_failures=0):
        self.clock = clock
        self.slow_clock = isinstance(clock, FakeClock)
        self.execute_error = execute_error
        self.close_failures = close_failures
        self.close_attempts = 0
        self.closed = False
        self.statements = []

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.close_attempts += 1
        if self.close_attempts <= self.close_failures:
            raise RuntimeError("close failed " + SECRET)
        self.closed = True


class DriverError(Exception):
    pass


class LiveFaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "monitoring.sqlite3"
        self.runners = []
        self.addCleanup(self._close_runners)

    def _close_runners(self):
        for runner in reversed(self.runners):
            runner.close()

    def config(self, **changes):
        fields = dict(enabled=True, host="localhost", user=USERNAME,
                      password=SECRET, no_tls=True)
        fields.update(changes)
        return live.FaultConfig(**fields)

    def runner(self, *, clock=None, wait=None, config=None):
        result = live.LiveFaultRunner(self.db, config=config or self.config(), clock=clock, wait=wait)
        self.runners.append(result)
        return result

    def driver(self, connect):
        return SimpleNamespace(VERSION=(1, 2, 3), connect=Mock(side_effect=connect),
                               err=SimpleNamespace(OperationalError=DriverError))

    def await_done(self, runner):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            thread = runner._thread
            if thread is None or not thread.is_alive():
                return runner.status()
            thread.join(timeout=.02)
        self.fail("Mock workload did not terminate")

    def test_target_identity_is_normalized_and_has_no_credential_material(self):
        expected = hashlib.sha256(b"db.example.test:3306").hexdigest()
        self.assertEqual(expected, live.database_target_id(" DB.EXAMPLE.TEST. ", 3306))
        self.assertEqual(live.database_target_id("[::1]", 3306),
                         live.database_target_id("0:0:0:0:0:0:0:1", 3306))
        for port in (True, 0, 65536, 3306.0, "3306"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                live.database_target_id("localhost", port)

    def test_disabled_and_missing_dedicated_env_never_use_collector_credentials(self):
        config = live.FaultConfig.from_env({"MYSQL_HOST": "localhost", "MYSQL_USER": "collector",
                                           "MYSQL_PASSWORD": SECRET})
        runner = self.runner(config=config)
        status = runner.status()
        self.assertFalse(status["enabled"])
        self.assertFalse(status["configured"])
        self.assertIsNone(status["target"])
        with patch.object(live, "pymysql") as driver, self.assertRaises(ValueError):
            runner.start("K2")
        driver.connect.assert_not_called()
        bad = live.FaultConfig.from_env({"ANOMALY_FAULT_ENABLED": "1", "FAULT_MYSQL_PORT": SECRET})
        self.assertFalse(bad.configured)
        self.assertNotIn(SECRET, repr(bad))

    def test_environment_target_and_loopback_only_plaintext_policy(self):
        config = live.FaultConfig.from_env({"ANOMALY_FAULT_ENABLED": "1", "FAULT_MYSQL_HOST": "LOCALHOST",
            "FAULT_MYSQL_USER": USERNAME, "FAULT_MYSQL_PASSWORD": SECRET,
            "FAULT_MYSQL_NO_TLS": "1", "FAULT_MYSQL_DATABASE": "demo"})
        self.assertTrue(config.configured)
        self.assertEqual("demo", config.target()["database"])
        self.assertNotIn(SECRET, repr(config))
        self.assertNotIn(USERNAME, repr(config))
        self.assertFalse(self.config(host="remote.example.test").configured)
        self.assertFalse(self.config(ssl_ca="ca.pem").configured)

    def test_verified_tls_and_bounded_connection_options(self):
        clock = FakeClock()
        connection = FakeConnection(clock)
        driver = self.driver(lambda **_: connection)
        runner = self.runner(config=self.config(host="db.example.test", no_tls=False),
                             clock=clock, wait=clock.wait)
        with patch.object(live, "pymysql", driver):
            runner.start("K2", duration_seconds=1, rate_per_second=1)
            self.await_done(runner)
        options = driver.connect.call_args.kwargs
        self.assertFalse(options["local_infile"])
        self.assertFalse(options["ssl_disabled"])
        self.assertTrue(options["autocommit"])
        self.assertEqual(ssl.CERT_REQUIRED, options["ssl"].verify_mode)
        self.assertTrue(options["ssl"].check_hostname)
        self.assertEqual(2, options["connect_timeout"])
        self.assertEqual(2, options["read_timeout"])
        self.assertEqual(2, options["write_timeout"])
        self.assertTrue(connection.closed)

    def test_k2_rate_is_total_paced_select_rate_and_never_writes(self):
        clock = FakeClock()
        connection = FakeConnection(clock)
        runner = self.runner(clock=clock, wait=clock.wait)
        with patch.object(live, "pymysql", self.driver(lambda **_: connection)) as driver:
            runner.start("K2", duration_seconds=2, rate_per_second=4, connections=20)
            job = self.await_done(runner)["job"]
        self.assertEqual("completed", job["status"])
        self.assertEqual(8, job["counters"]["successful_queries"])
        self.assertEqual(1, driver.connect.call_count)
        self.assertEqual([(index / 4, "SELECT 1") for index in range(8)], connection.statements)
        self.assertTrue(all(delay > 0 for delay in clock.waits))
        self.assertTrue(connection.closed)

    def test_k4_sets_session_only_and_counts_completed_sleeps_not_inferred_metrics(self):
        clock = FakeClock()
        connection = FakeConnection(clock)
        runner = self.runner(clock=clock, wait=clock.wait)
        with patch.object(live, "pymysql", self.driver(lambda **_: connection)):
            runner.start("K4", duration_seconds=1)
            job = self.await_done(runner)["job"]
        sql = [sql for _, sql in connection.statements]
        self.assertEqual("SET SESSION long_query_time = 0.05", sql[0])
        self.assertEqual(["SELECT SLEEP(0.2)"] * 5, sql[1:])
        self.assertEqual(5, job["counters"]["slow_queries"])
        self.assertEqual(5, job["counters"]["successful_queries"])
        self.assertTrue(connection.closed)

    def test_k3_holds_requested_connections_and_uses_unique_invalid_users(self):
        clock = FakeClock()
        opened = []
        invalid = []
        def connect(**options):
            if options["user"] != USERNAME:
                invalid.append(options)
                raise DriverError(1045 if len(invalid) % 2 else 1698, SECRET)
            connection = FakeConnection(clock)
            opened.append(connection)
            return connection
        runner = self.runner(clock=clock, wait=clock.wait)
        with patch.object(live, "pymysql", self.driver(connect)):
            runner.start("K3", duration_seconds=3, connections=4, auth_failures=3)
            job = self.await_done(runner)["job"]
        self.assertEqual("completed", job["status"])
        self.assertEqual(4, job["counters"]["opened_connections"])
        self.assertEqual(3, job["counters"]["expected_auth_failures"])
        self.assertEqual(3, len({options["user"] for options in invalid}))
        self.assertTrue(all(len(options["user"]) <= 32 for options in invalid))
        self.assertTrue(all(options["password"] != SECRET for options in invalid))
        self.assertTrue(all(connection.closed for connection in opened))
        self.assertTrue(all(not connection.statements for connection in opened))
        self.assertEqual([3], clock.waits)

    def test_non_authentication_error_fails_job_and_closes_held_connections(self):
        clock = FakeClock()
        opened = []
        def connect(**options):
            if options["user"] != USERNAME:
                raise DriverError(2003, "cannot connect " + SECRET)
            connection = FakeConnection(clock)
            opened.append(connection)
            return connection
        runner = self.runner(clock=clock, wait=clock.wait)
        with patch.object(live, "pymysql", self.driver(connect)):
            runner.start("K3", duration_seconds=1, connections=2, auth_failures=1)
            job = self.await_done(runner)["job"]
        self.assertEqual("failed", job["status"])
        self.assertEqual(0, job["counters"]["expected_auth_failures"])
        self.assertTrue(all(connection.closed for connection in opened))
        self.assertNotIn(SECRET, str(job))

    def test_failure_during_queries_closes_connection_and_never_persists_secret(self):
        clock = FakeClock()
        connection = FakeConnection(clock, execute_error=DriverError(999, SECRET + USERNAME))
        runner = self.runner(clock=clock, wait=clock.wait)
        with patch.object(live, "pymysql", self.driver(lambda **_: connection)):
            runner.start("K2", duration_seconds=1)
            status = self.await_done(runner)
        self.assertEqual("failed", status["job"]["status"])
        self.assertTrue(connection.closed)
        serialized = json.dumps(status)
        self.assertNotIn(SECRET, serialized)
        self.assertNotIn(USERNAME, serialized)
        with sqlite3.connect(self.db) as db:
            payloads = str(db.execute("SELECT * FROM live_fault_jobs").fetchall())
        self.assertNotIn(SECRET, payloads)
        self.assertNotIn(USERNAME, payloads)
        self.assertNotIn(SECRET.encode(), self.db.read_bytes())

    def test_audit_failure_after_connection_open_still_closes_connection(self):
        clock = FakeClock()
        connection = FakeConnection(clock)
        runner = self.runner(clock=clock, wait=clock.wait)
        with patch.object(live, "pymysql", self.driver(lambda **_: connection)), \
             patch.object(runner, "_bump", side_effect=sqlite3.OperationalError("audit " + SECRET)):
            runner.start("K2", duration_seconds=1)
            job = self.await_done(runner)["job"]
        self.assertEqual("failed", job["status"])
        self.assertTrue(connection.closed)
        self.assertNotIn(SECRET, str(job))

    def test_stop_cancels_hold_wait_closes_connections_and_guards_single_job(self):
        opened = []
        holding = Event()
        runner = self.runner()
        def wait(seconds):
            holding.set()
            return runner._stop_event.wait(seconds)
        runner._wait = wait
        def connect(**_):
            connection = FakeConnection(time.monotonic)
            opened.append(connection)
            return connection
        with patch.object(live, "pymysql", self.driver(connect)):
            runner.start("K3", duration_seconds=60, connections=3)
            self.assertTrue(holding.wait(2))
            with self.assertRaises(RuntimeError):
                runner.start("K2")
            status = runner.stop()
        self.assertEqual("stopped", status["job"]["status"])
        self.assertTrue(all(connection.closed for connection in opened))
        self.assertFalse(runner._thread.is_alive())
        self.assertEqual(status, runner.stop())

    def test_stopping_is_not_done_while_worker_is_still_closing(self):
        clock = FakeClock()
        closing = Event()
        release = Event()
        connection = FakeConnection(clock)
        def close():
            closing.set()
            release.wait(2)
            connection.closed = True
        connection.close = close
        runner = self.runner(clock=clock, wait=clock.wait)
        with patch.object(live, "pymysql", self.driver(lambda **_: connection)):
            runner.start("K2", duration_seconds=1, rate_per_second=1)
            self.assertTrue(closing.wait(2))
            with patch.object(live, "_STOP_JOIN_SECONDS", .01), self.assertRaises(RuntimeError):
                runner.stop()
            self.assertEqual("stopping", runner.status()["job"]["status"])
            with self.assertRaises(RuntimeError):
                runner.start("K2")
            release.set()
            status = runner.stop()
        self.assertEqual("stopped", status["job"]["status"])
        self.assertTrue(connection.closed)

    def test_failed_close_blocks_next_job_until_stop_retries_cleanup(self):
        clock = FakeClock()
        connection = FakeConnection(clock, close_failures=2)
        runner = self.runner(clock=clock, wait=clock.wait)
        with patch.object(live, "pymysql", self.driver(lambda **_: connection)):
            runner.start("K2", duration_seconds=1, rate_per_second=1)
            status = self.await_done(runner)
            self.assertEqual("stopping", status["job"]["status"])
            self.assertFalse(connection.closed)
            with self.assertRaises(RuntimeError):
                runner.start("K2")
            with self.assertRaises(RuntimeError):
                runner.stop()
            self.assertFalse(connection.closed)
            status = runner.stop()
        self.assertEqual("failed", status["job"]["status"])
        self.assertTrue(connection.closed)
        self.assertNotIn(SECRET, str(status))

    def test_options_are_strictly_bounded_and_do_not_accept_booleans(self):
        runner = self.runner()
        for field, values in {"duration_seconds": [True, 0, 61, 1.0],
                              "rate_per_second": [False, 0, 501],
                              "connections": [True, 0, 21],
                              "auth_failures": [False, -1, 4]}.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    runner.start("K2", **{field: value})
        for scenario in ("K1", "K2; DROP TABLE demo", True):
            with self.subTest(scenario=scenario), self.assertRaises(ValueError):
                runner.start(scenario)
        self.assertIsNone(runner.status()["job"])

    def test_completed_job_survives_restart_and_unfinished_job_becomes_interrupted(self):
        clock = FakeClock()
        runner = self.runner(clock=clock, wait=clock.wait)
        with patch.object(live, "pymysql", self.driver(lambda **_: FakeConnection(clock))):
            runner.start("K2", duration_seconds=1, rate_per_second=1)
            original = self.await_done(runner)["job"]
        runner.close()
        second = self.runner()
        self.assertEqual(original, second.status()["job"])
        second.close()
        with sqlite3.connect(self.db) as db:
            original.update(status="running", finished_at=None)
            db.execute("UPDATE live_fault_jobs SET payload = ? WHERE id = ?",
                       (json.dumps(original), original["id"]))
        restarted = self.runner()
        interrupted = restarted.status()["job"]
        self.assertEqual("interrupted", interrupted["status"])
        self.assertIsNotNone(interrupted["finished_at"])
        self.assertEqual(original["id"], interrupted["id"])
        self.assertEqual(original["counters"], interrupted["counters"])


if __name__ == "__main__":
    unittest.main()
