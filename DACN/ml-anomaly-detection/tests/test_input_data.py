"""Verify strict CSV recognition without guessing units or changing labels."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.input_data import METRIC_NAMES, prepare_mysql_csv


class MySQLInputDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.read_csv(PROJECT_ROOT / "data" / "mysql_normal.csv").iloc[:20].copy()

    def content(self, frame=None) -> bytes:
        return (self.frame if frame is None else frame).to_csv(index=False).encode("utf-8")

    def test_common_and_vietnamese_aliases_preserve_measurements_and_source(self) -> None:
        aliases = {
            "timestamp": "Thời gian", "queries_per_second": "QPS", "connections": "Threads_connected",
            "response_time_ms": "Độ trễ ms", "slow_queries": "Slow query count",
            "connection_errors": "Lỗi kết nối", "label": "Nhãn",
        }
        renamed = self.frame.rename(columns=aliases)
        original_frame = renamed.copy(deep=True)
        content = self.content(renamed)
        original_hash = sha256(content).hexdigest()
        normalized, preview, mapping = prepare_mysql_csv(content)
        self.assertEqual({value: key for key, value in aliases.items()}, mapping)
        self.assertEqual(original_hash, sha256(content).hexdigest())
        pd.testing.assert_frame_equal(original_frame, renamed)
        self.assertEqual(len(self.frame), len(preview))
        for metric in METRIC_NAMES:
            np.testing.assert_allclose(self.frame[metric], preview[metric], rtol=1e-12)
        self.assertEqual(self.frame["label"].tolist(), preview["label"].tolist())
        self.assertEqual(self.frame["scenario"].tolist(), preview["scenario"].tolist())
        self.assertEqual(list(preview.columns), list(pd.read_csv(BytesIO(normalized)).columns))

    def test_ambiguous_or_missing_headers_are_actionable(self) -> None:
        ambiguous = self.frame.assign(qps=self.frame["queries_per_second"])
        with self.assertRaisesRegex(ValueError, "nhiều cột.*queries_per_second"):
            prepare_mysql_csv(self.content(ambiguous))
        missing = self.frame.drop(columns=["connections"])
        with self.assertRaisesRegex(ValueError, "thiếu.*connections"):
            prepare_mysql_csv(self.content(missing))
        duplicate = self.content().replace(b",connections,", b",queries_per_second,", 1)
        with self.assertRaisesRegex(ValueError, "tên cột duy nhất"):
            prepare_mysql_csv(duplicate)

    def test_invalid_measurements_are_rejected_without_dropping_or_imputing(self) -> None:
        for invalid in ("not-a-number", "", -1, np.inf, True):
            with self.subTest(value=repr(invalid)):
                changed = self.frame.copy()
                changed["connections"] = changed["connections"].astype(object)
                changed.loc[4, "connections"] = invalid
                with self.assertRaisesRegex(ValueError, "số hữu hạn không âm"):
                    prepare_mysql_csv(self.content(changed))
        normalized, valid, _ = prepare_mysql_csv(self.content())
        self.assertEqual(20, len(valid))
        self.assertEqual(20, len(pd.read_csv(BytesIO(normalized))))

    def test_invalid_duplicate_and_numeric_times_are_rejected(self) -> None:
        for changed in (
            self.frame.assign(timestamp=["bad-date"] + self.frame["timestamp"].iloc[1:].tolist()),
            self.frame.assign(timestamp=[self.frame["timestamp"].iloc[1]] + self.frame["timestamp"].iloc[1:].tolist()),
            self.frame.assign(timestamp=list(range(20))),
        ):
            with self.subTest(first_time=changed["timestamp"].iloc[0]):
                with self.assertRaisesRegex(ValueError, "[Tt]hời gian"):
                    prepare_mysql_csv(self.content(changed))

    def test_labels_remain_optional_and_zero_one_meaning_is_never_inferred(self) -> None:
        _, unlabeled, mapping = prepare_mysql_csv(self.content(self.frame.drop(columns=["label"])))
        self.assertNotIn("label", unlabeled)
        self.assertNotIn("label", mapping)
        for labels in ([0, 1] * 10, [True] * 20, ["normal"] * 20):
            with self.subTest(labels=labels[:2]):
                with self.assertRaisesRegex(ValueError, "Nhãn kiểm thử phải dùng 1"):
                    prepare_mysql_csv(self.content(self.frame.assign(label=labels)))
        _, labeled, _ = prepare_mysql_csv(self.content(self.frame.assign(label=[1, -1] * 10)))
        self.assertEqual([1, -1] * 10, labeled["label"].tolist())

    def test_unit_conversion_is_not_guessed_from_seconds_or_generic_latency(self) -> None:
        for unknown in ("latency_seconds", "response_time_s", "latency"):
            with self.subTest(header=unknown):
                changed = self.frame.rename(columns={"response_time_ms": unknown})
                with self.assertRaisesRegex(ValueError, "response_time_ms"):
                    prepare_mysql_csv(self.content(changed))
        changed = self.frame.rename(columns={"response_time_ms": "latency_ms"})
        changed["latency_ms"] = .008
        _, normalized, _ = prepare_mysql_csv(self.content(changed))
        np.testing.assert_allclose(normalized["response_time_ms"], .008)

    def test_sorting_returns_new_chronology_and_requires_enough_observations(self) -> None:
        reversed_frame = self.frame.iloc[::-1]
        content = self.content(reversed_frame)
        _, sorted_frame, _ = prepare_mysql_csv(content)
        self.assertTrue(sorted_frame["timestamp"].is_monotonic_increasing)
        self.assertEqual(content, self.content(reversed_frame))
        np.testing.assert_allclose(self.frame["queries_per_second"], sorted_frame["queries_per_second"])
        with self.assertRaisesRegex(ValueError, "ít nhất 4 bản ghi"):
            prepare_mysql_csv(self.content(self.frame.iloc[:3]))


if __name__ == "__main__":
    unittest.main()
