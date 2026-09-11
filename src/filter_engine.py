"""
filter_engine.py
================
Dynamic, context-aware filter engine and preset management system for the Nassau Candy
Logistics Intelligence Platform.

Provides:
- Page-specific filter extraction and state tracking
- Preset saving, loading, and resetting
- Active filter count calculation
- Quick statistic computation (record count, total sales, on-time rate, avg lead time)
- Universal instant DataFrame masking
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils import PROJECT_ROOT, SHIP_MODES_ORDERED, format_number, get_logger

logger = get_logger(__name__)

PRESETS_DIR = PROJECT_ROOT / "data" / "presets"
PRESETS_FILE = PRESETS_DIR / "filter_presets.json"


def ensure_presets_dir() -> None:
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)


def load_presets() -> Dict[str, Dict[str, Any]]:
    """Load saved filter presets from disk."""
    ensure_presets_dir()
    if not PRESETS_FILE.exists():
        # Default built-in presets
        default_presets = {
            "Default (All Data)": {},
            "Delayed Orders Only": {"delay_only": True},
            "Year 2024 Scope": {"years": [2024]},
            "Express Modes (Air/Fast)": {"ship_modes": ["First Class", "Same Day"]},
            "Lot's O' Nuts Factory": {"factories": ["Lot's O' Nuts"]},
        }
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_presets, f, indent=2)
        return default_presets
    try:
        with open(PRESETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load presets: %s", e)
        return {}


def save_preset(name: str, filter_state: Dict[str, Any]) -> bool:
    """Save a named filter preset to disk."""
    ensure_presets_dir()
    presets = load_presets()
    presets[name] = filter_state
    try:
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2)
        return True
    except Exception as e:
        logger.error("Failed to save preset '%s': %s", name, e)
        return False


def get_active_filter_count(filters: Dict[str, Any], df_full: pd.DataFrame) -> int:
    """Count how many filter dimensions have non-default constraints applied."""
    count = 0
    if filters.get("search_text"):
        count += 1
    if filters.get("years"):
        year_col = "Shipment Year" if "Shipment Year" in df_full.columns else ("Ship Year" if "Ship Year" in df_full.columns else None)
        total_yrs = len(df_full[year_col].dropna().unique()) if year_col else 0
        if total_yrs and len(filters["years"]) < total_yrs:
            count += 1
    if filters.get("factories") and len(filters["factories"]) < len(df_full["Factory"].dropna().unique() if "Factory" in df_full.columns else []):
        count += 1
    if filters.get("regions") and len(filters["regions"]) < len(df_full["Region"].dropna().unique() if "Region" in df_full.columns else []):
        count += 1
    if filters.get("states") and len(filters["states"]) < len(df_full["State/Province"].dropna().unique() if "State/Province" in df_full.columns else []):
        count += 1
    if filters.get("ship_modes") and len(filters["ship_modes"]) < len(df_full["Ship Mode"].dropna().unique() if "Ship Mode" in df_full.columns else []):
        count += 1
    if filters.get("divisions") and len(filters["divisions"]) < len(df_full["Division"].dropna().unique() if "Division" in df_full.columns else []):
        count += 1
    if filters.get("products") and len(filters["products"]) > 0:
        count += 1
    if filters.get("delay_only"):
        count += 1
    if filters.get("lead_time_range"):
        min_lt = int(df_full["Shipping Lead Time"].min()) if "Shipping Lead Time" in df_full.columns else 0
        max_lt = int(df_full["Shipping Lead Time"].max()) if "Shipping Lead Time" in df_full.columns else 20
        if filters["lead_time_range"] != (min_lt, max_lt):
            count += 1
    return count


def compute_quick_stats(df_scope: pd.DataFrame, df_full: pd.DataFrame) -> Dict[str, Any]:
    """Calculate summary metrics for the currently filtered working dataset."""
    total_records = len(df_full)
    filtered_records = len(df_scope)
    pct_retained = (filtered_records / total_records * 100) if total_records else 0.0

    total_sales = float(df_scope["Sales"].sum()) if "Sales" in df_scope.columns and not df_scope.empty else 0.0
    avg_lead_time = float(df_scope["Shipping Lead Time"].mean()) if "Shipping Lead Time" in df_scope.columns and not df_scope.empty else 0.0
    on_time_pct = float((1.0 - df_scope["Delay Flag"].mean()) * 100) if "Delay Flag" in df_scope.columns and not df_scope.empty else 100.0

    return {
        "filtered_records": filtered_records,
        "total_records": total_records,
        "pct_retained": pct_retained,
        "total_sales": total_sales,
        "avg_lead_time": avg_lead_time,
        "on_time_pct": on_time_pct,
    }
