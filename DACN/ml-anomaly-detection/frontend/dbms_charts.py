"""Readable charts of measured MySQL activity and auditable alert times."""
from __future__ import annotations

import plotly.graph_objects as go


MYSQL_METRICS = (
    "queries_per_second", "connections", "response_time_ms",
    "slow_queries", "connection_errors",
)
METRIC_NAMES = {
    "queries_per_second": "Lưu lượng truy vấn",
    "connections": "Kết nối đang mở",
    "response_time_ms": "Thời gian phản hồi",
    "slow_queries": "Truy vấn chậm",
    "connection_errors": "Kết nối thất bại",
}
METRIC_UNITS = {
    "queries_per_second": "Truy vấn/giây",
    "connections": "Kết nối",
    "response_time_ms": "ms",
    "slow_queries": "Truy vấn/khoảng",
    "connection_errors": "Lỗi/khoảng",
}


def build_trend_figure(run, model: str, metric: str, dark: bool = False,
                       full_history: bool = False, show_labels: bool = False) -> go.Figure:
    """Plot exact measurements; the training band is context, not a verdict.

    Predictions belong only to the chronological holdout. The reference range
    is copied from training metadata and never recomputed from displayed data.
    A multivariate alert can occur while the selected metric is inside its band.
    """
    frame, data, meta = run.frame, run.predictions, run.metadata
    time = meta["timestamp_col"]
    visible = frame if full_history else data
    flags = data.loc[data[f"{model}_prediction"].eq(-1)]
    ink = "#e5edf9" if dark else "#17233b"
    muted = "#b2c2da" if dark else "#52627b"
    background = "#111c2e" if dark else "#ffffff"
    grid = "#2e405c" if dark else "#e6edf5"
    actual = "#38bdf8" if dark else "#2563eb"
    green = "#86efac" if dark else "#15803d"

    # Keep these two traces first: actual values, then selected-model alerts.
    figure = go.Figure(go.Scatter(
        x=visible[time], y=visible[metric], mode="lines", name="Giá trị thực tế",
        line={"color": actual, "width": 2.2}, legendrank=10,
        hovertemplate=("%{x|%d/%m/%Y %H:%M:%S} UTC<br>"
                       + METRIC_NAMES[metric] + ": %{y} " + METRIC_UNITS[metric]
                       + "<extra>Giá trị thực tế</extra>"),
    ))
    figure.add_trace(go.Scatter(
        x=flags[time], y=flags[metric], name="Thời điểm cảnh báo đa chỉ số",
        mode="markers", legendrank=11,
        customdata=flags[list(MYSQL_METRICS)].to_numpy(),
        marker={"color": "#dc2626", "size": 11, "symbol": "x", "line": {"width": 2}},
        hovertemplate=("%{x|%d/%m/%Y %H:%M:%S} UTC"
                       "<br>Truy vấn/giây: %{customdata[0]}"
                       "<br>Kết nối đang mở: %{customdata[1]}"
                       "<br>Phản hồi: %{customdata[2]} ms"
                       "<br>Truy vấn chậm/khoảng: %{customdata[3]}"
                       "<br>Kết nối thất bại/khoảng: %{customdata[4]}"
                       "<extra>Cần kiểm tra</extra>"),
    ))

    if show_labels and meta.get("label_col"):
        truth = data.loc[data[meta["label_col"]].eq(-1)]
        figure.add_trace(go.Scatter(
            x=truth[time], y=truth[metric], mode="markers", name="Nhãn bất thường kiểm thử",
            marker={"color": "#a855f7" if dark else "#7e22ce", "size": 15,
                    "symbol": "circle-open", "line": {"width": 2}},
            hovertemplate="%{x|%d/%m/%Y %H:%M:%S} UTC<br>Nhãn kiểm thử<extra></extra>",
            legendrank=12,
        ))

    baseline = meta.get("train_baselines", {}).get(metric)
    if baseline:
        figure.add_hrect(
            y0=baseline["lower_bound"], y1=baseline["upper_bound"],
            fillcolor="rgba(74,222,128,0.12)" if dark else "rgba(34,197,94,0.10)",
            line_width=0, layer="below", name="Vùng tham chiếu từ dữ liệu học",
            showlegend=True, legendrank=20,
        )
        figure.add_hline(
            y=baseline["median"], line_color=green, line_dash="dot", line_width=1.5,
            name="Trung vị giai đoạn học", showlegend=True, legendrank=21,
        )

    if full_history and not data.empty:
        boundary = data[time].iloc[0].isoformat()
        figure.add_vrect(
            x0=frame[time].iloc[0].isoformat(), x1=boundary,
            fillcolor="rgba(148,163,184,0.12)", line_width=0, layer="below",
        )
        figure.add_shape(
            type="line", x0=boundary, x1=boundary, y0=0, y1=1,
            xref="x", yref="paper", line={"color": muted, "dash": "dash", "width": 1.5},
        )
        figure.add_annotation(
            x=boundary, y=1.02, xref="x", yref="paper", text="Bắt đầu kiểm tra",
            showarrow=False, xanchor="left", font={"color": ink, "size": 13},
            bgcolor=background, borderpad=3,
        )

    axis = dict(
        tickfont={"color": ink, "size": 13}, title_font={"color": ink, "size": 14},
        gridcolor=grid, zerolinecolor=grid, linecolor=grid,
        automargin=True,
    )
    figure.update_layout(
        template="plotly_dark" if dark else "plotly_white",
        height=390, font={"family": "Arial, sans-serif", "size": 13, "color": ink},
        paper_bgcolor=background, plot_bgcolor=background,
        hovermode="closest",
        hoverlabel={"bgcolor": background, "font": {"color": ink, "size": 13}},
        xaxis={**axis, "title_text": "Thời gian (UTC)", "type": "date",
               "tickformat": "%H:%M\n%d/%m", "nticks": 6},
        yaxis={**axis, "title_text": METRIC_UNITS[metric], "rangemode": "nonnegative"},
        legend={"orientation": "h", "x": 0, "y": 1.24, "xanchor": "left", "yanchor": "top",
                "font": {"color": ink, "size": 13}, "bgcolor": background},
        margin={"l": 70, "r": 25, "t": 83, "b": 66},
    )
    return figure
