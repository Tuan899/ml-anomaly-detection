"""Interactive EDA plots for trend and seasonality."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .data_prep import add_time_features


def trend_figure(frame: pd.DataFrame, value_col: str, timestamp_col: str = "timestamp") -> go.Figure:
    """Create an interactive time-series trend chart."""
    return px.line(frame, x=timestamp_col, y=value_col, title=f"Trend - {value_col}")


def seasonality_figure(frame: pd.DataFrame, value_col: str, timestamp_col: str = "timestamp") -> go.Figure:
    """Create hourly and weekday seasonality charts."""
    # Derive grouping keys separately: source metrics may themselves be named
    # hour, day_of_week or hour_sin and must retain their measured values.
    calendar = add_time_features(frame[[timestamp_col]], timestamp_col)
    values = frame[value_col]
    hourly = values.groupby(calendar["hour"]).mean()
    weekday = values.groupby(calendar["day_of_week"]).mean()
    figure = make_subplots(rows=1, cols=2, subplot_titles=("Theo giờ", "Theo ngày trong tuần"))
    figure.add_trace(go.Scatter(x=hourly.index, y=hourly.to_numpy(), mode="lines+markers"), row=1, col=1)
    figure.add_trace(go.Bar(x=weekday.index, y=weekday.to_numpy()), row=1, col=2)
    figure.update_layout(title="Seasonality", xaxis_title="Giờ", xaxis2_title="Ngày trong tuần")
    return figure
