# modules/excel_export.py
# Excel 報表輸出：總班表 + 助理個人班表 + 醫師個人班表

import io
import collections
from datetime import datetime

import streamlit as st

from modules.data_utils import (
    generate_month_dates,
    get_padded_weeks,
    calculate_shift_limits,
    parse_slot_string,
    WEEKDAY_NAMES,
)


# ════════════════════════════════════════════════════════════
# 格式定義
# ════════════════════════════════════════════════════════════

def _build_formats(wb):
    """建立所有共用格式物件。"""
    def fmt(**kw):
        base = {"align": "center", "valign": "vcenter", "border": 1}
        base.update(kw)
        return wb.add_format(base)

    return {
        # 標題
        "title":   wb.add_format({"bold": True, "align": "center", "valign": "vcenter",
                                   "font_size": 18}),
        "name":    wb.add_format({"bold": True, "align": "left",   "valign": "vcenter",
                                   "font_size": 14}),
        # 欄標頭
        "h_col":   fmt(bold=True, bg_color="#E0E0E0"),
        "h_odd":   fmt(bold=True, bg_color="#FFD966"),    # 奇數日（一三五）
        "h_even":  fmt(bold=True, bg_color="#9DC3E6"),    # 偶數日（二四六）
        "h_gray":  fmt(bold=True, bg_color="#E0E0E0", font_color="#808080"),  # 跨月

        # 資料格（奇數日）
        "c_odd1":  fmt(bg_color="#FDE9D9"),
        "c_odd2":  fmt(bg_color="#FCD5B4"),
        "c_odd3":  fmt(bg_color="#FABF8F", right=2),

        # 資料格（偶數日）
        "c_even1": fmt(bg_color="#DDEBF7"),
        "c_even2": fmt(bg_color="#BDD7EE"),
        "c_even3": fmt(bg_color="#9DC3E6", right=2),

        # 灰色（跨月 / 非工作日）
        "c_gray":  fmt(bg_color="#F0F0F0", font_color="#A0A0A0"),
        "c_gray3": fmt(bg_color="#F0F0F0", font_color="#A0A0A0", right=2),

        # 個人班表
        "c_norm":  fmt(),
        "c_wknd":  fmt(bg_color="#FFF2CC"),  # 週六
        "note":    wb.add_format({"align": "left", "valign": "vcenter", "font_size": 11}),
    }


def _cell_fmts(fmts, is_curr, is_even, shift_idx):
    """回傳資料格格式（依是否本月、奇偶日、早/午/晚）。"""
    if not is_curr:
        return fmts["c_gray3"] if shift_idx == 2 else fmts["c_gray"]
    if is_even:
        return [fmts["c_even1"], fmts["c_even2"], fmts["c_even3"]][shift_idx]
    return [fmts["c_odd1"], fmts["c_odd2"], fmts["c_odd3"]][shift_idx]


def _val_with_rescue(raw_name: str, nick: str, rescued_list: list) -> str:
    if raw_name in rescued_list:
        return nick + "(救)"
    return nick


# ════════════════════════════════════════════════════════════
# 總班表
# ════════════════════════════════════════════════════════════

def to_excel_master(schedule_result, year, month, docs, assts):
    """
    輸出「總班表」Excel，格式仿參考 xlsm：
    按週分區，每日含早/午/晚三格；含醫師跟診、櫃台、流動列。
    """
    output = io.BytesIO()
    writer = __import__("pandas").ExcelWriter(output, engine="xlsxwriter")
    wb = writer.book
    ws = wb.add_worksheet("助理班表")
    fmts = _build_formats(wb)

    cfg  = st.session_state.config
    ms   = cfg.get("manual_schedule", [])
    ms_set   = {f"{x['Date']}_{x['Shift']}_{x['Doctor']}" for x in ms}
    doc_cnt  = collections.defaultdict(int)
    for x in ms:
        doc_cnt[f"{x['Date']}_{x['Shift']}"] += 1

    dyn_flt = cfg.get("dynamic_flt", True)
    dyn_ctr = cfg.get("dynamic_ctr", True)
    ctr_val = cfg.get("ctr_count", 2)
    flt_val = cfg.get("flt_count", 1)

    # 主標題
    ws.merge_range(0, 0, 0, 18, f"祐德牙醫診所 {month}月助理班表", fmts["title"])
    ws.set_row(0, 30)

    p_weeks = get_padded_weeks(year, month)
    row = 2

    for w_dates in p_weeks:
        # ── 日期列 ────────────────────────────────────────
        ws.write(row, 0, "日期", fmts["h_col"])
        col = 1
        for dt in w_dates:
            is_even  = dt["date"].weekday() % 2 != 0
            f_h = fmts["h_even"] if is_even else fmts["h_odd"]
            if not dt["is_curr"]:
                f_h = fmts["h_gray"]
            disp = (f"{dt['date'].month}/{dt['date'].day}"
                    f"({WEEKDAY_NAMES[dt['date'].weekday()]})"
                    if dt["is_curr"]
                    else f"非本月 {dt['date'].month}/{dt['date'].day}")
            ws.merge_range(row, col, row, col + 2, disp, f_h)
            col += 3
        row += 1

        # ── 時段列 ────────────────────────────────────────
        ws.write(row, 0, "時段", fmts["h_col"])
        col = 1
        for dt in w_dates:
            is_even = dt["date"].weekday() % 2 != 0
            for i, s in enumerate(["早", "午", "晚"]):
                ws.write(row, col, s, _cell_fmts(fmts, dt["is_curr"], is_even, i))
                col += 1
        row += 1

        # ── 醫師列 ────────────────────────────────────────
        for doc in docs:
            ws.write(row, 0, doc["nick"], fmts["h_col"])
            col = 1
            for dt in w_dates:
                is_even = dt["date"].weekday() % 2 != 0
                for i, s in enumerate(["早", "午", "晚"]):
                    f_c = _cell_fmts(fmts, dt["is_curr"], is_even, i)
                    if not dt["is_curr"]:
                        ws.write(row, col, "-", f_c)
                    else:
                        k    = f"{dt['str']}_{s}"
                        anm  = schedule_result.get(k, {}).get("doctors", {}).get(doc["name"], "")
                        resc = schedule_result.get(k, {}).get("rescued", {}).get("doctors", [])
                        if anm:
                            nick = next((a["nick"] for a in assts if a["name"] == anm), "")
                            val  = _val_with_rescue(anm, nick, resc)
                        elif f"{dt['str']}_{s}_{doc['name']}" in ms_set:
                            val = "⚠️缺"
                        else:
                            val = "休"
                        ws.write(row, col, val, f_c)
                    col += 1
            row += 1

        # ── 櫃台/流動/看行政列 ─────────────────────────────
        for rnm, rk, ri in [
            ("櫃台1", "counter", 0), ("櫃台2", "counter", 1),
            ("流動",  "floater", 0), ("流動2", "floater", 1),
            ("看/行", "look",    0),
        ]:
            ws.write(row, 0, rnm, fmts["h_col"])
            col = 1
            for dt in w_dates:
                is_even = dt["date"].weekday() % 2 != 0
                for i, s in enumerate(["早", "午", "晚"]):
                    f_c = _cell_fmts(fmts, dt["is_curr"], is_even, i)
                    if not dt["is_curr"]:
                        ws.write(row, col, "-", f_c)
                    else:
                        k    = f"{dt['str']}_{s}"
                        lst  = schedule_result.get(k, {}).get(rk, [])
                        resc = schedule_result.get(k, {}).get("rescued", {}).get(rk, [])
                        if ri < len(lst):
                            anm  = lst[ri]
                            nick = next((a["nick"] for a in assts if a["name"] == anm), "")
                            val  = _val_with_rescue(anm, nick, resc)
                        else:
                            req = 0
                            if rk == "counter":
                                req = max(ctr_val, 2) if (dyn_ctr and doc_cnt[k] >= 5) else ctr_val
                            elif rk == "floater":
                                req = max(flt_val, 2) if (dyn_flt and doc_cnt[k] >= 5) else flt_val
                            val = "⚠️缺" if ri < req else ""
                        ws.write(row, col, val, f_c)
                    col += 1
            row += 1

        row += 2  # 週間空行

    writer.close()
    output.seek(0)
    return output


# ════════════════════════════════════════════════════════════
# 助理個人班表
# ════════════════════════════════════════════════════════════

_SHIFT_NOTES = [
    "註：全診及午晚班有空請輪流抽空吃飯，謹守 30 分鐘規定，以免影響其他助理。",
    "1〉早午班 8:30AM～12:00PM 1:30PM～6:00PM",
    "2〉午晚班 1:30PM～10:00PM",
    "3〉早晚班 8:00AM～12:00PM 6:00PM～10:00PM",
    "4〉一個早班 8:00AM～12:00PM",
    "5〉一個午班 2:00PM～6:00PM",
    "6〉一個晚班 6:00PM～10:00PM",
    "7〉全診〈早午晚〉8:00AM～12:00PM 1:30PM～10:00PM",
]


def to_excel_individual(schedule_result, year, month, assts, docs):
    """
    輸出「助理個人班表」Excel，仿參考格式：
    月曆式雙欄佈局，顯示職位（看/櫃/流/醫師簡稱），下方附班別時間說明。
    """
    output = io.BytesIO()
    import pandas as pd
    writer = pd.ExcelWriter(output, engine="xlsxwriter")
    wb = writer.book
    fmts   = _build_formats(wb)
    dates  = generate_month_dates(year, month)
    b_min, b_max = calculate_shift_limits(year, month)

    adv_rules = st.session_state.config.get("adv_rules", {})
    parsed_admin = {n: parse_slot_string(r.get("admin_slots", ""))
                    for n, r in adv_rules.items()}

    for a in assts:
        anm = a["name"]
        ws  = wb.add_worksheet(a["nick"])

        # 計算實排診數
        act = 0
        for k, v in schedule_result.items():
            dt_str, sh = k.split("_")
            dt_obj = datetime.strptime(dt_str, "%Y-%m-%d").date()
            in_grid = anm in (
                list(v.get("doctors", {}).values())
                + v.get("counter", [])
                + v.get("floater", [])
                + v.get("look", [])
            )
            is_admin = (dt_obj.weekday(), sh) in parsed_admin.get(anm, set())
            if in_grid or is_admin:
                act += 1

        cap = a.get("custom_max") or b_max

        # 標題
        ws.merge_range(0, 0, 0, 10,
                       f"祐德牙醫診所 {month}月助理班表", fmts["title"])
        ws.set_row(0, 30)
        ws.merge_range(1, 0, 1, 10,
                       f"姓名：{anm}    實排：{act} / 上限：{cap}",
                       fmts["name"])
        ws.set_row(1, 25)

        # 欄頭（左右各一份）
        headers = ["日期", "星期", "早", "午", "晚"]
        for i, h in enumerate(headers):
            ws.write(3, i,     h, fmts["h_col"])
            ws.write(3, i + 6, h, fmts["h_col"])

        mid = (len(dates) + 1) // 2

        for r_idx, dt in enumerate(dates):
            col_off = 0 if r_idx < mid else 6
            row_off = r_idx if r_idx < mid else r_idx - mid
            is_sat  = dt.weekday() == 5
            fc = fmts["c_wknd"] if is_sat else fmts["c_norm"]

            ws.write(row_off + 4, col_off,     f"{dt.month}/{dt.day}", fc)
            ws.write(row_off + 4, col_off + 1, WEEKDAY_NAMES[dt.weekday()], fc)

            for ci, sh in enumerate(["早", "午", "晚"]):
                data = schedule_result.get(f"{dt}_{sh}", {})
                resc_all = (data.get("rescued", {}).get("doctors", [])
                            + data.get("rescued", {}).get("counter", [])
                            + data.get("rescued", {}).get("floater", []))
                v = ""
                if   (dt.weekday(), sh) in parsed_admin.get(anm, set()):
                    v = "行"
                elif anm in data.get("look", []):
                    v = "看"
                elif anm in data.get("floater", []):
                    v = "流"
                elif anm in data.get("counter", []):
                    v = "櫃"
                else:
                    for dn, asn in data.get("doctors", {}).items():
                        if asn == anm:
                            v = next((d["nick"] for d in docs if d["name"] == dn), dn)

                if v and anm in resc_all:
                    v += "(救)"
                ws.write(row_off + 4, col_off + 2 + ci, v, fc)

        # 附註
        last_row = mid + 6
        for i, note in enumerate(_SHIFT_NOTES):
            ws.merge_range(last_row + i, 0, last_row + i, 11, note, fmts["note"])

    writer.close()
    output.seek(0)
    return output


# ════════════════════════════════════════════════════════════
# 醫師個人班表
# ════════════════════════════════════════════════════════════

def to_excel_doctor(schedule_result, year, month, docs, assts):
    """
    輸出「醫師個人班表」Excel：
    月曆式雙欄佈局，顯示上班時段與搭配助理簡稱。
    """
    output = io.BytesIO()
    import pandas as pd
    writer = pd.ExcelWriter(output, engine="xlsxwriter")
    wb    = writer.book
    fmts  = _build_formats(wb)
    dates = generate_month_dates(year, month)
    ms    = st.session_state.config.get("manual_schedule", [])

    for doc in docs:
        dnm = doc["name"]
        ws  = wb.add_worksheet(doc["nick"])

        ws.merge_range(0, 0, 0, 10,
                       f"祐德牙醫診所 {month}月醫師班表", fmts["title"])
        ws.set_row(0, 30)
        ws.merge_range(1, 0, 1, 10, f"醫師：{dnm}", fmts["name"])
        ws.set_row(1, 25)

        headers = ["日期", "星期", "早", "午", "晚"]
        for i, h in enumerate(headers):
            ws.write(3, i,     h, fmts["h_col"])
            ws.write(3, i + 6, h, fmts["h_col"])

        mid = (len(dates) + 1) // 2

        for r_idx, dt in enumerate(dates):
            col_off = 0 if r_idx < mid else 6
            row_off = r_idx if r_idx < mid else r_idx - mid
            is_sat  = dt.weekday() == 5
            fc = fmts["c_wknd"] if is_sat else fmts["c_norm"]

            ws.write(row_off + 4, col_off,     f"{dt.month}/{dt.day}", fc)
            ws.write(row_off + 4, col_off + 1, WEEKDAY_NAMES[dt.weekday()], fc)

            for ci, sh in enumerate(["早", "午", "晚"]):
                has_shift = any(
                    m for m in ms
                    if m["Date"] == str(dt) and m["Shift"] == sh and m["Doctor"] == dnm
                )
                if has_shift:
                    data = schedule_result.get(f"{dt}_{sh}", {})
                    asst_name = data.get("doctors", {}).get(dnm, "")
                    nick = next((a["nick"] for a in assts if a["name"] == asst_name), "")
                    v = nick if nick else "⚠️缺"
                else:
                    v = ""
                ws.write(row_off + 4, col_off + 2 + ci, v, fc)

    writer.close()
    output.seek(0)
    return output
