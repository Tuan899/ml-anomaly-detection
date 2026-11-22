"""Public MySQL monitoring workspace with automatic anomaly alerts."""
from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from frontend.theme import apply_style
from frontend.research_app import show_table
from frontend.live_workspace import render_live_workspace


def main() -> None:
    st.set_page_config(page_title="ANOMALY LAB · Giám sát MySQL", page_icon="📈", layout="wide")
    with st.sidebar:
        st.markdown('<div class="brand-lockup"><span class="brand-mark" aria-hidden="true">AL</span><div><div class="brand">ANOMALY LAB</div><span class="brand-subtitle">Giám sát & phát hiện bất thường</span></div></div>', unsafe_allow_html=True)
        st.header("Giám sát MySQL")
        st.caption("Tự động chạy đủ 4 thuật toán: MAD, Isolation Forest, LOF và One-Class SVM.")
        st.markdown("[Bot cảnh báo](#bot-canh-bao)")
        dark = st.toggle("Giao diện tối", value=False, key="dark_mode")
        with st.expander("Hướng dẫn nhanh"):
            st.markdown("**Kết nối:** cấu hình bộ thu MySQL và chọn nguồn trực tiếp trong Công cụ bổ sung.\n\n"
                        "**Theo dõi:** xem trạng thái nguồn và các chỉ số mới nhất. Mất tín hiệu được hiển thị riêng.\n\n"
                        "**Cảnh báo:** chat tự thông báo các thời điểm cần kiểm tra và chỉ số thay đổi so với mức nền.")
    apply_style(dark)
    render_live_workspace(PROJECT_ROOT, dark, show_table, with_chat=True)


if __name__ == "__main__":
    main()
