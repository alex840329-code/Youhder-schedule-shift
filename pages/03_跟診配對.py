# pages/03_跟診配對.py — 醫師與跟診助理的優先配對矩陣

import streamlit as st
import pandas as pd
from modules.config import init_session_config, save_config, get_active_doctors, get_active_assistants

st.set_page_config(page_title="跟診配對", page_icon="🔗", layout="wide")
init_session_config()

st.title("🔗 跟診配對設定")
st.caption("為每位醫師指定第 1、2、3 順位的跟診助理。排班時會優先安排第 1 順位，若不可用則依序往下。")

cfg  = st.session_state.config
docs = get_active_doctors()
asst_opts = ["（不指定）"] + [a["name"] for a in get_active_assistants()]
pm   = cfg.get("pairing_matrix", {})

if not docs:
    st.warning("請先至「人員設定」啟用醫師。")
    st.stop()

st.markdown("---")

# ── 視覺化配對表 ─────────────────────────────────────────────
st.markdown("**設定說明：** 每列為一位醫師，選擇第 1→2→3 順位的跟診助理。")

matrix_data = []
for d in docs:
    dn  = d["name"]
    cur = pm.get(dn, {})
    matrix_data.append({
        "醫師":     d["name"],
        "第一順位": cur.get("1", "（不指定）") or "（不指定）",
        "第二順位": cur.get("2", "（不指定）") or "（不指定）",
        "第三順位": cur.get("3", "（不指定）") or "（不指定）",
    })

ed_mat = st.data_editor(
    pd.DataFrame(matrix_data),
    column_config={
        "醫師":     st.column_config.TextColumn("醫師", disabled=True, width="medium"),
        "第一順位": st.column_config.SelectboxColumn("第一順位", options=asst_opts, width="medium"),
        "第二順位": st.column_config.SelectboxColumn("第二順位", options=asst_opts, width="medium"),
        "第三順位": st.column_config.SelectboxColumn("第三順位", options=asst_opts, width="medium"),
    },
    use_container_width=True,
    hide_index=True,
    key="ed_pairing",
)

if st.button("💾 儲存配對矩陣", type="primary"):
    new_pm = {}
    for _, row in ed_mat.iterrows():
        dn = row["醫師"]
        def clean(v):
            return "" if v in ("（不指定）", None) else str(v)
        new_pm[dn] = {
            "1": clean(row["第一順位"]),
            "2": clean(row["第二順位"]),
            "3": clean(row["第三順位"]),
        }
    cfg["pairing_matrix"] = new_pm
    save_config(cfg)
    st.success("✅ 配對矩陣已儲存！")
    st.rerun()

# ── 衝突檢查 ─────────────────────────────────────────────────
st.markdown("---")
st.subheader("⚠️ 衝突檢查")

pm_saved = cfg.get("pairing_matrix", {})
assts    = get_active_assistants()
asst_rules = cfg.get("adv_rules", {})

has_issue = False
for d in docs:
    dn  = d["name"]
    cur = pm_saved.get(dn, {})
    for pri, nm in cur.items():
        if not nm:
            continue
        rule = asst_rules.get(nm, {})
        role_limit = rule.get("role_limit", "無限制")
        if role_limit in ("僅櫃台", "僅流動", "僅行政"):
            st.warning(f"⚠️ **{dn}** 的第{pri}順位 **{nm}** 的職位限制為「{role_limit}」，無法跟診！")
            has_issue = True

if not has_issue:
    st.success("✅ 目前配對無衝突。")

# ── 配對摘要卡片 ──────────────────────────────────────────────
st.markdown("---")
st.subheader("📋 配對摘要")

for d in docs:
    dn  = d["name"]
    cur = pm_saved.get(dn, {})
    p1  = cur.get("1", "") or "—"
    p2  = cur.get("2", "") or "—"
    p3  = cur.get("3", "") or "—"
    st.markdown(
        f"**{dn}（{d.get('nick','')}）**　👉　"
        f"①{p1}　②{p2}　③{p3}"
    )
