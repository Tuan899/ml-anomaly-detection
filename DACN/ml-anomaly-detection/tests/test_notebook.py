"""Execute the saved notebook without browser, display or fabricated outputs."""

import json
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
assert run.metadata["rows"] == 19
assert run.metadata["train_rows"] == 13
assert run.metadata["test_rows"] == 6
assert set(run.metadata["model_names"]) == {"mad", "isolation_forest", "lof", "one_class_svm"}
assert run.metadata["features"] == ["value"]
for parameters in run.metadata["parameters"].values():
    assert parameters["preprocessing"]["fit_rows"] == 13
    np.testing.assert_allclose(parameters["preprocessing"]["mean"], [run.frame.iloc[:13]["value"].mean()])
np.testing.assert_array_equal(run.predictions["timestamp"], run.frame.iloc[13:]["timestamp"])
assert namespace["test_annotation_count"] == 0
assert not namespace["quality_supported"]
assert namespace["metrics_table"].empty
assert any("no anomalies" in warning for warning in run.metadata["warnings"])
assert "Chưa hiển thị precision/recall/F1" in captured.getvalue()
assert len(namespace["trend_plot"].data) > 0
assert len(namespace["seasonality_plot"].data) > 0
plt.close("all")
print("Notebook cells completed: 19 rows, 13 train, 6 test; no quality claim.")
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
                    cwd=directory, capture_output=True, text=True, timeout=60,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertIn("Notebook cells completed", completed.stdout)


if __name__ == "__main__":
    unittest.main()
