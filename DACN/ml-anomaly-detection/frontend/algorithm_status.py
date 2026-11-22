"""Compact, evidence-only presentation of the four stored model decisions."""
from __future__ import annotations

import math
from numbers import Real

import pandas as pd
import streamlit as st

from frontend.live_charts import MODELS


def scoped_samples(latest: dict | None, samples: list[dict]) -> list[dict]:
    """Keep the same baseline, source and collector/replay session as the point."""
    if not latest or latest.get("baseline_id") is None or latest.get("source") is None:
        return []
    return [point for point in samples if all(
        point.get(key) == latest.get(key) for key in ("baseline_id", "source", "session_id")
    )]


def _decision(point: dict | None, field: str, model: str) -> int | None:
    value = ((point or {}).get(field) or {}).get(model)
    if isinstance(value, Real) and not isinstance(value, bool) and value in (-1, 1):
        return int(value)
    return None


def _latest_label(latest: dict | None, model: str) -> str:
    guarded = _decision(latest, "predictions", model)
    if guarded == -1:
        return "Gắn cờ"
    if guarded == 1:
        return "Đã lọc dao động" if _decision(latest, "raw_predictions", model) == -1 else "Không gắn cờ"
    return "Chưa có kết quả"


def build_algorithm_table(latest: dict | None, samples: list[dict]) -> pd.DataFrame:
    """Four rows of guarded results and counts, without imputing missing results."""
    recent = scoped_samples(latest, samples)
    rows = []
    for name, label in MODELS.items():
        decisions = [_decision(point, "predictions", name) for point in recent]
        missing = decisions.count(None)
        count = f"{decisions.count(-1)} / {len(recent)}" if recent else "Chưa có mẫu"
        if missing:
            count += f" · thiếu {missing} kết quả"
        rows.append({"Thuật toán": label, "Mẫu mới nhất": _latest_label(latest, name),
                     "Gắn cờ / N mẫu": count})
    return pd.DataFrame(rows)


def build_algorithm_details(latest: dict | None) -> pd.DataFrame:
    """Keep the original score scale and raw prediction separate from alerts."""
    rows = []
    for name, label in MODELS.items():
        raw = _decision(latest, "raw_predictions", name)
        score = ((latest or {}).get("scores") or {}).get(name)
        valid_score = isinstance(score, Real) and not isinstance(score, bool) and math.isfinite(score)
        rows.append({
            "Thuật toán": label,
            "Dự đoán gốc": "Gắn cờ" if raw == -1 else "Không gắn cờ" if raw == 1 else "Chưa có kết quả",
            "Điểm gốc": score if valid_score else None,
        })
    return pd.DataFrame(rows, dtype=object)


def render_algorithm_status(latest: dict | None, samples: list[dict], *, fresh: bool,
                            dark: bool, show_table) -> None:
    """Show a small summary; the caller determines whether the signal is fresh."""
    title = "4 thuật toán · mẫu mới nhất" if fresh else "Kết quả đã lưu của 4 thuật toán"
    if not latest:
        title = "4 thuật toán · chưa có số đo"
    recent = scoped_samples(latest, samples)
    with st.container(border=True, key="monitor_algorithm_status"):
        st.markdown(f"### {title}")
        if latest:
            st.caption(f"Mẫu #{latest.get('id', '—')} · Nền #{latest.get('baseline_id', '—')} · "
                       f"Nguồn {latest.get('source', '—')} · {len(recent)} mẫu gần nhất cùng nguồn và phiên.")
        show_table(build_algorithm_table(latest, samples), dark)
        st.caption("Gắn cờ là kết quả sau bộ lọc vận hành. Đã lọc dao động: mô hình gắn cờ ban đầu, "
                   "nhưng mẫu chưa vượt dung sai nền. Số mẫu gắn cờ không thể hiện độ chính xác.")
        if not fresh and latest:
            st.caption("Đây là kết quả của số đo đã lưu, chưa xác nhận tình trạng MySQL hiện tại.")
        with st.expander("Dự đoán gốc và điểm chi tiết", expanded=False):
            show_table(build_algorithm_details(latest), dark, column_config={
                "Điểm gốc": st.column_config.NumberColumn(format="%.6g"),
            })
            st.caption("Điểm gốc giữ nguyên từ Backend, không phải xác suất. Điểm lớn hơn biểu thị mẫu "
                       "thông thường hơn trong chính thuật toán đó; không so điểm giữa các thuật toán. "
                       "Ô trống là chưa có điểm hợp lệ.")
