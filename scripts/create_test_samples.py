"""Create small, explicit CSV examples for manual validation and detection tests.

All measurements and labels are synthetic. No existing research data is changed.
Run from any directory with: python path/to/scripts/create_test_samples.py
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
import json
from math import pi, sin
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "DACN" / "ml-anomaly-detection" / "data"
SAMPLES_DIR = DATA_DIR / "kiem_thu"
SPIKES = {151: 95.0, 172: 8.0, 185: 90.0}


def normal_rows(count: int) -> list[list[object]]:
    """Bounded measurements around 50, at five-minute intervals, with labels."""
    start = datetime(2026, 10, 1)
    return [
        [
            (start + timedelta(minutes=5 * index)).strftime("%Y-%m-%d %H:%M:%S"),
            round(50 + 1.2 * sin(2 * pi * index / 24) + .3 * sin(2 * pi * index / 7), 3),
            1,
        ]
        for index in range(count)
    ]


def create_samples() -> dict:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    files = []

    def write(name: str, headers: list[str], rows: list[list[object]], **expected) -> None:
        with (SAMPLES_DIR / name).open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(headers)
            writer.writerows(rows)
        files.append({"file": name, "input_rows": len(rows), **expected})

    normal = normal_rows(200)
    write(
        "01_binh_thuong.csv", ["timestamp", "value", "is_anomaly"], normal,
        outcome="valid", clean_rows=200, train_rows=140, test_rows=60,
        mad_alerts=0, note="Nhãn đều bình thường; không dùng Recall/F1 để kết luận chất lượng.",
    )
    anomalies = [row.copy() for row in normal]
    for index, value in SPIKES.items():
        anomalies[index][1:] = [value, -1]
    write(
        "02_bat_thuong_co_nhan.csv", ["timestamp", "value", "is_anomaly"], anomalies,
        outcome="valid_with_known_anomalies", clean_rows=200, train_rows=140,
        test_rows=60, true_test_anomalies=3, mad_alerts=3, mad_true_positives=3,
        mad_false_positives=0, mad_false_negatives=0,
    )

    rows = [row[:2] for row in normal_rows(20)]
    rows[5][0] = "2026-13-40 25:99:00"
    write("03_thoi_gian_sai.csv", ["timestamp", "value"], rows,
          outcome="reject", error_contains="invalid timestamps")

    rows = [row[:2] for row in normal_rows(20)]
    rows[5][0] = rows[4][0]
    write("04_trung_thoi_gian.csv", ["timestamp", "value"], rows,
          outcome="reject", error_contains="Duplicate timestamps")

    rows = [row[:2] for row in normal_rows(20)]
    invalid_values = {2: "", 5: "khong_ro", 8: "inf", 11: "-inf", 14: "NaN", 17: "50,2"}
    for index, value in invalid_values.items():
        rows[index][1] = value
    write(
        "05_gia_tri_loi.csv", ["timestamp", "value"], rows,
        outcome="clean_and_warn", clean_rows=14, dropped_rows=6,
        train_rows=9, test_rows=5,
        note="Dấu phẩy thập phân được đặt trong ngoặc kép: cấu trúc CSV vẫn đúng, giá trị không chuyển thành số được.",
    )

    rows = normal_rows(20)
    for index, row in enumerate(rows):
        row[2] = 1 if index == 18 else 0
    write(
        "06_nhan_sai.csv", ["timestamp", "value", "is_anomaly"], rows,
        outcome="reject_only_when_label_selected", error_contains="Labels must",
        note="Chọn is_anomaly làm nhãn để thấy lỗi. Không chọn nhãn thì vẫn phân tích chỉ số được.",
    )

    rows = [row[:2] + ["du_cot"] for row in normal_rows(5)]
    write("07_sai_so_cot.csv", ["timestamp", "value"], rows,
          outcome="reject", error_contains="fields do not match")

    rows = [row[:2] + [51] for row in normal_rows(5)]
    write("08_ten_cot_trung.csv", ["timestamp", "value", "value"], rows,
          outcome="reject", error_contains="Column names must be unique")

    write("09_qua_it_du_lieu.csv", ["timestamp", "value"],
          [row[:2] for row in normal_rows(3)], outcome="reject",
          error_contains="at least 3 training rows")

    manifest = {
        "source": "Dữ liệu giả lập để kiểm thử chức năng; không phải số liệu đo thực tế.",
        "settings": {"timestamp_col": "timestamp", "value_col": "value", "label_col": "is_anomaly (nếu có)",
                     "model_names": ["mad"], "train_fraction": .7, "contamination": .01,
                     "include_time": False},
        "known_anomalies": [
            {"csv_line": index + 2, "observation": index + 1, "timestamp": normal[index][0], "value": value}
            for index, value in SPIKES.items()
        ],
        "files": files,
    }
    (SAMPLES_DIR / "ket_qua_mong_doi.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    bundle = DATA_DIR / "bo_csv_kiem_thu.zip"
    members = [SAMPLES_DIR / entry["file"] for entry in files]
    members.append(SAMPLES_DIR / "ket_qua_mong_doi.json")
    if (SAMPLES_DIR / "HUONG_DAN.md").exists():
        members.append(SAMPLES_DIR / "HUONG_DAN.md")
    with ZipFile(bundle, "w", compression=ZIP_DEFLATED) as archive:
        for member in members:
            archive.write(member, arcname="kiem_thu/" + member.name)
    return manifest


if __name__ == "__main__":
    result = create_samples()
    print(f"Created {len(result['files'])} CSV examples in {SAMPLES_DIR}")
    print(f"ZIP: {DATA_DIR / 'bo_csv_kiem_thu.zip'}")
