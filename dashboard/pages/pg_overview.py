"""
pg_overview.py  —  Overview Page (no set_page_config here)
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.kpi import KPICalculator
from src.utils import FACTORY_COLOURS, PALETTE, REGION_COLOURS, get_palette
from src.visualization import bar_chart, line_chart, pie_chart


from src.right_filter_panel import render_right_filter_panel


def render(df_input: pd.DataFrame) -> None:
    df_full = st.session_state.get("df_full", df_input)
    df = render_right_filter_panel(df_full, current_page="overview")
    st.session_state["df_filtered"] = df

    calc = KPICalculator(df)
    kpis = calc.get_summary()
    theme = st.session_state.get("theme", "dark")
    palette = get_palette(theme) if 'get_palette' in globals() else PALETTE
    h1_clr = "#0F172A" if theme == "light" else "#E8EAED"
    sub_clr = "#64748B" if theme == "light" else "#9AA0B9"

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
        <span class="material-symbols-rounded" style="font-size:2rem;color:{palette['primary']};">dashboard</span>
        <h1 style="font-size:1.85rem;font-weight:800;color:{h1_clr};margin:0;letter-spacing:-.02em;">
            Executive Overview Scorecards & Trends
        </h1>
    </div>
    <p style="color:{sub_clr};font-size:.86rem;margin-bottom:24px;">
        Cross-functional logistics KPIs, balance scorecards, profitability margins, and monthly order trends.
    </p>
    """, unsafe_allow_html=True)

    # ── Financial KPIs ────────────────────────────────────────────────────────
    st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:{palette["accent"]};">payments</span>Financial Performance</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    fin_cards = [
        (c1, f"${kpis['total_sales']:,.0f}",        "Total Sales",     "#43E97B", "linear-gradient(90deg,#43E97B,#38F9D7)"),
        (c2, f"${kpis['total_profit']:,.0f}",        "Total Profit",    "#6C63FF", "linear-gradient(90deg,#6C63FF,#A78BFA)"),
        (c3, f"${kpis['total_cost']:,.0f}",          "Total Cost",      "#FF6584", "linear-gradient(90deg,#FF6584,#FC5C7D)"),
        (c4, f"{kpis['profit_margin_pct']:.1f}%",    "Profit Margin",   "#F7B731", "linear-gradient(90deg,#F7B731,#FCA652)"),
        (c5, f"{kpis['total_units']:,}",             "Total Units",     "#4FC3F7", "linear-gradient(90deg,#4FC3F7,#29B6F6)"),
    ]
    for col, val, lbl, clr, grad in fin_cards:
        with col:
            st.markdown(f"""<div class="kpi-card">
                <div style="height:3px;background:{grad};border-radius:4px;margin:-20px -24px 14px;"></div>
                <div class="kpi-value" style="color:{clr};">{val}</div>
                <div class="kpi-label">{lbl}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Logistics KPIs ────────────────────────────────────────────────────────
    st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:{palette["primary"]};">local_shipping</span>Logistics Performance</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    log_cards = [
        (c1, f"{kpis['total_orders']:,}",          "Total Orders",      "#6C63FF", "linear-gradient(90deg,#6C63FF,#A78BFA)"),
        (c2, f"{kpis['avg_lead_time']:.0f}d",      "Avg Lead Time",     "#4FC3F7", "linear-gradient(90deg,#4FC3F7,#29B6F6)"),
        (c3, f"{kpis['median_lead_time']:.0f}d",   "Median Lead Time",  "#F7B731", "linear-gradient(90deg,#F7B731,#FCA652)"),
        (c4, f"{kpis['delay_rate_pct']:.1f}%",     "Delay Rate",        "#FC5C7D", "linear-gradient(90deg,#FC5C7D,#FF6584)"),
        (c5, f"{kpis['on_time_rate_pct']:.1f}%",   "On-Time Rate",      "#43E97B", "linear-gradient(90deg,#43E97B,#38F9D7)"),
    ]
    for col, val, lbl, clr, grad in log_cards:
        with col:
            st.markdown(f"""<div class="kpi-card">
                <div style="height:3px;background:{grad};border-radius:4px;margin:-20px -24px 14px;"></div>
                <div class="kpi-value" style="color:{clr};">{val}</div>
                <div class="kpi-label">{lbl}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Monthly Trend ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">trending_up</span>Monthly Shipment Trend</div>', unsafe_allow_html=True)
    monthly = calc.monthly_trend()
    monthly["period"] = (monthly["Shipment Year"].astype(str) + "-"
                         + monthly["Shipment Month"].astype(str).str.zfill(2))

    t1, t2, t3 = st.tabs([":material/inventory_2: Shipments", ":material/payments: Revenue", ":material/trending_up: Profit"])
    with t1:
        st.plotly_chart(line_chart(monthly, x="period", y="shipments",
                                   title="Monthly Shipment Volume", height=340),
                        use_container_width=True)
    with t2:
        st.plotly_chart(line_chart(monthly, x="period", y="sales",
                                   title="Monthly Sales ($)", height=340),
                        use_container_width=True)
    with t3:
        st.plotly_chart(line_chart(monthly, x="period", y="profit",
                                   title="Monthly Gross Profit ($)", height=340),
                        use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Division & Region ─────────────────────────────────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">category</span>Division Breakdown</div>', unsafe_allow_html=True)
        div_df = (df.groupby("Division")
                  .agg(shipments=("Row ID","count"), sales=("Sales","sum"))
                  .reset_index())
        st.plotly_chart(pie_chart(div_df, names="Division", values="shipments",
                                  title="Shipments by Division", hole=0.45, height=360),
                        use_container_width=True)
    with col_r:
        st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">public</span>Regional Breakdown</div>', unsafe_allow_html=True)
        reg_df = (df.groupby("Region")
                  .agg(shipments=("Row ID","count"))
                  .reset_index())
        st.plotly_chart(pie_chart(reg_df, names="Region", values="shipments",
                                  title="Shipments by Region", hole=0.45,
                                  color_map=REGION_COLOURS, height=360),
                        use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Top & Bottom Products ─────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">military_tech</span>Product Performance</div>', unsafe_allow_html=True)
    tab_top, tab_bot = st.tabs([":material/star: Top 10 Products", ":material/warning: Bottom 10 Products"])
    with tab_top:
        top10 = calc.top_products(n=10, metric="sales")
        st.plotly_chart(bar_chart(top10, x="sales", y="Product Name", color="Factory",
                                  title="Top 10 Products by Sales", orientation="h",
                                  color_map=FACTORY_COLOURS, height=420),
                        use_container_width=True)
    with tab_bot:
        bot10 = calc.bottom_products(n=10, metric="sales")
        st.plotly_chart(bar_chart(bot10, x="sales", y="Product Name", color="Factory",
                                  title="Bottom 10 Products by Sales", orientation="h",
                                  color_map=FACTORY_COLOURS, height=420),
                        use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Factory Table ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:#5348E8;">factory</span>Factory Performance Summary</div>', unsafe_allow_html=True)
    fdf = calc.factory_performance()
    disp = fdf[["Factory","shipments","total_sales","total_profit",
                "avg_lead_time","delay_rate_pct","avg_efficiency_score"]].rename(columns={
        "shipments":"Shipments","total_sales":"Sales ($)","total_profit":"Profit ($)",
        "avg_lead_time":"Avg Lead Time","delay_rate_pct":"Delay %",
        "avg_efficiency_score":"Efficiency",
    })
    st.dataframe(disp, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False)
    st.download_button("Download Filtered Dataset", icon=":material/download:", data=csv,
                       file_name="nassau_filtered.csv", mime="text/csv")

    # ── Insights ───────────────────────────────────────────────────────────────
    best_f = fdf.loc[fdf["avg_efficiency_score"].idxmax(), "Factory"]
    st.markdown(f"""
    <div class="insight-box">
        <div class="insight-title"><span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;color:#10B981;margin-right:4px;">factory</span>Best Performing Factory</div>
        <strong>{best_f}</strong> achieves the highest Route Efficiency Score.
    </div>
    <div class="insight-box">
        <div class="insight-title"><span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;color:#EF4444;margin-right:4px;">warning</span>Overall Delay Rate</div>
        {kpis['delay_rate_pct']:.1f}% of shipments are delayed —
        <strong>{kpis['total_delayed']:,} shipments</strong> require attention.
    </div>
    <div class="insight-box">
        <div class="insight-title"><span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;color:#6C63FF;margin-right:4px;">payments</span>Profit Efficiency</div>
        Overall margin: <strong>{kpis['profit_margin_pct']:.1f}%</strong>
        on {kpis['total_orders']:,} orders.
    </div>""", unsafe_allow_html=True)

# ── Auto-run when executed as a Streamlit page ─────────────────────────────────
_df = st.session_state.get("df_filtered", None)
if _df is None:
    from src.utils import FEATURED_DATA_FILE, ensure_dirs
    ensure_dirs()
    _df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])

render(_df)
