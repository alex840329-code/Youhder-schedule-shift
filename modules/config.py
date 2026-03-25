# modules/config.py
# 設定管理模組 — 載入、儲存、預設值
# 支援 Supabase（雲端）+ 本地 JSON fallback

import json
import os
import streamlit as st
from datetime import datetime

from modules.default_data import (
    DEFAULT_DOCTORS, DEFAULT_ASSISTANTS,
    DEFAULT_PAIRING_MATRIX, DEFAULT_ADV_RULES
)

CONFIG_FILE = "yude_config_v11.json"
_SUPABASE_TABLE = "clinic_config"
_SUPABASE_ROW_ID = 1


# ════════════════════════════════════════════════════════════
# Supabase 連線（僅在 secrets 存在時啟用）
# ════════════════════════════════════════════════════════════

def _get_supabase():
    """
    若 .streamlit/secrets.toml 含 SUPABASE_URL / SUPABASE_KEY 就回傳 client，
    否則回傳 None（退回本地 JSON）。
    """
    try:
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if url and key:
            from supabase import create_client
            return create_client(url, key)
    except Exception:
        pass
    return None


# ════════════════════════════════════════════════════════════
# 預設設定
# ════════════════════════════════════════════════════════════

def get_default_config() -> dict:
    """傳回全域設定的預設值（含預設人員資料）。"""
    today = datetime.today()
    next_month = today.month % 12 + 1
    year = today.year if next_month > 1 else today.year + 1

    return {
        # 系統設定
        "api_key": "",
        "is_locked": False,

        # LINE 整合（Notify）
        "line_group_token": "",         # 群組 LINE Notify Token

        # 人員（line_notify_token 存在各人員 dict 的 "line_notify_token" 欄位）
        "doctors_struct":   DEFAULT_DOCTORS.copy(),
        "assistants_struct": DEFAULT_ASSISTANTS.copy(),

        # 排班邏輯
        "pairing_matrix":  DEFAULT_PAIRING_MATRIX.copy(),
        "adv_rules":       DEFAULT_ADV_RULES.copy(),
        "template_odd":    {},
        "template_even":   {},
        "first_week_type": "odd",       # "odd" 或 "even"

        # 月份
        "year":  year,
        "month": next_month,

        # 排班資料
        "manual_schedule": [],
        "leaves":          {},
        "saved_result":    {},
        "forced_assigns":  {},

        # 人力彈性開關
        "dynamic_flt": True,
        "dynamic_ctr": True,
        "balance_flt": True,
        "ctr_count":   2,
        "flt_count":   1,
    }


# ════════════════════════════════════════════════════════════
# 載入設定
# ════════════════════════════════════════════════════════════

def _merge_defaults(data: dict) -> dict:
    """補齊缺少的鍵，並清理損壞的列表資料。"""
    defaults = get_default_config()
    for k, v in defaults.items():
        if k not in data:
            data[k] = v
    for key in ("doctors_struct", "assistants_struct"):
        if isinstance(data.get(key), list):
            data[key] = [x for x in data[key] if isinstance(x, dict) and x]
    return data


def _load_from_supabase(sb) -> dict | None:
    """從 Supabase 載入設定，失敗時回傳 None。"""
    try:
        resp = sb.table(_SUPABASE_TABLE).select("data").eq("id", _SUPABASE_ROW_ID).execute()
        rows = resp.data
        if rows and rows[0].get("data"):
            return _merge_defaults(rows[0]["data"])
    except Exception as e:
        st.warning(f"⚠️ Supabase 讀取失敗，改用本地資料：{e}")
    return None


def _load_from_local() -> dict:
    """從本地 JSON 載入設定，失敗時回傳預設值。"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _merge_defaults(data)
        except Exception:
            pass
    return get_default_config()


def load_config() -> dict:
    """
    載入設定（優先 Supabase，其次本地 JSON，最後預設值）。
    """
    sb = _get_supabase()
    if sb:
        data = _load_from_supabase(sb)
        if data is not None:
            return data
    return _load_from_local()


# ════════════════════════════════════════════════════════════
# 儲存設定
# ════════════════════════════════════════════════════════════

def save_config(config: dict) -> None:
    """
    儲存設定（優先 Supabase，其次本地 JSON）。
    同時更新 session_state 以保持一致。
    """
    # 同步 session_state
    if "config" in st.session_state:
        st.session_state.config = config

    sb = _get_supabase()
    if sb:
        try:
            sb.table(_SUPABASE_TABLE).upsert({
                "id": _SUPABASE_ROW_ID,
                "data": config,
            }).execute()
            # 同步備份一份本地 JSON（供離線查看）
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=4)
            except Exception:
                pass
            return
        except Exception as e:
            st.error(f"❌ Supabase 儲存失敗：{e}（嘗試本地備份）")

    # 本地 JSON fallback
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"存檔出錯: {e}")


# ════════════════════════════════════════════════════════════
# Session 初始化
# ════════════════════════════════════════════════════════════

def init_session_config() -> None:
    """若 session_state 尚未初始化，載入設定並還原上次結果。"""
    if "config" not in st.session_state:
        st.session_state.config = load_config()
        if st.session_state.config.get("saved_result"):
            st.session_state.result = st.session_state.config["saved_result"]


# ════════════════════════════════════════════════════════════
# 快捷存取
# ════════════════════════════════════════════════════════════

def get_active_doctors() -> list:
    raw = st.session_state.config.get("doctors_struct") or []
    return sorted(
        [d for d in raw if isinstance(d, dict) and d.get("active", True)],
        key=lambda x: x.get("order", 99),
    )


def get_active_assistants() -> list:
    raw = st.session_state.config.get("assistants_struct") or []
    return [a for a in raw if isinstance(a, dict) and a.get("active", True)]


# ════════════════════════════════════════════════════════════
# 儲存後端狀態顯示（供 app.py 使用）
# ════════════════════════════════════════════════════════════

def get_storage_backend() -> str:
    """回傳目前儲存後端描述字串（供 UI 顯示）。"""
    sb = _get_supabase()
    if sb:
        return "☁️ Supabase（雲端）"
    return "💾 本地 JSON"
