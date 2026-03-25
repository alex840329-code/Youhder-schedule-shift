# modules/data_utils.py
# 日期工具、槽位解析、診次計算

import calendar
from datetime import date, timedelta
from typing import Dict, Set, Tuple

WEEKDAY_NAMES = ["一", "二", "三", "四", "五", "六"]
SHIFT_ORDER   = {"早": 1, "午": 2, "晚": 3}


# ── 日期生成 ────────────────────────────────────────────────


def generate_month_dates(year: int, month: int) -> list:
    """傳回當月所有上班日（週一至週六）的 date 物件清單。"""
    num_days = calendar.monthrange(year, month)[1]
    return [
        date(year, month, d)
        for d in range(1, num_days + 1)
        if date(year, month, d).weekday() != 6  # 排除週日
    ]


def get_padded_weeks(year: int, month: int) -> list:
    """
    以週一為起點、週六為終點（排除週日），產生含跨月日期的週組。
    每個週組為 list[dict]，各 dict 含：date, is_curr, str, disp。
    """
    first_day = date(year, month, 1)
    last_day  = date(year, month, calendar.monthrange(year, month)[1])
    curr = first_day - timedelta(days=first_day.weekday())
    weeks = []
    while True:
        if curr > last_day and curr.weekday() == 0:
            break
        week_dates = []
        for _ in range(7):
            if curr.weekday() != 6:
                is_curr = (curr.month == month)
                wd_ch = WEEKDAY_NAMES[curr.weekday()]
                week_dates.append({
                    "date":    curr,
                    "is_curr": is_curr,
                    "str":     str(curr),
                    "disp":    f"{curr.month}/{curr.day}({wd_ch})" if is_curr
                               else f"⬛ {curr.month}/{curr.day}",
                })
            curr += timedelta(days=1)
        weeks.append(week_dates)
    return weeks


# ── 診次上下限計算 ───────────────────────────────────────────


def calculate_shift_limits(year: int, month: int) -> Tuple[int, int]:
    """
    全職助理診次上下限。
    上限 = 當月工作日 * 2
    基本 (下限) = 上限 - 8
    """
    dates = generate_month_dates(year, month)
    max_s = len(dates) * 2
    return max_s - 8, max_s


# ── 槽位字串解析 ────────────────────────────────────────────


_WD_MAP  = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6}
_SH_MAP  = {"早": "早", "午": "午", "晚": "晚"}
_ROLE_MAP = {"櫃": "counter", "流": "floater", "看": "look", "跟": "doctor", "行": "look"}


def parse_slot_string(text: str, is_fixed: bool = False):
    """
    解析槽位字串。
    is_fixed=False → 回傳 set of (weekday_int, shift_str)
    is_fixed=True  → 回傳 dict of (weekday_int, shift_str): role_str
    格式範例：
      whitelist  → "一早,二午,六晚"
      fixed_slots → "一早櫃,五晚流"
    """
    if not text or not isinstance(text, str):
        return {} if is_fixed else set()
    items = [x.strip() for x in text.replace("、", ",").split(",") if x.strip()]
    if is_fixed:
        res: Dict[Tuple, str] = {}
        for item in items:
            if len(item) < 3:
                continue
            wd = _WD_MAP.get(item[0])
            sh = _SH_MAP.get(item[1])
            rl = _ROLE_MAP.get(item[2])
            if wd is not None and sh is not None and rl is not None:
                res[(wd, sh)] = rl
        return res
    else:
        res_set: Set[Tuple] = set()
        for item in items:
            if len(item) < 2:
                continue
            wd = _WD_MAP.get(item[0])
            sh = _SH_MAP.get(item[1])
            if wd is not None and sh is not None:
                res_set.add((wd, sh))
        return res_set


# ── 目標日期展開工具（消除重複邏輯）─────────────────────────


def get_target_dates(act: dict, year: int, month: int) -> list:
    """
    根據 action dict 解析目標日期字串清單。
    支援：
      - act["date"]        → 單一日期字串
      - act["weekday"]     → 當月所有符合星期（1=一 … 6=六）
      - act["week_number"] → 配合 weekday 指定第 N 個
    """
    targets = []
    if act.get("date"):
        targets.append(act["date"])
    elif act.get("weekday"):
        wd_target = act["weekday"] - 1  # 0=Monday
        count = 0
        for d in range(1, calendar.monthrange(year, month)[1] + 1):
            dt_obj = date(year, month, d)
            if dt_obj.weekday() == wd_target:
                count += 1
                if act.get("week_number") and count != act["week_number"]:
                    continue
                targets.append(str(dt_obj))
    return targets
