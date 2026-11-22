"""Preflight, malformed-response, and event-loop regression checks."""

import asyncio
from copy import deepcopy
import os
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import httpx

from backend import api
from frontend.api_client import (
    BackendError, MAX_UPLOAD_BYTES, compare_via_api, detect_via_api,
)


CSV = (
    b"timestamp,value,label\n"
    b"2026-01-01,1,1\n2026-01-02,2,1\n2026-01-03,1,1\n"
    b"2026-01-04,2,1\n2026-01-05,1,1\n2026-01-06,2,1\n"
    b"2026-01-07,1,1\n2026-01-08,2,1\n2026-01-09,1,1\n2026-01-10,99,-1\n"
)
DBMS_CSV = ("timestamp,queries_per_second,connections,response_time_ms,slow_queries,connection_errors,label\n"
            + "".join(f"2026-01-{day:02d},{50 if day < 10 else 500},8,2,0,0,{1 if day < 10 else -1}\n"
                      for day in range(1, 11))).encode()


class ClientPreflightTests(unittest.TestCase):
    def test_invalid_uploads_never_send_data_for_either_operation(self):
        for content in (b"", None, "timestamp,value", b"x" * (MAX_UPLOAD_BYTES + 1)):
            for operation in ("detect", "normal", "anomalous"):
                with self.subTest(operation=operation, kind=type(content).__name__), \
                        patch("frontend.api_client.httpx.post") as post:
                    with self.assertRaises(BackendError):
                        if operation == "detect":
                            detect_via_api(content, "data.csv")
                        elif operation == "normal":
                            compare_via_api(content, CSV)
                        else:
                            compare_via_api(CSV, content)
                    post.assert_not_called()

    def test_invalid_ports_never_send_data_for_either_operation(self):
        for address in ("http://localhost:0", "http://localhost:65536", "http://localhost:invalid",
                        "http://localhost:-1", "http://[::1"):
            for compare in (False, True):
                with self.subTest(address=address, compare=compare), \
                        patch.dict(os.environ, {"ANOMALY_API_URL": address}), \
                        patch("frontend.api_client.httpx.post") as post:
                    with self.assertRaisesRegex(BackendError, "Địa chỉ BE chưa hợp lệ"):
                        if compare:
                            compare_via_api(CSV, CSV)
                        else:
                            detect_via_api(CSV, "data.csv")
                    post.assert_not_called()


class ClientPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(api.app)
        cls.payload = cls.client.post(
            "/detect", params={"models": "mad", "label_col": "label", "include_context": True},
            files={"file": ("data.csv", CSV, "text/csv")},
        ).json()
        cls.dbms_payload = cls.client.post(
            "/detect", params={"analysis_mode": "dbms", "models": "mad", "label_col": "label",
                               "include_context": True},
            files={"file": ("mysql.csv", DBMS_CSV, "text/csv")},
        ).json()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_booleans_cannot_replace_numeric_observations_labels_predictions_or_scores(self):
        for section, column in (("context", "value"), ("context", "label"),
                                ("predictions", "mad_prediction"), ("predictions", "mad_score")):
            for boolean in (True, False):
                payload = deepcopy(self.payload)
                payload[section][0][column] = boolean
                with self.subTest(section=section, column=column, boolean=boolean), \
                        patch("frontend.api_client.httpx.post", return_value=httpx.Response(200, json=payload)):
                    with self.assertRaisesRegex(BackendError, "không đúng định dạng"):
                        detect_via_api(CSV, "data.csv", model_names=["mad"], label_col="label")

    def test_booleans_cannot_replace_dbms_measurements_raw_predictions_or_deviation_scores(self):
        for section, column in (("context", "connections"), ("predictions", "mad_raw_prediction"),
                                ("predictions", "queries_per_second_deviation"),
                                ("predictions", "queries_per_second_deviation_score"),
                                ("predictions", "max_deviation_score")):
            payload = deepcopy(self.dbms_payload)
            payload[section][0][column] = True
            with self.subTest(section=section, column=column), \
                    patch("frontend.api_client.httpx.post", return_value=httpx.Response(200, json=payload)):
                with self.assertRaisesRegex(BackendError, "không đúng định dạng"):
                    detect_via_api(DBMS_CSV, "mysql.csv", analysis_mode="dbms", model_names=["mad"], label_col="label")

    def test_valid_dbms_boolean_activity_flag_remains_accepted(self):
        with patch("frontend.api_client.httpx.post", return_value=httpx.Response(200, json=self.dbms_payload)):
            run = detect_via_api(DBMS_CSV, "mysql.csv", analysis_mode="dbms", model_names=["mad"], label_col="label")
        self.assertEqual(3, len(run.predictions))
        self.assertEqual("bool", str(run.predictions.activity_deviation.dtype))


class WorkerSerializationTests(unittest.IsolatedAsyncioTestCase):
    async def test_dataframe_serialization_uses_worker_for_detect_and_compare(self):
        loop_thread = threading.get_ident()
        original = api._result_payload
        worker_threads = []

        def serialize(result, include_context):
            worker_threads.append(threading.get_ident())
            self.assertNotEqual(loop_thread, worker_threads[-1])
            return original(result, include_context)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://test") as client:
            with patch("backend.api._result_payload", side_effect=serialize):
                detect = await client.post(
                    "/detect", params={"models": "mad", "include_context": True},
                    files={"file": ("data.csv", CSV, "text/csv")},
                )
                compare = await client.post(
                    "/compare", params={"models": "mad", "include_context": True},
                    files={"normal_file": ("normal.csv", DBMS_CSV, "text/csv"),
                           "anomalous_file": ("anomalous.csv", DBMS_CSV, "text/csv")},
                )
        self.assertEqual(200, detect.status_code, detect.text)
        self.assertEqual(200, compare.status_code, compare.text)
        self.assertEqual(3, len(worker_threads))

    async def test_health_responds_while_analysis_serialization_is_pending(self):
        started, release = threading.Event(), threading.Event()
        original = api._result_payload

        def serialize(result, include_context):
            started.set()
            if not release.wait(3):
                raise RuntimeError("Serialization worker was not released")
            return original(result, include_context)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://test") as client:
            with patch("backend.api._result_payload", side_effect=serialize):
                analysis = asyncio.create_task(client.post(
                    "/detect", params={"models": "mad", "include_context": True},
                    files={"file": ("data.csv", CSV, "text/csv")},
                ))
                try:
                    self.assertTrue(await asyncio.to_thread(started.wait, 2))
                    health = await asyncio.wait_for(client.get("/health"), timeout=1)
                    self.assertEqual({"status": "ok"}, health.json())
                    self.assertFalse(analysis.done())
                finally:
                    release.set()
                    response = await analysis
        self.assertEqual(200, response.status_code, response.text)


if __name__ == "__main__":
    unittest.main()
