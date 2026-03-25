# pages/06_請假登記.py — 助理請假登記（月曆格式）+ LINE 通知

import streamlit as st
from datetime import datetime

from modules.config import init_session_config, save_config, get_active_assistants, get_active_doctors
from modules.calendar_ui import render_month_calendar
from modules.line_integration import send_line_notify, format_leave_request_message

st.set_page_config(page_title="請假登記", page_icon="🏖️", layout="wide")
init_session_config()

st.title("🏖️ 請假登記")
st.caption("勾選助理的請假時段（打勾 = 請假）。可透過 LINE 傳送請假確認給助理。")

cfg       = st.session_state.config
y, m      = cfg.get("year"), cfg.get("month")
is_locked = cfg.get("is_locked", False)
leaves    = cfg.get("leaves", {})
assts     = get_active_assistants()

if not assts:
    st.warning("請先至「人員設定」啟用助理。")
    st.stop()
if is_locked:
    st.error("🔒 系統已鎖定，無法修改。")

st.info(f"📆 目前月份：**{y} 年 {m} 月**")

tab_asst, tab_doc = st.tabs(["👩‍⚕️ 助理請假", "👨‍⚕️ 醫師班表調整"])

# ════════════════════════════════════════════════════════════
# 助理請假
# ════════════════════════════════════════════════════════════

with tab_asst:
    col_sel, col_line = st.columns([2, 2])

    with col_sel:
        sel_a = st.selectbox("📌 選擇助理", [a["name"] for a in assts])

    with col_line:
        asst_info  = next((a for a in assts if a["name"] == sel_a), {})
        asst_token = asst_info.get("line_notify_token","")
        st.markdown("**📱 LINE 傳送**")
        if asst_token:
            if st.button("📤 傳送請假確認給此助理", use_container_width=True, key="line_asst_send"):
                text = format_leave_request_message(sel_a, leaves, y, m)
                ok, err = send_line_notify(asst_token, f"\n{text}")
                st.success("✅ 已傳送！") if ok else st.error(f"❌ {err}")
        else:
            st.info("此助理未設定 LINE Token")

    st.markdown(f"### 📆 {sel_a}　{y} 年 {m} 月　請假登記")
    st.caption("✅ 打勾 = 請假（此時段排班時自動跳過此助理）")

    # 建立已請假的集合
    leave_set = set()
    for key, val in leaves.items():
        if not val:
            continue
        parts = key.split("_")
        if len(parts) == 3 and parts[0] == sel_a:
            _, dt_str, sh = parts
            try:
                dt = datetime.strptime(dt_str, "%Y-%m-%d")
                if dt.year == y and dt.month == m:
                    leave_set.add((dt_str, sh))
            except Exception:
                pass

    cal_result = render_month_calendar(
        prefix="leave",
        person=sel_a,
        checked_set=leave_set,
        year=y, month=m,
        is_locked=is_locked,
    )

    # 儲存
    if not is_locked:
        if st.button("💾 儲存此助理請假", type="primary", key="save_leave"):
            new_leaves = {k: v for k, v in leaves.items() if not k.startswith(f"{sel_a}_")}
            for slot_key, checked in cal_result.items():
                if checked:
                    dt_str, sh = slot_key.rsplit("_", 1)
                    new_leaves[f"{sel_a}_{dt_str}_{sh}"] = True
            cfg["leaves"] = new_leaves
            save_config(cfg)
            st.success(f"✅ {sel_a} 的請假已儲存！")
            st.rerun()

    # 請假摘要
    st.divider()
    with st.expander("📋 本月所有助理請假摘要"):
        leave_summary = {}
        for key, val in cfg.get("leaves",{}).items():
            if not val: continue
            parts = key.split("_")
            if len(parts) == 3:
                nm, dt, sh = parts
                try:
                    d = datetime.strptime(dt, "%Y-%m-%d")
                    if d.year == y and d.month == m:
                        leave_summary.setdefault(nm, []).append(f"{d.month}/{d.day}({sh})")
                except Exception:
                    pass
        if leave_summary:
            for nm, dates in sorted(leave_summary.items()):
                st.markdown(f"**{nm}**：" + "　".join(sorted(dates)))
        else:
            st.info("目前無請假記錄。")

    # 批量 LINE
    st.divider()
    with st.expander("📱 批量傳送請假確認給所有助理"):
        if st.button("📤 批量傳送", key="bulk_leave_line"):
            ok_cnt, fail_list = 0, []
            current_leaves = cfg.get("leaves", {})
            for a in assts:
                tok = a.get("line_notify_token","")
                if tok:
                    text = format_leave_request_message(a["name"], current_leaves, y, m)
                    ok, err = send_line_notify(tok, f"\n{text}")
                    if ok: ok_cnt += 1
                    else:  fail_list.append(f"{a['name']}（{err}）")
            if ok_cnt:    st.success(f"✅ 成功傳送 {ok_cnt} 位！")
            if fail_list: st.error("❌ 失敗：" + "、".join(fail_list))

# ════════════════════════════════════════════════════════════
# 醫師班表調整（捷徑）
# ════════════════════════════════════════════════════════════

with tab_doc:
    st.info("💡 醫師的休假請直接到「月份調整」頁面操作（取消勾選日期）。")
    st.page_link("pages/05_月份調整.py", label="→ 前往月份調整", icon="📅")

    docs   = get_active_doctors()
    manual = cfg.get("manual_schedule", [])
    if manual and docs:
        from modules.data_utils import generate_month_dates
        dates_all = generate_month_dates(y, m)
        st.divider()
        st.subheader("📊 醫師未上診日期（休假推算）")
        for d in docs:
            working = {x["Date"] for x in manual if x["Doctor"] == d["name"]}
            off_days = [
                dt for dt in dates_all if str(dt) not in working
            ]
            if off_days:
                disp = "　".join(
                    datetime.strptime(str(dt),"%Y-%m-%d").strftime(f"%-m/%-d")
                    for dt in off_days[:12]
                )
                st.markdown(f"**{d['name']}** 休：{disp}" + ("..." if len(off_days)>12 else ""))
