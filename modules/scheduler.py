# modules/scheduler.py
# 核心排班演算法：Phase 1（嚴格） + Phase 2（填洞救援）

import collections
import random
from datetime import datetime

import streamlit as st

from modules.data_utils import (
    generate_month_dates,
    calculate_shift_limits,
    parse_slot_string,
    SHIFT_ORDER,
)
from modules.config import get_active_assistants, get_active_doctors


# ════════════════════════════════════════════════════════════
# 共用：狀態物件初始化
# ════════════════════════════════════════════════════════════


def _build_slot_sort_key(slot: str):
    dt_str, sh = slot.split("_")
    wd = datetime.strptime(dt_str, "%Y-%m-%d").date().weekday()
    return (0 if wd == 5 else 1, dt_str, SHIFT_ORDER.get(sh, 9))


def _init_counts(assts, year, month):
    """初始化各助理的診次計數器與每日班別記錄。"""
    std_min, std_max = calculate_shift_limits(year, month)
    p_limits  = {}
    p_targets = {}
    for a in assts:
        nm = a["name"]
        cap = std_max if a.get("type") == "全職" else (a.get("custom_max") or 15)
        p_limits[nm]  = cap
        p_targets[nm] = cap

    p_counts  = {a["name"]: 0 for a in assts}
    p_flt_cnt = {a["name"]: 0 for a in assts}
    p_daily   = {a["name"]: collections.defaultdict(set) for a in assts}
    return p_limits, p_targets, p_counts, p_flt_cnt, p_daily


def _empty_slot():
    return {"doctors": {}, "counter": [], "floater": [], "look": [],
            "rescued": {"doctors": [], "counter": [], "floater": []}}


# ════════════════════════════════════════════════════════════
# Phase 1：嚴格排班
# ════════════════════════════════════════════════════════════


def run_auto_schedule(
    manual_schedule, leaves, pairing_matrix, adv_rules,
    ctr_count, flt_count, forced_assigns,
    dynamic_flt=True, balance_flt=True, dynamic_ctr=True,
):
    assts = get_active_assistants()
    docs  = get_active_doctors()
    year  = st.session_state.config.get("year")
    month = st.session_state.config.get("month")
    dates = generate_month_dates(year, month)
    sat_dates = [str(dt) for dt in dates if dt.weekday() == 5]

    p_limits, p_targets, p_counts, p_flt_cnt, p_daily = _init_counts(assts, year, month)

    # 解析固定班與行政診
    parsed_fixed = {nm: parse_slot_string(r.get("fixed_slots", ""), is_fixed=True)
                    for nm, r in adv_rules.items()}
    parsed_admin = {nm: parse_slot_string(r.get("admin_slots", ""), is_fixed=False)
                    for nm, r in adv_rules.items()}

    # 生成槽位清單（依週六優先、時段排序）
    slots = sorted(
        list({f"{x['Date']}_{x['Shift']}" for x in manual_schedule}),
        key=_build_slot_sort_key,
    )
    result = {s: _empty_slot() for s in slots}

    # ── Step 1：套用固定班 ──────────────────────────────────
    for slot in slots:
        dt_str, sh = slot.split("_")
        wd = datetime.strptime(dt_str, "%Y-%m-%d").date().weekday()
        for nm, fix_map in parsed_fixed.items():
            if (wd, sh) in fix_map:
                role = fix_map[(wd, sh)]
                if role in ("look", "counter", "floater"):
                    result[slot][role].append(nm)
                    p_counts[nm] += 1
                    p_daily[nm][dt_str].add(sh)
                    if role == "floater":
                        p_flt_cnt[nm] += 1
        # 行政診：計入診數，不加進格子
        for nm, admin_set in parsed_admin.items():
            if (wd, sh) in admin_set:
                p_counts[nm] += 1
                p_daily[nm][dt_str].add(sh)

    # ── Step 2：套用強制指定 ────────────────────────────────
    for slot in slots:
        dt_str, sh = slot.split("_")
        f_assign  = forced_assigns.get(slot, {})
        duty_docs = [x["Doctor"] for x in manual_schedule
                     if x["Date"] == dt_str and x["Shift"] == sh]

        for d_name, a_name in f_assign.get("doctors", {}).items():
            if d_name in duty_docs and a_name:
                result[slot]["doctors"][d_name] = a_name
                p_counts[a_name] += 1
                p_daily[a_name][dt_str].add(sh)

        for a_name in f_assign.get("counter", []):
            if a_name and a_name not in result[slot]["counter"]:
                result[slot]["counter"].append(a_name)
                p_counts[a_name] += 1
                p_daily[a_name][dt_str].add(sh)

        for a_name in f_assign.get("floater", []):
            if a_name and a_name not in result[slot]["floater"]:
                result[slot]["floater"].append(a_name)
                p_counts[a_name] += 1
                p_daily[a_name][dt_str].add(sh)
                p_flt_cnt[a_name] += 1

    # ── Step 3：自動排班主循環 ──────────────────────────────
    for slot in slots:
        dt_str, sh = slot.split("_")
        curr_dt = datetime.strptime(dt_str, "%Y-%m-%d").date()
        wd = curr_dt.weekday()
        slot_res = result[slot]
        duty_docs = [x["Doctor"] for x in manual_schedule
                     if x["Date"] == dt_str and x["Shift"] == sh]

        # 動態人力閾值
        n_docs = len(duty_docs)
        cur_ctr = max(ctr_count, 2) if (dynamic_ctr and n_docs >= 5) else ctr_count
        cur_flt = max(flt_count, 2) if (dynamic_flt and n_docs >= 5) else flt_count

        # ── 查詢函式 ───────────────────────────────────────

        def _assigned(nm):
            is_admin = (wd, sh) in parsed_admin.get(nm, set())
            return (nm in slot_res["counter"] or nm in slot_res["floater"]
                    or nm in slot_res["look"]
                    or nm in slot_res["doctors"].values()
                    or is_admin)

        def _heaven_earth_check(nm):
            """天地班：當日已有早班且無午班，禁止排晚班。"""
            day = p_daily[nm][dt_str]
            if sh == "晚" and "早" in day and "午" not in day:
                return False  # 違反
            return True

        def _consec_triple_check(nm):
            """
            連三診防護：今天若安排第三診（早午晚齊全），
            檢查昨日是否也是三診，若是則禁止。
            """
            day = p_daily[nm][dt_str]
            if sh == "晚" and "早" in day and "午" in day:
                # 今日將成為三診，查昨日
                from datetime import timedelta
                yesterday = str(curr_dt - timedelta(days=1))
                if len(p_daily[nm][yesterday]) >= 3:
                    return False  # 連續兩天三診，禁止
            return True

        def can_assign_strict(nm, role):
            if _assigned(nm):
                return False
            if f"{nm}_{dt_str}_{sh}" in leaves:
                return False
            if not _heaven_earth_check(nm):
                return False
            if not _consec_triple_check(nm):
                return False

            rule = adv_rules.get(nm, {})
            s_wl = parse_slot_string(rule.get("slot_whitelist", ""))
            if s_wl and (wd, sh) not in s_wl:
                return False

            asst_info = next((a for a in assts if a["name"] == nm), {})

            # 週六嚴格鐵律（全職）
            if wd == 5 and asst_info.get("type") == "全職":
                sat_nites = sum(1 for d in sat_dates if "晚" in p_daily[nm][d])
                if sh == "晚" and sat_nites >= 2:
                    return False
                worked_sats = [sd for sd in sat_dates if len(p_daily[nm][sd]) > 0]
                if dt_str not in worked_sats and len(worked_sats) >= len(sat_dates) - 1:
                    return False

            if p_counts[nm] >= p_limits[nm] and wd != 5:
                return False

            if rule.get("role_limit") == "僅櫃台"   and role != "counter": return False
            if rule.get("role_limit") == "僅流動"   and role != "floater": return False
            if rule.get("role_limit") == "僅跟診"   and role != "doctor":  return False
            if rule.get("shift_limit") == "僅晚班"  and sh != "晚":        return False
            if rule.get("shift_limit") == "僅早班"  and sh != "早":        return False
            if rule.get("shift_limit") == "僅午班"  and sh != "午":        return False

            if role == "counter":
                for av in [x.strip() for x in rule.get("avoid", "").split(",") if x.strip()]:
                    if av in slot_res["counter"]:
                        return False
            return True

        def calc_priority(candidates, r_type):
            scored = []
            for c in candidates:
                if not can_assign_strict(c, r_type):
                    continue
                asst_info = next((a for a in assts if a["name"] == c), {})
                rule = adv_rules.get(c, {})
                score = (p_targets[c] - p_counts[c]) * 2000

                s_wl = parse_slot_string(rule.get("slot_whitelist", ""))
                if s_wl and (wd, sh) in s_wl:
                    score += 500_000

                if r_type == "counter":
                    if asst_info.get("is_main_counter"):
                        score += 50_000
                    if asst_info.get("type") == "兼職":
                        score += 20_000
                    if rule.get("shift_limit") == "僅晚班" and sh == "晚":
                        score += 800_000

                if r_type == "floater":
                    if asst_info.get("is_main_counter"):
                        score -= 100_000
                    else:
                        weight = 100_000 if balance_flt else 500
                        score += (50 - p_flt_cnt[c]) * weight

                # 週六超級磁吸
                if wd == 5 and asst_info.get("type") == "全職":
                    score += 15_000
                    worked_sats = sum(1 for sd in sat_dates
                                      if sd != dt_str and len(p_daily[c][sd]) > 0)
                    sat_nites   = sum(1 for d in sat_dates
                                      if d != dt_str and "晚" in p_daily[c][d])
                    total_sats  = len(sat_dates)

                    if sh == "早":
                        if worked_sats < total_sats - 1:
                            score += (4 - worked_sats) * 1_000_000
                        else:
                            score -= 50_000_000
                    elif sh == "午":
                        if "早" in p_daily[c][dt_str]:
                            score += 50_000_000
                        elif worked_sats < total_sats - 1:
                            score += (4 - worked_sats) * 1_000_000
                        else:
                            score -= 50_000_000
                    elif sh == "晚":
                        if "午" in p_daily[c][dt_str]:
                            if sat_nites < 2:
                                score += 50_000_000
                            else:
                                score -= 50_000_000
                        else:
                            score -= 50_000_000

                scored.append((c, score + random.random()))
            scored.sort(key=lambda x: x[1], reverse=True)
            return [x[0] for x in scored]

        cand_pool = [a["name"] for a in assts]

        # 填櫃台
        needed_ctr = cur_ctr - len(slot_res["counter"])
        for c in calc_priority(cand_pool, "counter"):
            if needed_ctr <= 0:
                break
            slot_res["counter"].append(c)
            p_counts[c] += 1
            p_daily[c][dt_str].add(sh)
            needed_ctr -= 1

        # 填跟診 & 流動（依 balance_flt 決定順序）
        def _fill_doctors():
            for d_name in duty_docs:
                if d_name in slot_res["doctors"]:
                    continue
                picked = None
                for t in [pairing_matrix.get(d_name, {}).get(k) for k in ("1","2","3")]:
                    if t and can_assign_strict(t, "doctor"):
                        picked = t; break
                if not picked:
                    cands = calc_priority(cand_pool, "doctor")
                    if cands:
                        picked = cands[0]
                if picked:
                    slot_res["doctors"][d_name] = picked
                    p_counts[picked] += 1
                    p_daily[picked][dt_str].add(sh)

        def _fill_floater():
            needed = cur_flt - len(slot_res["floater"])
            for c in calc_priority(cand_pool, "floater"):
                if needed <= 0:
                    break
                slot_res["floater"].append(c)
                p_counts[c] += 1
                p_daily[c][dt_str].add(sh)
                p_flt_cnt[c] += 1
                needed -= 1

        if balance_flt:
            _fill_floater()
            _fill_doctors()
        else:
            _fill_doctors()
            _fill_floater()

    return result


# ════════════════════════════════════════════════════════════
# Phase 2：填洞救援（破格抓人）
# ════════════════════════════════════════════════════════════


def run_phase2_rescue(
    current_result, manual_schedule, leaves, adv_rules,
    assts, ctr_count, flt_count, year, month,
):
    dates     = generate_month_dates(year, month)
    sat_dates = [str(dt) for dt in dates if dt.weekday() == 5]
    _,_, p_counts, p_flt_cnt, p_daily = _init_counts(assts, year, month)

    dyn_flt = st.session_state.config.get("dynamic_flt", True)
    dyn_ctr = st.session_state.config.get("dynamic_ctr", True)

    parsed_admin = {nm: parse_slot_string(r.get("admin_slots", ""))
                    for nm, r in adv_rules.items()}

    # 重算現有診數
    for slot, res in current_result.items():
        dt_str, sh = slot.split("_")
        for a_name in res.get("doctors", {}).values():
            if a_name:
                p_counts[a_name] += 1; p_daily[a_name][dt_str].add(sh)
        for a_name in res.get("counter", []):
            if a_name:
                p_counts[a_name] += 1; p_daily[a_name][dt_str].add(sh)
        for a_name in res.get("floater", []):
            if a_name:
                p_counts[a_name] += 1; p_daily[a_name][dt_str].add(sh)
                p_flt_cnt[a_name] += 1
        for a_name in res.get("look", []):
            if a_name:
                p_counts[a_name] += 1; p_daily[a_name][dt_str].add(sh)

    slots = sorted(
        current_result.keys(),
        key=lambda x: (x.split("_")[0], SHIFT_ORDER.get(x.split("_")[1], 9)),
    )

    p_targets = {}
    std_min, std_max = calculate_shift_limits(year, month)
    for a in assts:
        cap = std_max if a.get("type") == "全職" else (a.get("custom_max") or 15)
        p_targets[a["name"]] = cap

    for slot in slots:
        dt_str, sh = slot.split("_")
        curr_dt = datetime.strptime(dt_str, "%Y-%m-%d").date()
        wd = curr_dt.weekday()
        slot_res = current_result[slot]
        if "rescued" not in slot_res:
            slot_res["rescued"] = {"doctors": [], "counter": [], "floater": []}

        duty_docs = [x["Doctor"] for x in manual_schedule
                     if x["Date"] == dt_str and x["Shift"] == sh]
        n_docs = len(duty_docs)
        cur_ctr = max(ctr_count, 2) if (dyn_ctr and n_docs >= 5) else ctr_count
        cur_flt = max(flt_count, 2) if (dyn_flt and n_docs >= 5) else flt_count

        needed_ctr = cur_ctr - len(slot_res["counter"])
        needed_flt = cur_flt - len(slot_res["floater"])
        missing_docs = [d for d in duty_docs
                        if not slot_res["doctors"].get(d)]

        if needed_ctr <= 0 and needed_flt <= 0 and not missing_docs:
            continue

        def _in_slot(nm):
            return (nm in slot_res["counter"] or nm in slot_res["floater"]
                    or nm in slot_res["look"]
                    or nm in slot_res["doctors"].values())

        def can_rescue(nm, role):
            if _in_slot(nm): return False
            if f"{nm}_{dt_str}_{sh}" in leaves: return False
            rule = adv_rules.get(nm, {})
            s_wl = parse_slot_string(rule.get("slot_whitelist", ""))
            if s_wl and (wd, sh) not in s_wl: return False
            if rule.get("role_limit") == "僅櫃台"  and role != "counter": return False
            if rule.get("role_limit") == "僅流動"  and role != "floater": return False
            if rule.get("role_limit") == "僅跟診"  and role != "doctor":  return False
            if rule.get("shift_limit") == "僅晚班" and sh != "晚":        return False
            if rule.get("shift_limit") == "僅早班" and sh != "早":        return False
            if rule.get("shift_limit") == "僅午班" and sh != "午":        return False
            return True

        def score_rescue(candidates, r_type):
            scored = []
            for c in candidates:
                if not can_rescue(c, r_type): continue
                asst_info = next((a for a in assts if a["name"] == c), {})
                score = (p_targets[c] - p_counts[c]) * 2000

                # 軟阻擋（扣分但不硬擋）
                if wd == 5 and asst_info.get("type") == "全職":
                    sat_nites = sum(1 for d in sat_dates if "晚" in p_daily[c][d])
                    if sh == "晚" and sat_nites >= 2:
                        score -= 1_000_000
                    worked = [sd for sd in sat_dates if len(p_daily[c][sd]) > 0]
                    if dt_str not in worked and len(worked) >= len(sat_dates) - 1:
                        score -= 1_000_000
                    if sh == "晚" and "午" not in p_daily[c][dt_str]:
                        score -= 1_000_000
                    if sh == "午" and "早" not in p_daily[c][dt_str]:
                        score -= 100_000

                scored.append((c, score + random.random()))
            scored.sort(key=lambda x: x[1], reverse=True)
            return [x[0] for x in scored]

        cand_pool = [a["name"] for a in assts]

        if needed_ctr > 0:
            for c in score_rescue(cand_pool, "counter"):
                if needed_ctr <= 0: break
                slot_res["counter"].append(c)
                slot_res["rescued"]["counter"].append(c)
                p_counts[c] += 1; p_daily[c][dt_str].add(sh)
                needed_ctr -= 1

        if needed_flt > 0:
            for c in score_rescue(cand_pool, "floater"):
                if needed_flt <= 0: break
                slot_res["floater"].append(c)
                slot_res["rescued"]["floater"].append(c)
                p_counts[c] += 1; p_daily[c][dt_str].add(sh)
                p_flt_cnt[c] += 1; needed_flt -= 1

        for d_name in missing_docs:
            for c in score_rescue(cand_pool, "doctor"):
                slot_res["doctors"][d_name] = c
                slot_res["rescued"]["doctors"].append(c)
                p_counts[c] += 1; p_daily[c][dt_str].add(sh)
                break

    return current_result
