# app.py — 祐德牙醫排班系統 首頁
# 架構：Streamlit 多頁面 (pages/ 資料夾)

import streamlit as st
from datetime import datetime
from modules.config import init_session_config, save_config
from modules.data_utils import calculate_shift_limits

st.set_page_config(
    page_title="祐德牙醫排班系統",
    layout="wide",
    page_icon="🦷",
)

# ── 全域 CSS ─────────────────────────────────────────────────
st.markdown("""
<style>
  .block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; }
  .step-card {
    background: #f8f9fa;
    border-left: 4px solid #4CAF50;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 8px;
  }
  .step-card.warning { border-left-color: #ff9800; }
  .step-card.done    { border-left-color: #2196F3; background: #e8f4f8; }
  .metric-box {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
  }
</style>
""", unsafe_allow_html=True)

init_session_config()

# ════════════════════════════════════════════════════════════
# 首頁標題
# ════════════════════════════════════════════════════════════

st.title("🦷 祐德牙醫排班系統")

cfg = st.session_state.config
y, m = cfg.get("year", datetime.today().year), cfg.get("month", datetime.today().month)
min_s, max_s = calculate_shift_limits(y, m)

is_locked = cfg.get("is_locked", False)
if is_locked:
    st.error("🔒 系統目前已鎖定（前台唯讀）")

# ── 月份快速設定 ─────────────────────────────────────────────
with st.expander("📅 切換排班月份", expanded=False):
    c1, c2, c3 = st.columns([1, 1, 2])
    new_y = c1.number_input("年", 2025, 2030, y, key="home_year")
    new_m = c2.number_input("月", 1, 12, m, key="home_month")
    if c3.button("✅ 確認切換月份", use_container_width=True):
        cfg["year"] = new_y
        cfg["month"] = new_m
        save_config(cfg)
        st.rerun()

st.markdown(f"**目前排班月份：{y} 年 {m} 月**　｜　全職上限 {max_s} 診 / 基本 {min_s} 診")
st.divider()

# ── 狀態儀表板 ───────────────────────────────────────────────
docs_count  = sum(1 for d in cfg.get("doctors_struct", []) if d.get("active"))
asst_count  = sum(1 for a in cfg.get("assistants_struct", []) if a.get("active"))
has_manual  = bool(cfg.get("manual_schedule"))
has_result  = bool(st.session_state.get("result") or cfg.get("saved_result"))

cols = st.columns(4)
with cols[0]:
    st.markdown(f"""<div class="metric-box">
        <div style="font-size:2em">👨‍⚕️</div>
        <div style="font-size:1.5em;font-weight:bold">{docs_count}</div>
        <div>醫師</div></div>""", unsafe_allow_html=True)
with cols[1]:
    st.markdown(f"""<div class="metric-box">
        <div style="font-size:2em">👩‍⚕️</div>
        <div style="font-size:1.5em;font-weight:bold">{asst_count}</div>
        <div>助理</div></div>""", unsafe_allow_html=True)
with cols[2]:
    status_color = "#4CAF50" if has_manual else "#ff9800"
    status_text  = "✅ 已設定" if has_manual else "⏳ 待設定"
    st.markdown(f"""<div class="metric-box">
        <div style="font-size:2em">📋</div>
        <div style="font-size:1em;font-weight:bold;color:{status_color}">{status_text}</div>
        <div>醫師班表</div></div>""", unsafe_allow_html=True)
with cols[3]:
    r_color = "#4CAF50" if has_result else "#ff9800"
    r_text  = "✅ 已生成" if has_result else "⏳ 待生成"
    st.markdown(f"""<div class="metric-box">
        <div style="font-size:2em">📅</div>
        <div style="font-size:1em;font-weight:bold;color:{r_color}">{r_text}</div>
        <div>排班結果</div></div>""", unsafe_allow_html=True)

st.divider()

# ── 排班步驟導引 ─────────────────────────────────────────────
st.subheader("📌 排班步驟")

steps = [
    ("1️⃣", "人員設定",    "建立醫師與助理的基本資料",               "01_人員設定",     docs_count > 0),
    ("2️⃣", "助理規則",    "設定每位助理的職位限制、請假白名單",      "02_助理規則",     asst_count > 0),
    ("3️⃣", "跟診配對",    "指定每位醫師的第 1~3 順位跟診助理",      "03_跟診配對",     bool(cfg.get("pairing_matrix"))),
    ("4️⃣", "醫師班表",    "設定單雙週固定上診範本",                  "04_醫師班表",     bool(cfg.get("template_odd"))),
    ("5️⃣", "月份調整",    "確認當月醫師實際上診（含請假加班）",      "05_月份調整",     has_manual),
    ("6️⃣", "請假登記",    "登記助理當月請假時段（可 LINE 通知）",    "06_請假登記",     True),
    ("7️⃣", "自動排班",    "執行排班、即時儀表板、NLP 微調",          "07_自動排班",     has_result),
    ("8️⃣", "報表輸出",    "下載 Excel 班表並透過 LINE 傳送",         "08_報表輸出",     has_result),
]

for icon, title, desc, page, done in steps:
    card_cls = "done" if done else ""
    check = "✅" if done else "⬜"
    st.markdown(f"""
    <div class="step-card {card_cls}">
      <b>{icon} {check} {title}</b> — {desc}
    </div>""", unsafe_allow_html=True)

st.divider()

# ── 備份/還原 ────────────────────────────────────────────────
with st.expander("💾 備份與還原設定"):
    import json
    LOGIC_KEYS = ["api_key", "line_notify_tokens", "line_bot_token",
                  "doctors_struct", "assistants_struct", "pairing_matrix",
                  "adv_rules", "template_odd", "template_even",
                  "forced_assigns", "dynamic_flt", "dynamic_ctr", "balance_flt"]
    MONTH_KEYS = ["year", "month", "manual_schedule", "leaves", "saved_result", "forced_assigns"]

    t1, t2 = st.tabs(["⚙️ 邏輯設定", "📅 班表資料"])
    with t1:
        st.download_button(
            "📥 下載邏輯設定 JSON",
            json.dumps({k: cfg.get(k) for k in LOGIC_KEYS}, ensure_ascii=False, indent=2),
            f"yude_logic_{datetime.now().strftime('%Y%m%d')}.json",
            "application/json", use_container_width=True,
        )
        ul = st.file_uploader("📤 還原邏輯設定", type="json", key="ul_logic")
        if ul and st.button("確認還原", key="btn_logic"):
            try:
                new = json.load(ul)
                for k in LOGIC_KEYS:
                    if k in new:
                        cfg[k] = new[k]
                save_config(cfg); st.rerun()
            except Exception as e:
                st.error(f"還原失敗：{e}")
    with t2:
        st.download_button(
            "📥 下載班表資料 JSON",
            json.dumps({k: cfg.get(k) for k in MONTH_KEYS}, ensure_ascii=False, indent=2),
            f"yude_month_{y}_{m}.json", "application/json", use_container_width=True,
        )
        um = st.file_uploader("📤 還原班表資料", type="json", key="ul_month")
        if um and st.button("確認還原", key="btn_month"):
            try:
                new = json.load(um)
                for k in MONTH_KEYS:
                    if k in new:
                        cfg[k] = new[k]
                if cfg.get("saved_result"):
                    st.session_state.result = cfg["saved_result"]
                save_config(cfg); st.rerun()
            except Exception as e:
                st.error(f"還原失敗：{e}")

# ── 系統管理（鎖定） ─────────────────────────────────────────
with st.expander("🔒 系統管理"):
    new_lock = st.toggle("鎖定前台修改（醫師/助理入口變唯讀）", value=is_locked)
    if new_lock != is_locked:
        cfg["is_locked"] = new_lock
        save_config(cfg)
        st.rerun()
