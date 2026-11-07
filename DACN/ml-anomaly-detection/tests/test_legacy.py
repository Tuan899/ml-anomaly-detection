"""Checks for the import-safe synthetic legacy entry point."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from src import pipeline


LEGACY_PATH = Path(__file__).resolve().parents[2] / "anomaly_detection.py"


def load_legacy():
    spec = importlib.util.spec_from_file_location("legacy_synthetic_demo", LEGACY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LegacyDemoTests(unittest.TestCase):
    def test_labels_match_inserted_spikes_in_training_and_held_out_rows(self):
        demo = load_legacy()
        frame = demo.make_synthetic_data()
        self.assertEqual(frame.index[frame["is_anomaly"] == -1].tolist(), [1000, 2500, 3100, 3600])
        split = int(len(frame) * 0.7)
        self.assertTrue((frame.iloc[:split]["is_anomaly"] == -1).any())
        self.assertTrue((frame.iloc[split:]["is_anomaly"] == -1).any())
        for index, value in demo.SYNTHETIC_SPIKES.items():
            self.assertEqual(frame.loc[index, "value"], value)
        self.assertLess(frame.loc[3600, "value"], frame["value"].median())

    def test_generator_is_reproducible_and_leaves_global_rng_untouched(self):
        demo = load_legacy()
        before = np.random.get_state()
        first = demo.make_synthetic_data(seed=42)
        after = np.random.get_state()
        self.assertEqual(before[0], after[0])
        np.testing.assert_array_equal(before[1], after[1])
        self.assertEqual(before[2:], after[2:])
        pd.testing.assert_frame_equal(first, demo.make_synthetic_data(seed=42))
        self.assertFalse(first["value"].equals(demo.make_synthetic_data(seed=43)["value"]))

    def test_import_does_not_generate_fit_or_plot(self):
        plotting = MagicMock()
        with patch.dict(sys.modules, {"matplotlib.pyplot": plotting}), \
                patch("numpy.random.default_rng", side_effect=AssertionError("generated on import")), \
                patch("numpy.random.seed", side_effect=AssertionError("global seed on import")), \
                patch.object(pipeline, "run_detection", side_effect=AssertionError("fitted on import")):
            demo = load_legacy()
        self.assertTrue(callable(demo.run_demo))
        plotting.show.assert_not_called()

    def test_run_uses_shared_train_only_pipeline_and_detects_both_tails(self):
        result = load_legacy().run_demo()
        split = int(4032 * 0.7)
        self.assertEqual(result.metadata["train_rows"], split)
        self.assertEqual(result.metadata["test_rows"], 4032 - split)
        self.assertEqual(set(result.metrics), {"mad", "isolation_forest", "lof", "one_class_svm"})
        pd.testing.assert_frame_equal(
            result.predictions[["timestamp", "value", "is_anomaly"]],
            result.frame.iloc[split:][["timestamp", "value", "is_anomaly"]].reset_index(drop=True),
        )
        for name in result.metadata["model_names"]:
            self.assertEqual(result.metadata["parameters"][name]["preprocessing"]["fit_rows"], split)
        spikes = result.predictions[result.predictions["is_anomaly"] == -1]
        self.assertEqual(len(spikes), 2)
        self.assertEqual(spikes["mad_prediction"].tolist(), [-1, -1])
        self.assertIn("Synthetic", result.metadata["data_source"])
        self.assertTrue(any("real data" in warning for warning in result.metadata["warnings"]))

    def test_cli_resolves_shared_pipeline_from_another_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.run(
                [sys.executable, str(LEGACY_PATH)], cwd=directory,
                capture_output=True, text=True, encoding="utf-8", timeout=60, check=True,
            )
        output = json.loads(process.stdout)
        self.assertEqual(output["metadata"]["rows"], 4032)
        self.assertEqual(output["metadata"]["train_rows"], 2822)
        self.assertEqual(output["metadata"]["test_rows"], 1210)
        self.assertEqual(output["metadata"]["synthetic_seed"], 42)


if __name__ == "__main__":
    unittest.main()
