r"""Render report figures from the saved, measured venv evaluation only.

Run with C:\Users\User\DACN\.venv\Scripts\python.exe <this file>.
No MySQL connection, model fitting, or modification of evaluation inputs occurs.
"""
from __future__ import annotations

from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
EVALUATION = HERE.parent
PROJECT = HERE.parents[3]
REPORT = json.loads((EVALUATION / "evaluation.json").read_text(encoding="utf-8"))
MODEL_LABELS = {"mad": "MAD", "isolation_forest": "Isolation Forest",
                "lof": "LOF", "one_class_svm": "One-Class SVM"}
AVAILABLE_FONTS = {font.name for font in font_manager.fontManager.ttflist}
FONT = "Times New Roman" if "Times New Roman" in AVAILABLE_FONTS else "DejaVu Serif"
plt.rcParams.update({"font.family": FONT, "font.size": 9, "axes.titlesize": 9.5,
                     "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
                     "figure.facecolor": "white", "savefig.facecolor": "white",
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.unicode_minus": False})
BLUE, RED, GRAY = "#155e9a", "#b91c1c", "#e9edf1"


def save(fig, stem):
    fig.savefig(HERE / f"{stem}.png", dpi=240)
    fig.savefig(HERE / f"{stem}.pdf")
    plt.close(fig)


def incident_bounds(frame):
    anomaly_times = frame.loc[frame["label"].eq(-1), "timestamp"]
    if anomaly_times.empty:
        return None
    return anomaly_times.min(), anomaly_times.max() + pd.Timedelta(minutes=1)


def architecture():
    fig, ax = plt.subplots(figsize=(6.3, 3.6))
    fig.subplots_adjust(left=.015, right=.985, top=.96, bottom=.07)
    ax.set(xlim=(0, 10), ylim=(0, 6.2))
    ax.axis("off")

    def box(x, y, w, h, title, body, color="#f4f8fc"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=.06,rounding_size=.08",
                                   facecolor=color, edgecolor="#8ba6ba", linewidth=.8))
        ax.text(x+w/2, y+h-.21, title, ha="center", va="top", weight="bold", fontsize=9)
        ax.text(x+w/2, y+.42, body, ha="center", va="center", fontsize=8.7, linespacing=1.3)

    def arrow(a, b):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=10,
                                    linewidth=.9, color="#506574", connectionstyle="arc3"))

    box(.18, 4.85, 2.9, 1.18, "Đầu vào mô phỏng", "CSV: 1.440 mẫu × 5 chỉ số\nNhãn chỉ dùng đánh giá")
    box(3.64, 4.85, 2.9, 1.18, "Kiểm tra dữ liệu", "Giá trị hợp lệ, thời gian duy nhất\nSắp xếp theo thời gian")
    box(7.05, 4.85, 2.7, 1.18, "Chia theo thời gian", "1.008 mẫu train (70%)\n432 mẫu test (30%)")
    box(.48, 2.7, 4.1, 1.40, "Train: dữ liệu quá khứ", "Fit StandardScaler và 4 mô hình\nƯớc lượng ngưỡng lọc từ train")
    box(5.4, 2.7, 4.1, 1.40, "Test: dữ liệu chưa thấy", "Transform bằng scaler của train\nDự đoán và giữ nhãn gốc")
    box(.48, .46, 4.1, 1.40, "Hai đầu ra được lưu riêng", "Dự đoán thô của mô hình\nCảnh báo = dự đoán thô ∩ lệch ngưỡng")
    box(5.4, .46, 4.1, 1.40, "Kết quả có thể đối chiếu", "TP, FP, FN, TN; Precision, Recall, F1\nThời gian; CSV và JSON")
    arrow((3.14, 5.44), (3.57, 5.44))
    arrow((6.6, 5.44), (6.98, 5.44))
    arrow((8.4, 4.77), (7.58, 4.18))
    arrow((7.15, 4.76), (3.48, 4.18))
    arrow((4.66, 3.4), (5.32, 3.4))
    arrow((7.4, 2.62), (3.6, 1.94))
    arrow((4.66, 1.16), (5.32, 1.16))
    ax.text(5, .02, "Toàn bộ mô hình và thống kê tiền xử lý chỉ học từ train.",
            ha="center", va="center", fontsize=8, color="#334155")
    save(fig, "fig3_1_experiment_pipeline")


def datasets():
    specs = [
        ("mysql_normal.csv", "queries_per_second", "(a) Bình thường", "Truy vấn/giây"),
        ("mysql_query_spike.csv", "queries_per_second", "(b) Tăng truy vấn", "Truy vấn/giây"),
        ("mysql_connection_spike.csv", "connections", "(c) Tăng kết nối", "Số kết nối"),
        ("mysql_latency_spike.csv", "response_time_ms", "(d) Tăng độ trễ", "Độ trễ (ms)"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(6.3, 4.1))
    fig.subplots_adjust(left=.105, right=.985, top=.93, bottom=.20, hspace=.64, wspace=.38)
    for ax, (name, metric, title, ylabel) in zip(axes.flat, specs):
        frame = pd.read_csv(PROJECT / "data" / name, parse_dates=["timestamp"])
        split = REPORT["datasets"][name]["metadata"]["train_rows"]
        boundary = frame.loc[split, "timestamp"]
        ax.axvspan(frame.timestamp.iloc[0], boundary, color=GRAY, zorder=0)
        bounds = incident_bounds(frame)
        if bounds:
            ax.axvspan(*bounds, color=RED, alpha=.14, zorder=1)
        ax.plot(frame.timestamp, frame[metric], linewidth=.7, color=BLUE, zorder=2)
        ax.axvline(boundary, color="#475569", linestyle="--", linewidth=.75)
        ax.set(title=title, ylabel=ylabel, xlim=(frame.timestamp.iloc[0], frame.timestamp.iloc[-1]))
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 6, 12, 18]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.grid(axis="y", color="#dfe5eb", linewidth=.45)
    fig.legend(handles=[Patch(facecolor=GRAY, label="Train: 1.008 mẫu"),
                        Line2D([], [], color="#475569", linestyle="--", linewidth=.8, label="Bắt đầu test"),
                        Patch(facecolor=RED, alpha=.14, label="Nhãn bất thường")],
               loc="lower center", bbox_to_anchor=(.5, .058), ncol=3, frameon=False, fontsize=8)
    fig.text(.5, .025, "Dữ liệu mô phỏng ngày 01/10/2026; chu kỳ 1 phút; test: 432 mẫu mỗi file.",
             ha="center", fontsize=8)
    save(fig, "fig3_2_synthetic_datasets")


def confusion_matrices():
    fig, axes = plt.subplots(2, 2, figsize=(6.3, 4.1))
    fig.subplots_adjust(left=.14, right=.97, top=.83, bottom=.20, wspace=.52, hspace=1.0)
    rows = [x for x in REPORT["comparison"]
            if x["dataset"] == "mysql_query_spike.csv" and x["scope"] == "operational_alert"]
    for ax, row in zip(axes.flat, rows):
        matrix = np.array([[row["TN"], row["FP"]], [row["FN"], row["TP"]]])
        ax.imshow(matrix, cmap="Blues", vmin=0, vmax=388, aspect="auto")
        for i in range(2):
            for j in range(2):
                ax.text(j, i, str(matrix[i, j]), ha="center", va="center", fontsize=11,
                        color="white" if matrix[i, j] > 194 else "#172337")
        ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["Bình thường", "Bất thường"],
               yticklabels=["Bình thường", "Bất thường"], xlabel="Dự đoán", ylabel="Thực tế",
               title=MODEL_LABELS[row["algorithm"]])
        ax.tick_params(length=0, pad=3)
    fig.text(.5, .975, "Tăng truy vấn: ma trận nhầm lẫn của cảnh báo sau lọc", ha="center", va="top", fontsize=10)
    fig.text(.5, .025, "432 mẫu test: 388 bình thường, 44 bất thường. Ô: [[TN, FP], [FN, TP]].",
             ha="center", fontsize=8)
    save(fig, "fig4_1_query_confusion_matrices")


def query_timeline():
    frame = pd.read_csv(EVALUATION / "mysql_query_spike_predictions.csv", parse_dates=["timestamp"])
    fig, axes = plt.subplots(5, 1, figsize=(6.3, 3.9), sharex=True,
                             gridspec_kw={"height_ratios": [2.3, .7, .7, .7, .7]})
    fig.subplots_adjust(left=.19, right=.97, top=.91, bottom=.19, hspace=.13)
    bounds = incident_bounds(frame)
    for ax in axes:
        ax.axvspan(*bounds, color=RED, alpha=.13)
        ax.set_xlim(frame.timestamp.iloc[0], frame.timestamp.iloc[-1])
        ax.grid(axis="x", color="#e2e8f0", linewidth=.4)
    axes[0].plot(frame.timestamp, frame.queries_per_second, color=BLUE, linewidth=.9)
    axes[0].set_ylabel("Truy vấn/giây")
    axes[0].set_title("Tăng truy vấn: nhãn sự cố và cảnh báo sau lọc trên tập test", pad=8)
    for ax, (model, label) in zip(axes[1:], MODEL_LABELS.items()):
        selected = frame[f"{model}_prediction"].eq(-1)
        times = frame.loc[selected, "timestamp"]
        ax.scatter(times, np.ones(len(times)), marker="|", s=38, linewidths=.85, color=BLUE)
        ax.set(ylim=(.6, 1.4), yticks=[], ylabel=label)
        ax.yaxis.label.set(rotation=0, ha="right", va="center", fontsize=8)
        ax.spines["left"].set_visible(False)
        ax.text(.99, .5, f"{selected.sum()} cảnh báo", transform=ax.transAxes,
                ha="right", va="center", fontsize=8, color="#334155")
    axes[-1].xaxis.set_major_locator(mdates.HourLocator(interval=1))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.legend(handles=[Patch(facecolor=RED, alpha=.13, label="Nhãn bất thường: 44 mẫu"),
                        Line2D([], [], color=BLUE, marker="|", linestyle="None", markersize=8, label="Cảnh báo sau lọc")],
               loc="lower center", bbox_to_anchor=(.55, .065), ncol=2, frameon=False, fontsize=8)
    fig.text(.55, .024, "Dữ liệu mô phỏng; IF bỏ sót toàn bộ 44 mẫu bất thường ở cấu hình mặc định.",
             ha="center", fontsize=8)
    save(fig, "fig4_2_query_alert_timeline")


if __name__ == "__main__":
    architecture()
    datasets()
    confusion_matrices()
    query_timeline()
    from PIL import Image
    print(f"Font: {FONT}")
    for path in sorted(HERE.glob("*.png")):
        with Image.open(path) as im:
            print(f"{path.name}: {im.size[0]}x{im.size[1]}")
