# modules/calendar_ui.py — 月曆式勾選 UI 元件（共用）

import calendar as _cal
import streamlit as st

SHIFTS     = ["早", "午", "晚"]
SHIFT_BG   = {"早": "#FDE9D9", "午": "#BDD7EE", "晚": "#FABF8F"}
DAY_NAMES  = ["一", "二", "三", "四", "五", "六"]


def render_month_calendar(
    prefix: str,
    person: str,
    checked_set: set,   # set of (dt_str, shift) 表示已勾選
    year: int,
    month: int,
    is_locked: bool = False,
    shift_labels: dict = None,  # 可覆寫顯示文字，如 {"早":"早班","晚":"休早晚"}
) -> dict:
    """
    渲染月曆勾選表。
    回傳 dict: {"YYYY-MM-DD_早": True/False, ...}
    """
    if shift_labels is None:
        shift_labels = {s: s for s in SHIFTS}

    st.markdown("""
    <style>
    .cal-hdr  {text-align:center;font-weight:bold;font-size:14px;
               background:#e8e8e8;border-radius:4px;padding:4px;margin-bottom:4px;}
    .cal-date {text-align:center;font-weight:bold;font-size:13px;
               background:#f5f5f5;border-radius:4px;padding:3px;margin-bottom:2px;}
    .cal-empty{min-height:60px;}
    </style>
    """, unsafe_allow_html=True)

    # 欄位標頭
    h_cols = st.columns(6)
    for i, dn in enumerate(DAY_NAMES):
        h_cols[i].markdown(f"<div class='cal-hdr'>星期{dn}</div>", unsafe_allow_html=True)

    result  = {}
    cal_wks = _cal.monthcalendar(year, month)

    for week in cal_wks:
        cols = st.columns(6)
        for ci in range(6):          # Mon-Sat only
            day_num = week[ci]
            with cols[ci]:
                if day_num == 0:
                    st.markdown("<div class='cal-empty'></div>", unsafe_allow_html=True)
                else:
                    dt_str = f"{year}-{month:02d}-{day_num:02d}"
                    st.markdown(f"<div class='cal-date'>{month}/{day_num}</div>",
                                unsafe_allow_html=True)
                    for sh in SHIFTS:
                        val = st.checkbox(
                            shift_labels[sh],
                            value=(dt_str, sh) in checked_set,
                            key=f"{prefix}_{person}_{dt_str}_{sh}",
                            disabled=is_locked,
                        )
                        result[f"{dt_str}_{sh}"] = val
        st.markdown("<br>", unsafe_allow_html=True)

    return result
