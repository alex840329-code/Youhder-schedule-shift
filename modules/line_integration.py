# modules/line_integration.py
# LINE Notify 整合 + 班表格式化 + 圖片生成

import io
import calendar as _cal
import requests
from datetime import datetime
from typing import Optional

LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"
WEEKDAY_NAMES   = ["一", "二", "三", "四", "五", "六", "日"]
SHIFT_TIMES     = {"早": "09:00–12:30", "午": "14:00–17:30", "晚": "18:00–21:00"}
SHIFTS          = ["早", "午", "晚"]


# ════════════════════════════════════════════════════════════
# LINE Notify 傳送
# ════════════════════════════════════════════════════════════


def send_line_notify(token: str, message: str) -> tuple:
    """傳送文字訊息。回傳 (成功, 錯誤訊息)"""
    if not token or not token.strip():
        return False, "未設定 LINE Notify Token"
    try:
        resp = requests.post(
            LINE_NOTIFY_URL,
            headers={"Authorization": f"Bearer {token.strip()}"},
            data={"message": message},
            timeout=10,
        )
        if resp.status_code == 200:
            return True, ""
        elif resp.status_code == 401:
            return False, "Token 無效或已過期，請重新取得"
        return False, f"LINE API {resp.status_code}"
    except requests.exceptions.Timeout:
        return False, "連線逾時"
    except Exception as e:
        return False, str(e)


def send_line_notify_with_image(token: str, message: str, image_bytes: bytes) -> tuple:
    """傳送含圖片的 LINE Notify 訊息。"""
    if not token or not token.strip():
        return False, "未設定 LINE Notify Token"
    try:
        resp = requests.post(
            LINE_NOTIFY_URL,
            headers={"Authorization": f"Bearer {token.strip()}"},
            data={"message": message},
            files={"imageFile": ("schedule.png", image_bytes, "image/png")},
            timeout=30,
        )
        if resp.status_code == 200:
            return True, ""
        elif resp.status_code == 401:
            return False, "Token 無效或已過期"
        return False, f"LINE API {resp.status_code}"
    except requests.exceptions.Timeout:
        return False, "連線逾時"
    except Exception as e:
        return False, str(e)


# ════════════════════════════════════════════════════════════
# 圖片班表生成
# ════════════════════════════════════════════════════════════


def generate_schedule_image(
    person_name: str,
    result: dict,
    year: int,
    month: int,
    assts: list,
    docs: list,
    role: str = "assistant",   # "assistant" or "doctor"
) -> bytes:
    """
    生成月曆格式的班表 PNG 圖片（bytes）。
    需要 matplotlib 套件。
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib import font_manager
    except ImportError:
        raise ImportError("需要 matplotlib：pip install matplotlib")

    # 嘗試載入 CJK 字型（macOS / Linux）
    FONT_CANDIDATES = [
        "/System/Library/Fonts/PingFang.ttc",           # macOS
        "/System/Library/Fonts/STHeiti Light.ttc",      # macOS 舊版
        "/System/Library/Fonts/Supplemental/Arial Unicode MS.ttf",  # macOS
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", # Linux (常見)
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",           # Linux WenQuanYi
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",   # Linux Noto
    ]
    cjk_font = None
    for fp in FONT_CANDIDATES:
        try:
            font_manager.fontManager.addfont(fp)
            cjk_font = font_manager.FontProperties(fname=fp)
            break
        except Exception:
            pass
    fp_dict = {"fontproperties": cjk_font} if cjk_font else {}

    # --- 資料整理 ---
    nm2n = {a["name"]: a.get("nick", a["name"]) for a in assts}

    def get_cell_text(dt_str):
        texts = []
        for sh in SHIFTS:
            slot = f"{dt_str}_{sh}"
            v    = result.get(slot, {})
            if role == "assistant":
                # 找此助理在此時段的角色
                for doc_name, paired in v.get("doctors", {}).items():
                    if paired == person_name:
                        doc_nick = next((d.get("nick", d["name"]) for d in docs if d["name"] == doc_name), doc_name)
                        texts.append(f"{sh}跟{doc_nick}")
                        break
                else:
                    if person_name in v.get("counter", []):
                        texts.append(f"{sh}櫃")
                    elif person_name in v.get("floater", []):
                        texts.append(f"{sh}流")
                    elif person_name in v.get("look", []):
                        texts.append(f"{sh}行政")
            else:  # doctor
                paired = v.get("doctors", {}).get(person_name, "")
                if paired:
                    texts.append(f"{sh}:{nm2n.get(paired, paired)}")
                elif any(x["Date"] == dt_str and x["Shift"] == sh and x["Doctor"] == person_name
                         for x in []):
                    texts.append(f"{sh}—")
        return "\n".join(texts) if texts else ""

    # --- 繪圖 ---
    cal_weeks = _cal.monthcalendar(year, month)
    n_weeks   = len(cal_weeks)
    fig_h     = 2.2 + n_weeks * 1.6

    fig, ax = plt.subplots(figsize=(13, fig_h))
    ax.set_xlim(0, 6)
    ax.set_ylim(0, n_weeks + 0.8)
    ax.axis("off")

    # 標題
    title_str = f"{year}年{month}月　{person_name}　班表"
    ax.text(3, n_weeks + 0.55, title_str, ha="center", va="center",
            fontsize=16, fontweight="bold", **fp_dict)

    # 星期標頭
    day_labels = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六"]
    for ci, lbl in enumerate(day_labels):
        ax.add_patch(mpatches.FancyBboxPatch(
            (ci + 0.02, n_weeks + 0.05), 0.96, 0.45,
            boxstyle="round,pad=0.02", facecolor="#4472C4", edgecolor="none"
        ))
        ax.text(ci + 0.5, n_weeks + 0.28, lbl, ha="center", va="center",
                color="white", fontsize=11, fontweight="bold", **fp_dict)

    # 月曆格子
    SHIFT_BG = {"早": "#FDE9D9", "午": "#BDD7EE", "晚": "#FABF8F"}
    for wi, week in enumerate(reversed(cal_weeks)):
        row_y = n_weeks - wi - 1
        for ci in range(6):
            day_num = week[ci]
            # 格子底色
            bg = "#f9f9f9" if day_num == 0 else "white"
            ax.add_patch(mpatches.FancyBboxPatch(
                (ci + 0.02, row_y + 0.02), 0.96, 0.96,
                boxstyle="round,pad=0.02", facecolor=bg,
                edgecolor="#cccccc", linewidth=0.8
            ))
            if day_num == 0:
                continue
            dt_str  = f"{year}-{month:02d}-{day_num:02d}"
            cell_tx = get_cell_text(dt_str)

            # 日期號碼
            ax.text(ci + 0.1, row_y + 0.82, str(day_num),
                    ha="left", va="top", fontsize=11, color="#555", **fp_dict)

            # 班表文字
            if cell_tx:
                ax.text(ci + 0.5, row_y + 0.42, cell_tx,
                        ha="center", va="center", fontsize=9,
                        color="#1a1a1a", **fp_dict,
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="#E8F4FD",
                                  edgecolor="none", alpha=0.8))

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close()
    buf.seek(0)
    return buf.getvalue()


# ════════════════════════════════════════════════════════════
# 班表格式化（文字版）
# ════════════════════════════════════════════════════════════


def _date_disp(dt_str: str) -> str:
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d")
        return f"{dt.month}/{dt.day}({WEEKDAY_NAMES[dt.weekday()]})"
    except Exception:
        return dt_str


def format_assistant_schedule(asst_name, result, year, month, docs) -> str:
    lines = [f"【{asst_name} {month}月個人班表】", "─"*20]
    count = 0
    for slot in sorted(result.keys()):
        if "_" not in slot: continue
        dt_str, sh = slot.rsplit("_", 1)
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d")
        except Exception:
            continue
        if dt.year != year or dt.month != month: continue

        v = result[slot]
        role_str = None
        for doc_name, paired in v.get("doctors", {}).items():
            if paired == asst_name:
                doc_nick = next((d.get("nick", doc_name) for d in docs if d["name"] == doc_name), doc_name)
                role_str = f"跟診-{doc_nick}"
                break
        if not role_str and asst_name in v.get("counter", []): role_str = "主櫃台"
        if not role_str and asst_name in v.get("floater", []): role_str = "流動"
        if not role_str and asst_name in v.get("look",    []): role_str = "行政"
        if role_str:
            lines.append(f"{_date_disp(dt_str)} {sh} {role_str}")
            count += 1

    lines += ["─"*20, f"本月共計：{count} 診", "",
              "📌 班別時間："] + [f"  {sh}診：{t}" for sh, t in SHIFT_TIMES.items()]
    return "\n".join(lines)


def format_doctor_schedule(doc_name, manual_schedule, year, month, result=None) -> str:
    lines = [f"【{doc_name} {month}月上診班表】", "─"*20]
    doc_slots = sorted(
        [x for x in manual_schedule if x["Doctor"] == doc_name],
        key=lambda x: (x["Date"], {"早":0,"午":1,"晚":2}.get(x["Shift"],9))
    )
    count = 0
    for x in doc_slots:
        dt_str, sh = x["Date"], x["Shift"]
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d")
        except Exception:
            continue
        if dt.year != year or dt.month != month: continue
        asst_str = ""
        if result:
            paired = result.get(f"{dt_str}_{sh}", {}).get("doctors", {}).get(doc_name, "")
            if paired: asst_str = f"（跟：{paired}）"
        lines.append(f"{_date_disp(dt_str)} {sh}{asst_str}")
        count += 1

    lines += ["─"*20, f"本月共計：{count} 診", "",
              "📌 班別時間："] + [f"  {sh}診：{t}" for sh, t in SHIFT_TIMES.items()]
    lines.append("\n如需調整，請聯繫管理員。")
    return "\n".join(lines)


def format_leave_request_message(person_name, leaves, year, month) -> str:
    slots = []
    for key, val in leaves.items():
        if not val: continue
        parts = key.split("_")
        if len(parts) == 3 and parts[0] == person_name:
            _, dt_str, sh = parts
            try:
                dt = datetime.strptime(dt_str, "%Y-%m-%d")
                if dt.year == year and dt.month == month:
                    slots.append((dt_str, sh))
            except Exception:
                pass
    slots.sort()
    lines = [f"【{person_name} {month}月請假記錄】", "─"*20]
    if slots:
        for dt_str, sh in slots:
            lines.append(f"{_date_disp(dt_str)} {sh}")
        lines += ["─"*20, f"共 {len(slots)} 個時段請假"]
    else:
        lines.append("（本月無請假）")
    lines.append("\n如有誤，請聯繫管理員更正。")
    return "\n".join(lines)
