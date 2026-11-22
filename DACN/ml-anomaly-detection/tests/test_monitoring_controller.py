"""Concurrent mode changes must never leave an untracked replay writer alive."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Lock
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_scenarios import baseline_records
from src.monitoring_controller import MonitoringController


class MonitoringControllerConcurrencyTests(unittest.TestCase):
    def test_concurrent_start_transitions_join_previous_writer_and_stop_all_writes(self):
        with TemporaryDirectory() as directory:
            controller = MonitoringController(Path(directory) / 'monitor.sqlite3')
            controller.train(baseline_records())
            original_stop, original_worker = controller.stop, controller._replay_worker
            counts = {'active': 0, 'maximum': 0}
            workers, events = [], []
            count_lock = Lock()

            def slow_stop():
                result = original_stop()
                # Expose the former race deterministically: without a lock
                # covering the WHOLE start transition, concurrent requests all
                # finish stop() here before any starts its new replay worker.
                time.sleep(.03)
                return result

            def tracked_worker(records, loop, stop):
                with count_lock:
                    counts['active'] += 1
                    counts['maximum'] = max(counts['maximum'], counts['active'])
                    events.append(stop)
                try:
                    return original_worker(records, loop, stop)
                finally:
                    with count_lock:
                        counts['active'] -= 1

            try:
                with patch.object(controller, 'stop', new=slow_stop), \
                     patch.object(controller, '_replay_worker', new=tracked_worker):
                    with ThreadPoolExecutor(max_workers=8) as requests:
                        futures = [requests.submit(controller.start_replay, scenario='K1',
                                                   interval_seconds=.1, rows=30) for _ in range(8)]
                        for future in futures:
                            future.result(timeout=10)
                            worker = controller._thread
                            if worker is not None:
                                workers.append(worker)
                    controller.stop()
                self.assertEqual(1, counts['maximum'], 'Concurrent starts created overlapping replay writers')
                self.assertEqual(0, counts['active'])
                self.assertTrue(all(not worker.is_alive() for worker in workers))
                before = len(controller.engine.history(limit=1000))
                time.sleep(.2)
                self.assertEqual(before, len(controller.engine.history(limit=1000)))
                self.assertEqual('stopped', controller.collector_status()['status'])
            finally:
                # Even a regression must not leak daemon writers into the rest
                # of the suite; each captured worker gets its own stop token.
                for event in events:
                    event.set()
                for worker in workers:
                    worker.join(timeout=2)
                controller.close()


if __name__ == '__main__':
    unittest.main()
