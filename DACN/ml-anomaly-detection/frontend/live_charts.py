"""Readable monitoring charts without changing measurements or decisions."""
from __future__ import annotations

import math

import plotly.graph_objects as go
from plotly.subplots import make_subplots


METRICS = {
    "queries_per_second": ("Truy vấn/giây", "QPS"),
    "connections": ("Kết nối đang mở", "kết nối"),
    "response_time_ms": ("Thời gian phản hồi", "ms"),
    "slow_queries": ("Truy vấn chậm", "sự kiện/kỳ"),
    "connection_errors": ("Kết nối thất bại", "sự kiện/kỳ"),
}
MODELS = {"mad": "MAD", "isolation_forest": "Isolation Forest", "lof": "LOF", "one_class_svm": "One-Class SVM"}
COLORS = {"watch": "#64748b", "warning": "#d97706", "critical": "#dc2626"}


def _palette(dark: bool) -> dict:
    return ({"ink": "#e2e8f0", "muted": "#a5b4c8", "grid": "#243247",
             "surface": "#101c2d", "line": "#60a5fa", "normal": "#20354e",
             "band": "rgba(96,165,250,.08)", "reference": "#94a3b8"}
            if dark else
            {"ink": "#172b45", "muted": "#64748b", "grid": "#e8eef5",
             "surface": "#ffffff", "line": "#2563eb", "normal": "#e8f0fc",
             "band": "rgba(37,99,235,.055)", "reference": "#94a3b8"})


def _layout(figure: go.Figure, dark: bool, height: int, *, comparison: bool = False) -> go.Figure:
    palette = _palette(dark)
    figure.update_layout(
        template="plotly_dark" if dark else "plotly_white",
        height=height, autosize=True,
        margin={"l": 92 if comparison else 76, "r": 12, "t": 58 if comparison else 20, "b": 48},
        font={"family": "Segoe UI, Arial, sans-serif", "size": 14, "color": palette["ink"]},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=palette["surface"],
        hovermode="closest", hoverdistance=28,
        hoverlabel={"bgcolor": palette["surface"], "bordercolor": palette["grid"],
                    "font": {"family": "Segoe UI, Arial, sans-serif", "size": 13, "color": palette["ink"]},
                    "align": "left"},
        dragmode="pan", uirevision="monitor-comparison" if comparison else "monitor-activity",
    )
    figure.update_xaxes(
        type="date", tickformat="%H:%M:%S", nticks=4, automargin=True,
        tickfont={"size": 13, "color": palette["muted"]},
        title_font={"size": 14, "color": palette["muted"]},
        showgrid=False, zeroline=False, showline=False, ticks="", fixedrange=False,
    )
    figure.update_yaxes(
        automargin=True, tickfont={"size": 13, "color": palette["muted"]},
        title_font={"size": 14, "color": palette["ink"]}, title_standoff=10,
        gridcolor=palette["grid"], gridwidth=1, zeroline=False, showline=False, ticks="",
        fixedrange=True,
    )
    return figure


def _customdata(samples: list[dict], raw: bool = False) -> list[list]:
    """Retain the established field order used by tooltips and exported checks."""
    return [[*[point.get(metric) for metric in METRICS], point.get("timestamp"),
             point.get("source"), point.get("raw_votes" if raw else "votes", 0),
             ", ".join(MODELS.get(name, name) for name in point.get("raw_voters" if raw else "voters", []))]
            for point in samples]


HOVER = (
    "<b>Nhận lúc %{x|%d/%m/%Y %H:%M:%S} UTC</b>"
    "<br>Thời điểm nguồn: %{customdata[5]}"
    "<br>QPS: %{customdata[0]:,.3g}"
    "<br>Kết nối: %{customdata[1]:,.0f}"
    "<br>Phản hồi: %{customdata[2]:,.3g} ms"
    "<br>Truy vấn chậm: %{customdata[3]:,.0f}"
    "<br>Kết nối thất bại: %{customdata[4]:,.0f}"
    "<br>Nguồn: %{customdata[6]}"
    "<br>Đồng thuận sau lọc: %{customdata[7]}/4"
    "<br>Bỏ phiếu: %{customdata[8]}<extra></extra>"
)


def _reference(samples: list[dict], metric: str) -> tuple[float, float] | None:
    if not samples:
        return None
    evidence = next((item for item in samples[0].get("evidence", []) if item.get("metric") == metric), None)
    if not evidence:
        return None
    center, tolerance = evidence.get("baseline"), evidence.get("allowed_deviation")
    if (any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            for value in (center, tolerance)) or tolerance < 0):
        return None
    return float(center), float(tolerance)


def activity_figure(samples: list[dict], dark: bool = False) -> go.Figure:
    """Five compact measured channels, with stored baseline bands and real votes."""
    palette = _palette(dark)
    figure = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=.045)
    x = [point.get("received_at", point["timestamp"]) for point in samples]
    customdata = _customdata(samples)
    axis_titles = ("QPS", "Kết nối", "Phản hồi<br>(ms)", "Truy vấn<br>chậm", "Lỗi kết nối")
    for row, (metric, (label, unit)) in enumerate(METRICS.items(), 1):
        # A model decision is multivariate. Highlight this channel only when
        # the Backend's stored evidence explicitly identifies its deviation.
        # Missing evidence must not make every measured channel look faulty.
        flags = [point for point in samples if point.get("votes", 0) and any(
            item.get("metric") == metric and item.get("material") is True
            for item in point.get("evidence", [])
        )]
        metric_hover = (
            "<b>" + label + ": %{y:,.4g} " + unit + "</b>"
            "<br>Nhận lúc %{x|%d/%m/%Y %H:%M:%S} UTC"
            "<br>Thời điểm nguồn: %{customdata[5]}"
            "<br>Nguồn: %{customdata[6]}"
            "<br>Thuật toán phát hiện: %{customdata[8]}"
            "<br>Đồng thuận sau lọc: %{customdata[7]}/4<extra></extra>"
        )
        figure.add_trace(go.Scatter(
            x=x, y=[point[metric] for point in samples],
            mode="lines+markers" if len(samples) <= 2 else "lines",
            line={"color": palette["line"], "width": 2.2},
            marker={"size": 4, "color": palette["line"]},
            customdata=customdata, hovertemplate=metric_hover, name=label, showlegend=False,
            connectgaps=False,
        ), row=row, col=1)
        figure.add_trace(go.Scatter(
            x=[point.get("received_at", point["timestamp"]) for point in flags],
            y=[point[metric] for point in flags], mode="markers", name="Chỉ số lệch nền có cảnh báo",
            customdata=_customdata(flags), hovertemplate=metric_hover,
            marker={"size": 7,
                    "color": [COLORS.get(point.get("level"), COLORS["watch"]) for point in flags],
                    "symbol": ["diamond" if point.get("level") == "warning" else "x" if point.get("level") == "critical" else "circle" for point in flags],
                    "line": {"width": 1, "color": palette["surface"]}},
            showlegend=False,
        ), row=row, col=1)
        # Add reference shapes after traces so Plotly includes the populated
        # subplot instead of dropping shapes from an initially empty row.
        reference = _reference(samples, metric)
        if reference is not None:
            center, tolerance = reference
            if tolerance:
                figure.add_hrect(y0=max(0., center - tolerance), y1=center + tolerance,
                                 line_width=0, fillcolor=palette["band"], layer="below", row=row, col=1)
            figure.add_hline(y=center, line={"color": palette["reference"], "width": 1, "dash": "dot"},
                            layer="below", row=row, col=1)
        figure.update_yaxes(title_text=axis_titles[row - 1], rangemode="tozero", row=row, col=1)
    figure.update_xaxes(title_text="Thời gian nhận dữ liệu (UTC)", row=5, col=1)
    return _layout(figure, dark, 640)


def comparison_figure(samples: list[dict], raw: bool = False, dark: bool = False) -> go.Figure:
    """Same observation/time grid for all four stored model decisions."""
    palette = _palette(dark)
    field = "raw_predictions" if raw else "predictions"
    z = [[int(point[field][name] == -1) for point in samples] for name in MODELS]
    base_customdata = _customdata(samples, raw)
    customdata = [[[*values, "Bất thường" if point[field][name] == -1 else "Không gắn cờ"]
                   for point, values in zip(samples, base_customdata)] for name in MODELS]
    hover = HOVER.replace("Đồng thuận sau lọc", "Đồng thuận gốc" if raw else "Đồng thuận sau lọc")
    hover = hover.replace("<extra></extra>", "<br>Thuật toán: %{y}<br>Kết quả: <b>%{customdata[9]}</b><extra></extra>")
    figure = go.Figure(go.Heatmap(
        x=[point.get("received_at", point["timestamp"]) for point in samples],
        y=list(MODELS.values()), z=z, zmin=0, zmax=1,
        colorscale=[[0, palette["normal"]], [.499, palette["normal"]], [.5, "#dc2626"], [1, "#dc2626"]],
        xgap=0, ygap=5, showscale=False, customdata=customdata, hovertemplate=hover,
        hoverongaps=False,
    ))
    _layout(figure, dark, 330, comparison=True)
    figure.update_xaxes(title_text="Cùng thời gian nhận dữ liệu (UTC)")
    figure.update_yaxes(
        autorange="reversed", showgrid=False, tickmode="array",
        tickvals=list(MODELS.values()), ticktext=["MAD", "Isolation<br>Forest", "LOF", "One-Class<br>SVM"],
        tickfont={"size": 14, "color": palette["ink"]},
    )
    figure.add_annotation(xref="paper", yref="paper", x=0, y=1.08, xanchor="left", yanchor="bottom",
                          text='Ô nhạt: không gắn cờ<br><span style="color:#dc2626">■</span> Ô đỏ: bất thường',
                          align="left", showarrow=False, font={"size": 12, "color": palette["muted"]})
    return figure
