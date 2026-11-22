"""Write the exact fixed synthetic scenarios used by the monitoring API."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.demo_scenarios import METRICS, baseline_records, scenario_catalog, scenario_records


def main() -> None:
    output = ROOT / "resources" / "replay"
    output.mkdir(parents=True, exist_ok=True)
    columns = ["timestamp", *METRICS, "label", "scenario"]
    datasets = {"baseline_K1.csv": baseline_records(), **{
        f'{item["id"]}.csv': scenario_records(item["id"]) for item in scenario_catalog()}}
    files = {}
    for name, records in datasets.items():
        path = output / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)
        files[name] = {"rows": len(records), "injected_anomalies": sum(row["label"] == -1 for row in records),
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {"provenance": "Fixed synthetic scenarios, not observed server measurements.",
        "generator": "scripts/generate_replay_scenarios.py", "sampling_interval_seconds": 1,
        "training": "baseline_K1.csv only; replay files have disjoint, later source timestamps.",
        "labels": {"1": "generated normal observation", "-1": "predefined injected incident"},
        "incident_policy": "K2–K4 replace indices [rows//3, rows//2), independent of estimators.",
        "fault_injection": "Changes simulated measurements only; no workload SQL is executed.",
        "files": files}
    (ROOT / "docs" / "replay_scenarios_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(files, indent=2))


if __name__ == "__main__":
    main()
