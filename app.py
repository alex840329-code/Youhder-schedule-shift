import streamlit as st
import pandas as pd
import json
import os
import calendar
from datetime import datetime, date
import io

# ==========================================
# ⚙️ 系統初始化與常數設定
# ==========================================
st.set_page_config(page_title="祐德牙醫 - 智慧排班系統", layout="wide", page_icon="🦷")

CONFIG_FILE = "yude_config_v11.json"

# 預設醫師資料
DEFAULT_DOCTORS = ["郭", "沁", "鈴", "毓", "安", "吳", "蔡", "貞", "麗", "魏", "東"]

# 預設助理資料 (姓名, 簡稱, 職級, 櫃台屬性)
DEFAULT_ASSISTANTS = [
    {"name": "雯萱", "short": "萱", "type": "全職", "counter": "主櫃"},
    {"name": "小瑜", "short": "瑜", "type": "兼職", "counter": "主櫃"},
    {"name": "欣霓", "short": "霓", "type": "兼職", "counter": "主櫃"},
    {"name": "昀霏", "short": "霏", "type": "全職", "counter": "次櫃"},
    {"name": "湘婷", "short": "湘", "type": "全職", "counter": "次櫃"},
    {"name": "怡安", "short": "怡", "type": "全職", "counter": "次櫃"},
    {"name": "嘉宜", "short": "宜", "type": "全職", "counter": "次櫃"},
    {"name": "芷瑜", "short": "芷", "type": "全職", "counter": "次櫃"},
    {"name": "佳臻", "short": "臻", "type": "全職", "counter": "次櫃"},
    {"name": "紫心", "short": "紫", "type": "全職", "counter": "次櫃"},
    {"name": "又嘉", "short": "又", "type": "全職", "counter": "次櫃"},
    {"name": "佳萱", "short": "佳", "type": "全職", "counter": "次櫃"},
    {"name": "紫媛", "short": "媛", "type": "全職", "counter": "次櫃"},
    {"name": "暐貽", "short": "貽", "type": "兼職", "counter": "無"},
]

# 避免同班名單
AVOID_PAIRS = [("瑜", "怡"), ("媛", "霏")]

# 初始化系統狀態
if 'config' not in st.session_state:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            st.session_state.config = json.load(f)
    else:
        st.session_state.config = {
            "doctors": DEFAULT_DOCTORS,
            "assistants": DEFAULT_ASSISTANTS,
            "lock_frontend": False,
            "is_biweekly": False
        }

def save_config():
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(st.session_state.config, f, ensure_ascii=False, indent=4)

# ==========================================
# 🛠️ 輔助函式 (日期與表格生成)
# ==========================================
def get_month_days(year, month):
    num_days = calendar.monthrange(year, month)[1]
    days = []
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    for day in range(1, num_days + 1):
        dt = date(year, month, day)
        days.append(f"{month}/{day}({weekdays[dt.weekday()]})")
    return days

def init_schedule_df(year, month):
    days = get_month_days(year, month)
    shifts = ["早", "午", "晚"]
    columns = []
    for d in days:
        # 過濾掉星期日
        if "(日)" not in d:
            for s in shifts:
                columns.append(f"{d} {s}")
    
    # 建立空的 DataFrame
    staff_names = [a["short"] for a in st.session_state.config["assistants"]]
    df = pd.DataFrame("", index=staff_names, columns=columns)
    return df

# ==========================================
# 🧠 排班演算法核心 (防護與防勞機制)
# ==========================================
def auto_schedule(df):
    """
    這是一個貪婪演算法(Greedy Algorithm)的簡化版。
    會優先填入「絕對固定班」，然後根據規則嘗試填補。
    """
    new_df = df.copy()
    columns = new_df.columns
    
    # 1. 填入絕對固定班 (Hard Rules)
    for col in columns:
        day_str, shift = col.split(" ")
        
        # 暐貽: 只上二三四晚，六午晚流動
        if "貽" in new_df.index:
            if shift == "晚" and any(x in day_str for x in ["(二)", "(三)", "(四)"]):
                new_df.at["貽", col] = "流"
            elif any(x in day_str for x in ["(六)"]) and shift in ["午", "晚"]:
                new_df.at["貽", col] = "流"
            else:
                new_df.at["貽", col] = "休" # 其他時間預設休
                
        # 小瑜: 每天晚上櫃台
        if "瑜" in new_df.index:
            if shift == "晚":
                new_df.at["瑜", col] = "櫃"
            else:
                new_df.at["瑜", col] = "休"
                
        # 欣霓: 一二下午，四晚上櫃台
        if "霓" in new_df.index:
            if (shift == "午" and any(x in day_str for x in ["(一)", "(二)"])) or \
               (shift == "晚" and "(四)" in day_str):
                new_df.at["霓", col] = "櫃"
            else:
                new_df.at["霓", col] = "休"
                
        # 雯萱: 固定規則
        if "萱" in new_df.index:
            if "(一)" in day_str and shift in ["早", "晚"]: new_df.at["萱", col] = "櫃"
            if "(二)" in day_str and shift == "早": new_df.at["萱", col] = "櫃"
            if "(三)" in day_str and shift == "早": new_df.at["萱", col] = "櫃"
            if "(四)" in day_str and shift == "午": new_df.at["萱", col] = "櫃"
            if "(五)" in day_str: new_df.at["萱", col] = "櫃"
            
    # 2. 檢查防過勞 (標記警告用，不強制覆蓋)
    # 實作於 Dashboard 檢測區，這裡先處理基本排班
    
    return new_df

def analyze_schedule(df):
    warnings = []
    shift_counts = {idx: 0 for idx in df.index}
    
    for idx in df.index:
        person_schedule = df.loc[idx]
        
        # 計算總診數
        worked_shifts = person_schedule[~person_schedule.isin(["", "休", "行政"])].count()
        shift_counts[idx] = worked_shifts
        
        # 檢查天地班 (早+晚，無午)
        days = list(dict.fromkeys([c.split(" ")[0] for c in df.columns]))
        for d in days:
            m = person_schedule.get(f"{d} 早", "")
            a = person_schedule.get(f"{d} 午", "")
            e = person_schedule.get(f"{d} 晚", "")
            
            is_m = m not in ["", "休", "行政"]
            is_a = a not in ["", "休", "行政"]
            is_e = e not in ["", "休", "行政"]
            
            if is_m and is_e and not is_a:
                warnings.append(f"⚠️ 天地班警告: {idx} 於 {d} 排了早晚班但無午班。")
            
            if is_m and is_a and is_e:
                 warnings.append(f"🔴 連三診警告: {idx} 於 {d} 安排了早午晚連三診，請注意隔日排班。")
                 
        # 互斥規則檢查
        for col in df.columns:
            for p1, p2 in AVOID_PAIRS:
                if p1 in df.index and p2 in df.index:
                    if df.at[p1, col] not in ["", "休"] and df.at[p2, col] not in ["", "休"]:
                        warnings.append(f"❌ 互斥警告: {p1} 與 {p2} 於 {col} 同時上班！")

    return shift_counts, warnings

# ==========================================
# 🎨 UI 介面架構
# ==========================================
menu = st.sidebar.radio("📌 系統導覽", ["1. 系統與人員設定", "2. 總管排班與微調", "3. 個人專屬入口 (前台)", "4. 匯出 Excel 報表"])

# 總開關
st.sidebar.markdown("---")
lock = st.sidebar.checkbox("🔒 鎖定前台修改 (Deadline)", value=st.session_state.config.get("lock_frontend", False))
st.session_state.config["lock_frontend"] = lock
save_config()

# ------------------------------------------
# 模組 1: 系統與人員設定
# ------------------------------------------
if menu == "1. 系統與人員設定":
    st.title("⚙️ 系統與人員設定")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("👨‍⚕️ 醫師名單")
        doctors_text = st.text_area("編輯醫師 (以逗號分隔)", ", ".join(st.session_state.config["doctors"]))
        if st.button("更新醫師名單"):
            st.session_state.config["doctors"] = [x.strip() for x in doctors_text.split(",") if x.strip()]
            save_config()
            st.success("醫師名單已更新！")
            
    with col2:
        st.subheader("👩‍⚕️ 助理名單管理")
        st.info("請直接在下方表格修改助理資料，修改後系統會自動儲存。")
        ast_df = pd.DataFrame(st.session_state.config["assistants"])
        edited_ast_df = st.data_editor(ast_df, num_rows="dynamic")
        if st.button("儲存助理名單"):
            st.session_state.config["assistants"] = edited_ast_df.to_dict('records')
            save_config()
            st.success("助理名單已更新！")

# ------------------------------------------
# 模組 4: 總管排班與微調 (核心功能)
# ------------------------------------------
elif menu == "2. 總管排班與微調":
    st.title("📅 總管排班與微調面板")
    
    col_y, col_m = st.columns(2)
    with col_y:
        selected_year = st.selectbox("年份", [2024, 2025, 2026], index=2)
    with col_m:
        selected_month = st.selectbox("月份", list(range(1, 13)), index=datetime.now().month % 12) # 預設下個月
    
    # 建立或讀取當月班表
    session_key = f"schedule_{selected_year}_{selected_month}"
    if session_key not in st.session_state:
        st.session_state[session_key] = init_schedule_df(selected_year, selected_month)
        
    df = st.session_state[session_key]
    
    st.markdown("### 🤖 智慧排班動作")
    if st.button("✨ 執行基礎自動排班 (帶入固定規則)"):
        df = auto_schedule(df)
        st.session_state[session_key] = df
        st.rerun()

    st.markdown("### ✍️ 班表微調區")
    st.caption("提示：點擊儲存格即可修改。可輸入 '櫃', '流', '跟-郭', '休' 等。")
    
    # 使用 st.data_editor 提供類似 Excel 的編輯體驗
    edited_df = st.data_editor(df, height=600, use_container_width=True)
    
    if st.button("💾 儲存班表變更"):
        st.session_state[session_key] = edited_df
        st.success("班表已儲存至系統暫存！")
        st.rerun()

    st.markdown("---")
    st.markdown("### 📊 儀表板與異常監控")
    shift_counts, warnings = analyze_schedule(edited_df)
    
    col_warn, col_stat = st.columns([2, 1])
    with col_warn:
        st.subheader("🚨 異常防勞警告")
        if not warnings:
            st.success("目前班表合乎規則，無重大異常。")
        else:
            for w in warnings:
                if "❌" in w: st.error(w)
                elif "🔴" in w: st.error(w)
                else: st.warning(w)
                
    with col_stat:
        st.subheader("📈 助理診數統計")
        # 簡單計算工作日 (不含週日)
        workdays = len([d for d in get_month_days(selected_year, selected_month) if "(日)" not in d])
        standard_shifts = workdays * 2
        basic_shifts = standard_shifts - 8
        
        stat_data = []
        for ast in st.session_state.config["assistants"]:
            name = ast["short"]
            count = shift_counts.get(name, 0)
            status = "🟢 正常"
            if ast["type"] == "全職":
                if count < basic_shifts: status = "🟡 過低"
                elif count > standard_shifts: status = "🔴 爆班"
            stat_data.append({"助理": name, "目前診數": count, "狀態": status})
            
        st.dataframe(pd.DataFrame(stat_data), hide_index=True)

# ------------------------------------------
# 模組 2: 個人專屬入口
# ------------------------------------------
elif menu == "3. 個人專屬入口 (前台)":
    st.title("📱 個人專屬入口")
    
    if st.session_state.config.get("lock_frontend", False):
        st.error("🔒 目前班表已鎖定，進入唯讀模式，禁止修改。如有疑問請洽總管。")
        is_disabled = True
    else:
        st.info("您可以在此預排您的休假或期望班表。")
        is_disabled = False
        
    all_staff = [a["name"] for a in st.session_state.config["assistants"]]
    user = st.selectbox("請選擇您的名字", all_staff)
    user_short = next(a["short"] for a in st.session_state.config["assistants"] if a["name"] == user)
    
    selected_month = st.selectbox("查看月份", list(range(1, 13)), index=datetime.now().month % 12)
    selected_year = 2026 # 預設今年
    
    session_key = f"schedule_{selected_year}_{selected_month}"
    if session_key in st.session_state:
        # 只取出該使用者的資料轉置顯示
        user_data = st.session_state[session_key].loc[[user_short]].T
        user_data.columns = ["班別安排"]
        
        st.dataframe(user_data, height=500, use_container_width=True)
    else:
        st.warning("該月份班表尚未建立。")

# ------------------------------------------
# 模組 5: 報表輸出
# ------------------------------------------
elif menu == "4. 匯出 Excel 報表":
    st.title("🖨️ 匯出客製化 Excel 報表")
    
    selected_month = st.selectbox("選擇要匯出的月份", list(range(1, 13)), index=datetime.now().month % 12)
    selected_year = 2026
    
    session_key = f"schedule_{selected_year}_{selected_month}"
    
    if session_key not in st.session_state:
        st.warning("該月份班表尚未建立，無法匯出。")
    else:
        df = st.session_state[session_key]
        
        # 準備 Excel 檔案 (使用 BytesIO 讓使用者下載)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # 1. 總表
            df.to_excel(writer, sheet_name='總班表')
            
            # 2. 助理個人表 (簡單範例：將總表轉置)
            df.T.to_excel(writer, sheet_name='個人視角表')
            
            # 美化 Excel (欄寬等)
            workbook = writer.book
            worksheet = writer.sheets['總班表']
            format_center = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
            worksheet.set_column('A:A', 10, format_center)
            worksheet.set_column('B:ZZ', 15, format_center)

        excel_data = output.getvalue()
        
        st.success("報表產生成功！")
        st.download_button(
            label="📊 點擊下載 Excel 報表",
            data=excel_data,
            file_name=f"祐德牙醫_排班表_{selected_year}_{selected_month}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
