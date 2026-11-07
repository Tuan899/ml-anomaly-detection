"""Exercise the HTTP client contract and failures without a live server."""

from copy import deepcopy
from io import BytesIO
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import httpx
import pandas as pd
from fastapi.testclient import TestClient

from backend.api import app
from frontend.api_client import BackendError, detect_via_api


CSV = (
    b"timestamp,value,label\n"
    b"2026-01-01,49.8,1\n2026-01-02,50,1\n2026-01-03,50.2,1\n"
    b"2026-01-04,49.9,1\n2026-01-05,50.1,1\n2026-01-06,50,1\n"
    b"2026-01-07,49.8,1\n2026-01-08,95,-1\n2026-01-09,50,1\n2026-01-10,50.1,1\n"
)


class ApiClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = TestClient(app)
        response = cls.api.post("/detect", params={"models": "mad", "label_col": "label", "include_context": True},
                                files={"file": ("observations.csv", CSV, "text/csv")})
        response.raise_for_status()
        cls.payload = response.json()

    @classmethod
    def tearDownClass(cls):
        cls.api.close()

    def call_client(self):
        return detect_via_api(CSV, "observations.csv", model_names=["mad"], label_col="label")

    def test_http_round_trip_preserves_context_predictions_and_exports(self):
        def forward(url, **kwargs):
            kwargs.pop("trust_env")
            kwargs.pop("timeout")
            return self.api.post(url, **kwargs)

        with patch("frontend.api_client.httpx.post", side_effect=forward) as post:
            result = self.call_client()
        post.assert_called_once()
        self.assertEqual(10, len(result.frame))
        self.assertEqual(3, len(result.predictions))
        self.assertEqual(pd.Timestamp("2026-01-08"), result.predictions.timestamp.iloc[0])
        self.assertEqual({"precision": 1.0, "recall": 1.0, "f1": 1.0}, result.metrics["mad"])
        pd.testing.assert_series_equal(result.frame.iloc[7:].value.reset_index(drop=True), result.predictions.value)
        self.assertEqual(3, len(pd.read_csv(BytesIO(result.export_csv()))))
        self.assertEqual(1, len(result.summary()["anomalies"]["mad"]))

    def test_backend_url_configuration_preserves_query_and_file(self):
        with patch.dict(os.environ, {"ANOMALY_API_URL": " http://localhost:8123/api/ "}), \
                patch("frontend.api_client.httpx.post", return_value=httpx.Response(200, json=self.payload)) as post:
            self.call_client()
        args, kwargs = post.call_args
        self.assertEqual(("http://localhost:8123/api/detect",), args)
        self.assertEqual("mad", kwargs["params"]["models"])
        self.assertTrue(kwargs["params"]["include_context"])
        self.assertEqual("label", kwargs["params"]["label_col"])
        self.assertEqual(("observations.csv", CSV, "text/csv"), kwargs["files"]["file"])
        self.assertFalse(kwargs["trust_env"])
        self.assertEqual(3, kwargs["timeout"].connect)

    def test_reference_mode_uses_fixed_protocol_through_actual_api(self):
        project = Path(__file__).resolve().parents[1]
        content = (project / "data" / "nab_cpu_labeled.csv").read_bytes()

        def forward(url, **kwargs):
            kwargs.pop("trust_env")
            kwargs.pop("timeout")
            return self.api.post(url, **kwargs)

        with patch("frontend.api_client.httpx.post", side_effect=forward) as post:
            result = detect_via_api(content, "nab.csv", analysis_mode="notebook_reference")
        params = post.call_args.kwargs["params"]
        self.assertEqual("notebook_reference", params["analysis_mode"])
        self.assertEqual("mad,isolation_forest,lof", params["models"])
        self.assertEqual(3550, params["split_index"])
        self.assertEqual(1 / 3550, params["contamination"])
        self.assertEqual("is_anomaly", params["label_col"])
        self.assertFalse(params["include_time"])
        self.assertEqual(4032, len(result.frame))
        self.assertEqual(482, len(result.predictions))
        self.assertEqual([[2964, 1066], [0, 2]], result.metadata["reference_baseline"]["confusion_matrix"])
        self.assertEqual(4032, len(result.metadata["reference_baseline"]["predictions"]))

    def test_reference_request_rejects_a_generic_or_incomplete_response(self):
        with patch("frontend.api_client.httpx.post", return_value=httpx.Response(200, json=self.payload)):
            with self.assertRaisesRegex(BackendError, "không đúng định dạng"):
                detect_via_api(CSV, "data.csv", analysis_mode="notebook_reference")

    def test_reference_rejects_malformed_baseline_and_matrices_before_display(self):
        project = Path(__file__).resolve().parents[1]
        content = (project / "data" / "nab_cpu_labeled.csv").read_bytes()
        response = self.api.post(
            "/detect", params={"analysis_mode": "notebook_reference", "include_context": True},
            files={"file": ("nab.csv", content, "text/csv")},
        )
        response.raise_for_status()
        valid = response.json()
        baseline = ("metadata", "reference_baseline")
        cases = [
            ("missing baseline", baseline, None),
            ("missing median", baseline + ("median",), None),
            ("zero MAD", baseline + ("mad",), 0),
            ("wrong threshold", baseline + ("threshold",), 4),
            ("missing metrics", baseline + ("metrics",), None),
            ("invalid metric", baseline + ("metrics", "f1"), 2),
            ("empty record objects", baseline + ("predictions",), [{}] * 4032),
            ("missing timestamp", baseline + ("predictions", 0, "timestamp"), None),
            ("invalid timestamp", baseline + ("predictions", 0, "timestamp"), "not-a-date"),
            ("infinite value", baseline + ("predictions", 0, "value"), "Infinity"),
            ("boolean label", baseline + ("predictions", 0, "is_anomaly"), True),
            ("invalid prediction", baseline + ("predictions", 0, "mad_prediction"), 0),
            ("nonfinite score", baseline + ("predictions", 0, "mad_score"), "NaN"),
            ("nonfinite z score", baseline + ("predictions", 0, "z_score"), "-Infinity"),
            ("mismatched observation", baseline + ("predictions", 0, "value"), 42),
            ("mismatched test prediction", baseline + ("predictions", 3550, "mad_prediction"),
             -valid["predictions"][0]["mad_prediction"]),
            ("malformed full matrix", baseline + ("confusion_matrix",), [[4032]]),
            ("negative full count", baseline + ("confusion_matrix",), [[2964, 1066], [-1, 3]]),
            ("boolean full count", baseline + ("confusion_matrix",), [[2964, 1066], [False, 2]]),
            ("inconsistent full matrix", baseline + ("confusion_matrix",), [[2963, 1067], [0, 2]]),
            ("missing test matrices", ("metadata", "confusion_matrices"), None),
            ("malformed test matrix", ("metadata", "confusion_matrices", "lof"), [[481, 0], [0, 0]]),
        ]
        for name, path, value in cases:
            payload = deepcopy(valid)
            target = payload
            for key in path[:-1]:
                target = target[key]
            if value is None:
                del target[path[-1]]
            else:
                target[path[-1]] = value
            with self.subTest(case=name), patch("frontend.api_client.httpx.post", return_value=httpx.Response(200, json=payload)):
                with self.assertRaisesRegex(BackendError, "không đúng định dạng"):
                    detect_via_api(content, "nab.csv", analysis_mode="notebook_reference")

    def test_valid_unsigned_context_and_signed_test_values_are_accepted(self):
        content = (
            b"timestamp,value\n2026-01-01,18446744073709551615\n"
            b"2026-01-02,2\n2026-01-03,1\n2026-01-04,99\n"
        )

        def forward(url, **kwargs):
            kwargs.pop("trust_env")
            kwargs.pop("timeout")
            return self.api.post(url, **kwargs)

        with patch("frontend.api_client.httpx.post", side_effect=forward):
            result = detect_via_api(content, "unsigned.csv", model_names=["mad"], train_fraction=.75)
        self.assertEqual(18446744073709551615, result.frame.value.iloc[0])
        self.assertEqual(99, result.predictions.value.iloc[0])
        self.assertEqual(1, len(result.predictions))

    def test_nanosecond_timestamps_survive_http_and_json_export(self):
        content = ("timestamp,value\n" + "".join(
            f"2026-01-01T00:00:00.{index:09d},{index + 1}\n" for index in range(5)
        )).encode("utf-8")

        def forward(url, **kwargs):
            kwargs.pop("trust_env")
            kwargs.pop("timeout")
            return self.api.post(url, **kwargs)

        with patch("frontend.api_client.httpx.post", side_effect=forward):
            result = detect_via_api(content, "nanoseconds.csv", model_names=["mad"], train_fraction=.6)
        self.assertEqual(5, result.frame.timestamp.nunique())
        self.assertEqual(2, result.predictions.timestamp.nunique())
        exported = result.summary(date_unit="ns")["predictions"]
        self.assertNotEqual(exported[0]["timestamp"], exported[1]["timestamp"])
        self.assertEqual(1, pd.Timestamp(exported[1]["timestamp"]).value - pd.Timestamp(exported[0]["timestamp"]).value)

    def test_connection_and_timeout_failures_are_actionable(self):
        for error, message in (
            (httpx.ConnectError("refused"), "Không kết nối được BE"),
            (httpx.ReadTimeout("slow"), "BE xử lý quá lâu"),
            (httpx.WriteError("closed"), "Không kết nối được BE"),
        ):
            with self.subTest(error=type(error).__name__), \
                    patch("frontend.api_client.httpx.post", side_effect=error) as post:
                with self.assertRaisesRegex(BackendError, message):
                    self.call_client()
                post.assert_called_once()

    def test_http_errors_are_translated_without_showing_server_internals(self):
        cases = [
            (422, {"detail": "Labels must be explicit -1 (anomaly) or 1 (normal), without missing values"}, "Nhãn phải dùng 1"),
            (422, {"detail": [{"loc": ["query", "train_fraction"], "msg": "invalid"}]}, "kiểm tra lại dữ liệu"),
            (413, {"detail": "CSV upload exceeds 10 MiB"}, "10 MiB"),
            (500, {"detail": "secret internal traceback"}, "HTTP 500"),
            (404, {"detail": "Not Found"}, "HTTP 404"),
        ]
        for status, payload, expected in cases:
            with self.subTest(status=status, payload=payload), \
                    patch("frontend.api_client.httpx.post", return_value=httpx.Response(status, json=payload)):
                with self.assertRaisesRegex(BackendError, expected) as caught:
                    self.call_client()
                self.assertNotIn("traceback", str(caught.exception))

    def test_wrong_or_incomplete_backend_response_is_rejected(self):
        broken = []
        missing_context = deepcopy(self.payload)
        del missing_context["context"]
        broken.append(missing_context)
        mismatched_partition = deepcopy(self.payload)
        mismatched_partition["metadata"]["test_rows"] = 100
        broken.append(mismatched_partition)
        wrong_model = deepcopy(self.payload)
        wrong_model["metadata"]["model_names"] = ["lof"]
        broken.append(wrong_model)
        wrong_time = deepcopy(self.payload)
        wrong_time["predictions"][0]["timestamp"] = "2020-01-01T00:00:00"
        broken.append(wrong_time)
        wrong_metric = deepcopy(self.payload)
        wrong_metric["metrics"]["mad"]["f1"] = 4.2
        broken.append(wrong_metric)
        wrong_prediction = deepcopy(self.payload)
        wrong_prediction["predictions"][0]["mad_prediction"] = 0
        broken.append(wrong_prediction)
        for payload in broken:
            with self.subTest(payload=payload), \
                    patch("frontend.api_client.httpx.post", return_value=httpx.Response(200, json=payload)):
                with self.assertRaisesRegex(BackendError, "không đúng định dạng"):
                    self.call_client()
        with patch("frontend.api_client.httpx.post", return_value=httpx.Response(200, text="<html>wrong service</html>")):
            with self.assertRaisesRegex(BackendError, "không đúng định dạng"):
                self.call_client()

    def test_invalid_backend_address_never_sends_uploaded_data(self):
        for address in ("", "ftp://localhost:8000", "http://user:password@localhost:8000", "http://localhost:8000/?token=x"):
            with self.subTest(address=address), patch.dict(os.environ, {"ANOMALY_API_URL": address}), \
                    patch("frontend.api_client.httpx.post") as post:
                with self.assertRaisesRegex(BackendError, "Địa chỉ BE chưa hợp lệ"):
                    self.call_client()
                post.assert_not_called()

    def test_frontend_client_import_does_not_load_training_pipeline(self):
        project = Path(__file__).resolve().parents[1]
        code = "import sys; import frontend.api_client; assert 'src.pipeline' not in sys.modules; assert 'src.models' not in sys.modules"
        completed = subprocess.run([sys.executable, "-c", code], cwd=project, capture_output=True, text=True, timeout=30)
        self.assertEqual(0, completed.returncode, completed.stderr)


if __name__ == "__main__":
    unittest.main()
