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
