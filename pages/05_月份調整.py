# pages/05_月份調整.py — 當月醫師班表微調（月曆格式）+ LINE 傳送

import streamlit as st
import collections
from datetime import datetime

from modules.config import init_session_config, save_config, get_active_doctors
from modules.calendar_ui import render_month_calendar
from modules.line_integration import format_doctor_schedule, send_line_notify

st.set_page_config(page_title="月份調整", page_icon="📅", layout="wide")
init_session_config()

st.title("📅 月份醫師班表調整")
st.caption("在範本基礎上調整當月實際上診（取消勾選 = 休假，額外勾選 = 加診）。")

cfg       = st.session_state.config
docs      = get_active_doctors()
y, m      = cfg.get("year"), cfg.get("month")
manual    = cfg.get("manual_schedule", [])
is_locked = cfg.get("is_locked", False)

if not docs:
    st.warning("請先至「人員設定」啟用醫師。")
    st.stop()
if not manual:
    st.warning("請先至「醫師班表」設定範本並套用月份。")
    st.stop()
if is_locked:
    st.error("🔒 系統已鎖定，無法修改。")

st.info(f"📆 目前調整月份：**{y} 年 {m} 月**")

# ── 醫師選擇 ─────────────────────────────────────────────────
col_sel, col_line = st.columns([2, 2])

with col_sel:
    sel_doc = st.selectbox("📌 選擇醫師", [d["name"] for d in docs])

with col_line:
    doc_info  = next((d for d in docs if d["name"] == sel_doc), {})
    doc_token = doc_info.get("line_notify_token", "")
    st.markdown("**📱 LINE 傳送**")
    if doc_token:
        if st.button("📤 傳送當月班表給此醫師", use_container_width=True, key="line_doc_send"):
            text = format_doctor_schedule(sel_doc, manual, y, m)
            ok, err = send_line_notify(doc_token, f"\n【{y}年{m}月班表確認】\n{text}\n\n如需調整請聯繫管理員。")
            st.success("✅ 已傳送！") if ok else st.error(f"❌ {err}")
    else:
        st.info("此醫師未設定 LINE Token（至「人員設定」→「LINE Token 設定」填入）")

st.markdown(f"### 📆 {sel_doc}　{y} 年 {m} 月")
st.caption("✅ 打勾 = 有診；取消 = 休假。可以直接點格子修改。")

# ── 月曆式勾選 ────────────────────────────────────────────────
scheduled_set = {
    (x["Date"], x["Shift"]) for x in manual if x["Doctor"] == sel_doc
}

cal_result = render_month_calendar(
    prefix="doc",
    person=sel_doc,
    checked_set=scheduled_set,
    year=y, month=m,
    is_locked=is_locked,
)

# ── 儲存 ─────────────────────────────────────────────────────
if not is_locked:
    c1, c2 = st.columns([1, 3])
    if c1.button("💾 儲存此醫師班表", type="primary", use_container_width=True):
        new_man = [x for x in manual if x["Doctor"] != sel_doc]
        for slot_key, checked in cal_result.items():
            if checked:
                dt_str, sh = slot_key.rsplit("_", 1)
                new_man.append({"Date": dt_str, "Shift": sh, "Doctor": sel_doc})
        cfg["manual_schedule"] = new_man
        save_config(cfg)
        st.success(f"✅ {sel_doc} 的班表已儲存！")
        st.rerun()
    c2.info("💡 儲存後請到「請假登記」確認助理請假，再執行自動排班。")

# ── 統計摘要 ─────────────────────────────────────────────────
st.divider()
with st.expander("📊 當月所有醫師上診統計"):
    summary = collections.defaultdict(lambda: {"早":0,"午":0,"晚":0})
    for x in cfg.get("manual_schedule", []):
        summary[x["Doctor"]][x["Shift"]] += 1
    rows = []
    for d in get_active_doctors():
        s = summary.get(d["name"], {})
        rows.append({
            "醫師": d["name"],
            "早診": s.get("早",0), "午診": s.get("午",0), "晚診": s.get("晚",0),
            "總計": sum(s.values()),
        })
    if rows:
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── 批量 LINE 傳送 ─────────────────────────────────────────────
st.divider()
with st.expander("📱 批量傳送班表給所有醫師"):
    st.warning("⚠️ 確認班表定稿後再傳送！")
    if st.button("📤 批量傳送所有醫師班表", type="secondary"):
        ok_cnt, fail_list = 0, []
        all_manual = cfg.get("manual_schedule", [])
        for d in get_active_doctors():
            tok = d.get("line_notify_token","")
            if tok:
                text = format_doctor_schedule(d["name"], all_manual, y, m)
                ok, err = send_line_notify(tok, f"\n【{y}年{m}月班表確認】\n{text}")
                if ok: ok_cnt += 1
                else:  fail_list.append(f"{d['name']}（{err}）")
        if ok_cnt:   st.success(f"✅ 成功傳送 {ok_cnt} 位！")
        if fail_list: st.error("❌ 失敗：" + "、".join(fail_list))
