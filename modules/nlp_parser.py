# modules/nlp_parser.py
# 自然語言指令解析（本地 Regex + Google Gemini API）

import re
import json
import time
import requests

from modules.data_utils import get_target_dates


# ════════════════════════════════════════════════════════════
# 人名模糊比對
# ════════════════════════════════════════════════════════════


def fuzzy_match_person(name_str: str, lst: list) -> str:
    """
    從 list[dict(name, nick)] 中找出最佳比對。
    先精確，再最長重疊子字串。
    """
    clean = name_str.replace("醫師", "").strip()
    for item in lst:
        if clean == item["name"] or (item.get("nick") and clean == item["nick"]):
            return item["name"]

    best, max_overlap = None, 0
    for item in lst:
        nm, nk = item["name"], item.get("nick", "")
        for cand in (nm, nk):
            if not cand:
                continue
            if cand in clean and len(cand) > max_overlap:
                best, max_overlap = item["name"], len(cand)
            elif clean in cand and len(clean) > max_overlap:
                best, max_overlap = item["name"], len(clean)

    if best:
        return best
    # 無比對時，判斷是否為醫師名稱
    if any("醫師" in d["name"] for d in lst):
        return clean + "醫師"
    return clean


# ════════════════════════════════════════════════════════════
# 本地 Regex 解析
# ════════════════════════════════════════════════════════════


_WD_MAP = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"日":7,"天":7,
           "1":1,"2":2,"3":3,"4":4,"5":5,"6":6,"7":7}


def _expand_multi_date(line: str) -> list:
    """
    將「小瑜 4/4, 4/11, 4/18 晚上上班」展開為多行。
    """
    m = re.match(
        r'^([^\s\d]+(?:醫師)?)\s+([\d/.,、\s]+)\s+([^\d/.,、\s].+)$',
        line.strip()
    )
    if m:
        name, dates_str, action = m.group(1), m.group(2), m.group(3)
        dates = re.split(r'[、,，\s]+', dates_str.strip())
        return [f"{name} {d} {action}" for d in dates if d]
    return [line]


def parse_command_local(cmd: str, year: int, month: int, docs: list, assts: list) -> list:
    """
    解析多行口語指令，傳回 action dict 清單。
    支援的句型：
      1. 醫師＋星期＋助理跟診
      2. 人員＋第N個星期X＋時段＋動作
      3. 人員＋M/D＋時段＋動作（支援多日期展開）
    """
    acts = []
    all_people = assts + docs

    # 展開多日期行
    expanded = []
    for raw in cmd.split("\n"):
        raw = raw.strip()
        if raw:
            expanded.extend(_expand_multi_date(raw))

    for line in expanded:
        line = line.strip()
        if not line:
            continue

        # ── 句型 1：醫師/星期/指定助理跟診 ─────────────────
        m1 = re.search(
            r'([^\s\d\(\)]+?)(?:醫師)?\s*(?:禮拜|星期|週|周)([一二三四五六日天1-7])'
            r'\s*(整天|早上|下午|晚上|早午晚|早午|午晚|早晚|早|午|晚)?'
            r'\s*(?:給|讓|由|指定)?\s*([^\s\d\(\)]+?)\s*(?:跟|上)',
            line
        )
        if m1:
            doc   = fuzzy_match_person(m1.group(1), docs)
            wd    = _WD_MAP.get(m1.group(2))
            sh_s  = m1.group(3) or "整天"
            asst  = fuzzy_match_person(m1.group(4), assts)
            shift = ("早" if "早" in sh_s and "午" not in sh_s
                     else "午" if "午" in sh_s or "下午" in sh_s
                     else "晚" if "晚" in sh_s
                     else None)
            acts.append({"action": "assign_assistant_to_doctor",
                          "doctor": doc, "assistant": asst,
                          "weekday": wd, "shift": shift})
            continue

        # ── 句型 2：第N個星期X ───────────────────────────
        m2 = re.search(
            r'([^\s\d\(\)]+?)(?:醫師)?\s*第\s*(\d+)\s*[個]*\s*'
            r'(?:星期|禮拜|週|周)([一二三四五六日天1-7])'
            r'\s*(整天|早上|下午|晚上|早午晚|早午|午晚|早晚|早|午|晚)?'
            r'\s*(?:要|想)?(?:休假|請假|排班|上班|休息)',
            line
        )
        if m2:
            person  = fuzzy_match_person(m2.group(1), all_people)
            w_num   = int(m2.group(2))
            wd      = _WD_MAP.get(m2.group(3))
            sh_s    = m2.group(4) or "整天"
            is_leave = any(x in line for x in ("休", "請", "息"))
            act_type = "leave" if is_leave else "force_assign"
            shifts = []
            if "早" in sh_s or "整" in sh_s: shifts.append("早")
            if "午" in sh_s or "整" in sh_s or "下" in sh_s: shifts.append("午")
            if "晚" in sh_s or "整" in sh_s: shifts.append("晚")
            if not shifts: shifts = [None]
            for s in shifts:
                if "醫師" in person:
                    acts.append({"action": "doctor_leave", "doctor": person,
                                 "weekday": wd, "week_number": w_num, "shift": s})
                else:
                    acts.append({"action": act_type, "assistant": person,
                                 "weekday": wd, "week_number": w_num, "shift": s})
            continue

        # ── 句型 3：M月D日（或 M/D）───────────────────────
        m3 = re.search(
            r'([^\s\d\(\)]+?)(?:醫師)?\s*(?:於)?\s*(\d+)[月/.\-]\s*(\d+)[號日]?'
            r'(?:\(?\s*(?:星期|禮拜|週|周)?\s*[一二三四五六日天1-7]\s*\)?)?'
            r'\s*(整天|早上|下午|晚上|早午晚|早午|午晚|早晚|早|午|晚)?'
            r'\s*(?:要|想)?(休假|請假|排班|上班|休息)',
            line
        )
        m3r = re.search(
            r'(\d+)[月/.\-]\s*(\d+)[號日]?'
            r'(?:\(?\s*(?:星期|禮拜|週|周)?\s*[一二三四五六日天1-7]\s*\)?)?'
            r'\s*(?:由|讓|是)?\s*([^\s\d\(\)]+?)(?:醫師)?'
            r'\s*(整天|早上|下午|晚上|早午晚|早午|午晚|早晚|早|午|晚)?'
            r'\s*(?:要|想)?(休假|請假|排班|上班|休息)',
            line
        )
        if m3 or m3r:
            if m3:
                pstr, mstr, dstr = m3.group(1), m3.group(2), m3.group(3)
                sh_s = m3.group(4) or "整天"; act_str = m3.group(5)
            else:
                mstr, dstr, pstr = m3r.group(1), m3r.group(2), m3r.group(3)
                sh_s = m3r.group(4) or "整天"; act_str = m3r.group(5)

            person = fuzzy_match_person(pstr, all_people)
            date_str = f"{year}-{int(mstr):02d}-{int(dstr):02d}"
            is_leave = any(x in act_str for x in ("休", "請", "息"))
            act_type = "leave" if is_leave else "force_assign"
            shifts = []
            if "早" in sh_s or "整" in sh_s: shifts.append("早")
            if "午" in sh_s or "整" in sh_s or "下" in sh_s: shifts.append("午")
            if "晚" in sh_s or "整" in sh_s: shifts.append("晚")
            if not shifts: shifts = [None]
            for s in shifts:
                if "醫師" in person:
                    acts.append({"action": "doctor_leave", "doctor": person,
                                 "date": date_str, "shift": s})
                else:
                    acts.append({"action": act_type, "assistant": person,
                                 "date": date_str, "shift": s})

    return acts


# ════════════════════════════════════════════════════════════
# Google Gemini API 呼叫
# ════════════════════════════════════════════════════════════


def call_gemini_api(api_key: str, prompt: str) -> str:
    models = ["gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-pro"]
    for model in models:
        url = (f"https://generativelanguage.googleapis.com/v1beta/"
               f"models/{model}:generateContent?key={api_key}")
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        for delay in (3, 8):
            try:
                resp = requests.post(url, json=payload, timeout=20)
                if resp.status_code == 200 and "candidates" in resp.json():
                    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                if resp.status_code == 429:
                    time.sleep(delay); continue
                if resp.status_code == 404:
                    break
            except Exception:
                time.sleep(delay); continue
    return "ERROR: Google API 額度耗盡或無可用模型，請改用「本地關鍵字解析」！"


# ════════════════════════════════════════════════════════════
# 統一套用 action 到設定（本地＋AI 共用）
# ════════════════════════════════════════════════════════════


def apply_actions(acts: list, forced: dict, leaves: dict, manual: list,
                  year: int, month: int, adv_rules: dict) -> int:
    """
    將解析後的 action 清單寫入 forced/leaves/manual，
    傳回成功套用數量。
    """
    count = 0
    for act in acts:
        targets   = get_target_dates(act, year, month)
        anm       = act.get("assistant")
        doc_name  = act.get("doctor")
        act_type  = act.get("action")
        shifts    = ["早", "午", "晚"] if not act.get("shift") else [act["shift"]]

        for dt_str in targets:
            for sh in shifts:
                k = f"{dt_str}_{sh}"
                if k not in forced:
                    forced[k] = {"doctors": {}, "counter": [], "floater": []}

                if act_type == "leave":
                    leaves[f"{anm}_{dt_str}_{sh}"] = True
                    for dk, av in list(forced[k]["doctors"].items()):
                        if av == anm: forced[k]["doctors"].pop(dk, None)
                    for lst_key in ("counter", "floater"):
                        if anm in forced[k][lst_key]:
                            forced[k][lst_key].remove(anm)
                    count += 1

                elif act_type == "doctor_leave":
                    manual[:] = [m for m in manual
                                  if not (m["Date"] == dt_str
                                          and m["Shift"] == sh
                                          and m["Doctor"] == doc_name)]
                    count += 1

                elif act_type == "assign_assistant_to_doctor":
                    for dk, av in list(forced[k]["doctors"].items()):
                        if av == anm: forced[k]["doctors"].pop(dk, None)
                    forced[k]["doctors"][doc_name] = anm
                    for lst_key in ("counter", "floater"):
                        if anm in forced[k][lst_key]:
                            forced[k][lst_key].remove(anm)
                    leaves.pop(f"{anm}_{dt_str}_{sh}", None)
                    count += 1

                elif act_type == "force_assign":
                    already = (anm in forced[k]["doctors"].values()
                               or anm in forced[k]["counter"]
                               or anm in forced[k]["floater"])
                    if not already:
                        role_limit = adv_rules.get(anm, {}).get("role_limit", "")
                        lst_key = "counter" if role_limit == "僅櫃台" else "floater"
                        if anm not in forced[k][lst_key]:
                            forced[k][lst_key].append(anm)
                    leaves.pop(f"{anm}_{dt_str}_{sh}", None)
                    count += 1

    return count
