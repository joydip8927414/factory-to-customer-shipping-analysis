"""pg_orders.py — Order Drill Down, Year/Month/Day Filtering & Advanced CSV Management"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.right_filter_panel import render_right_filter_panel
from src.utils import get_palette

def render(df_input: pd.DataFrame) -> None:
    df_full = st.session_state.get("df_full", df_input)
    df = render_right_filter_panel(df_full, current_page="orders")
    st.session_state["df_filtered"] = df

    theme = st.session_state.get("theme", "dark")
    palette = get_palette(theme)
    card_bg = "#FFFFFF" if theme == "light" else "rgba(30,33,48,.8)"
    card_border = "rgba(83,72,232,.2)" if theme == "light" else "rgba(108,99,255,.25)"
    text_color = "#0F172A" if theme == "light" else "#E8EAED"
    muted_color = "#64748B" if theme == "light" else "#9AA0B9"

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
        <span class="material-symbols-rounded" style="font-size:2rem;color:{palette['primary']};">search</span>
        <h1 style="font-size:1.85rem;font-weight:800;color:{text_color};margin:0;letter-spacing:-.02em;">
            Order Drill Down & Multi-Format Dataset Explorer
        </h1>
    </div>
    <p style="color:{muted_color};font-size:.86rem;margin-bottom:22px;">
        Interactive order inquiry, year-wise quick filters, multi-column search, and instant exports (CSV and Excel .xlsx).
    </p>""", unsafe_allow_html=True)

    # ── Quick Order Year Filter Buttons ──
    st.markdown(f'<div style="font-size:.78rem;font-weight:700;color:{palette["primary"]};text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;"><span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;margin-right:4px;">flash_on</span>Quick Year Filter (Click to Filter Table & CSV)</div>', unsafe_allow_html=True)
    
    if "Order Year" in df.columns:
        order_years = sorted([int(y) for y in df["Order Year"].dropna().unique()])
    elif "Order Date" in df.columns:
        df["Order Year"] = pd.to_datetime(df["Order Date"], dayfirst=True, errors="coerce").dt.year
        order_years = sorted([int(y) for y in df["Order Year"].dropna().unique()])
    elif "Shipment Year" in df.columns:
        order_years = sorted([int(y) for y in df["Shipment Year"].dropna().unique()])
    else:
        order_years = []
    y_cols = st.columns(len(order_years) + 1)
    
    # Initialize session state for order page quick filter if not present
    if "quick_order_year" not in st.session_state:
        st.session_state["quick_order_year"] = "All"

    with y_cols[0]:
        is_active = st.session_state["quick_order_year"] == "All"
        btn_type = "primary" if is_active else "secondary"
        if st.button("All Years", key="btn_all_years", type=btn_type, use_container_width=True):
            st.session_state["quick_order_year"] = "All"
            st.rerun()

    for i, yr in enumerate(order_years):
        with y_cols[i + 1]:
            is_active = str(st.session_state["quick_order_year"]) == str(yr)
            btn_type = "primary" if is_active else "secondary"
            cnt = (df["Order Year"] == yr).sum()
            if st.button(f"{yr} ({cnt:,})", key=f"btn_yr_{yr}", type=btn_type, icon=":material/calendar_today:", use_container_width=True):
                st.session_state["quick_order_year"] = yr
                st.rerun()

    # ── Search & Filter Panel ─────────────────────────────────────────────────
    st.markdown('<hr class="styled-divider" style="margin:16px 0;">', unsafe_allow_html=True)
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">search</span>Detailed Search & Table Controls</div>', unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    with c1:
        search = st.text_input("Search", placeholder="Search Order ID, Customer, City, State, Product, Factory…",
                               label_visibility="collapsed")
    with c2:
        delay_f = st.selectbox("Delay Status", ["All", "Delayed Only", "On Time Only"],
                               label_visibility="collapsed")
    with c3:
        sort_by = st.selectbox("Sort by", ["Order Date", "Ship Date", "Shipping Lead Time", "Sales", "Gross Profit",
                                           "Route Efficiency Score"], label_visibility="collapsed")
    with c4:
        sort_asc = st.selectbox("Order", ["Descending", "Ascending"], label_visibility="collapsed")

    # ── Apply Filters ──────────────────────────────────────────────────────────
    dv = df.copy()

    # Apply Quick Year Filter if selected
    if st.session_state["quick_order_year"] != "All":
        dv = dv[dv["Order Year"].astype(str) == str(st.session_state["quick_order_year"])]

    if search.strip():
        t = search.strip().lower()
        mask = (
            dv["Order ID"].astype(str).str.lower().str.contains(t, na=False) |
            dv["Customer ID"].astype(str).str.lower().str.contains(t, na=False) |
            dv["City"].astype(str).str.lower().str.contains(t, na=False) |
            dv["State/Province"].astype(str).str.lower().str.contains(t, na=False) |
            dv["Product Name"].astype(str).str.lower().str.contains(t, na=False) |
            dv["Factory"].astype(str).str.lower().str.contains(t, na=False)
        )
        dv = dv[mask]
        
    if delay_f == "Delayed Only":
        dv = dv[dv["Delay Flag"] == True]
    elif delay_f == "On Time Only":
        dv = dv[dv["Delay Flag"] == False]

    dv = dv.sort_values(sort_by, ascending=(sort_asc == "Ascending"))

    # ── KPI Strip ─────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, val, lbl, clr in [
        (c1, f"{len(dv):,}",                         "Records Filtered", palette["primary"]),
        (c2, f"${dv['Sales'].sum():,.0f}",             "Filtered Sales",   palette["accent"]),
        (c3, f"${dv['Gross Profit'].sum():,.0f}",      "Filtered Profit",  palette["secondary"]),
        (c4, f"{dv['Shipping Lead Time'].mean():.0f}d","Avg Lead Time",    palette["info"]),
        (c5, f"{dv['Delay Flag'].mean()*100:.1f}%",   "Delay Rate",       palette["danger"]),
    ]:
        with col:
            st.markdown(f'<div class="kpi-card"><div class="kpi-value" style="color:{clr};">{val}</div>'
                        f'<div class="kpi-label">{lbl}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Table Display ─────────────────────────────────────────────────────────
    show_cols = ["Order ID", "Order Date", "Ship Date", "Order Year", "Ship Mode", "Customer ID", "City",
                 "State/Province", "Region", "Product Name", "Factory", "Division", "Sales",
                 "Units", "Gross Profit", "Cost", "Shipping Lead Time", "Delay Flag",
                 "Route Efficiency Score", "Factory → State Route"]
    avail = [c for c in show_cols if c in dv.columns]
    dd = dv[avail].copy()
    dd["Order Date"] = pd.to_datetime(dd["Order Date"]).dt.strftime("%Y-%m-%d")
    dd["Ship Date"]  = pd.to_datetime(dd["Ship Date"]).dt.strftime("%Y-%m-%d")
    dd["Delay Flag"] = dd["Delay Flag"].map({True: "Delayed", False: "On Time"})
    dd["Route Efficiency Score"] = dd["Route Efficiency Score"].round(3)
    if "Factory → State Route" in dd.columns:
        dd["Factory → State Route"] = dd["Factory → State Route"].str.replace("→", "->")
    dd = dd.rename(columns={"Factory → State Route": "Route", "State/Province": "State",
                            "Gross Profit": "Profit ($)", "Shipping Lead Time": "Lead (d)",
                            "Route Efficiency Score": "Efficiency", "Order Year": "Year"})

    st.dataframe(dd, use_container_width=True, hide_index=True, height=520,
                 column_config={
                     "Sales":      st.column_config.NumberColumn("Sales ($)", format="$%.2f"),
                     "Profit ($)": st.column_config.NumberColumn("Profit ($)", format="$%.2f"),
                     "Cost":       st.column_config.NumberColumn("Cost ($)", format="$%.2f"),
                     "Efficiency": st.column_config.ProgressColumn("Efficiency", min_value=0, max_value=1, format="%.3f"),
                     "Lead (d)":   st.column_config.NumberColumn("Lead (d)", format="%d days"),
                 })

    # ── Export & CSV Download Options ─────────────────────────────────────────
    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">file_download</span>Export Filtered CSV Data</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-subtitle">Download exactly what you see filtered ({len(dv):,} rows) for spreadsheet analysis and reporting.</div>', unsafe_allow_html=True)
    
    col_dl1, col_dl2, col_dl3 = st.columns([2, 2, 2])
    year_suffix = f"_{st.session_state['quick_order_year']}" if st.session_state['quick_order_year'] != 'All' else "_all"
    
    with col_dl1:
        st.download_button(
            f"Download Filtered CSV ({len(dv):,} rows)",
            data=dv.to_csv(index=False),
            file_name=f"nassau_candy_orders{year_suffix}.csv",
            mime="text/csv",
            icon=":material/download:",
            use_container_width=True
        )
    with col_dl2:
        # Download Clean Summary CSV
        summary_cols = ["Order ID", "Order Date", "Ship Date", "Customer ID", "City", "State/Province", "Factory", "Sales", "Gross Profit", "Shipping Lead Time", "Delay Flag"]
        avail_summary = [c for c in summary_cols if c in dv.columns]
        st.download_button(
            "Download Summary CSV (Key Columns)",
            data=dv[avail_summary].to_csv(index=False),
            file_name=f"nassau_orders_summary{year_suffix}.csv",
            mime="text/csv",
            icon=":material/download:",
            use_container_width=True
        )
    with col_dl3:
        try:
            import io
            buf = io.BytesIO()
            dv.to_excel(buf, index=False, engine="openpyxl")
            buf.seek(0)
            st.download_button("Download Excel (.xlsx)", data=buf,
                               file_name=f"nassau_orders{year_suffix}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               icon=":material/download:",
                               use_container_width=True)
        except Exception:
            st.info("Install openpyxl for Excel export: `pip install openpyxl`")

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Single Order Deep Dive ────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">receipt_long</span>Single Order Dossier</div>', unsafe_allow_html=True)
    order_ids = sorted(df["Order ID"].unique())
    selected_order = st.selectbox("Select Order ID for Full Line-Item Breakdown",
                                  options=["— Select —"] + list(order_ids[:600]),
                                  label_visibility="collapsed")

    if selected_order != "— Select —":
        od = df[df["Order ID"] == selected_order].copy()
        if not od.empty:
            row = od.iloc[0]
            col_l, col_r = st.columns(2)
            delay_s = '<span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;margin-right:3px;">warning</span>Delayed' if row["Delay Flag"] else '<span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;margin-right:3px;">check_circle</span>On Time'
            delay_c = palette["danger"] if row["Delay Flag"] else palette["accent"]

            with col_l:
                st.markdown(f"""<div style="background:{card_bg};border:1px solid {card_border};
                    border-radius:14px;padding:20px;box-shadow:0 4px 16px rgba(0,0,0,{'0.04' if theme == 'light' else '0.2'});">
                    <div style="font-size:.74rem;color:{palette['primary']};font-weight:800;text-transform:uppercase;
                    letter-spacing:.08em;margin-bottom:12px;">Customer & Routing Summary</div>
                    <table style="width:100%;font-size:.84rem;color:{text_color};border-collapse:collapse;">
                        <tr><td style="color:{muted_color};padding:5px 0;">Order ID</td>
                            <td style="font-weight:700;">{row['Order ID']}</td></tr>
                        <tr><td style="color:{muted_color};padding:5px 0;">Customer ID</td><td>{row['Customer ID']}</td></tr>
                        <tr><td style="color:{muted_color};padding:5px 0;">Order Date</td><td>{str(row['Order Date'])[:10]}</td></tr>
                        <tr><td style="color:{muted_color};padding:5px 0;">Ship Date</td><td>{str(row['Ship Date'])[:10]}</td></tr>
                        <tr><td style="color:{muted_color};padding:5px 0;">Ship Mode</td><td>{row['Ship Mode']}</td></tr>
                        <tr><td style="color:{muted_color};padding:5px 0;">Destination</td>
                            <td>{row['City']}, {row['State/Province']}</td></tr>
                        <tr><td style="color:{muted_color};padding:5px 0;">Region</td><td>{row['Region']}</td></tr>
                    </table></div>""", unsafe_allow_html=True)

            with col_r:
                st.markdown(f"""<div style="background:{card_bg};border:1px solid {card_border};
                    border-radius:14px;padding:20px;box-shadow:0 4px 16px rgba(0,0,0,{'0.04' if theme == 'light' else '0.2'});">
                    <div style="font-size:.74rem;color:{palette['primary']};font-weight:800;text-transform:uppercase;
                    letter-spacing:.08em;margin-bottom:12px;">Factory Dispatch & Performance</div>
                    <table style="width:100%;font-size:.84rem;color:{text_color};border-collapse:collapse;">
                        <tr><td style="color:{muted_color};padding:5px 0;">Factory</td>
                            <td style="font-weight:700;">{row['Factory']}</td></tr>
                        <tr><td style="color:{muted_color};padding:5px 0;">Division</td><td>{row['Division']}</td></tr>
                        <tr><td style="color:{muted_color};padding:5px 0;">Lead Time</td>
                            <td><strong>{row['Shipping Lead Time']}</strong> days</td></tr>
                        <tr><td style="color:{muted_color};padding:5px 0;">Status</td>
                            <td style="color:{delay_c};font-weight:700;">{delay_s}</td></tr>
                        <tr><td style="color:{muted_color};padding:5px 0;">Route Efficiency</td>
                            <td>{row['Route Efficiency Score']:.3f}</td></tr>
                        <tr><td style="color:{muted_color};padding:5px 0;">Order Total Sales</td>
                            <td>${od['Sales'].sum():,.2f}</td></tr>
                        <tr><td style="color:{muted_color};padding:5px 0;">Order Total Profit</td>
                            <td>${od['Gross Profit'].sum():,.2f}</td></tr>
                    </table></div>""", unsafe_allow_html=True)

            st.markdown("<br><div class='section-header'><span class=\"material-symbols-rounded\" style=\"vertical-align:middle;margin-right:6px;\">inventory_2</span>Line Items in this Order</div>", unsafe_allow_html=True)
            st.dataframe(od[["Product Name", "Units", "Sales", "Gross Profit", "Cost"]],
                         use_container_width=True, hide_index=True,
                         column_config={
                             "Sales":        st.column_config.NumberColumn("Sales ($)", format="$%.2f"),
                             "Gross Profit": st.column_config.NumberColumn("Profit ($)", format="$%.2f"),
                             "Cost":         st.column_config.NumberColumn("Cost ($)", format="$%.2f"),
                         })

# ── Auto-run when executed as a Streamlit page ─────────────────────────────────
_df = st.session_state.get("df_filtered", None)
if _df is None:
    from src.utils import FEATURED_DATA_FILE, ensure_dirs
    ensure_dirs()
    _df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])

render(_df)
