# pages/01_人員設定.py — 醫師與助理基本資料 + LINE Token 統一管理

import streamlit as st
import pandas as pd
import numpy as np
from modules.config import init_session_config, save_config
from modules.data_utils import calculate_shift_limits

st.set_page_config(page_title="人員設定", page_icon="👥", layout="wide")
init_session_config()

st.markdown("""
<style>
  .dataframe td, .dataframe th { font-size: 15px !important; }
  [data-testid="stDataEditor"] td { font-size: 14px !important; }
  [data-testid="stDataEditor"] th { font-size: 14px !important; font-weight: bold !important; }
</style>
""", unsafe_allow_html=True)

st.title("👥 人員設定 & LINE Token")
st.caption("管理醫師與助理基本資料，以及 LINE Notify Token（統一在此設定）。")

cfg = st.session_state.config
y, m = cfg.get("year"), cfg.get("month")
min_s, max_s = calculate_shift_limits(y, m)
st.info(f"📅 **{y} 年 {m} 月**　｜　全職上限 **{max_s}** 診　基本 **{min_s}** 診")

tab_doc, tab_asst, tab_line = st.tabs(["👨‍⚕️ 醫師", "👩‍⚕️ 助理", "📱 LINE Token 設定"])

# ════════════════════════════════════════════════════════════
# 醫師
# ════════════════════════════════════════════════════════════

with tab_doc:
    st.caption("`name` 全名、`nick` 班表簡稱、`active` 是否啟用、`order` 排序（數字越小越前面）")

    doc_df = pd.DataFrame(cfg.get("doctors_struct", []))
    if doc_df.empty:
        doc_df = pd.DataFrame(columns=["name", "nick", "active", "order"])
    for col in ["name", "nick", "active", "order"]:
        if col not in doc_df.columns:
            doc_df[col] = None

    ed_doc = st.data_editor(
        doc_df[["name", "nick", "active", "order"]],
        column_config={
            "name":   st.column_config.TextColumn("姓名",  width=130),
            "nick":   st.column_config.TextColumn("簡稱",  width=70),
            "active": st.column_config.CheckboxColumn("啟用", width=60),
            "order":  st.column_config.NumberColumn("排序", min_value=1, max_value=99, width=70),
        },
        use_container_width=False,
        hide_index=True,
        num_rows="dynamic",
        key="ed_doctors",
    )

    if st.button("💾 儲存醫師清單", type="primary"):
        records = ed_doc.replace({np.nan: None}).to_dict("records")
        records = [r for r in records if r.get("name")]
        # 合併保留原本的 line_notify_token
        old_map = {d["name"]: d for d in cfg.get("doctors_struct", [])}
        for r in records:
            old = old_map.get(r["name"], {})
            r.setdefault("line_notify_token", old.get("line_notify_token", ""))
        cfg["doctors_struct"] = records
        save_config(cfg)
        st.success(f"✅ 已儲存 {len(records)} 位醫師")
        st.rerun()

    active_docs = [r for r in cfg.get("doctors_struct", []) if r.get("active")]
    if active_docs:
        st.caption("啟用醫師：" + "　".join(
            f"{d['name']}（{d.get('nick','')}）" for d in sorted(active_docs, key=lambda x: x.get("order", 99))
        ))

# ════════════════════════════════════════════════════════════
# 助理
# ════════════════════════════════════════════════════════════

with tab_asst:
    st.caption("`type` 全職/兼職、`is_main_counter` 主櫃台（不跟診）、`custom_max` 兼職每月上限診次")

    asst_df = pd.DataFrame(cfg.get("assistants_struct", []))
    if asst_df.empty:
        asst_df = pd.DataFrame(columns=["name", "nick", "type", "active", "is_main_counter", "custom_max"])
    for col in ["name", "nick", "type", "active", "is_main_counter", "custom_max"]:
        if col not in asst_df.columns:
            asst_df[col] = None

    ed_asst = st.data_editor(
        asst_df[["name", "nick", "type", "active", "is_main_counter", "custom_max"]],
        column_config={
            "name":            st.column_config.TextColumn("姓名",  width=100),
            "nick":            st.column_config.TextColumn("簡稱",  width=70),
            "type":            st.column_config.SelectboxColumn("類型", options=["全職","兼職"], width=80),
            "active":          st.column_config.CheckboxColumn("啟用",  width=60),
            "is_main_counter": st.column_config.CheckboxColumn("主櫃台", width=70),
            "custom_max":      st.column_config.NumberColumn("兼職上限", min_value=1, max_value=60, width=80),
        },
        use_container_width=False,
        hide_index=True,
        num_rows="dynamic",
        key="ed_assistants",
    )

    if st.button("💾 儲存助理清單", type="primary"):
        records = ed_asst.replace({np.nan: None}).to_dict("records")
        records = [r for r in records if r.get("name")]
        old_map = {a["name"]: a for a in cfg.get("assistants_struct", [])}
        for r in records:
            old = old_map.get(r["name"], {})
            r.setdefault("line_notify_token", old.get("line_notify_token", ""))
        cfg["assistants_struct"] = records
        save_config(cfg)
        st.success(f"✅ 已儲存 {len(records)} 位助理")
        st.rerun()

    all_asst   = cfg.get("assistants_struct", [])
    active_a   = [a for a in all_asst if a.get("active")]
    ft = [a["name"] for a in active_a if a.get("type") == "全職"]
    pt = [a["name"] for a in active_a if a.get("type") == "兼職"]
    mc = [a["name"] for a in active_a if a.get("is_main_counter")]
    if active_a:
        c1, c2, c3 = st.columns(3)
        c1.metric("啟用全職", len(ft))
        c2.metric("啟用兼職", len(pt))
        c3.metric("主櫃台", len(mc))

# ════════════════════════════════════════════════════════════
# LINE Token 統一設定（醫師 + 助理 + 群組）
# ════════════════════════════════════════════════════════════

with tab_line:
    st.markdown("""
    **所有 LINE Notify Token 集中在此設定。**
    設定後可至「報表輸出」頁面傳送班表。
    """)

    with st.expander("ℹ️ 如何取得 LINE Notify Token？", expanded=False):
        st.markdown("""
        **個人 Token（1 對 1 通知）：**
        1. 前往 [notify-bot.line.me](https://notify-bot.line.me/) 並登入
        2. 右上角帳號 → 個人頁面 → 發行存取權杖（開發人員用）
        3. 服務名稱輸入「祐德排班」，選「**透過 1 對 1 聊天接收通知**」
        4. 複製 Token 填入下方對應欄位

        **群組 Token：**
        1. 先將「LINE Notify」官方帳號加入診所群組
        2. 個人頁面 → 發行權杖 → 選「**透過群組接收**」→ 選對應群組
        3. 複製 Token 填入下方群組欄位
        """)

    # 群組 Token
    st.subheader("📢 診所群組")
    new_group_token = st.text_input(
        "群組 LINE Notify Token",
        value=cfg.get("line_group_token", ""),
        type="password",
        key="group_token_main",
    )
    if new_group_token != cfg.get("line_group_token", ""):
        cfg["line_group_token"] = new_group_token
        save_config(cfg)

    st.divider()

    # 醫師 Token
    st.subheader("👨‍⚕️ 醫師個人 Token")
    docs_data = cfg.get("doctors_struct", [])
    changed_docs = False
    for d in [x for x in docs_data if x.get("active")]:
        col1, col2 = st.columns([1, 3])
        col1.markdown(f"**{d['name']}**")
        new_tok = col2.text_input(
            "", value=d.get("line_notify_token", ""),
            type="password", key=f"ltok_doc_{d['name']}",
            label_visibility="collapsed",
            placeholder="貼上 Token...",
        )
        if new_tok != d.get("line_notify_token", ""):
            d["line_notify_token"] = new_tok
            changed_docs = True
    if changed_docs:
        cfg["doctors_struct"] = docs_data
        save_config(cfg)

    st.divider()

    # 助理 Token
    st.subheader("👩‍⚕️ 助理個人 Token")
    asst_data = cfg.get("assistants_struct", [])
    changed_asst = False
    for a in [x for x in asst_data if x.get("active")]:
        col1, col2 = st.columns([1, 3])
        col1.markdown(f"**{a['name']}**（{a.get('type','')}）")
        new_tok = col2.text_input(
            "", value=a.get("line_notify_token", ""),
            type="password", key=f"ltok_asst_{a['name']}",
            label_visibility="collapsed",
            placeholder="貼上 Token...",
        )
        if new_tok != a.get("line_notify_token", ""):
            a["line_notify_token"] = new_tok
            changed_asst = True
    if changed_asst:
        cfg["assistants_struct"] = asst_data
        save_config(cfg)

    # Token 狀態總覽
    st.divider()
    st.subheader("📊 Token 設定狀態")
    all_people = [
        {"姓名": d["name"], "角色": "醫師",
         "已設定": "✅" if d.get("line_notify_token") else "❌"}
        for d in docs_data if d.get("active")
    ] + [
        {"姓名": a["name"], "角色": f"助理({a.get('type','')})",
         "已設定": "✅" if a.get("line_notify_token") else "❌"}
        for a in asst_data if a.get("active")
    ]
    if all_people:
        df = pd.DataFrame(all_people)
        ok_cnt = sum(1 for p in all_people if p["已設定"] == "✅")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"已設定 {ok_cnt}/{len(all_people)} 人")
