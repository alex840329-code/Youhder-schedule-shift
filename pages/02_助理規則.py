# pages/02_助理規則.py — 助理工作限制與進階規則

import streamlit as st
from modules.config import init_session_config, save_config, get_active_assistants
from modules.data_utils import parse_slot_string, WEEKDAY_NAMES

st.set_page_config(page_title="助理規則", page_icon="🛡️", layout="wide")
init_session_config()

st.title("🛡️ 助理規則設定")
st.caption("設定每位助理的職位限制、可排時段白名單、互斥同事等條件。")

cfg   = st.session_state.config
assts = get_active_assistants()

if not assts:
    st.warning("請先至「人員設定」啟用助理。")
    st.stop()

ROLE_OPTS  = ["無限制", "僅跟診", "僅櫃台", "僅流動", "僅行政"]
SHIFT_OPTS = ["無限制", "僅早班", "僅午班", "僅晚班"]
DAYS       = WEEKDAY_NAMES
SHIFTS     = ["早", "午", "晚"]

curr_rules = cfg.get("adv_rules", {})
new_rules  = {}
asst_names = [a["name"] for a in assts]

# ── 頂部快速跳轉列 ────────────────────────────────────────────
st.markdown("**快速跳轉：**")
jump_cols = st.columns(min(len(assts), 8))
for i, a in enumerate(assts):
    if jump_cols[i % 8].button(a["name"], key=f"jump_{a['name']}", use_container_width=True):
        st.session_state["jump_to"] = a["name"]

# 跳轉錨點處理
jump_target = st.session_state.get("jump_to", "")

st.divider()

# ── 逐人設定 ────────────────────────────────────────────────
for a in assts:
    nm = a["name"]
    r  = curr_rules.get(nm, {})

    # 跳轉高亮
    expanded_default = (jump_target == nm)

    with st.expander(
        f"**{nm}**（{a.get('type','全職')}）"
        + ("　🏷️ 主櫃台" if a.get("is_main_counter") else ""),
        expanded=expanded_default
    ):
        # 如果是跳轉目標，顯示錨點
        if jump_target == nm:
            st.info(f"👆 正在查看 {nm} 的規則")
            st.session_state["jump_to"] = ""

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("##### 基本限制")
            role_v = st.selectbox(
                "職位限制", ROLE_OPTS,
                index=ROLE_OPTS.index(r.get("role_limit","無限制"))
                      if r.get("role_limit","無限制") in ROLE_OPTS else 0,
                key=f"role_{nm}",
                help="此助理只能擔任哪種職位？",
            )
            shift_v = st.selectbox(
                "班別限制", SHIFT_OPTS,
                index=SHIFT_OPTS.index(r.get("shift_limit","無限制"))
                      if r.get("shift_limit","無限制") in SHIFT_OPTS else 0,
                key=f"shift_{nm}",
                help="此助理只能上哪個時段？",
            )
            avoid_v = st.multiselect(
                "❌ 不能同時站**櫃台或流動**的同事",
                [x["name"] for x in assts if x["name"] != nm],
                default=[x.strip() for x in r.get("avoid","").split(",")
                         if x.strip() in asst_names],
                key=f"avoid_{nm}",
                help="注意：僅限制不能同時排在「櫃台」或「流動」，不影響同天不同職位的搭配。",
            )

            st.markdown("##### 固定班（每週）")
            st.caption("格式：`一早櫃,一晚櫃,二早櫃`　留空=無固定班")
            fixed_v = st.text_input(
                "固定班", value=r.get("fixed_slots",""),
                key=f"fixed_{nm}", label_visibility="collapsed",
                placeholder="一早櫃,五晚流...",
            )

        with col_right:
            st.markdown("##### 可排時段白名單")
            st.caption("全部不勾 = 無限制（任何時段皆可）；有勾選時僅排白名單時段")

            wl_set = parse_slot_string(r.get("slot_whitelist",""))

            hc = st.columns([2,1,1,1])
            hc[1].markdown("**早**"); hc[2].markdown("**午**"); hc[3].markdown("**晚**")
            wl_result = []
            for di, day in enumerate(DAYS):
                rc = st.columns([2,1,1,1])
                rc[0].markdown(f"星期{day}")
                for si, sh in enumerate(SHIFTS):
                    if rc[si+1].checkbox("", value=(di,sh) in wl_set,
                                         key=f"wl_{nm}_{di}_{sh}",
                                         label_visibility="collapsed"):
                        wl_result.append(f"{day}{sh}")

            st.markdown("##### 行政診時段")
            st.caption("助理在此時段處理行政（計診次，不排跟診）")
            ad_set = parse_slot_string(r.get("admin_slots",""))
            ad_hc  = st.columns([2,1,1,1])
            ad_hc[1].markdown("早"); ad_hc[2].markdown("午"); ad_hc[3].markdown("晚")
            ad_result = []
            for di, day in enumerate(DAYS):
                rc = st.columns([2,1,1,1])
                rc[0].markdown(f"星期{day}")
                for si, sh in enumerate(SHIFTS):
                    if rc[si+1].checkbox("", value=(di,sh) in ad_set,
                                         key=f"ad_{nm}_{di}_{sh}",
                                         label_visibility="collapsed"):
                        ad_result.append(f"{day}{sh}")

        new_rules[nm] = {
            "role_limit":     role_v,
            "shift_limit":    shift_v,
            "avoid":          ",".join(avoid_v),
            "slot_whitelist": ",".join(wl_result),
            "admin_slots":    ",".join(ad_result),
            "fixed_slots":    fixed_v,
        }

# ── 儲存 ─────────────────────────────────────────────────────
st.divider()
if st.button("💾 儲存所有助理規則", type="primary", use_container_width=True):
    cfg["adv_rules"] = new_rules
    save_config(cfg)
    st.success("✅ 所有助理規則已儲存！")
    st.rerun()

# ── 規則摘要 ─────────────────────────────────────────────────
with st.expander("📋 規則摘要"):
    for nm, r in cfg.get("adv_rules", {}).items():
        parts = []
        if r.get("role_limit")  != "無限制": parts.append(f"職位：{r['role_limit']}")
        if r.get("shift_limit") != "無限制": parts.append(f"班別：{r['shift_limit']}")
        if r.get("avoid"):                   parts.append(f"互斥（櫃/流）：{r['avoid']}")
        if r.get("slot_whitelist"):          parts.append(f"白名單：{r['slot_whitelist']}")
        if r.get("fixed_slots"):             parts.append(f"固定：{r['fixed_slots']}")
        st.markdown(("**" + nm + "**：" + "　｜　".join(parts)) if parts else f"**{nm}**：無特殊限制")
