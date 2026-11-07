"""Small, readable Plotly charts backed only by actual run predictions."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from src.monitoring_summary import METRIC_NAMES, METRIC_UNITS, MODEL_NAMES, alert_mask


def _layout(figure, dark=False, height=320):
    ink = "#e5edf9" if dark else "#17233b"
    background = "#111c2e" if dark else "#ffffff"
    grid = "#2e405c" if dark else "#e6edf5"
    figure.update_layout(
        template="plotly_dark" if dark else "plotly_white", height=height,
        font={"family": "Arial, sans-serif", "size": 13, "color": ink},
        paper_bgcolor=background, plot_bgcolor=background,
        hoverlabel={"bgcolor": background, "font": {"color": ink}},
        legend={"orientation": "h", "x": 0, "y": 1.22, "font": {"color": ink}},
        margin={"l": 60, "r": 20, "t": 65, "b": 50}, hovermode="closest",
    )
    figure.update_xaxes(gridcolor=grid, tickfont={"color": ink}, title_font={"color": ink}, automargin=True)
    figure.update_yaxes(gridcolor=grid, tickfont={"color": ink}, title_font={"color": ink}, automargin=True)
    return figure


def build_score_figure(run, model: str, dark: bool = False) -> go.Figure:
    """Negate the original decision margin; no rescaling or model-score mixing."""
    data, time = run.predictions, run.metadata["timestamp_col"]
    if model not in run.metadata.get("model_names", []) or f"{model}_score" not in data:
        raise ValueError("Chưa có điểm của thuật toán được chọn; hãy chạy phân tích lại.")
    score = -data[f"{model}_score"].astype(float)
    raw = data.get(f"{model}_raw_prediction", data[f"{model}_prediction"]).eq(-1)
    flags = data[f"{model}_prediction"].eq(-1)
    labels = np.where(flags, "Cảnh báo sau cấu hình vận hành",
                      np.where(raw, "Mô hình đánh dấu, chưa thành cảnh báo vận hành", "Không có cảnh báo"))
    figure = go.Figure(go.Scatter(
        x=data[time], y=score, customdata=labels, mode="lines", name=f"Điểm {MODEL_NAMES.get(model, model)}",
        line={"color": "#818cf8" if dark else "#4f46e5", "width": 2},
        hovertemplate="%{x|%d/%m/%Y %H:%M:%S} UTC<br>Điểm: %{y:.5g}<br>%{customdata}<extra></extra>",
    ))
    figure.add_trace(go.Scatter(
        x=data.loc[raw, time], y=score.loc[raw], mode="markers", name="Mô hình đánh dấu ban đầu",
        marker={"color": "#d97706", "symbol": "circle-open", "size": 8},
        hovertemplate="%{x|%d/%m/%Y %H:%M:%S} UTC<br>Điểm: %{y:.5g}<extra>Mô hình đánh dấu</extra>",
    ))
    figure.add_trace(go.Scatter(
        x=data.loc[flags, time], y=score.loc[flags], mode="markers", name="Cảnh báo vận hành",
        marker={"color": "#dc2626", "symbol": "x", "size": 10, "line": {"width": 2}},
        hovertemplate="%{x|%d/%m/%Y %H:%M:%S} UTC<br>Điểm: %{y:.5g}<extra>Cần kiểm tra</extra>",
    ))
    figure.add_hline(y=0, line_dash="dash", line_color="#64748b", annotation_text="Mốc quyết định mô hình: 0",
                     annotation_font_color="#cbd5e1" if dark else "#475569")
    figure.update_xaxes(title_text="Thời gian (UTC)", tickformat="%H:%M\n%d/%m", nticks=6)
    figure.update_yaxes(title_text="Điểm bất thường (âm điểm quyết định)")
    return _layout(figure, dark)


def build_count_figure(run, dark: bool = False) -> go.Figure:
    """Count each analyzed observation once, even with several detecting models."""
    count = int(alert_mask(run).sum())
    figure = go.Figure(go.Bar(
        x=["Không có cảnh báo", "Có cảnh báo"], y=[len(run.predictions) - count, count],
        marker_color=["#16a34a", "#dc2626"], text=[len(run.predictions) - count, count],
        textposition="auto", hovertemplate="%{x}<br>%{y} bản ghi<extra></extra>",
    ))
    figure.update_yaxes(title_text="Số bản ghi kiểm tra", rangemode="tozero", dtick=1 if len(run.predictions) < 10 else None)
    return _layout(figure, dark, height=290)


def build_comparison_figure(left, right, metric: str, dark: bool = False) -> go.Figure:
    """Show exact holdout measurements from two runs with their own timestamps."""
    if metric not in METRIC_NAMES:
        raise ValueError("Chỉ số MySQL không được hỗ trợ.")
    figure = go.Figure()
    for run, title, color in ((left, "Hoạt động bình thường", "#16a34a"),
                              (right, "Dữ liệu cần kiểm tra", "#4f46e5")):
        data, time = run.predictions, run.metadata["timestamp_col"]
        flags = alert_mask(run)
        figure.add_trace(go.Scatter(
            x=data[time], y=data[metric], mode="lines", name=title,
            line={"color": color, "width": 2},
            customdata=np.where(flags, "Có cảnh báo", "Không có cảnh báo"),
            hovertemplate=("%{x|%d/%m/%Y %H:%M:%S} UTC<br>" + METRIC_NAMES[metric]
                           + ": %{y}<br>%{customdata}<extra>" + title + "</extra>"),
        ))
        figure.add_trace(go.Scatter(
            x=data.loc[flags, time], y=data.loc[flags, metric], mode="markers",
            name=f"Cảnh báo · {title.lower()}",
            marker={"color": "#dc2626", "symbol": "x", "size": 9},
            hovertemplate="%{x|%d/%m/%Y %H:%M:%S} UTC<br>Giá trị: %{y}<extra>Cần kiểm tra</extra>",
        ))
    figure.update_xaxes(title_text="Thời gian (UTC)", tickformat="%H:%M\n%d/%m", nticks=6)
    figure.update_yaxes(title_text=METRIC_UNITS[metric], rangemode="nonnegative")
    return _layout(figure, dark, height=360)
