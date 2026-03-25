# modules/default_data.py
# 預設人員資料庫 — 祐德牙醫診所排班系統

DEFAULT_DOCTORS = [
    {"name": "郭長熀醫師", "nick": "熀",  "active": True, "order": 1},
    {"name": "冰沁醫師",   "nick": "沁",  "active": True, "order": 2},
    {"name": "志鈴醫師",   "nick": "鈴",  "active": True, "order": 3},
    {"name": "陳哲毓醫師", "nick": "毓",  "active": True, "order": 4},
    {"name": "安醫師",     "nick": "安",  "active": True, "order": 5},
    {"name": "吳醫師",     "nick": "吳",  "active": True, "order": 6},
    {"name": "燿東醫師",   "nick": "東",  "active": True, "order": 7},
    {"name": "峻豪醫師",   "nick": "豪",  "active": True, "order": 8},
]

DEFAULT_ASSISTANTS = [
    # 全職
    {"name": "嘉宜",   "nick": "宜",  "type": "全職", "active": True, "custom_max": None, "is_main_counter": False, "pref": "normal"},
    {"name": "又嘉",   "nick": "嘉",  "type": "全職", "active": True, "custom_max": None, "is_main_counter": False, "pref": "normal"},
    {"name": "昀霏",   "nick": "霏",  "type": "全職", "active": True, "custom_max": None, "is_main_counter": False, "pref": "normal"},
    {"name": "佳萱",   "nick": "佳",  "type": "全職", "active": True, "custom_max": None, "is_main_counter": False, "pref": "normal"},
    {"name": "紫媛",   "nick": "媛",  "type": "全職", "active": True, "custom_max": None, "is_main_counter": False, "pref": "normal"},
    {"name": "紫心",   "nick": "心",  "type": "全職", "active": True, "custom_max": None, "is_main_counter": False, "pref": "normal"},
    {"name": "怡安",   "nick": "安",  "type": "全職", "active": True, "custom_max": None, "is_main_counter": False, "pref": "normal"},
    {"name": "芷瑜",   "nick": "芷",  "type": "全職", "active": True, "custom_max": None, "is_main_counter": False, "pref": "normal"},
    # 主櫃台 (兼職性質的固定班型)
    {"name": "雯萱",   "nick": "萱",  "type": "全職", "active": True, "custom_max": None, "is_main_counter": True,  "pref": "normal"},
    {"name": "小瑜",   "nick": "瑜",  "type": "兼職", "active": True, "custom_max": 20,   "is_main_counter": True,  "pref": "normal"},
    {"name": "欣霓",   "nick": "霓",  "type": "兼職", "active": True, "custom_max": 12,   "is_main_counter": True,  "pref": "normal"},
    # 兼職
    {"name": "暐貽",   "nick": "貽",  "type": "兼職", "active": True, "custom_max": 12,   "is_main_counter": False, "pref": "normal"},
    {"name": "湘婷",   "nick": "婷",  "type": "兼職", "active": True, "custom_max": 15,   "is_main_counter": False, "pref": "normal"},
]

# 醫師跟診優先矩陣
DEFAULT_PAIRING_MATRIX = {
    "郭長熀醫師": {"1": "又嘉",   "2": "紫心",  "3": "怡安"},
    "冰沁醫師":   {"1": "嘉宜",   "2": "芷瑜",  "3": ""},
    "志鈴醫師":   {"1": "紫媛",   "2": "芷瑜",  "3": ""},
    "陳哲毓醫師": {"1": "佳萱",   "2": "",       "3": ""},
    "安醫師":     {"1": "",        "2": "",       "3": ""},
    "吳醫師":     {"1": "",        "2": "",       "3": ""},
    "燿東醫師":   {"1": "",        "2": "",       "3": ""},
    "峻豪醫師":   {"1": "",        "2": "",       "3": ""},
}

# 進階規則預設值
# slot_whitelist 格式：「一早,一午,二晚」等星期+時段組合
# fixed_slots    格式：「一早櫃,二午流」等固定職位槽
# admin_slots    格式：「三午,四早」行政診時段
DEFAULT_ADV_RULES = {
    # 嘉宜：基本診為主，可多 1-2 診
    "嘉宜": {
        "role_limit": "無限制", "shift_limit": "無限制",
        "avoid": "", "slot_whitelist": "", "admin_slots": "", "fixed_slots": ""
    },
    # 又嘉：比最大診次少 2-3 診（透過 custom_max 控制，規則無限制）
    "又嘉": {
        "role_limit": "無限制", "shift_limit": "無限制",
        "avoid": "", "slot_whitelist": "", "admin_slots": "", "fixed_slots": ""
    },
    # 昀霏：唯一可週六不休息（不設強制全休，由調度決定）
    "昀霏": {
        "role_limit": "無限制", "shift_limit": "無限制",
        "avoid": "小瑜", "slot_whitelist": "", "admin_slots": "", "fixed_slots": ""
    },
    # 佳萱：主跟陳哲毓醫師（透過 pairing_matrix 控制）
    "佳萱": {
        "role_limit": "僅跟診", "shift_limit": "無限制",
        "avoid": "", "slot_whitelist": "", "admin_slots": "", "fixed_slots": ""
    },
    # 暐貽：僅流動，上二、三、四晚及六午晚
    "暐貽": {
        "role_limit": "僅流動", "shift_limit": "無限制",
        "avoid": "",
        "slot_whitelist": "二晚,三晚,四晚,六午,六晚",
        "admin_slots": "", "fixed_slots": ""
    },
    # 小瑜：僅每晚櫃台，月休 2-3 晚診
    "小瑜": {
        "role_limit": "僅櫃台", "shift_limit": "僅晚班",
        "avoid": "昀霏",
        "slot_whitelist": "一晚,二晚,三晚,四晚,五晚,六晚",
        "admin_slots": "", "fixed_slots": ""
    },
    # 欣霓：僅櫃檯，上一、二午及四晚
    "欣霓": {
        "role_limit": "僅櫃台", "shift_limit": "無限制",
        "avoid": "",
        "slot_whitelist": "一午,二午,四晚",
        "admin_slots": "", "fixed_slots": ""
    },
    # 雯萱：複雜固定班型
    # 一早晚櫃、二早櫃/下午自由、三早櫃/下午行政自由、四午櫃、五全櫃
    # 六：一週全休/兩週全櫃/一週晚上休（由排班員手動調整六）
    "雯萱": {
        "role_limit": "僅櫃台", "shift_limit": "無限制",
        "avoid": "",
        "slot_whitelist": "一早,一晚,二早,三早,四午,五早,五午,五晚,六早,六午,六晚",
        "admin_slots": "三午",
        "fixed_slots": "一早櫃,一晚櫃,二早櫃,三早櫃,四午櫃,五早櫃,五午櫃,五晚櫃"
    },
    # 行政診需求人員（紫媛、紫心、怡安）
    "紫媛": {
        "role_limit": "無限制", "shift_limit": "無限制",
        "avoid": "昀霏",
        "slot_whitelist": "", "admin_slots": "", "fixed_slots": ""
    },
    "紫心": {
        "role_limit": "無限制", "shift_limit": "無限制",
        "avoid": "", "slot_whitelist": "", "admin_slots": "", "fixed_slots": ""
    },
    "怡安": {
        "role_limit": "無限制", "shift_limit": "無限制",
        "avoid": "昀霏",
        "slot_whitelist": "", "admin_slots": "", "fixed_slots": ""
    },
    "芷瑜": {
        "role_limit": "無限制", "shift_limit": "無限制",
        "avoid": "", "slot_whitelist": "", "admin_slots": "", "fixed_slots": ""
    },
    "湘婷": {
        "role_limit": "無限制", "shift_limit": "無限制",
        "avoid": "", "slot_whitelist": "", "admin_slots": "", "fixed_slots": ""
    },
}
