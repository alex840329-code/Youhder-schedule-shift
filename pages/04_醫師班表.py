# pages/04_醫師班表.py — 醫師固定班表範本（單雙週）＋套用目標月份

import collections
import streamlit as st
import pandas as pd
from datetime import datetime

try:
    from st_aggrid import AgGrid, JsCode
    HAS_AGGRID = True
except ImportError:
    HAS_AGGRID = False

from modules.config import init_session_config, save_config, get_active_doctors
from modules.data_utils import generate_month_dates, WEEKDAY_NAMES

st.set_page_config(page_title="醫師班表", page_icon="📋", layout="wide")
init_session_config()

st.markdown("""
<style>
  [data-testid="stDataEditor"] td { font-size: 14px !important; }
</style>
""", unsafe_allow_html=True)

st.title("📋 醫師固定班表範本")
st.caption("設定單週 / 雙週範本，再選擇要套用的月份，按「套用」即可生成當月醫師上診記錄。")

cfg  = st.session_state.config
docs = get_active_doctors()
DAYS = WEEKDAY_NAMES

if not docs:
    st.warning("請先至「人員設定」啟用醫師。")
    st.stop()

if not HAS_AGGRID:
    st.error("🚨 需要 `streamlit-aggrid`，請在 requirements.txt 加入後重新啟動。")
    st.stop()

cell_style_js = JsCode("""
function(params){
  var sh=params.colDef.headerName;
  var s={'textAlign':'center','display':'flex','alignItems':'center','justifyContent':'center','fontSize':'14px'};
  if(sh==='早') s['backgroundColor']='#FDE9D9';
  if(sh==='午') s['backgroundColor']='#BDD7EE';
  if(sh==='晚') s['backgroundColor']='#FABF8F';
  if(sh==='晚') s['borderRight']='2px solid #aaa';
  return s;
}
""")

def render_template_grid(key: str):
    data = cfg.get(key, {})
    rows = []
    for d in docs:
        row = {"醫師": f"👨‍⚕️ {d['name']}"}
        s_arr = data.get(d["name"], [False]*18)
        for i, dn in enumerate(DAYS):
            for si, sn in enumerate(["早","午","晚"]):
                row[f"{dn}_{sn}"] = bool(s_arr[i*3+si]) if len(s_arr)>=18 else False
        rows.append(row)

    col_defs = [{
        "headerName": "醫師", "field": "醫師", "pinned": "left",
        "width": 140, "editable": False,
        "cellStyle": {"fontWeight":"bold","backgroundColor":"#fff","borderRight":"2px solid #ccc","fontSize":"14px"}
    }]
    for i, dn in enumerate(DAYS):
        children = [
            {"headerName": sn, "field": f"{dn}_{sn}", "editable": True,
             "cellEditor": "agCheckboxCellEditor",
             "cellRenderer": "agCheckboxCellRenderer",
             "cellStyle": cell_style_js, "width": 58}
            for sn in ["早","午","晚"]
        ]
        col_defs.append({
            "headerName": f"星期{dn}", "children": children,
            "headerClass": "header-odd" if i%2==0 else "header-even",
        })

    res = AgGrid(
        pd.DataFrame(rows),
        gridOptions={"columnDefs": col_defs, "rowHeight": 48},
        height=len(docs)*48+130,
        allow_unsafe_jscode=True, theme="alpine",
        key=f"ag_{key}",
    )
    if res and res.get("data") is not None:
        rd = res["data"]
        df = pd.DataFrame(rd) if isinstance(rd, list) else rd
        out = {}
        for _, row in df.iterrows():
            doc_clean = str(row["醫師"]).replace("👨‍⚕️ ","")
            out[doc_clean] = [
                bool(row.get(f"{dn}_{sn}", False))
                for dn in DAYS for sn in ["早","午","晚"]
            ]
        cfg[key] = out

# ── 第一週設定 ───────────────────────────────────────────────
fws = st.radio(
    "**本月第一週屬於：**",
    ["單週（奇數週）", "雙週（偶數週）"],
    index=0 if cfg.get("first_week_type","odd")=="odd" else 1,
    horizontal=True,
)
cfg["first_week_type"] = "odd" if "單" in fws else "even"

t_odd, t_even = st.tabs(["📅 單週（1、3、5 週）", "📅 雙週（2、4 週）"])
with t_odd:
    st.info("ℹ️ 單週範本")
    render_template_grid("template_odd")
with t_even:
    st.info("ℹ️ 雙週範本（若與單週相同可不填）")
    render_template_grid("template_even")

# ── 套用目標月份 ─────────────────────────────────────────────
st.divider()
st.subheader("🚀 套用至指定月份")

c1, c2, c3 = st.columns([1, 1, 3])
target_y = c1.number_input("套用年份", 2025, 2030, cfg.get("year"), key="tgt_year")
target_m = c2.number_input("套用月份", 1, 12, cfg.get("month"), key="tgt_month")
c3.markdown("")
c3.markdown("")
c3.info(
    f"💡 目前設定：{target_y} 年 {target_m} 月　"
    f"（第一週為{'單' if cfg.get('first_week_type','odd')=='odd' else '雙'}週）"
)

if st.button("🚀 套用至此月份", type="primary"):
    save_config(cfg)
    cfg["year"]  = target_y
    cfg["month"] = target_m

    docs_active   = get_active_doctors()
    use_odd_first = (cfg.get("first_week_type","odd") == "odd")
    generated     = []
    dates_all     = generate_month_dates(target_y, target_m)
    weeks_map     = collections.defaultdict(list)
    for dt in dates_all:
        weeks_map[dt.isocalendar()[1]].append(dt)

    for wi, w_dates in enumerate(weeks_map.values()):
        use_odd = (wi%2==0) if use_odd_first else (wi%2!=0)
        tmpl    = cfg.get("template_odd" if use_odd else "template_even", {})
        for dt in w_dates:
            base = dt.weekday() * 3
            for si, sn in enumerate(["早","午","晚"]):
                for d in docs_active:
                    arr = tmpl.get(d["name"])
                    if arr and len(arr) > base+si and arr[base+si]:
                        generated.append({"Date": str(dt), "Shift": sn, "Doctor": d["name"]})

    cfg["manual_schedule"] = generated
    save_config(cfg)
    st.success(
        f"✅ 已生成 {len(generated)} 筆上診記錄（{target_y}/{target_m}）！"
        "請到「月份調整」頁面確認並微調。"
    )
    st.rerun()

# ── 預覽 ─────────────────────────────────────────────────────
with st.expander("📊 當月醫師上診預覽"):
    manual = cfg.get("manual_schedule", [])
    if manual:
        for d in get_active_doctors():
            cnt = sum(1 for x in manual if x["Doctor"] == d["name"])
            st.markdown(f"**{d['name']}** — 共 {cnt} 診")
    else:
        st.info("尚未套用班表")
