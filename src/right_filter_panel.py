"""
right_filter_panel.py
=====================
Collapsible, context-aware Right-Side Filter Panel for the Nassau Candy Platform.

Features:
- Dynamic context: adapts widgets based on active page (Overview, Routes, ML, Factory, Product, Customer, etc.)
- Collapsible design with active filter count badge
- Global search input
- Preset management (Save, Load, Reset)
- Quick statistics scorecard (records in scope, retained %, sales volume, on-time SLA %)
- Expandable grouped filter sections
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.filter_engine import (
    compute_quick_stats,
    get_active_filter_count,
    load_presets,
    save_preset,
)
from src.utils import SHIP_MODES_ORDERED, format_number, get_palette


def render_right_filter_panel(df_full: pd.DataFrame, current_page: str = "overview") -> pd.DataFrame:
    """
    Renders the dynamic right filter panel and applies filters instantly to df_full.
    Returns the filtered DataFrame.
    """
    theme = st.session_state.get("theme", "dark")
    palette = get_palette(theme)
    h1_clr = "#0F172A" if theme == "light" else "#E8EAED"
    sub_clr = "#64748B" if theme == "light" else "#9AA0B9"
    card_bg = "#FFFFFF" if theme == "light" else "rgba(30,33,48,0.95)"
    border_clr = "rgba(83,72,232,0.2)" if theme == "light" else "rgba(108,99,255,0.28)"

    # Initialize persistent filter state dictionary in session_state if missing
    if "global_filters" not in st.session_state:
        st.session_state["global_filters"] = {}

    filters = st.session_state["global_filters"]
    presets = load_presets()

    # Determine default full values
    year_col = "Shipment Year" if "Shipment Year" in df_full.columns else ("Ship Year" if "Ship Year" in df_full.columns else None)
    month_col = "Shipment Month" if "Shipment Month" in df_full.columns else ("Ship Month" if "Ship Month" in df_full.columns else None)
    all_years = sorted(df_full[year_col].dropna().unique().tolist()) if year_col else []
    all_months = list(range(1, 13))
    all_factories = sorted(df_full["Factory"].dropna().unique().tolist()) if "Factory" in df_full.columns else []
    all_regions = sorted(df_full["Region"].dropna().unique().tolist()) if "Region" in df_full.columns else []
    all_states = sorted(df_full["State/Province"].dropna().unique().tolist()) if "State/Province" in df_full.columns else []
    all_modes = [m for m in SHIP_MODES_ORDERED if m in df_full["Ship Mode"].unique()] if "Ship Mode" in df_full.columns else []
    all_divisions = sorted(df_full["Division"].dropna().unique().tolist()) if "Division" in df_full.columns else []
    all_products = sorted(df_full["Product Name"].dropna().unique().tolist()) if "Product Name" in df_full.columns else []
    min_lt = int(df_full["Shipping Lead Time"].min()) if "Shipping Lead Time" in df_full.columns else 0
    max_lt = int(df_full["Shipping Lead Time"].max()) if "Shipping Lead Time" in df_full.columns else 20

    # Panel open/closed state
    panel_open = st.session_state.get("filter_panel_expanded", False)
    active_count = get_active_filter_count(filters, df_full)

    # Top floating filter drawer bar
    top_c1, top_c2 = st.columns([3.5, 1.5])
    with top_c2:
        badge_text = f" ({active_count} Active)" if active_count > 0 else ""
        btn_label = "🎛️ Close Filter Rail" if panel_open else f"🎛️ Dynamic Filters{badge_text}"
        if st.button(btn_label, width="stretch", key="toggle_filter_panel_btn", help="Open/Close right filter drawer"):
            st.session_state["filter_panel_expanded"] = not panel_open
            st.rerun()

    # If collapsed, compute filter mask from current filter state and return
    if not panel_open:
        return apply_mask(df_full, filters, all_years, all_factories, all_regions, all_states, all_modes, all_divisions, min_lt, max_lt)

    # If expanded, render the dedicated right filter drawer
    st.markdown(f"""
    <div style="background:{card_bg};border:1px solid {border_clr};border-radius:18px;padding:20px 24px;margin-bottom:24px;
                box-shadow:0 8px 32px rgba(0,0,0,{'0.06' if theme == 'light' else '0.35'});">
        <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid {border_clr};padding-bottom:12px;margin-bottom:16px;">
            <div style="display:flex;align-items:center;gap:8px;">
                <span class="material-symbols-rounded" style="color:{palette['primary']};font-size:1.6rem;">tune</span>
                <div>
                    <h3 style="margin:0;font-size:1.15rem;font-weight:800;color:{h1_clr};letter-spacing:-.01em;">
                        Dynamic Filter Rail — <span style="color:{palette['primary']};text-transform:capitalize;">{current_page.replace('_', ' ')}</span>
                    </h3>
                    <div style="font-size:.74rem;color:{sub_clr};">Contextual parameters synchronized across all visualizations</div>
                </div>
            </div>
            <span style="background:rgba(108,99,255,0.15);color:{palette['primary']};font-size:.72rem;font-weight:700;padding:3px 10px;border-radius:20px;">
                {active_count} ACTIVE FILTERS
            </span>
        </div>
    """, unsafe_allow_html=True)

    # 1. Universal Search & Presets Toolbar
    tb_c1, tb_c2, tb_c3 = st.columns([2, 1.5, 1])
    with tb_c1:
        search_txt = st.text_input("🔍 Quick Universal Search", value=filters.get("search_text", ""), placeholder="Search order ID, city, customer, product...", key="filter_search_txt")
        filters["search_text"] = search_txt
    with tb_c2:
        preset_names = ["-- Select Preset --"] + list(presets.keys())
        selected_preset = st.selectbox("📂 Preset Filter Template", preset_names, index=0, key="filter_preset_select")
        if selected_preset != "-- Select Preset --" and st.button("Apply Preset", key="btn_apply_preset"):
            st.session_state["global_filters"] = presets[selected_preset].copy()
            st.rerun()
    with tb_c3:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 Reset All", width="stretch", key="btn_reset_filters"):
            st.session_state["global_filters"] = {}
            st.rerun()

    # 2. Context-Specific Filter Sections
    f_col1, f_col2 = st.columns(2)

    # LEFT COLUMN: Temporal & Spatial
    with f_col1:
        # Group A: Time Horizon
        with st.expander("📅 Temporal Horizon & Calendar", expanded=True):
            sel_years = st.multiselect("Shipment Year", all_years, default=filters.get("years", all_years), key="f_years")
            filters["years"] = sel_years

            months_names = {1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"May", 6:"Jun", 7:"Jul", 8:"Aug", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dec"}
            sel_months = st.multiselect("Shipment Month", all_months, default=filters.get("months", all_months), format_func=lambda m: f"{months_names.get(m, m)} ({m})", key="f_months")
            filters["months"] = sel_months

        # Group B: Supply Chain & Geographic Scope
        with st.expander("🏭 Origin Plants & Destination Regions", expanded=(current_page in ["routes", "geo", "factory", "overview"])):
            sel_factories = st.multiselect("Manufacturing Plant / Factory", all_factories, default=filters.get("factories", all_factories), key="f_factories")
            filters["factories"] = sel_factories

            sel_regions = st.multiselect("Destination Region", all_regions, default=filters.get("regions", all_regions), key="f_regions")
            filters["regions"] = sel_regions

            sel_states = st.multiselect("Destination State", all_states, default=filters.get("states", all_states), key="f_states", placeholder="All US States")
            filters["states"] = sel_states

    # RIGHT COLUMN: Carrier Modes, Products & Performance
    with f_col2:
        # Group C: Commercial & Product Portfolio
        with st.expander("🍬 Commercial Divisions & SKUs", expanded=(current_page in ["product", "customer", "overview"])):
            sel_divs = st.multiselect("Confection Division", all_divisions, default=filters.get("divisions", all_divisions), key="f_divisions")
            filters["divisions"] = sel_divs

            sel_prods = st.multiselect("Specific Product SKU", all_products, default=filters.get("products", []), placeholder="All Confections", key="f_products")
            filters["products"] = sel_prods

        # Group D: Carrier Service & Operational Bounds
        with st.expander("🚚 Delivery Class & Lead Time Bounds", expanded=(current_page in ["shipmode", "routes", "ml", "simulator"])):
            sel_modes = st.multiselect("Delivery Class / Mode", all_modes, default=filters.get("ship_modes", all_modes), key="f_modes")
            filters["ship_modes"] = sel_modes

            default_lt = filters.get("lead_time_range", (min_lt, max_lt))
            sel_lt = st.slider("Lead Time Bound (Days)", min_lt, max_lt, default_lt, key="f_leadtime")
            filters["lead_time_range"] = sel_lt

            delay_only = st.checkbox("Only Delayed Shipments (Delay Flag = True)", value=filters.get("delay_only", False), key="f_delay_only")
            filters["delay_only"] = delay_only

    # 3. Save Preset Row
    st.markdown("<hr style='border:none;height:1px;background:rgba(108,99,255,0.15);margin:14px 0 10px 0;'>", unsafe_allow_html=True)
    sv_c1, sv_c2 = st.columns([3, 1])
    with sv_c1:
        new_preset_name = st.text_input("Preset Name to Save Current Filter Configuration", placeholder="e.g. Q3 2024 Sugar Shack Delayed Orders", key="new_preset_name")
    with sv_c2:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("💾 Save as New Preset", width="stretch", key="btn_save_preset"):
            if new_preset_name.strip():
                save_preset(new_preset_name.strip(), filters)
                st.success(f"Preset '{new_preset_name.strip()}' saved.")
                st.rerun()
            else:
                st.error("Please enter a preset name.")

    st.markdown("</div>", unsafe_allow_html=True)

    # 4. Instant In-Memory Filter Mask Application
    df_filtered = apply_mask(df_full, filters, all_years, all_factories, all_regions, all_states, all_modes, all_divisions, min_lt, max_lt)

    # 5. Quick Statistics Scoreboard
    stats = compute_quick_stats(df_filtered, df_full)
    qs_c1, qs_c2, qs_c3, qs_c4 = st.columns(4)
    with qs_c1:
        st.metric("Working Scope Records", f"{stats['filtered_records']:,} rows", f"{stats['pct_retained']:.1f}% retained")
    with qs_c2:
        st.metric("Total Revenue in Scope", format_number(stats['total_sales'], prefix="$"))
    with qs_c3:
        st.metric("Avg Lead Time", f"{stats['avg_lead_time']:.1f} days")
    with qs_c4:
        st.metric("On-Time Delivery Rate", f"{stats['on_time_pct']:.1f}%")

    st.markdown("<div style='margin-bottom:16px;'></div>", unsafe_allow_html=True)
    return df_filtered


def apply_mask(
    df: pd.DataFrame,
    filters: Dict[str, Any],
    all_years: List[int],
    all_factories: List[str],
    all_regions: List[str],
    all_states: List[str],
    all_modes: List[str],
    all_divisions: List[str],
    min_lt: int,
    max_lt: int,
) -> pd.DataFrame:
    """Applies filter dictionary to full dataframe."""
    if df.empty:
        return df

    mask = pd.Series(True, index=df.index)

    # Universal Search
    search_q = filters.get("search_text", "")
    if search_q:
        search_mask = pd.Series(False, index=df.index)
        search_cols = ["Order ID", "Product Name", "City", "Customer ID"]
        for col in search_cols:
            if col in df.columns:
                search_mask = search_mask | df[col].astype(str).str.contains(search_q, case=False, na=False)
        mask = mask & search_mask

    # Years
    years = filters.get("years", all_years)
    year_col = "Shipment Year" if "Shipment Year" in df.columns else ("Ship Year" if "Ship Year" in df.columns else None)
    if years and year_col:
        mask = mask & df[year_col].isin(years)

    # Months
    months = filters.get("months", list(range(1, 13)))
    month_col = "Shipment Month" if "Shipment Month" in df.columns else ("Ship Month" if "Ship Month" in df.columns else None)
    if months and month_col:
        mask = mask & df[month_col].isin(months)

    # Factories
    facs = filters.get("factories", all_factories)
    if facs and "Factory" in df.columns:
        mask = mask & df["Factory"].isin(facs)

    # Regions
    regs = filters.get("regions", all_regions)
    if regs and "Region" in df.columns:
        mask = mask & df["Region"].isin(regs)

    # States
    states = filters.get("states", all_states)
    if states and "State/Province" in df.columns:
        mask = mask & df["State/Province"].isin(states)

    # Ship Modes
    modes = filters.get("ship_modes", all_modes)
    if modes and "Ship Mode" in df.columns:
        mask = mask & df["Ship Mode"].isin(modes)

    # Divisions
    divs = filters.get("divisions", all_divisions)
    if divs and "Division" in df.columns:
        mask = mask & df["Division"].isin(divs)

    # Products
    prods = filters.get("products", [])
    if prods and "Product Name" in df.columns:
        mask = mask & df["Product Name"].isin(prods)

    # Lead Time Range
    lt_range = filters.get("lead_time_range", (min_lt, max_lt))
    if lt_range and "Shipping Lead Time" in df.columns:
        mask = mask & df["Shipping Lead Time"].between(lt_range[0], lt_range[1])

    # Delayed Only
    if filters.get("delay_only") and "Delay Flag" in df.columns:
        mask = mask & (df["Delay Flag"] == True)

    return df[mask].copy()
