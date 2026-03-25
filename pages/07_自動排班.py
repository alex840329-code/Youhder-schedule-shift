# pages/07_自動排班.py — 執行排班 + 即時儀表板 + NLP 微調

import collections
import time
import re
import json
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd

try:
    from st_aggrid import AgGrid, JsCode
    HAS_AGGRID = True
except ImportError:
    HAS_AGGRID = False

from modules.config import (
    init_session_config, save_config,
    get_active_doctors, get_active_assistants,
)
from modules.data_utils import (
    generate_month_dates, get_padded_weeks,
    calculate_shift_limits, parse_slot_string, WEEKDAY_NAMES,
)
from modules.scheduler import run_auto_schedule, run_phase2_rescue
from modules.nlp_parser import parse_command_local, apply_actions, call_gemini_api

st.set_page_config(page_title="自動排班", page_icon="🤖", layout="wide")
init_session_config()

st.markdown("""
<style>
  [data-testid="stDataEditor"] td { font-size: 14px !important; }
  .ag-cell { font-size: 14px !important; }
  .ag-header-cell-label { font-size: 14px !important; font-weight: bold !important; }
  .ag-header-group-cell-label { font-size: 14px !important; font-weight: bold !important; }
</style>
""", unsafe_allow_html=True)

cfg   = st.session_state.config
y, m  = cfg.get("year"), cfg.get("month")
dates = generate_month_dates(y, m)
std_min, std_max = calculate_shift_limits(y, m)
assts = get_active_assistants()
docs  = get_active_doctors()
sat_dates = [str(dt) for dt in dates if dt.weekday() == 5]
WD_NAMES  = ["一","二","三","四","五","六","日"]

st.title(f"🤖 自動排班　{y} 年 {m} 月")

if not HAS_AGGRID:
    st.error("🚨 需要 `streamlit-aggrid` 套件。")
    st.stop()
if not cfg.get("manual_schedule"):
    st.warning("⚠️ 請先至「醫師班表」→「月份調整」設定醫師上診時間。")
    st.stop()


# ════════════════════════════════════════════════════════════
# 即時監控側邊欄（可點選展開明細）
# ════════════════════════════════════════════════════════════

def _date_disp(dt_str):
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d")
        return f"{dt.month}/{dt.day}({WD_NAMES[dt.weekday()]})"
    except Exception:
        return dt_str


with st.sidebar:
    st.subheader("📊 即時診次監控")

    result = st.session_state.get("result") or cfg.get("saved_result") or {}
    if result:
        # 計算各助理統計
        curr_counts   = {a["name"]: 0 for a in assts}
        curr_floaters = {a["name"]: 0 for a in assts}
        daily_p       = collections.defaultdict(lambda: collections.defaultdict(set))
        adv_rules     = cfg.get("adv_rules", {})
        p_admin       = {n: parse_slot_string(r.get("admin_slots",""))
                         for n, r in adv_rules.items()}

        for k, v in result.items():
            if "_" not in k: continue
            dt_str, sh = k.rsplit("_", 1)
            try:
                dt_obj = datetime.strptime(dt_str, "%Y-%m-%d").date()
            except Exception:
                continue
            for a in assts:
                nm   = a["name"]
                in_g = nm in (list(v.get("doctors",{}).values())
                              + v.get("counter",[]) + v.get("floater",[]) + v.get("look",[]))
                is_adm = (dt_obj.weekday(), sh) in p_admin.get(nm, set())
                if in_g or is_adm:
                    curr_counts[nm] += 1
                    daily_p[nm][dt_str].add(sh)
                if nm in v.get("floater", []):
                    curr_floaters[nm] += 1

        for a in assts:
            nm  = a["name"]
            cnt = curr_counts[nm]

            # 顏色
            if cnt < std_min - 2:   color_icon = "🟡"
            elif cnt > std_max + 2: color_icon = "🔴"
            else:                   color_icon = "🟢"

            # 統計：週六
            sat_off = sat_night = sat_day = sat_other = 0
            sat_off_dates = sat_night_dates = sat_day_dates = []
            sat_off_dates, sat_night_dates, sat_day_dates, sat_other_dates = [], [], [], []
            for d in sat_dates:
                ss   = daily_p[nm].get(d, set())
                disp = _date_disp(d)
                if not ss:
                    sat_off += 1; sat_off_dates.append(disp)
                elif "晚" in ss:
                    sat_night += 1; sat_night_dates.append(disp)
                elif ss:
                    sat_day += 1; sat_day_dates.append(disp)

            sat_ok = "✅" if (sat_off >= 1 and sat_night <= 2 and sat_other == 0) else "⚠️"
            if a.get("type") == "兼職": sat_ok = "🆗"

            # 統計：問題班別
            triple_days      = {d: s for d, s in daily_p[nm].items() if len(s) == 3}
            early_late_days  = {d: s for d, s in daily_p[nm].items()
                                if "早" in s and "晚" in s and "午" not in s}

            # 主標題可展開
            with st.expander(
                f"{color_icon} **{nm}**（{a.get('type','')}）\n"
                f"診次：{cnt}/{std_max}　流動：{curr_floaters[nm]}\n"
                f"{sat_ok} 六：休{sat_off}｜有晚班{sat_night}｜沒晚班{sat_day}",
                expanded=False,
            ):
                # 週六明細
                st.markdown("**📅 週六明細**")
                for d in sat_off_dates:
                    st.write(f"😴 {d} — 全休")
                for d in sat_night_dates:
                    st.write(f"🌙 {d} — 有晚班")
                for d in sat_day_dates:
                    st.write(f"☀️ {d} — 沒晚班")

                # 全天班明細
                if triple_days:
                    st.markdown("**⚠️ 全天班（早＋午＋晚）**")
                    for d in sorted(triple_days):
                        st.write(f"📌 {_date_disp(d)}")

                # 早晚班明細
                if early_late_days:
                    st.markdown("**🚩 早晚班（跳過午班）**")
                    for d in sorted(early_late_days):
                        st.write(f"⚠️ {_date_disp(d)}")

            st.markdown("---")
    else:
        st.info("尚未生成班表")


# ════════════════════════════════════════════════════════════
# 排班控制列
# ════════════════════════════════════════════════════════════

st.subheader("⚙️ 排班參數")
cc1, cc2, cc3 = st.columns(3)
ctr = cc1.slider("預設櫃台數", 1, 3, cfg.get("ctr_count", 2))
flt = cc2.slider("預設流動數", 0, 3, cfg.get("flt_count", 1))
with cc3:
    dyn_ctr = st.checkbox("醫師≥5 → 雙櫃台", cfg.get("dynamic_ctr", True))
    dyn_flt = st.checkbox("醫師≥5 → 雙流動", cfg.get("dynamic_flt", True))
    bal_flt = st.checkbox("平均流動診次",     cfg.get("balance_flt", True))

if any([
    ctr != cfg.get("ctr_count",2), flt != cfg.get("flt_count",1),
    dyn_ctr != cfg.get("dynamic_ctr",True), dyn_flt != cfg.get("dynamic_flt",True),
    bal_flt != cfg.get("balance_flt",True),
]):
    cfg.update(ctr_count=ctr, flt_count=flt, dynamic_ctr=dyn_ctr, dynamic_flt=dyn_flt, balance_flt=bal_flt)
    save_config(cfg)

btn1, btn2 = st.columns(2)
if btn1.button("🚀 執行嚴格自動排班", type="primary", use_container_width=True):
    with st.spinner("排班中..."):
        res = run_auto_schedule(
            cfg["manual_schedule"], cfg["leaves"],
            cfg.get("pairing_matrix",{}), cfg.get("adv_rules",{}),
            ctr, flt, cfg.get("forced_assigns",{}),
            dyn_flt, bal_flt, dyn_ctr,
        )
        st.session_state.result = res
        cfg["saved_result"] = res
        save_config(cfg)
        st.rerun()

if btn2.button("🚑 填洞救援", type="secondary", use_container_width=True):
    if "result" not in st.session_state:
        st.error("請先執行嚴格排班！")
    else:
        with st.spinner("填洞中..."):
            # run_phase2_rescue 簽名：(current_result, manual_schedule, leaves, adv_rules, assts, ctr_count, flt_count, year, month)
            res = run_phase2_rescue(
                st.session_state.result,
                cfg["manual_schedule"], cfg["leaves"],
                cfg.get("adv_rules",{}),
                assts, ctr, flt, y, m,
            )
            st.session_state.result = res
            cfg["saved_result"] = res
            save_config(cfg)
            st.rerun()

if "result" not in st.session_state and cfg.get("saved_result"):
    st.session_state.result = cfg["saved_result"]

if "result" not in st.session_state:
    st.info("📋 尚未生成班表。點擊「執行嚴格自動排班」開始。")
    st.stop()


# ════════════════════════════════════════════════════════════
# NLP 快速調整
# ════════════════════════════════════════════════════════════

st.divider()
with st.expander("💬 口語指令微調（NLP）", expanded=False):
    mode = st.radio("解析模式", ["🔧 本地 Regex（推薦）","🤖 Google Gemini AI"], horizontal=True)

    if "本地" in mode:
        st.info(
            "**範例句型：**\n"
            "- `峻豪醫師禮拜四整天給昀霏跟`\n"
            "- `小瑜 4/4, 4/11, 4/18 晚上上班`\n"
            "- `雯萱第3個星期六休假`\n"
            "- `佳萱 4/15 請假`"
        )
        cmd = st.text_area("輸入指令（可多行）", key="nlp_cmd", placeholder="每行一個指令...")
        if st.button("✅ 執行本地調整"):
            if cmd.strip():
                acts   = parse_command_local(cmd, y, m, docs, assts)
                forced = cfg.get("forced_assigns",{})
                lvs    = cfg.get("leaves",{})
                manual = cfg.get("manual_schedule",[])
                n = apply_actions(acts, forced, lvs, manual, y, m, cfg.get("adv_rules",{}))
                if n:
                    cfg.update(forced_assigns=forced, leaves=lvs, manual_schedule=manual)
                    save_config(cfg)
                    res = run_auto_schedule(
                        manual, lvs, cfg.get("pairing_matrix",{}),
                        cfg.get("adv_rules",{}), ctr, flt, forced, dyn_flt, bal_flt, dyn_ctr,
                    )
                    st.session_state.result = res
                    cfg["saved_result"] = res
                    save_config(cfg)
                    st.success(f"✅ 套用 {n} 筆！")
                    time.sleep(0.5); st.rerun()
                else:
                    st.error("❌ 無法識別，請確認格式後重試。")
    else:
        api_key = st.text_input("Gemini API Key", type="password", value=cfg.get("api_key",""))
        cmd_ai  = st.text_area("口語指令", key="nlp_ai_cmd", placeholder="峻豪醫師禮拜四昀霏跟診")
        if st.button("🤖 執行 AI 調整"):
            if api_key and cmd_ai:
                cfg["api_key"] = api_key; save_config(cfg)
                with st.spinner("AI 分析中..."):
                    docs_s = ",".join(d["name"] for d in docs)
                    asst_s = ",".join(a["name"] for a in assts)
                    prompt = (f"牙醫排班{y}年{m}月。醫師:{docs_s}。助理:{asst_s}。"
                              f"輸出JSON動作陣列。指令:{cmd_ai[:500]}")
                    raw = call_gemini_api(api_key, prompt)
                    if raw.startswith("ERROR:"):
                        st.error(raw)
                    else:
                        try:
                            acts  = json.loads(re.sub(r"```json\s*|\s*```","",raw).strip())
                            forced= cfg.get("forced_assigns",{})
                            lvs   = cfg.get("leaves",{})
                            manual= cfg.get("manual_schedule",[])
                            n = apply_actions(acts, forced, lvs, manual, y, m, cfg.get("adv_rules",{}))
                            cfg.update(forced_assigns=forced, leaves=lvs, manual_schedule=manual)
                            save_config(cfg)
                            res = run_auto_schedule(
                                manual, lvs, cfg.get("pairing_matrix",{}),
                                cfg.get("adv_rules",{}), ctr, flt, forced, dyn_flt, bal_flt, dyn_ctr,
                            )
                            st.session_state.result = res
                            cfg["saved_result"] = res
                            save_config(cfg)
                            st.success(f"✅ AI 套用 {n} 筆！")
                            time.sleep(0.5); st.rerun()
                        except Exception as e:
                            st.error(f"AI 解析失敗：{e}")

    if st.button("🧹 清除所有強制指定"):
        cfg["forced_assigns"] = {}; save_config(cfg); st.rerun()


# ════════════════════════════════════════════════════════════
# 班表網格（AgGrid 可微調）
# ════════════════════════════════════════════════════════════

st.divider()
st.markdown("**📋 班表總覽**　灰底=空格/休　橘紅=缺人　紫色=救援")
st.caption("可直接在格子內下拉選人調整。")

# ── AgGrid 單元格樣式 ──────────────────────────────────────
cell_style_js = JsCode("""
function(params){
  var sh=params.colDef.headerName, cls=params.colDef.cellClass||'', isOdd=cls==='is_odd';
  var val=params.value||'';
  var s={'textAlign':'center','borderRight':'1px solid #d3d3d3','borderBottom':'1px solid #d3d3d3',
         'color':'#000','fontWeight':'bold','display':'flex','alignItems':'center',
         'justifyContent':'center','fontSize':'14px'};
  if(sh==='晚') s['borderRight']='2px solid #333';
  // 空格：純白
  if(!val||val==='-'||val==='休'){s['backgroundColor']='#ffffff';s['color']='#ccc';return s;}
  // 缺人
  if(val.includes('⚠️')){s['backgroundColor']='#ffcccc';s['color']='#e60000';return s;}
  // 救援
  if(val.includes('(救)')){s['backgroundColor']='#e6ccff';s['color']='#4b0082';return s;}
  // 有人：按時段上色
  if(isOdd){
    if(sh==='早') s['backgroundColor']='#FDE9D9';
    if(sh==='午') s['backgroundColor']='#FCD5B4';
    if(sh==='晚') s['backgroundColor']='#FABF8F';
  }else{
    if(sh==='早') s['backgroundColor']='#DDEBF7';
    if(sh==='午') s['backgroundColor']='#BDD7EE';
    if(sh==='晚') s['backgroundColor']='#9DC3E6';
  }
  return s;
}
""")

p_weeks     = get_padded_weeks(y, m)
nm2n        = {a["name"]: a.get("nick","") for a in assts}
n2nm        = {a.get("nick",""): a["name"] for a in assts}
base_nicks  = [a.get("nick","") for a in assts if a.get("nick","")]
a_opts      = ["", "⚠️缺", "休"] + base_nicks + [f"{n}(救)" for n in base_nicks]
leaves_data = cfg.get("leaves",{})
ms_set      = {f"{x['Date']}_{x['Shift']}_{x['Doctor']}" for x in cfg.get("manual_schedule",[])}
dc_map = collections.defaultdict(int)
for x in cfg.get("manual_schedule",[]):
    dc_map[f"{x['Date']}_{x['Shift']}"] += 1

with st.form("adj_form"):
    for wi, w_dates in enumerate(p_weeks):
        # 計算下班人員（本週各時段）
        off_map = {}
        for dt in w_dates:
            if not dt["is_curr"]: continue
            for sh in ["早","午","晚"]:
                f    = f"{dt['str']}_{sh}"
                data = st.session_state.result.get(f, {})
                working = set(
                    list(data.get("doctors",{}).values())
                    + data.get("counter",[]) + data.get("floater",[]) + data.get("look",[])
                )
                off_map[f] = [
                    a["name"] for a in assts
                    if a["name"] not in working
                    and not leaves_data.get(f"{a['name']}_{dt['str']}_{sh}")
                ]

        # 建立每列資料
        rows = []
        for doc in docs:
            r = {"person": f"👨‍⚕️ {doc.get('nick', doc['name'])}", "type": "doc", "name": doc["name"]}
            for dt in w_dates:
                for s in ["早","午","晚"]:
                    f = f"{dt['str']}_{s}"
                    if dt["is_curr"]:
                        anm   = st.session_state.result.get(f,{}).get("doctors",{}).get(doc["name"],"")
                        resc  = st.session_state.result.get(f,{}).get("rescued",{}).get("doctors",[])
                        sched = f"{dt['str']}_{s}_{doc['name']}" in ms_set
                        if anm:
                            r[f] = nm2n.get(anm, anm) + ("(救)" if anm in resc else "")
                        elif sched:
                            r[f] = "⚠️缺"
                        else:
                            r[f] = ""   # 醫師無班 → 空格
                    else:
                        r[f] = "-"
            rows.append(r)

        for rnm, rk, ri in [("櫃1","counter",0),("櫃2","counter",1),
                              ("流","floater",0),("流2","floater",1),
                              ("行政","look",0)]:
            r = {"person": rnm, "type": "role", "key": rk, "idx": ri}
            for dt in w_dates:
                for s in ["早","午","晚"]:
                    f = f"{dt['str']}_{s}"
                    if dt["is_curr"]:
                        lst  = st.session_state.result.get(f,{}).get(rk,[])
                        resc = st.session_state.result.get(f,{}).get("rescued",{}).get(rk,[])
                        if ri < len(lst):
                            anm  = lst[ri]
                            r[f] = nm2n.get(anm, anm) + ("(救)" if anm in resc else "")
                        else:
                            req = 0
                            if rk == "counter":
                                req = max(ctr,2) if (dyn_ctr and dc_map[f]>=5) else ctr
                            elif rk == "floater":
                                req = max(flt,2) if (dyn_flt and dc_map[f]>=5) else flt
                            r[f] = "⚠️缺" if ri < req else ""
                    else:
                        r[f] = "-"
            rows.append(r)

        # AgGrid 列定義
        col_defs = [{
            "headerName": "人員", "field": "person", "pinned": "left", "width": 80,
            "editable": False,
            "cellStyle": {"fontWeight":"bold","borderRight":"2px solid #333",
                          "backgroundColor":"#fff","fontSize":"14px"}
        }]
        for dt in w_dates:
            is_odd = (dt["date"].weekday() % 2 == 0) if hasattr(dt.get("date"), "weekday") else True
            children = [
                {"headerName": s, "field": f"{dt['str']}_{s}",
                 "editable": dt["is_curr"],
                 "cellEditor": "agSelectCellEditor",
                 "cellEditorParams": {"values": a_opts},
                 "cellClass": "is_odd" if is_odd else "is_even",
                 "cellStyle": cell_style_js, "width": 56}
                for s in ["早","午","晚"]
            ]
            col_defs.append({
                "headerName": dt["disp"], "children": children,
                "headerClass": "header-odd" if is_odd else "header-even",
            })

        AgGrid(
            pd.DataFrame(rows),
            gridOptions={"columnDefs": col_defs, "rowHeight": 40},
            height=len(rows)*40+120,
            allow_unsafe_jscode=True, theme="alpine",
            key=f"ag_final_{wi}",
        )

        # 下班人員顯示
        if any(dt["is_curr"] for dt in w_dates):
            off_cols = st.columns(len(w_dates))
            for idx, dt in enumerate(w_dates):
                if dt["is_curr"]:
                    html = ""
                    for sh in ["早","午","晚"]:
                        nicks = [nm2n.get(n, n) for n in off_map.get(f"{dt['str']}_{sh}",[]) if n]
                        html += (f"<div><b>{sh}:</b> "
                                 + (",".join(nicks) if nicks else "<span style='color:#ccc'>皆排班</span>")
                                 + "</div>")
                    off_cols[idx].markdown(
                        f'<div style="background:#fff;border:1px solid #ffcccc;border-left:5px solid #ff4b4b;'
                        f'padding:6px;margin-top:4px;font-size:12px;border-radius:4px;">{html}</div>',
                        unsafe_allow_html=True,
                    )
        st.markdown("<br>", unsafe_allow_html=True)

    if st.form_submit_button("💾 同步更新並儲存"):
        for wi in range(len(p_weeks)):
            ag_s = st.session_state.get(f"ag_final_{wi}")
            if ag_s is None: continue
            ag_data = getattr(ag_s, "data", None) or (ag_s.get("data") if isinstance(ag_s, dict) else None)
            if ag_data is None: continue
            df_out = pd.DataFrame(ag_data) if isinstance(ag_data, list) else ag_data
            for _, r in df_out.iterrows():
                r_type = r.get("type")
                for dt in p_weeks[wi]:
                    if not dt["is_curr"]: continue
                    for s in ["早","午","晚"]:
                        f    = f"{dt['str']}_{s}"
                        if f not in r: continue
                        raw  = r[f] if r[f] is not None else ""
                        nick = str(raw).replace("(救)","").strip()
                        vname = n2nm.get(nick,"") if nick not in ("-","⚠️缺","休","") else ""
                        if r_type == "doc":
                            if vname:
                                st.session_state.result[f]["doctors"][r["name"]] = vname
                            else:
                                st.session_state.result[f]["doctors"].pop(r["name"], None)
                        elif r_type == "role":
                            rk, idx = r.get("key",""), r.get("idx",0)
                            lst = st.session_state.result.setdefault(f,{}).setdefault(rk,[])
                            while len(lst) <= idx: lst.append("")
                            lst[idx] = vname
                            while lst and not lst[-1]: lst.pop()
                            st.session_state.result[f][rk] = lst
        cfg["saved_result"] = st.session_state.result
        save_config(cfg)
        st.rerun()

# ── JSON 匯出 ─────────────────────────────────────────────────
with st.expander("💬 匯出班表 JSON（供 AI 檢查）"):
    payload = {
        "month":    f"{y}-{m}",
        "schedule": st.session_state.result,
        "rules":    cfg.get("adv_rules",{}),
        "leaves":   cfg.get("leaves",{}),
    }
    st.text_area("JSON：", json.dumps(payload, ensure_ascii=False), height=200)
