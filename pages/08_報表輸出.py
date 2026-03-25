# pages/08_報表輸出.py — Excel 下載 + LINE 傳送（文字 + 圖片）

import streamlit as st
import pandas as pd

from modules.config import init_session_config, save_config, get_active_doctors, get_active_assistants
from modules.excel_export import to_excel_master, to_excel_individual, to_excel_doctor
from modules.line_integration import (
    send_line_notify,
    send_line_notify_with_image,
    format_assistant_schedule,
    format_doctor_schedule,
    generate_schedule_image,
)

st.set_page_config(page_title="報表輸出", page_icon="📊", layout="wide")
init_session_config()

st.title("📊 報表輸出")
st.caption("下載 Excel 班表，並透過 LINE 傳送個人班表（文字或圖片）。")
st.info("💡 LINE Token 請至「人員設定 → LINE Token 設定」統一管理。")

cfg   = st.session_state.config
y, m  = cfg.get("year"), cfg.get("month")
docs  = get_active_doctors()
assts = get_active_assistants()

result = st.session_state.get("result") or cfg.get("saved_result") or {}
if not result:
    st.warning("⚠️ 尚未生成班表，請先至「自動排班」執行排班。")
    st.stop()

st.success(f"✅ 班表已生成　{y} 年 {m} 月")
st.divider()

# ════════════════════════════════════════════════════════════
# Excel 下載
# ════════════════════════════════════════════════════════════

st.subheader("📥 下載 Excel 班表")
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("**助理總班表**")
    st.caption("按週次，含所有助理早午晚")
    st.download_button(
        "📋 下載總班表",
        to_excel_master(result, y, m, docs, assts),
        f"祐德助理總班表_{m}月.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with c2:
    st.markdown("**助理個人班表**")
    st.caption("月曆格式，含職位與診次統計")
    st.download_button(
        "👤 下載助理個人表",
        to_excel_individual(result, y, m, assts, docs),
        f"祐德助理個人表_{m}月.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with c3:
    st.markdown("**醫師個人班表**")
    st.caption("月曆格式，含跟診助理")
    st.download_button(
        "🩺 下載醫師班表",
        to_excel_doctor(result, y, m, docs, assts),
        f"祐德醫師班表_{m}月.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

st.divider()

# ════════════════════════════════════════════════════════════
# LINE 傳送
# ════════════════════════════════════════════════════════════

st.subheader("📱 LINE 傳送班表")

# 傳送模式選擇
send_mode = st.radio(
    "**傳送格式**",
    ["📝 文字訊息", "🖼️ 圖片班表（月曆圖）"],
    horizontal=True,
    help="圖片班表需安裝 matplotlib 套件（pip install matplotlib）",
)
use_image = "圖片" in send_mode

tab_asst, tab_doc, tab_group = st.tabs(["👩‍⚕️ 助理班表", "👨‍⚕️ 醫師班表", "📢 群組通知"])

# ── 助理 ─────────────────────────────────────────────────────
with tab_asst:
    col_s, col_p = st.columns([1, 2])
    sel_asst     = col_s.selectbox("選擇助理", [a["name"] for a in assts], key="ls_asst")
    asst_info    = next((a for a in assts if a["name"] == sel_asst), {})
    asst_token   = asst_info.get("line_notify_token","")

    preview_text = format_assistant_schedule(sel_asst, result, y, m, docs)
    col_p.text_area("📋 預覽（文字版）", preview_text, height=200, key="pv_asst")

    ca, cb = st.columns(2)
    if ca.button("📤 傳送此助理班表", use_container_width=True):
        if asst_token:
            if use_image:
                try:
                    img_bytes = generate_schedule_image(
                        sel_asst, result, y, m, assts, docs, role="assistant"
                    )
                    ok, err = send_line_notify_with_image(
                        asst_token, f"\n【{y}年{m}月個人班表】", img_bytes
                    )
                except Exception as e:
                    ok, err = False, f"圖片生成失敗：{e}"
            else:
                ok, err = send_line_notify(asst_token, f"\n{preview_text}")
            st.success("✅ 已傳送！") if ok else st.error(f"❌ {err}")
        else:
            st.warning(f"⚠️ {sel_asst} 未設定 LINE Token（至「人員設定」填入）")

    if cb.button("📤 批量傳送所有助理", type="secondary", use_container_width=True):
        ok_cnt, fail_list = 0, []
        progress = st.progress(0)
        for i, a in enumerate(assts):
            tok = a.get("line_notify_token","")
            if tok:
                if use_image:
                    try:
                        img_bytes = generate_schedule_image(
                            a["name"], result, y, m, assts, docs, role="assistant"
                        )
                        ok, err = send_line_notify_with_image(tok, f"\n【{y}年{m}月個人班表】", img_bytes)
                    except Exception as e:
                        ok, err = False, str(e)
                else:
                    text = format_assistant_schedule(a["name"], result, y, m, docs)
                    ok, err = send_line_notify(tok, f"\n{text}")
                if ok: ok_cnt += 1
                else:  fail_list.append(f"{a['name']}（{err}）")
            progress.progress((i+1)/len(assts))
        if ok_cnt:    st.success(f"✅ 成功傳送 {ok_cnt} 位！")
        if fail_list: st.error("❌ 失敗：" + "、".join(fail_list))

    no_tok = [a["name"] for a in assts if not a.get("line_notify_token")]
    if no_tok:
        st.caption(f"⚠️ 未設定 Token（無法自動傳送）：{', '.join(no_tok)}")

# ── 醫師 ─────────────────────────────────────────────────────
with tab_doc:
    col_s, col_p = st.columns([1, 2])
    sel_doc      = col_s.selectbox("選擇醫師", [d["name"] for d in docs], key="ls_doc")
    doc_info     = next((d for d in docs if d["name"] == sel_doc), {})
    doc_token    = doc_info.get("line_notify_token","")

    manual       = cfg.get("manual_schedule",[])
    doc_preview  = format_doctor_schedule(sel_doc, manual, y, m, result)
    col_p.text_area("📋 預覽（文字版）", doc_preview, height=200, key="pv_doc")

    da, db = st.columns(2)
    if da.button("📤 傳送此醫師班表", use_container_width=True, key="send_doc_one"):
        if doc_token:
            if use_image:
                try:
                    img_bytes = generate_schedule_image(
                        sel_doc, result, y, m, assts, docs, role="doctor"
                    )
                    ok, err = send_line_notify_with_image(doc_token, f"\n【{y}年{m}月班表確認】", img_bytes)
                except Exception as e:
                    ok, err = False, f"圖片生成失敗：{e}"
            else:
                ok, err = send_line_notify(doc_token, f"\n{doc_preview}")
            st.success("✅ 已傳送！") if ok else st.error(f"❌ {err}")
        else:
            st.warning(f"⚠️ {sel_doc} 未設定 LINE Token")

    if db.button("📤 批量傳送所有醫師", type="secondary", use_container_width=True, key="send_doc_all"):
        ok_cnt, fail_list = 0, []
        for d in docs:
            tok = d.get("line_notify_token","")
            if tok:
                if use_image:
                    try:
                        img_bytes = generate_schedule_image(
                            d["name"], result, y, m, assts, docs, role="doctor"
                        )
                        ok, err = send_line_notify_with_image(tok, f"\n【{y}年{m}月班表確認】", img_bytes)
                    except Exception as e:
                        ok, err = False, str(e)
                else:
                    text = format_doctor_schedule(d["name"], manual, y, m, result)
                    ok, err = send_line_notify(tok, f"\n{text}")
                if ok: ok_cnt += 1
                else:  fail_list.append(f"{d['name']}（{err}）")
        if ok_cnt:    st.success(f"✅ 成功傳送 {ok_cnt} 位！")
        if fail_list: st.error("❌ 失敗：" + "、".join(fail_list))

# ── 群組 ─────────────────────────────────────────────────────
with tab_group:
    group_token = st.text_input(
        "群組 LINE Notify Token",
        value=cfg.get("line_group_token",""),
        type="password",
        key="gp_token",
    )
    if group_token != cfg.get("line_group_token",""):
        cfg["line_group_token"] = group_token; save_config(cfg)

    group_msg = st.text_area(
        "傳送內容",
        value=f"【{y}年{m}月班表已定稿】\n請等候管理員傳送您的個人班表，或至排班系統查詢。",
        height=100,
    )
    if st.button("📤 傳送至群組", use_container_width=True):
        if group_token:
            ok, err = send_line_notify(group_token, f"\n{group_msg}")
            st.success("✅ 已傳送至群組！") if ok else st.error(f"❌ {err}")
        else:
            st.warning("請先填入群組 Token（也可至「人員設定 → LINE Token 設定」填入）。")
