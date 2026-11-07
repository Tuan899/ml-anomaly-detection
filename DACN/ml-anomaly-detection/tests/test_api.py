"""HTTP contract and validation checks without network access."""

import unittest

from fastapi.testclient import TestClient

from backend.api import app


CSV = b"timestamp,value,label\n2026-01-01,1,1\n2026-01-02,2,1\n2026-01-03,1,1\n2026-01-04,99,-1\n"


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_detect_contract_contains_only_test_predictions(self):
        response = self.client.post("/detect", params={"models": "mad", "split_index": 3, "label_col": "label"},
                                    files={"file": ("sample.csv", CSV, "text/csv")})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["rows"], 4)
        self.assertEqual(payload["metadata"]["train_rows"], 3)
        self.assertEqual(len(payload["predictions"]), 1)
        self.assertEqual(payload["models"], payload["anomalies"])
        self.assertEqual(payload["metrics"]["mad"]["f1"], 1.0)
        self.assertNotIn("context", payload)
        self.assertEqual(payload["predictions"][0]["timestamp"], "2026-01-04T00:00:00.000")

    def test_context_returns_full_timeline_without_expanding_predictions(self):
        response = self.client.post(
            "/detect",
            params={"models": "mad", "split_index": 3, "include_context": True},
            files={"file": ("sample.csv", CSV, "text/csv")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload["context"]), payload["rows"])
        self.assertEqual(len(payload["context"]), 4)
        self.assertEqual(len(payload["predictions"]), payload["metadata"]["test_rows"])
        self.assertEqual(len(payload["predictions"]), 1)
        self.assertEqual(set(payload["context"][0]), {"timestamp", "value"})
        self.assertEqual(payload["context"][0]["timestamp"], "2026-01-01T00:00:00.000000000")
        self.assertEqual(payload["context"][-1]["timestamp"], payload["predictions"][0]["timestamp"])
        self.assertEqual(payload["models"], payload["anomalies"])

    def test_context_uses_selected_columns_and_cleaned_chronological_rows(self):
        csv = (
            b"observed_at,cpu,truth,unselected\n"
            b"2026-01-05,99,-1,discard\n"
            b"2026-01-02,2,1,discard\n"
            b"2026-01-01,1,1,discard\n"
            b"2026-01-03,1,1,discard\n"
            b"2026-01-04,missing,1,discard\n"
        )
        response = self.client.post(
            "/detect",
            params={"models": "mad", "split_index": 3, "include_context": True,
                    "timestamp_col": "observed_at", "value_col": "cpu", "label_col": "truth"},
            files={"file": ("custom.csv", csv, "text/csv")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["metadata"]["cleaning"]["dropped_rows"], 1)
        self.assertEqual(payload["context"], [
            {"observed_at": "2026-01-01T00:00:00.000000000", "cpu": 1.0, "truth": 1},
            {"observed_at": "2026-01-02T00:00:00.000000000", "cpu": 2.0, "truth": 1},
            {"observed_at": "2026-01-03T00:00:00.000000000", "cpu": 1.0, "truth": 1},
            {"observed_at": "2026-01-05T00:00:00.000000000", "cpu": 99.0, "truth": -1},
        ])
        self.assertEqual(len(payload["predictions"]), 1)
        self.assertEqual(payload["predictions"][0]["observed_at"], payload["context"][-1]["observed_at"])
        self.assertEqual(payload["metrics"]["mad"]["f1"], 1.0)

    def test_context_preserves_distinct_submillisecond_timestamps(self):
        timestamps = [f"2026-01-01T00:00:00.00000000{index}" for index in range(1, 6)]
        csv = ("timestamp,value\n" + "\n".join(
            f"{timestamp},{value}" for timestamp, value in zip(timestamps, [1, 2, 1, 99, 2])
        )).encode()
        response = self.client.post(
            "/detect", params={"models": "mad", "split_index": 3, "include_context": True},
            files={"file": ("high_precision.csv", csv, "text/csv")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual([row["timestamp"] for row in payload["context"]], timestamps)
        self.assertEqual([row["timestamp"] for row in payload["predictions"]], timestamps[3:])
        self.assertEqual(len({row["timestamp"] for row in payload["context"]}), 5)

    def test_context_is_omitted_when_explicitly_disabled(self):
        response = self.client.post(
            "/detect", params={"models": "mad", "split_index": 3, "include_context": False},
            files={"file": ("sample.csv", CSV, "text/csv")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("context", response.json())

    def test_invalid_upload_and_parameters_return_422(self):
        cases = [
            ({"models": "unknown"}, CSV),
            ({"models": "mad", "split_index": 2}, CSV),
            ({"models": "mad", "contamination": 0}, CSV),
            ({"models": "mad"}, b""),
            ({"models": "mad"}, b"timestamp,value\ninvalid,1\n"),
            ({"models": "mad"}, b"timestamp,value\n\xff,1\n"),
            ({"models": "mad", "label_col": "label"}, CSV.replace(b"99,-1", b"99,0")),
        ]
        for params, content in cases:
            with self.subTest(params=params, content=content):
                response = self.client.post("/detect", params=params,
                                            files={"file": ("sample.csv", content, "text/csv")})
                self.assertEqual(response.status_code, 422, response.text)

    def test_upload_size_limit(self):
        response = self.client.post("/detect", files={"file": ("large.csv", b"x" * (10 * 1024 * 1024 + 1), "text/csv")})
        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
