"""Execute the saved notebook without browser, display or fabricated outputs."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


PROJECT = Path(__file__).resolve().parents[1]
NOTEBOOK = PROJECT / "notebooks" / "exploratory.ipynb"

EXECUTE_NOTEBOOK = r'''
import contextlib
from io import StringIO
import json
from pathlib import Path
import sys
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import plotly.io as pio

pio.renderers.default = "json"
notebook_path = Path(sys.argv[1])
notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
namespace = {"__name__": "__main__"}
captured = StringIO()
with contextlib.redirect_stdout(captured), patch.object(plt, "show", side_effect=lambda: plt.close("all")), \
     patch("plotly.basedatatypes.BaseFigure.show", side_effect=AssertionError("Notebook opened an interactive renderer")):
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            source = "".join(cell["source"])
            exec(compile(source, f"{notebook_path}:cell-{index}", "exec"), namespace)

run = namespace["run"]
assert namespace["ROOT"] == notebook_path.parent.parent
assert run.metadata["rows"] == 4032
assert run.metadata["train_rows"] == 3550
assert run.metadata["test_rows"] == 482
assert set(run.metadata["model_names"]) == {"mad", "isolation_forest", "lof"}
assert run.metadata["features"] == ["value"]
assert run.metadata["contamination"] == 1 / 3550
assert run.metadata["random_state"] == 42
assert "StandardScaler" not in json.dumps(run.metadata["parameters"])
np.testing.assert_array_equal(run.predictions["timestamp"], run.frame.iloc[3550:]["timestamp"])
assert (run.frame.iloc[:3550]["is_anomaly"] == -1).sum() == 1
assert (run.predictions["is_anomaly"] == -1).sum() == 1
assert {value.strftime("%Y-%m-%d %H:%M:%S")
        for value in run.frame.loc[run.frame["is_anomaly"] == -1, "timestamp"]} == {
            "2014-02-26 22:05:00", "2014-02-27 17:15:00"}
baseline = run.metadata["reference_baseline"]
assert baseline["fit_rows"] == 4032
assert baseline["rows"] == 4032
assert len(baseline["predictions"]) == 4032
assert np.asarray(baseline["confusion_matrix"]).sum() == 4032
np.testing.assert_array_equal(
    namespace["baseline_predictions"]["mad_prediction"].iloc[3550:],
    run.predictions["mad_prediction"],
)
for name in run.metadata["model_names"]:
    matrix = np.asarray(run.metadata["confusion_matrices"][name])
    assert matrix.sum() == 482
    assert matrix[1].sum() == 1
assert namespace["test_annotation_count"] == 1
assert namespace["quality_supported"]
assert namespace["metrics_table"].shape == (3, 3)
assert namespace["reference_metrics_table"]["số_điểm_đánh_giá"].tolist() == [4032, 482, 482]
assert "MAD vẫn dùng thống kê toàn bộ dữ liệu" in captured.getvalue()
plt.close("all")
print("Notebook cells completed: 4032 rows, 3550 train, 482 test; evaluation scopes explicit.")
'''


class NotebookTests(unittest.TestCase):
    def test_saved_notebook_has_no_execution_outputs(self):
        notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                self.assertIsNone(cell["execution_count"])
                self.assertEqual(cell["outputs"], [])

    def test_cells_run_sequentially_from_supported_working_directories(self):
        directories = (PROJECT.parents[1], PROJECT.parent, PROJECT, NOTEBOOK.parent)
        for directory in directories:
            with self.subTest(cwd=directory):
                completed = subprocess.run(
                    [sys.executable, "-c", EXECUTE_NOTEBOOK, str(NOTEBOOK)],
                    cwd=directory, capture_output=True, text=True, encoding="utf-8", timeout=90,
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertIn("Notebook cells completed", completed.stdout)


if __name__ == "__main__":
    unittest.main()
