import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import calendar
import io
import collections
import random
from datetime import datetime, date, timedelta

# 嘗試匯入 AI 模組
try:
    import google.generativeai as genai
    HAS_AI_LIB = True
except ImportError:
    HAS_AI_LIB = False

# --- 頁面設定 ---
st.set_page_config(page_title="祐德牙醫排班系統 v16.3 (終極雙層日曆版)", layout="wide", page_icon="🦷")
CONFIG_FILE = 'yude_config_v11.json'

# --- 1. 核心資料結構 ---

def get_default_config():
    return {
        "api_key": "", 
        "is_locked": False, 
        "doctors_struct": [
            {"order": 1, "name": "郭長熀醫師", "nick": "郭", "active": True},
            {"order": 2, "name": "陳冰沁醫師", "nick": "沁", "active": True},
            {"order": 3, "name": "陳志鈴醫師", "nick": "鈴", "active": True},
            {"order": 4, "name": "陳哲毓醫師", "nick": "毓", "active": True},
            {"order": 5, "name": "陳奕安醫師", "nick": "安", "active": True},
            {"order": 6, "name": "吳峻豪醫師", "nick": "吳", "active": True},
            {"order": 7, "name": "蔡尚妤醫師", "nick": "蔡", "active": True},
            {"order": 8, "name": "陳貞羽醫師", "nick": "貞", "active": True},
            {"order": 9, "name": "吳麗君醫師", "nick": "麗", "active": True},
            {"order": 10, "name": "魏大鈞醫師", "nick": "魏", "active": True},
            {"order": 11, "name": "郭燿東醫師", "nick": "東", "active": True}
        ],
        "assistants_struct": [
            {"name": "雯萱", "nick": "萱", "active": True, "type": "全職", "custom_max": None, "pref": "normal", "is_main_counter": True},
            {"name": "小瑜", "nick": "瑜", "active": True, "type": "兼職", "custom_max": 20, "pref": "normal", "is_main_counter": True},
            {"name": "欣霓", "nick": "霓", "active": True, "type": "兼職", "custom_max": 15, "pref": "normal", "is_main_counter": True},
            {"name": "昀霏", "nick": "霏", "active": True, "type": "全職", "custom_max": None, "pref": "normal", "is_main_counter": False},
            {"name": "湘婷", "nick": "湘", "active": True, "type": "全職", "custom_max": None, "pref": "normal", "is_main_counter": False},
            {"name": "怡安", "nick": "怡", "active": True, "type": "全職", "custom_max": None, "pref": "normal", "is_main_counter": False},
            {"name": "嘉宜", "nick": "宜", "active": True, "type": "全職", "custom_max": None, "pref": "low", "is_main_counter": False},
            {"name": "芷瑜", "nick": "芷", "active": True, "type": "全職", "custom_max": None, "pref": "normal", "is_main_counter": False},
            {"name": "佳臻", "nick": "臻", "active": True, "type": "全職", "custom_max": None, "pref": "normal", "is_main_counter": False},
            {"name": "紫心", "nick": "紫", "active": True, "type": "全職", "custom_max": None, "pref": "normal", "is_main_counter": False},
            {"name": "又嘉", "nick": "又", "active": True, "type": "全職", "custom_max": None, "pref": "low", "is_main_counter": False},
            {"name": "佳萱", "nick": "佳", "active": True, "type": "全職", "custom_max": None, "pref": "normal", "is_main_counter": False},
            {"name": "紫媛", "nick": "媛", "active": True, "type": "全職", "custom_max": None, "pref": "normal", "is_main_counter": False},
            {"name": "暐貽", "nick": "貽", "active": True, "type": "兼職", "custom_max": 18, "pref": "normal", "is_main_counter": False}
        ],
        "pairing_matrix": {
            "郭長熀醫師": {"1": "又嘉", "2": "紫心", "3": "怡安"},
            "陳冰沁醫師": {"1": "嘉宜", "2": "芷瑜", "3": ""},
            "陳志鈴醫師": {"1": "紫媛", "2": "芷瑜", "3": ""},
            "陳哲毓醫師": {"1": "佳萱", "2": "", "3": ""},
            "陳奕安醫師": {"1": "昀霏", "2": "", "3": ""},
            "吳峻豪醫師": {"1": "湘婷", "2": "", "3": ""},
            "蔡尚妤醫師": {"1": "佳臻", "2": "", "3": ""},
            "陳貞羽醫師": {"1": "怡安", "2": "", "3": ""},
            "吳麗君醫師": {"1": "又嘉", "2": "芷瑜", "3": ""},
            "魏大鈞醫師": {"1": "又嘉", "2": "", "3": ""},
            "郭燿東醫師": {"1": "芷瑜", "2": "嘉宜", "3": "昀霏"}
        },
        "adv_rules": {
            "雯萱": {"role_limit": "僅櫃台(含行政)", "shift_limit": "無限制", "slot_whitelist": "", "fixed_slots": "一早櫃,一晚櫃,二早櫃,二午看,三早櫃,三午看,四午櫃,五早櫃,五午櫃,五晚櫃", "avoid": ""},
            "小瑜": {"role_limit": "僅櫃台(含行政)", "shift_limit": "僅晚班", "slot_whitelist": "", "fixed_slots": "", "avoid": "怡安"},
            "欣霓": {"role_limit": "僅櫃台(含行政)", "shift_limit": "無限制", "slot_whitelist": "一午,二午,四晚", "fixed_slots": "", "avoid": ""},
            "暐貽": {"role_limit": "僅流動", "shift_limit": "無限制", "slot_whitelist": "二晚,三晚,四晚,六午,六晚", "fixed_slots": "", "avoid": ""},
            "怡安": {"role_limit": "無限制", "shift_limit": "無限制", "slot_whitelist": "", "fixed_slots": "", "avoid": "小瑜"},
            "紫媛": {"role_limit": "無限制", "shift_limit": "無限制", "slot_whitelist": "", "fixed_slots": "", "avoid": "昀霏"},
            "昀霏": {"role_limit": "無限制", "shift_limit": "無限制", "slot_whitelist": "", "fixed_slots": "", "avoid": "紫媛"}
        },
        "template_odd": {}, 
        "template_even": {},
        "year": 2026,
        "month": 4,
        "manual_schedule": {}, 
        "clinic_holidays": [], 
        "leaves": {}
    }

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "is_locked" not in data: data["is_locked"] = False
                if "adv_rules" not in data: data["adv_rules"] = get_default_config()["adv_rules"]
                if "assistants_struct" in data:
                    for a in data["assistants_struct"]:
                        if "pref" not in a: a["pref"] = "normal"
                        if "type" not in a: a["type"] = "全職"
                        if "is_main_counter" not in a: a["is_main_counter"] = False
                if "doctors_struct" not in data: return get_default_config()
                return data
        except:
            return get_default_config()
    return get_default_config()

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"存檔發生錯誤: {e}")

if 'config' not in st.session_state:
    st.session_state.config = load_config()

# --- 2. 輔助函式 ---

def get_active_doctors():
    docs = sorted(st.session_state.config["doctors_struct"], key=lambda x: x["order"])
    return [d for d in docs if d["active"]]

def get_active_assistants():
    return [a for a in st.session_state.config["assistants_struct"] if a["active"]]

def generate_month_dates(year, month):
    num_days = calendar.monthrange(year, month)[1]
    dates = []
    for d in range(1, num_days + 1):
        dt = date(year, month, d)
        if dt.weekday() == 6: continue 
        dates.append(dt)
    return dates

def get_workdays_count(year, month):
    return len(generate_month_dates(year, month))

def get_full_weeks(year, month):
    first_day = date(year, month, 1)
    start_date = first_day - timedelta(days=first_day.weekday()) 
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    
    weeks = []
    current_date = start_date
    while current_date <= last_day or current_date.weekday() != 0:
        if current_date > last_day and current_date.weekday() == 0:
            break
        week_dates = []
        for _ in range(7):
            if current_date.weekday() != 6: 
                week_dates.append(current_date)
            current_date += timedelta(days=1)
        weeks.append(week_dates)
    return weeks

def parse_slot_string(text, is_fixed=False):
    wd_map = {"一":0, "二":1, "三":2, "四":3, "五":4, "六":5}
    shift_map = {"早":"早", "午":"午", "晚":"晚"}
    role_map = {"櫃":"counter", "流":"floater", "看":"look", "跟":"doctor"}
    if not text: return {} if is_fixed else set()
    items = [x.strip() for x in text.replace("、", ",").split(",") if x.strip()]
    if is_fixed:
        res = {}
        for item in items:
            if len(item) < 3: continue
            wd = wd_map.get(item[0]); sh = shift_map.get(item[1]); rl = role_map.get(item[2])
            if wd is not None and sh is not None and rl is not None: res[(wd, sh)] = rl
        return res
    else:
        res = set()
        for item in items:
            if len(item) < 2: continue
            wd = wd_map.get(item[0]); sh = shift_map.get(item[1])
            if wd is not None and sh is not None: res.add((wd, sh))
        return res

# --- 3. AI 修改指令解析 ---

def get_dynamic_model(api_key):
    if not HAS_AI_LIB: return None
    genai.configure(api_key=api_key)
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods: return m.name
    except: pass
    return 'gemini-1.5-flash'

def call_ai_parse_leaves(api_key, text, year, month):
    if not HAS_AI_LIB or not api_key: return []
    try:
        model = genai.GenerativeModel(get_dynamic_model(api_key))
        prompt = f"""解析休假文字。{year}年{month}月。文字：{text}
        回傳 JSON Array: [{{"name": "小瑜", "date": "{year}-04-01", "shifts": ["早","午","晚"]}}]"""
        res = model.generate_content(prompt)
        return json.loads(res.text.replace("```json","").replace("```","").strip())
    except: return []

# --- 4. 核心排班演算法 ---

def run_auto_schedule(manual_schedule, leaves, pairing_matrix, adv_rules, ctr_count, flt_count):
    assts = get_active_assistants()
    docs = get_active_doctors()
    year = st.session_state.config.get("year", 2026)
    month = st.session_state.config.get("month", 4)
    dates = generate_month_dates(year, month)
    workdays = len(dates)
    
    std_max = workdays * 2
    std_min = std_max - 8
    total_sats = len([dt for dt in dates if dt.weekday() == 5])
    
    main_counters = [a["name"] for a in assts if a.get("is_main_counter", False)]
    
    p_targets = {}; p_limits = {}
    for a in assts:
        nm = a["name"]
        if a.get("type") == "全職":
            p_limits[nm] = std_max
            p_targets[nm] = std_min + 1 if a.get("pref") == "low" else std_max
        else:
            lim = a.get("custom_max") if a.get("custom_max") else 15
            p_limits[nm] = lim
            p_targets[nm] = lim
    if "又嘉" in p_targets: p_targets["又嘉"] = max(0, std_max - 3)

    p_counts = {a["name"]: 0 for a in assts}
    p_daily = {a["name"]: {} for a in assts} 
    
    shift_order = {"早": 1, "午": 2, "晚": 3}
    slots = sorted(list(set([f"{x['Date']}_{x['Shift']}" for x in manual_schedule])), 
                   key=lambda x: (x.split("_")[0], shift_order.get(x.split("_")[1], 99)))
                   
    result = {s: {"doctors": {}, "counter": [], "floater": [], "look": []} for s in slots}
    
    parsed_fixed = {}
    for name, r in adv_rules.items():
        if r.get("fixed_slots"): parsed_fixed[name] = parse_slot_string(r["fixed_slots"], is_fixed=True)

    for slot in slots:
        dt_str, sh = slot.split("_")
        wd = datetime.strptime(dt_str, "%Y-%m-%d").date().weekday()
        for name, fix_map in parsed_fixed.items():
            if (wd, sh) in fix_map:
                role = fix_map[(wd, sh)]
                if role == "look": result[slot]["look"].append(name)
                elif role == "counter": result[slot]["counter"].append(name)
                elif role == "floater": result[slot]["floater"].append(name)
                if role in ["look", "counter", "floater"]:
                    p_counts[name] += 1
                    if dt_str not in p_daily[name]: p_daily[name][dt_str] = set()
                    p_daily[name][dt_str].add(sh)

    for slot in slots:
        dt_str, sh = slot.split("_")
        wd = datetime.strptime(dt_str, "%Y-%m-%d").date().weekday()
        
        duty_docs = [x["Doctor"] for x in manual_schedule if x["Date"]==dt_str and x["Shift"]==sh]
        d_order = {d["name"]: d["order"] for d in docs}
        duty_docs.sort(key=lambda x: d_order.get(x, 99))
        slot_res = result[slot]
        
        def assigned_in_slot(name):
            return name in slot_res["counter"] or name in slot_res["floater"] or name in slot_res["look"] or name in slot_res["doctors"].values()

        def can_assign(name, role):
            if assigned_in_slot(name): return False
            if f"{name}_{slot}" in leaves: return False
            if p_counts[name] >= p_limits[name]: return False 
            
            rule = adv_rules.get(name, {})
            r_lim = rule.get("role_limit", "無限制")
            if r_lim == "僅櫃台(含行政)" and role not in ["counter", "look"]: return False
            if r_lim == "僅流動" and role != "floater": return False
            if r_lim == "僅跟診" and role != "doctor": return False
            if role == "look" and r_lim not in ["僅櫃台(含行政)"]: return False 
            
            s_lim = rule.get("shift_limit", "無限制")
            if s_lim == "僅早班" and sh != "早": return False
            if s_lim == "僅午班" and sh != "午": return False
            if s_lim == "僅晚班" and sh != "晚": return False
            
            s_wl_str = rule.get("slot_whitelist", "")
            if s_wl_str:
                s_wl = parse_slot_string(s_wl_str, is_fixed=False)
                if (wd, sh) not in s_wl: return False

            avoid_str = rule.get("avoid", "")
            if avoid_str:
                avoids = [x.strip() for x in avoid_str.split(",")]
                for av in avoids:
                    if assigned_in_slot(av): return False 

            today = p_daily[name].get(dt_str, set())
            
            if sh == "晚" and "早" in today and "午" not in today: return False 
            
            if sh == "晚" and "早" in today and "午" in today:
                curr_dt = datetime.strptime(dt_str, "%Y-%m-%d").date()
                yesterday_str = str(curr_dt - timedelta(days=1))
                yesterday_shifts = p_daily[name].get(yesterday_str, set())
                if len(yesterday_shifts) == 3: return False 

            return True

        def calculate_priority(candidates, curr_wd, curr_sh, curr_dt_str):
            scored = []
            for c in candidates:
                gap = p_targets[c] - p_counts[c]
                score = gap + random.random() * 0.3
                
                if curr_wd == 5:
                    is_ft = next((a["type"] == "全職" for a in assts if a["name"] == c), False)
                    if is_ft:
                        sats_worked = 0; sat_nights = 0
                        sat_dates = [str(dt) for dt in dates if dt.weekday() == 5]
                        for d in sat_dates:
                            if d in p_daily[c] and p_daily[c][d]:
                                sats_worked += 1
                                if "晚" in p_daily[c][d]: sat_nights += 1
                        
                        working_today = curr_dt_str in p_daily[c] and bool(p_daily[c][curr_dt_str])
                        
                        if curr_sh == "晚" and sat_nights >= 2: score -= 50
                        elif curr_sh != "晚" and not working_today and sats_worked >= total_sats - 1: score -= 50
                                
                scored.append((c, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            return [x[0] for x in scored]

        candidates_pool = [a["name"] for a in assts]
        
        for doc_name in duty_docs:
            if doc_name in slot_res["doctors"] and slot_res["doctors"][doc_name]: continue 
            picked = None
            prefs = pairing_matrix.get(doc_name, {})
            targets = [prefs.get("1"), prefs.get("2"), prefs.get("3")]
            targets = [t for t in targets if t]
            for t in targets:
                if can_assign(t, "doctor"): picked = t; break
            if not picked:
                for c in calculate_priority(candidates_pool, wd, sh, dt_str):
                    if can_assign(c, "doctor"): picked = c; break
            if picked:
                slot_res["doctors"][doc_name] = picked
                p_counts[picked] += 1
                if dt_str not in p_daily[picked]: p_daily[picked][dt_str] = set()
                p_daily[picked][dt_str].add(sh)
            else: slot_res["doctors"][doc_name] = ""

        needed_ctr = ctr_count - len(slot_res["counter"])
        if needed_ctr > 0:
            has_main = any(c in main_counters for c in slot_res["counter"])
            if not has_main:
                for c in calculate_priority(main_counters, wd, sh, dt_str):
                    if can_assign(c, "counter"):
                        slot_res["counter"].append(c)
                        p_counts[c] += 1
                        if dt_str not in p_daily[c]: p_daily[c][dt_str] = set()
                        p_daily[c][dt_str].add(sh)
                        needed_ctr -= 1
                        break
            for c in calculate_priority(candidates_pool, wd, sh, dt_str):
                if needed_ctr <= 0: break
                if can_assign(c, "counter"):
                    slot_res["counter"].append(c)
                    p_counts[c] += 1
                    if dt_str not in p_daily[c]: p_daily[c][dt_str] = set()
                    p_daily[c][dt_str].add(sh)
                    needed_ctr -= 1
        
        needed_flt = flt_count - len(slot_res["floater"])
        if needed_flt > 0:
            for c in calculate_priority(candidates_pool, wd, sh, dt_str):
                if needed_flt <= 0: break
                if can_assign(c, "floater"):
                    slot_res["floater"].append(c)
                    p_counts[c] += 1
                    if dt_str not in p_daily[c]: p_daily[c][dt_str] = set()
                    p_daily[c][dt_str].add(sh)
                    needed_flt -= 1

        result[slot] = slot_res

    return result, p_counts, std_min, std_max

# --- 5. Excel 輸出 ---
def to_excel_master(schedule_result, year, month, docs, assts):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book
    bg_w1 = '#FFFFFF'; bg_w2 = '#F5F5F5'
    fmt_base = {'align': 'center', 'valign': 'vcenter', 'border': 1}
    fmt_header = workbook.add_format({**fmt_base, 'bold': True, 'bg_color': '#E0E0E0'})
    sheet = workbook.add_worksheet("總班表")
    dates = generate_month_dates(year, month); weeks = {}; shifts = ["早", "午", "晚"]
    for dt in dates:
        iso = dt.isocalendar()[1]
        if iso not in weeks: weeks[iso] = []
        weeks[iso].append(dt)
    current_row = 0
    for wk_idx, (iso, week_dates) in enumerate(weeks.items()):
        bg = bg_w1 if wk_idx % 2 == 0 else bg_w2
        fmt_wk = workbook.add_format({**fmt_base, 'bg_color': bg})
        fmt_wk_bold = workbook.add_format({**fmt_base, 'bg_color': bg, 'bold': True})
        sheet.write(current_row, 0, f"第 {wk_idx+1} 週", fmt_header)
        col = 1
        for dt in week_dates:
            sheet.merge_range(current_row, col, current_row, col+2, f"{dt.month}/{dt.day} ({['一','二','三','四','五','六'][dt.weekday()]})", fmt_header)
            col += 3
        current_row += 1
        sheet.write(current_row, 0, "時段", fmt_header)
        col = 1
        for dt in week_dates:
            for s in shifts:
                sheet.write(current_row, col, s, fmt_wk_bold); col += 1
        current_row += 1
        for doc in docs:
            sheet.write(current_row, 0, doc["nick"], fmt_wk_bold)
            col = 1
            for dt in week_dates:
                for s in shifts:
                    k = f"{dt}_{s}"; v = ""
                    if k in schedule_result:
                        v = schedule_result[k]["doctors"].get(doc["name"], "")
                        for a in assts: 
                            if a["name"]==v: v=a["nick"]; break
                    sheet.write(current_row, col, v, fmt_wk); col += 1
            current_row += 1
        roles = [("櫃台1", "counter", 0), ("櫃台2", "counter", 1), ("流動", "floater", 0), ("看", "look", 0)]
        for rname, rkey, ridx in roles:
            sheet.write(current_row, 0, rname, fmt_wk_bold)
            col = 1
            for dt in week_dates:
                for s in shifts:
                    k = f"{dt}_{s}"; v = ""
                    if k in schedule_result:
                        lst = schedule_result[k].get(rkey, [])
                        if ridx < len(lst):
                            nm = lst[ridx]
                            for a in assts:
                                if a["name"]==nm: v=a["nick"]; break
                            if not v: v = nm
                    sheet.write(current_row, col, v, fmt_wk); col += 1
            current_row += 1
        current_row += 1
    ws_stat = workbook.add_worksheet("統計")
    ws_stat.write_row(0, 0, ["助理", "上限", "實排"], fmt_header)
    cnts = {a["name"]: 0 for a in assts}
    for k, v in schedule_result.items():
        ppl = list(v["doctors"].values()) + v["counter"] + v["floater"] + v.get("look", [])
        for p in ppl: 
            if p in cnts: cnts[p] += 1
    base_min, base_max = calculate_shift_limits(year, month)
    for i, a in enumerate(assts):
        lim = a["custom_max"] if a["custom_max"] is not None else base_max
        ws_stat.write(i+1, 0, a["name"])
        ws_stat.write(i+1, 1, lim)
        ws_stat.write(i+1, 2, cnts[a["name"]])
    writer.close()
    output.seek(0)
    return output

def to_excel_individual(schedule_result, year, month, assts, docs):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book
    fmt_h = workbook.add_format({'bold': True, 'align': 'center', 'border': 1, 'bg_color': '#E0E0E0'})
    fmt_c = workbook.add_format({'align': 'center', 'border': 1})
    fmt_n = workbook.add_format({'align': 'left', 'valign': 'top', 'text_wrap': True})
    dates = generate_month_dates(year, month); mid = (len(dates) + 1) // 2
    dL, dR = dates[:mid], dates[mid:]
    b_min, b_max = calculate_shift_limits(year, month)
    note = "註：全診及午晚班有空請輪流抽空吃飯，謹守30分鐘規定。\n1〉早午班 8:30-12:00 13:30-18:00\n2〉午晚班 13:30-22:00\n3〉早晚班 08:00-12:00 18:00-22:00"
    for a in assts:
        s = workbook.add_worksheet(a["nick"])
        aname = a["name"]; act = 0
        for k, v in schedule_result.items():
            ppl = list(v["doctors"].values()) + v["counter"] + v["floater"] + v.get("look",[])
            if aname in ppl: act += 1
        lim = a["custom_max"] if a["custom_max"] is not None else b_max
        s.write(0, 0, f"{aname} - {month}月", fmt_h)
        s.write(0, 8, f"應排: {lim}", fmt_c)
        s.write(1, 8, f"實排: {act}", fmt_c)
        for i, h in enumerate(["日期","星期","早","午","晚"]):
            s.write(2, i, h, fmt_h); s.write(2, i+6, h, fmt_h)
        def fill(d_lst, off):
            for r, dt in enumerate(d_lst):
                row = r + 3
                s.write(row, off, f"{dt.month}/{dt.day}", fmt_c)
                s.write(row, off+1, ['一','二','三','四','五','六'][dt.weekday()], fmt_c)
                for c, sh in enumerate(["早", "午", "晚"]):
                    k = f"{dt}_{sh}"; v = ""
                    if k in schedule_result:
                        data = schedule_result[k]
                        if aname in data.get("look", []): v="看"
                        elif aname in data["floater"]: v="流"
                        elif aname in data["counter"]: v="櫃"
                        else:
                            for dn, asg in data["doctors"].items():
                                if asg == aname: v = next((d["nick"] for d in docs if d["name"]==dn), dn)
                    s.write(row, off+2+c, v, fmt_c)
        fill(dL, 0); fill(dR, 6)
        s.merge_range(max(len(dL), len(dR))+5, 0, max(len(dL), len(dR))+10, 10, note, fmt_n)
    writer.close()
    output.seek(0)
    return output

def to_excel_doctor_personal(schedule_result, year, month, docs, assts):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book
    fmt_h = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': '#E0E0E0', 'border': 1})
    fmt_c = workbook.add_format({'align': 'center', 'border': 1})
    dates = generate_month_dates(year, month); weeks = {}
    for dt in dates:
        iso = dt.isocalendar()[1]
        if iso not in weeks: weeks[iso] = []
        weeks[iso].append(dt)
    for doc in docs:
        s = workbook.add_worksheet(doc["nick"]); dn = doc["name"]
        s.write(0, 0, f"{dn} - {month}月", fmt_h)
        cr = 1
        for iso, wds in weeks.items():
            s.write(cr, 0, "日期", fmt_h); c = 1
            for dt in wds: s.write(cr, c, f"{dt.month}/{dt.day}", fmt_h); c+=1
            cr+=1
            for sh in ["早", "午", "晚"]:
                s.write(cr, 0, sh, fmt_c); c = 1
                for dt in wds:
                    k = f"{dt}_{sh}"; v = "" 
                    if k in schedule_result:
                        if dn in schedule_result[k]["doctors"]:
                            an = schedule_result[k]["doctors"][dn]
                            v = next((a["nick"] for a in assts if a["name"]==an), an)
                    s.write(cr, c, v, fmt_c); c+=1
                cr+=1
            cr+=1
    writer.close()
    output.seek(0)
    return output

def to_excel_single_doctor(schedule_result, year, month, dname, dnick):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book
    fmt_h = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': '#E0E0E0', 'border': 1})
    fmt_c = workbook.add_format({'align': 'center', 'border': 1})
    dates = generate_month_dates(year, month); weeks = {}
    for dt in dates:
        iso = dt.isocalendar()[1]
        if iso not in weeks: weeks[iso] = []
        weeks[iso].append(dt)
    s = workbook.add_worksheet(dnick)
    s.write(0, 0, f"{dname} - {month}月 班表確認", fmt_h)
    cr = 1
    for iso, wds in weeks.items():
        s.write(cr, 0, "日期", fmt_h); c = 1
        for dt in wds: s.write(cr, c, f"{dt.month}/{dt.day} ({['一','二','三','四','五','六'][dt.weekday()]})", fmt_h); c+=1
        cr+=1
        for sh in ["早", "午", "晚"]:
            s.write(cr, 0, sh, fmt_c); c = 1
            for dt in wds:
                k = f"{dt}_{sh}"; v = "" 
                if k in schedule_result and dname in schedule_result[k]["doctors"]: v = "V"
                s.write(cr, c, v, fmt_c); c+=1
            cr+=1
        cr+=1
    writer.close()
    output.seek(0)
    return output

# --- 7. UI 介面 ---

st.title("🦷 祐德牙醫 - 智慧排班系統 v16.3")

is_locked_system = st.session_state.config.get("is_locked", False)

with st.sidebar:
    st.divider()
    st.subheader("⚙️ 系統權限管理")
    new_lock_state = st.toggle("🔒 鎖定前台修改 (Deadline)", value=is_locked_system, help="開啟後，醫師與助理將無法更改假單。")
    if new_lock_state != is_locked_system:
        st.session_state.config["is_locked"] = new_lock_state; save_config(st.session_state.config); st.rerun()

step = st.sidebar.radio("導覽步驟", [
    "1. 系統與人員設定", "2. 醫師配對順位", "3. 助理進階限制", "4. 醫師範本與生成", 
    "5. 👨‍⚕️ 醫師專屬入口 (請假/加診)", "6. 👩‍⚕️ 助理專屬入口 (劃假)", "7. 排班與總管微調", "8. 報表下載"
])

if step == "1. 系統與人員設定":
    st.header("人員與權重設定")
    y = st.session_state.config.get("year", 2026); m = st.session_state.config.get("month", 4)
    wds = get_workdays_count(y, m)
    st.info(f"📅 {y}年{m}月 (工作日:{wds}天) ｜ 全職標準：上限 {wds*2} 診，基本 {wds*2-8} 診")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("👨‍⚕️ 醫師名單")
        ed_doc = st.data_editor(pd.DataFrame(st.session_state.config["doctors_struct"]), use_container_width=True, hide_index=True)
        if st.button("存醫師"): st.session_state.config["doctors_struct"] = ed_doc.to_dict('records'); save_config(st.session_state.config); st.success("儲存成功")
    with c2:
        st.subheader("👩‍⚕️ 助理名單")
        ed_asst = st.data_editor(pd.DataFrame(st.session_state.config["assistants_struct"]), column_config={
            "type": st.column_config.SelectboxColumn("全/兼職", options=["全職","兼職"]),
            "custom_max": st.column_config.NumberColumn("兼職上限", min_value=0),
            "pref": st.column_config.SelectboxColumn("偏好", options=["high","normal","low"]),
            "is_main_counter": st.column_config.CheckboxColumn("主櫃台?")
        }, use_container_width=True, hide_index=True)
        if st.button("存助理"): st.session_state.config["assistants_struct"] = ed_asst.replace({np.nan: None}).to_dict('records'); save_config(st.session_state.config); st.success("儲存成功")

elif step == "2. 醫師配對順位":
    st.header("跟診指定順位表")
    docs = get_active_doctors(); assts = [""] + [a["name"] for a in get_active_assistants()]
    matrix_data = []
    curr = st.session_state.config.get("pairing_matrix", {})
    for doc in docs:
        row = {"醫師": doc["name"]}; prefs = curr.get(doc["name"], {})
        row["第一順位"] = prefs.get("1", ""); row["第二順位"] = prefs.get("2", ""); row["第三順位"] = prefs.get("3", "")
        matrix_data.append(row)
    ed_mat = st.data_editor(pd.DataFrame(matrix_data), column_config={
        "醫師": st.column_config.TextColumn(disabled=True),
        "第一順位": st.column_config.SelectboxColumn(options=assts),
        "第二順位": st.column_config.SelectboxColumn(options=assts),
        "第三順位": st.column_config.SelectboxColumn(options=assts)
    }, hide_index=True, use_container_width=True)
    if st.button("儲存配對"):
        new_mat = {}
        for idx, row in ed_mat.iterrows(): new_mat[row["醫師"]] = {"1": row["第一順位"], "2": row["第二順位"], "3": row["第三順位"]}
        st.session_state.config["pairing_matrix"] = new_mat; save_config(st.session_state.config); st.success("儲存成功")

elif step == "3. 助理進階限制":
    st.header("🛡️ 助理進階動態鎖定")
    assts = get_active_assistants(); curr_rules = st.session_state.config.get("adv_rules", {}); rule_data = []
    for a in assts:
        nm = a["name"]; r = curr_rules.get(nm, {})
        rule_data.append({
            "助理": nm, "限定職位": r.get("role_limit", "無限制"), "限定班別": r.get("shift_limit", "無限制"),
            "限定星期時段": r.get("slot_whitelist", ""), "絕對固定班": r.get("fixed_slots", ""), "避開人員": r.get("avoid", "")
        })
    ed_rules = st.data_editor(pd.DataFrame(rule_data), column_config={
        "助理": st.column_config.TextColumn(disabled=True),
        "限定職位": st.column_config.SelectboxColumn(options=["無限制", "僅櫃台(含行政)", "僅流動", "僅跟診"]),
        "限定班別": st.column_config.SelectboxColumn(options=["無限制", "僅早班", "僅午班", "僅晚班"])
    }, hide_index=True, use_container_width=True, height=550)
    if st.button("儲存進階限制"):
        new_rules = {}
        for idx, row in ed_rules.iterrows():
            new_rules[row["助理"]] = {"role_limit": row["限定職位"], "shift_limit": row["限定班別"], "slot_whitelist": row["限定星期時段"], "fixed_slots": row["絕對固定班"], "avoid": row["避開人員"]}
        st.session_state.config["adv_rules"] = new_rules; save_config(st.session_state.config); st.success("儲存成功")

elif step == "4. 醫師範本與生成":
    st.header("醫師班表範本與初始化")
    
    # ★ v16.3 雙層日曆 UI 實作
    doc_names = [d["name"] for d in get_active_doctors()]
    days = ["一", "二", "三", "四", "五", "六"]; shifts = ["早", "午", "晚"]
    
    # 建立雙層表頭 (MultiIndex Columns)
    multi_cols = pd.MultiIndex.from_product([[f"星期{d}" for d in days], shifts])
    
    def get_df(key):
        data = st.session_state.config.get(key, {})
        rows = []
        for doc in doc_names:
            sched = data.get(doc, [False]*18)
            if len(sched) != 18: sched = [False]*18
            rows.append(sched)
        df = pd.DataFrame(rows, index=doc_names, columns=multi_cols)
        return df

    def save_df(df, key):
        res = {}
        for doc, row in df.iterrows(): res[doc] = [bool(x) for x in row.tolist()]
        st.session_state.config[key] = res

    # 顯示雙層表格 (免用 column_config，系統自動解析布林值為勾選框)
    t1, t2 = st.tabs(["單週範本", "雙週範本"])
    with t1: e1 = st.data_editor(get_df("template_odd"), use_container_width=True, key="e_t_odd")
    with t2: e2 = st.data_editor(get_df("template_even"), use_container_width=True, key="e_t_even")
    
    if st.button("存範本"):
        save_df(e1, "template_odd"); save_df(e2, "template_even"); save_config(st.session_state.config); st.success("儲存成功")
        
    st.divider()
    st.subheader("生成本月初始班表")
    c1, c2, c3 = st.columns(3)
    y = c1.number_input("年", 2025, 2030, st.session_state.config.get("year", 2026))
    m = c2.number_input("月", 1, 12, st.session_state.config.get("month", 4))
    
    # ★ v16.3 第一週設定開關 (解決 ISO 跨月單雙顛倒 Bug)
    first_week_setting = c3.radio("本月【畫面第 1 週】設定為：", ["單週", "雙週"])
    is_first_odd = (first_week_setting == "單週")
    
    if st.button("一鍵生成本月初始班表", type="primary"):
        st.session_state.config["year"] = y; st.session_state.config["month"] = m
        generated = []
        t_odd = st.session_state.config.get("template_odd", {}); t_even = st.session_state.config.get("template_even", {})
        
        weeks = get_full_weeks(y, m)
        for w_idx, w_dates in enumerate(weeks):
            # 完全對齊畫面的週數邏輯
            is_odd_week = (w_idx % 2 == 0) if is_first_odd else (w_idx % 2 != 0)
            tmpl = t_odd if is_odd_week else t_even
            
            for dt in w_dates:
                if dt.month != m: continue # 跨月反黑日期不生成
                if dt.weekday() == 6: continue 
                
                base = dt.weekday()*3
                for s_idx, s in enumerate(["早", "午", "晚"]):
                    idx = base + s_idx
                    for doc in get_active_doctors():
                        dn = doc["name"]
                        if dn in tmpl and idx < len(tmpl[dn]) and tmpl[dn][idx]:
                            generated.append({"Date": str(dt), "Shift": s, "Doctor": dn})
                            
        st.session_state.config["manual_schedule"] = generated; save_config(st.session_state.config)
        st.success(f"生成完畢！第 1 週已套用【{first_week_setting}】範本。")

elif step == "5. 👨‍⚕️ 醫師專屬入口 (請假/加診)":
    st.header("👨‍⚕️ 醫師個人班表確認與修改")
    if is_locked_system: st.error("🔒 修改期限已過，目前為唯讀模式。")
    else: st.info("請選擇名字。若要請假請將勾選取消；若要加診請打勾。反黑區域不可點選。")
        
    docs = get_active_doctors(); selected_doc = st.selectbox("📌 選擇醫師", [d["name"] for d in docs])
    y = st.session_state.config.get("year", 2026); m = st.session_state.config.get("month", 4)
    manual = st.session_state.config.get("manual_schedule", []); weeks = get_full_weeks(y, m)
    edited_dfs = {}; col_map = {}
    st.markdown(f"### 📅 {selected_doc} - {m}月 班表")
    
    for i, w_dates in enumerate(weeks):
        st.markdown(f"**第 {i+1} 週**")
        cols = []; disabled_cols = set()
        for dt in w_dates:
            wd_str = ['一','二','三','四','五','六'][dt.weekday()]
            if dt.month == m: disp = f"{dt.month}/{dt.day} ({wd_str})"
            else: disp = f"⬛ {dt.month}/{dt.day} ({wd_str})"; disabled_cols.add(disp)
            cols.append(disp); col_map[disp] = (str(dt), dt.month == m)

        rows = []
        for s in ["早", "午", "晚"]:
            row = {"時段": s}
            for c, dt in zip(cols, w_dates):
                if c not in disabled_cols: row[c] = any(x for x in manual if x["Date"] == str(dt) and x["Shift"] == s and x["Doctor"] == selected_doc)
                else: row[c] = "" 
            rows.append(row)

        df = pd.DataFrame(rows).set_index("時段")
        cfg = {}
        for c in cols:
            if c in disabled_cols: cfg[c] = st.column_config.TextColumn(c, disabled=True) 
            else: cfg[c] = st.column_config.CheckboxColumn(c) 
                
        edited_dfs[i] = st.data_editor(df, column_config=cfg, key=f"doc_wk_{i}", use_container_width=True, disabled=is_locked_system)
    
    col1, col2 = st.columns(2)
    with col1:
        if not is_locked_system and st.button("💾 儲存我的班表修改", type="primary"):
            new_manual = [x for x in manual if x["Doctor"] != selected_doc]
            for iso, df in edited_dfs.items():
                for shift, row in df.iterrows():
                    for c in df.columns:
                        d_str, is_curr_month = col_map[c]
                        if is_curr_month and row[c] == True: 
                            new_manual.append({"Date": d_str, "Shift": shift, "Doctor": selected_doc})
            st.session_state.config["manual_schedule"] = new_manual; save_config(st.session_state.config); st.success(f"✅ {selected_doc} 儲存成功！"); st.rerun()
    with col2:
        dummy_res = {}
        for x in manual:
            if x["Doctor"] == selected_doc:
                k = f"{x['Date']}_{x['Shift']}"
                if k not in dummy_res: dummy_res[k] = {"doctors": {}}
                dummy_res[k]["doctors"][selected_doc] = "V"
        doc_nick = next((d["nick"] for d in docs if d["name"] == selected_doc), selected_doc)
        excel_data = to_excel_single_doctor(dummy_res, y, m, selected_doc, doc_nick)
        st.download_button(f"📥 下載 {selected_doc} 班表", excel_data, f"{selected_doc}_{m}月班表.xlsx")

elif step == "6. 👩‍⚕️ 助理專屬入口 (劃假)":
    st.header("👩‍⚕️ 助理個人休假登記")
    if is_locked_system: st.error("🔒 劃假期限已過，目前為唯讀模式。")
    else: st.info("請選擇名字。在想休假的時段「打勾」。反黑區域不可點選。")
        
    assts = get_active_assistants(); selected_asst = st.selectbox("📌 選擇助理", [a["name"] for a in assts])
    y = st.session_state.config.get("year", 2026); m = st.session_state.config.get("month", 4)
    current_leaves = st.session_state.config.get("leaves", {})
    weeks = get_full_weeks(y, m); edited_dfs = {}; col_map = {}
    st.markdown(f"### 🌴 {selected_asst} - {m}月 休假表")
    
    for i, w_dates in enumerate(weeks):
        st.markdown(f"**第 {i+1} 週**")
        cols = []; disabled_cols = set()
        for dt in w_dates:
            wd_str = ['一','二','三','四','五','六'][dt.weekday()]
            if dt.month == m: disp = f"{dt.month}/{dt.day} ({wd_str})"
            else: disp = f"⬛ {dt.month}/{dt.day} ({wd_str})"; disabled_cols.add(disp)
            cols.append(disp); col_map[disp] = (str(dt), dt.month == m)

        rows = []
        for s in ["早", "午", "晚"]:
            row = {"時段": s}
            for c, dt in zip(cols, w_dates):
                if c not in disabled_cols: row[c] = current_leaves.get(f"{selected_asst}_{str(dt)}_{s}", False)
                else: row[c] = ""
            rows.append(row)

        df = pd.DataFrame(rows).set_index("時段")
        cfg = {}
        for c in cols:
            if c in disabled_cols: cfg[c] = st.column_config.TextColumn(c, disabled=True)
            else: cfg[c] = st.column_config.CheckboxColumn(c)
                
        edited_dfs[i] = st.data_editor(df, column_config=cfg, key=f"asst_wk_{i}", use_container_width=True, disabled=is_locked_system)
    
    if not is_locked_system and st.button("💾 儲存我的休假", type="primary"):
        new_leaves = {k: v for k, v in current_leaves.items() if not k.startswith(f"{selected_asst}_")}
        for iso, df in edited_dfs.items():
            for shift, row in df.iterrows():
                for c in df.columns:
                    d_str, is_curr = col_map[c]
                    if is_curr and row[c] == True: new_leaves[f"{selected_asst}_{d_str}_{shift}"] = True
        st.session_state.config["leaves"] = new_leaves; save_config(st.session_state.config); st.success(f"✅ {selected_asst} 儲存成功！"); st.rerun()

elif step == "7. 排班與總管微調":
    st.header("智慧排班與微調面板")
    c1, c2 = st.columns(2)
    ctr = c1.slider("預設櫃台數", 1, 3, 2); flt = c2.slider("預設流動數", 0, 3, 1)
    
    if st.button("🚀 執行自動排班", type="primary"):
        man = st.session_state.config.get("manual_schedule", []); lea = st.session_state.config.get("leaves", {})
        pair = st.session_state.config.get("pairing_matrix", {}); rules = st.session_state.config.get("adv_rules", {}) 
        res, counts, s_min, s_max = run_auto_schedule(man, lea, pair, rules, ctr, flt)
        st.session_state.result = res; st.success("排班演算法執行完成！(空白格子代表受限於規則無法排入，請手動指派)")
    
    if 'result' in st.session_state:
        st.divider()
        col_ed, col_stat = st.columns([3, 1])
        y = st.session_state.config.get("year"); m = st.session_state.config.get("month")
        dates = generate_month_dates(y, m)
        wds = len(dates); std_max = wds*2; std_min = std_max-8
        weeks = get_full_weeks(y, m)
        
        edited_res = st.session_state.result.copy()
        docs = get_active_doctors(); assts = get_active_assistants()
        asst_opts = [""] + [a["nick"] for a in assts]
        n2nm = {a["nick"]: a["name"] for a in assts}; nm2n = {a["name"]: a["nick"] for a in assts}
        
        with col_ed:
            st.subheader("📝 班表微調區 (雙層日曆)")
            for i, w_dates in enumerate(weeks):
                st.markdown(f"**第 {i+1} 週**")
                multi_cols = []; cmap = {}; disabled_cols = set()
                
                for dt in w_dates:
                    is_curr = (dt.month == m); wd_str = ['一','二','三','四','五','六'][dt.weekday()]
                    if is_curr: disp_date = f"{dt.month}/{dt.day} ({wd_str})"
                    else: 
                        disp_date = f"⬛ {dt.month}/{dt.day} ({wd_str})"
                        disabled_cols.add(disp_date)
                    
                    for s in ["早", "午", "晚"]:
                        multi_cols.append((disp_date, s))
                        cmap[(disp_date, s)] = (f"{dt}_{s}", is_curr)
                        
                rows = []
                for doc in docs:
                    r = []
                    for c_tuple in multi_cols:
                        k, is_curr = cmap[c_tuple]
                        if is_curr and k in edited_res: r.append(nm2n.get(edited_res[k]["doctors"].get(doc["name"], ""), ""))
                        else: r.append("")
                    rows.append(r)
                    
                r_defs = [("櫃1", "counter", 0), ("櫃2", "counter", 1), ("流", "floater", 0), ("看", "look", 0)]
                for rn, rk, ri in r_defs:
                    r = []
                    for c_tuple in multi_cols:
                        k, is_curr = cmap[c_tuple]
                        if is_curr and k in edited_res:
                            lst = edited_res[k].get(rk, [])
                            if ri < len(lst): r.append(nm2n.get(lst[ri], ""))
                            else: r.append("")
                        else: r.append("")
                    rows.append(r)
                    
                idx_names = [f"👨‍⚕️{d['nick']}" for d in docs] + [r[0] for r in r_defs]
                dfw = pd.DataFrame(rows, index=idx_names, columns=pd.MultiIndex.from_tuples(multi_cols))
                
                cfg = {}
                for c_tuple in multi_cols:
                    k_str = str(c_tuple) # 將 tuple 轉為字串作為設定鍵值，完美避開 JSON 序列化錯誤
                    if c_tuple[0] in disabled_cols: cfg[k_str] = st.column_config.TextColumn(disabled=True)
                    else: cfg[k_str] = st.column_config.SelectboxColumn(options=asst_opts, width="small")
                        
                edw = st.data_editor(dfw, column_config=cfg, key=f"mw_{i}")
                
                for idx, row in edw.iterrows():
                    is_doc = "👨‍⚕️" in str(idx)
                    doc_name = next((d["name"] for d in docs if d["nick"]==str(idx).replace("👨‍⚕️","")), "")
                    for c_tuple in multi_cols:
                        v_nick = row[c_tuple]
                        k, is_curr = cmap[c_tuple]
                        if not is_curr or k not in edited_res: continue
                        v_name = n2nm.get(v_nick, "")
                        if is_doc: edited_res[k]["doctors"][doc_name] = v_name
                        else:
                            for rn, rk, ri in r_defs:
                                if str(idx) == rn:
                                    if rk not in edited_res[k]: edited_res[k][rk] = []
                                    while len(edited_res[k][rk]) <= ri: edited_res[k][rk].append("")
                                    edited_res[k][rk][ri] = v_name
            if st.button("💾 儲存並更新數據", type="primary"):
                st.session_state.result = edited_res; st.rerun()

        with col_stat:
            st.subheader("📊 即時診數與週六指標")
            curr_counts = {a["name"]: 0 for a in assts}
            sat_dates = [str(dt) for dt in dates if dt.weekday() == 5]
            sat_stats = {a["name"]: {"worked_days": 0, "nights": 0, "no_night_worked": 0, "full_off": 0} for a in assts}
            daily_shifts = collections.defaultdict(lambda: collections.defaultdict(set))
            
            for k, v in edited_res.items():
                dt_str, sh = k.split("_")
                ppl = list(v["doctors"].values()) + v["counter"] + v["floater"] + v.get("look", [])
                for p in ppl: 
                    if p:
                        daily_shifts[p][dt_str].add(sh)
                        curr_counts[p] += 1
                        
            for a in assts:
                nm = a["name"]
                for d in sat_dates:
                    shifts = daily_shifts[nm][d]
                    if shifts:
                        sat_stats[nm]["worked_days"] += 1
                        if "晚" in shifts: sat_stats[nm]["nights"] += 1
                        else: sat_stats[nm]["no_night_worked"] += 1
                    else:
                        sat_stats[nm]["full_off"] += 1

            for a in assts:
                nm = a["name"]; c_val = curr_counts[nm]
                if a["type"] == "全職":
                    lim = std_max; target = std_min if a["pref"] == "low" else std_max
                    msg = f"**{a['nick']}**: {c_val} (標:{target})"
                    if c_val < std_min: st.warning(f"🟡 {msg}")
                    elif c_val > lim: st.error(f"🔴 {msg} 爆")
                    else: st.success(f"🟢 {msg}")
                    
                    s_off = sat_stats[nm]["full_off"]
                    s_non = sat_stats[nm]["no_night_worked"]
                    s_nit = sat_stats[nm]["nights"]
                    sat_ok = (s_off >= 1) and (s_nit == 2) 
                    sat_icon = "✅" if sat_ok else "⚠️"
                    st.caption(f"{sat_icon} 週六: 全休{s_off} | 日班{s_non} | 晚班{s_nit}")
                else:
                    lim = a["custom_max"] if a["custom_max"] else 15
                    msg = f"**{a['nick']} (PT)**: {c_val}/{lim}"
                    if c_val > lim: st.error(f"🔴 {msg}")
                    else: st.info(f"🔵 {msg}")

elif step == "8. 報表下載":
    st.header("下載 Excel 報表")
    if 'result' in st.session_state:
        sch = st.session_state.result
        y = st.session_state.config.get("year"); m = st.session_state.config.get("month")
        d = get_active_doctors(); a = get_active_assistants()
        c1, c2, c3 = st.columns(3)
        c1.download_button("📊 總班表", to_excel_master(sch, y, m, d, a), f"祐德總班表_{m}月.xlsx")
        c2.download_button("👤 助理個人表", to_excel_individual(sch, y, m, a, d), f"祐德助理表_{m}月.xlsx")
        c3.download_button("🩺 醫師所有排班", to_excel_doctor_personal(sch, y, m, d, a), f"祐德醫師表_{m}月.xlsx")
