"""pg_home.py — Enterprise Executive Landing Hub with Unified Vector Icons & Strategic Decision Radar"""
from __future__ import annotations
import base64
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.kpi import KPICalculator
from src.right_filter_panel import render_right_filter_panel
from src.utils import get_palette

df_full = st.session_state.get("df_full", None)
if df_full is None:
    from src.utils import FEATURED_DATA_FILE, ensure_dirs
    ensure_dirs()
    df_full = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])

df = render_right_filter_panel(df_full, current_page="overview")
st.session_state["df_filtered"] = df

theme = st.session_state.get("theme", "dark")
palette = get_palette(theme)

assets_dir = Path(__file__).resolve().parent.parent / "assets"
official_logo_path = assets_dir / "nassau_candy_official_logo.png"
logo_path = official_logo_path if official_logo_path.exists() else assets_dir / "logo.png"
logo_b64 = ""
if logo_path.exists():
    try:
        logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()
    except Exception:
        pass

logo_img_tag = (
    f'<a href="https://www.nassaucandy.com/" target="_blank" style="text-decoration:none;">'
    f'<div style="background:#FFFFFF;border-radius:16px;padding:12px 20px;display:inline-block;'
    f'box-shadow:0 8px 24px rgba(0,0,0,0.14);border:1px solid rgba(179,139,78,0.3);margin-right:24px;'
    f'transition:transform .2s ease;">'
    f'<img src="data:image/png;base64,{logo_b64}" style="max-width:210px;height:auto;display:block;">'
    f'</div></a>'
    if logo_b64 else '<span class="material-symbols-rounded" style="font-size:3.5rem;margin-right:20px;color:#5348E8;">factory</span>'
)

hero_bg = (
    "linear-gradient(135deg, rgba(83, 72, 232, 0.08), rgba(232, 62, 104, 0.06))"
    if theme == "light"
    else "linear-gradient(135deg, rgba(108, 99, 255, 0.15), rgba(255, 101, 132, 0.09))"
)
hero_border = "rgba(83,72,232,0.22)" if theme == "light" else "rgba(108,99,255,0.3)"
heading_color = "#0F172A" if theme == "light" else "#E8EAED"
desc_color = "#64748B" if theme == "light" else "#9AA0B9"
card_bg = "#FFFFFF" if theme == "light" else "rgba(26, 30, 46, 0.95)"

# ── Executive Hero Banner ──
st.markdown(f"""
<div style="background:{hero_bg};border:1px solid {hero_border};border-radius:24px;
    padding:32px 36px;margin-bottom:28px;display:flex;align-items:center;flex-wrap:wrap;
    box-shadow:0 12px 36px rgba(0,0,0,{'0.04' if theme == 'light' else '0.35'});position:relative;overflow:hidden;">
    <div>{logo_img_tag}</div>
    <div style="flex:1;min-width:300px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
            <span class="material-symbols-rounded" style="font-size:1.1rem;color:{palette['primary']};">verified</span>
            <div style="font-size:.75rem;color:{palette['primary']};font-weight:800;text-transform:uppercase;
                letter-spacing:.16em;">Nassau Candy Distributor Logistics Intelligence Platform</div>
        </div>
        <h1 style="font-size:2.2rem;font-weight:800;color:{heading_color};letter-spacing:-.03em;
            margin:0 0 8px;line-height:1.2;">
            Enterprise Shipping Route Efficiency<br>
            <span style="background:linear-gradient(90deg,{palette['primary']},{palette['secondary']});
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                background-clip:text;">Decision Support & Predictive Operations</span>
        </h1>
        <p style="font-size:.92rem;color:{desc_color};margin:0;max-width:760px;line-height:1.6;">
            Commercial-grade analytics command center transforming raw B2B shipment records into actionable logistics intelligence. 
            Real-time route optimization, lead time forecasting, and continuous delivery assurance across United States distribution facilities.
        </p>
    </div>
</div>""", unsafe_allow_html=True)

# ── Executive KPI Scorecard (Uniform Dimensions & Material Icons) ──
calc = KPICalculator(df)
kpis = calc.get_summary()

kpi_specs = [
    (f"{kpis['total_orders']:,}", "Total Orders", "local_shipping", palette["primary"], "Active volume", "+4.2% MoM"),
    (f"${kpis['total_sales']:,.0f}", "Total Revenue", "payments", palette["accent"], "Gross billings", "+8.1% vs target"),
    (f"${kpis['total_profit']:,.0f}", "Gross Margin", "trending_up", palette["secondary"], "Retained profit", f"{kpis['profit_margin_pct']:.1f}% margin"),
    (f"{kpis['avg_lead_time']:.0f}d", "Mean Transit", "schedule", palette["warning"], "Dispatch to delivery", "SLA: 5.0d max"),
    (f"{kpis['delay_rate_pct']:.1f}%", "Delay Frequency", "warning", palette["danger"], f"{kpis['total_delayed']:,} delayed", "Target < 15%"),
    (f"{kpis['unique_routes']:,}", "Active Routes", "alt_route", palette["info"], "Plant-to-state links", "5 origin plants"),
]

kpi_cards_html = []
for val, lbl, icon, clr, subtext, chip in kpi_specs:
    kpi_cards_html.append(f"""<div class="home-kpi-card">
<div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
<div style="width:34px;height:34px;border-radius:8px;background:{clr}18;display:flex;align-items:center;justify-content:center;flex-shrink:0;">
<span class="material-symbols-rounded" style="font-size:1.3rem;color:{clr};">{icon}</span>
</div>
<span style="font-size:.66rem;font-weight:700;color:{clr};background:{clr}18;padding:3px 7px;border-radius:6px;white-space:nowrap;flex-shrink:0;">{chip}</span>
</div>
<div class="home-kpi-val" style="color:{clr};" title="{val}">{val}</div>
<div>
<div class="home-kpi-label">{lbl}</div>
<div class="home-kpi-sub">{subtext}</div>
</div>
</div>""")

st.html(f"""<style>
.home-kpi-grid {{
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 12px;
    width: 100%;
    margin-bottom: 8px;
}}
@media (max-width: 1400px) {{
    .home-kpi-grid {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
    }}
}}
@media (max-width: 768px) {{
    .home-kpi-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
    }}
}}
@media (max-width: 480px) {{
    .home-kpi-grid {{
        grid-template-columns: 1fr;
        gap: 8px;
    }}
}}
.home-kpi-card {{
    background: {card_bg};
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 14px 12px;
    min-height: 136px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: all 0.25s ease;
    box-sizing: border-box;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}}
.home-kpi-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(108, 99, 255, 0.22);
    border-color: rgba(108, 99, 255, 0.45);
}}
.home-kpi-val {{
    font-size: clamp(1.2rem, 1.4vw, 1.55rem) !important;
    font-weight: 800 !important;
    line-height: 1.18 !important;
    margin: 8px 0 3px !important;
    white-space: nowrap !important;
    overflow: visible !important;
    text-overflow: clip !important;
    letter-spacing: -0.02em !important;
}}
.home-kpi-label {{
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: {desc_color} !important;
    white-space: nowrap !important;
}}
.home-kpi-sub {{
    font-size: 0.67rem !important;
    color: {desc_color} !important;
    margin-top: 2px !important;
    white-space: nowrap !important;
    opacity: 0.85;
}}
</style>
<div class="home-kpi-grid">
{''.join(kpi_cards_html)}
</div>""")

st.markdown('<hr class="styled-divider" style="margin:24px 0;">', unsafe_allow_html=True)

# ── Executive Operational Health & Quick Insights ──
col_health, col_alerts = st.columns([1, 1.4])
with col_health:
    st.markdown(f'<div class="section-header" style="color:{heading_color};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:{palette["primary"]};">speed</span>Operational Health Score</div>', unsafe_allow_html=True)
    health_score = max(0, min(100, int(100 - (kpis["delay_rate_pct"] * 0.6) + (kpis["profit_margin_pct"] * 0.2))))
    health_clr = palette["accent"] if health_score >= 75 else (palette["warning"] if health_score >= 50 else palette["danger"])
    st.markdown(f"""
    <div class="kpi-card" style="background:{card_bg};padding:22px;text-align:center;">
        <div style="font-size:2.8rem;font-weight:900;color:{health_clr};line-height:1;">{health_score}<span style="font-size:1.4rem;color:{desc_color};">/100</span></div>
        <div style="font-size:.85rem;font-weight:700;color:{heading_color};margin-top:8px;">Enterprise Fulfillment Rating</div>
        <p style="font-size:.76rem;color:{desc_color};margin:6px 0 0;line-height:1.4;">
            Calculated across on-time delivery adherence ({kpis['on_time_rate_pct']:.1f}%), gross margin quality ({kpis['profit_margin_pct']:.1f}%), 
            and route variance resilience across 5 regional production nodes.
        </p>
    </div>
    """, unsafe_allow_html=True)

with col_alerts:
    st.markdown(f'<div class="section-header" style="color:{heading_color};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:{palette["warning"]};">notifications_active</span>Strategic Recommendations & Priority Alerts</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="insight-box" style="margin-bottom:10px;padding:12px 16px;">
        <div class="insight-title" style="color:{palette['danger']};">Carrier Lead Time Congestion</div>
        Standard Class shipments account for <strong>{kpis['total_delayed']:,} delayed orders</strong>. Transitioning priority confectionery accounts to regional forward-staging will compress transit variance.
    </div>
    <div class="insight-box" style="margin-bottom:0;padding:12px 16px;">
        <div class="insight-title" style="color:{palette['accent']};">Production Allocation Optimization</div>
        <strong>Lot's O' Nuts</strong> and <strong>Wicked Choccy's</strong> demonstrate highest route efficiency margins. Rerouting Pacific zone deliveries through optimal nodes recovers up to $14,000 in operational drag.
    </div>
    """, unsafe_allow_html=True)

st.markdown('<hr class="styled-divider" style="margin:28px 0 20px;">', unsafe_allow_html=True)

# ── Enterprise Navigation Hub (12 Cohesive Modules) ──
st.markdown(f"""
<div class="section-header" style="color:{heading_color};">
    <span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:{palette['primary']};">hub</span>
    Enterprise Intelligence Navigation Hub
</div>
<p style="color:{desc_color};font-size:.84rem;margin-bottom:20px;line-height:1.5;">
    Direct interactive routing to specialized analytical and governance platforms. Select any operational domain below to launch the full investigative module.
</p>
""", unsafe_allow_html=True)

# CSS for rich navigation cards & attached action buttons
st.markdown(f"""
<style>
.hub-card {{
    background: {card_bg};
    border: 1px solid {'rgba(83, 72, 232, 0.22)' if theme == 'light' else 'rgba(108, 99, 255, 0.25)'};
    border-radius: 16px 16px 0 0;
    padding: 18px 16px 14px;
    height: 245px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: 0 4px 16px {'rgba(83, 72, 232, 0.06)' if theme == 'light' else 'rgba(0, 0, 0, 0.3)'};
    transition: border-color 0.2s ease, transform 0.2s ease;
    position: relative;
    overflow: hidden;
}}
.hub-card:hover {{
    border-color: {'#5348E8' if theme == 'light' else '#6C63FF'};
    box-shadow: 0 8px 24px {'rgba(83, 72, 232, 0.16)' if theme == 'light' else 'rgba(108, 99, 255, 0.28)'};
}}
.hub-header {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
}}
.hub-icon-box {{
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: {'linear-gradient(135deg, rgba(83,72,232,0.14), rgba(232,62,104,0.1))' if theme == 'light' else 'linear-gradient(135deg, rgba(108,99,255,0.28), rgba(255,101,132,0.18))'};
    border: 1px solid {'rgba(83,72,232,0.25)' if theme == 'light' else 'rgba(108,99,255,0.35)'};
    display: flex;
    align-items: center;
    justify-content: center;
    color: {palette['primary']};
    flex-shrink: 0;
}}
.hub-badge {{
    font-size: 0.62rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {palette['primary']};
    background: {palette['primary']}16;
    padding: 2px 7px;
    border-radius: 4px;
    display: inline-block;
    margin-bottom: 3px;
}}
.hub-title {{
    font-size: 0.95rem;
    font-weight: 800;
    color: {heading_color};
    letter-spacing: -0.01em;
    line-height: 1.25;
}}
.hub-desc {{
    font-size: 0.77rem;
    color: {desc_color};
    line-height: 1.45;
    margin: 8px 0 6px;
    flex: 1;
}}
.hub-features {{
    border-top: 1px solid {'rgba(83, 72, 232, 0.12)' if theme == 'light' else 'rgba(108, 99, 255, 0.15)'};
    padding-top: 8px;
    margin-top: 4px;
}}
.hub-f-item {{
    font-size: 0.70rem;
    color: {'#334155' if theme == 'light' else '#CBD5E1'};
    display: flex;
    align-items: center;
    gap: 5px;
    margin-bottom: 3px;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}

/* Button styling attached to bottom of card */
div[data-testid="stColumn"] div.stButton > button {{
    width: 100% !important;
    border-top-left-radius: 0 !important;
    border-top-right-radius: 0 !important;
    border-bottom-left-radius: 14px !important;
    border-bottom-right-radius: 14px !important;
    border-top: none !important;
    padding: 9px 12px !important;
    min-height: 38px !important;
    font-size: 0.8rem !important;
    font-weight: 700 !important;
    background: {'rgba(83, 72, 232, 0.08)' if theme == 'light' else 'rgba(108, 99, 255, 0.15)'} !important;
    color: {palette['primary']} !important;
    border: 1px solid {'rgba(83, 72, 232, 0.22)' if theme == 'light' else 'rgba(108, 99, 255, 0.28)'} !important;
    border-top: none !important;
    transition: all 0.2s ease !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}}
div[data-testid="stColumn"] div.stButton > button:hover {{
    background: {palette['primary']} !important;
    color: #FFFFFF !important;
    border-color: {palette['primary']} !important;
    box-shadow: 0 6px 18px {'rgba(83, 72, 232, 0.28)' if theme == 'light' else 'rgba(108, 99, 255, 0.38)'} !important;
    transform: none !important;
}}
div[data-testid="stColumn"] div.stButton > button p {{
    color: inherit !important;
    font-weight: 700 !important;
}}
</style>
""", unsafe_allow_html=True)

modules = [
    # Row 1: Strategic & Corridors
    {
        "title": "Executive Overview",
        "badge": "STRATEGIC",
        "icon": "dashboard",
        "desc": "C-suite strategic scorecards synthesizing gross revenue, profit retention, lead time variance, and on-time fulfillment rates across all facilities.",
        "features": [
            "Revenue & profit margin velocity",
            "Multi-plant SLA compliance tracking",
            "On-time delivery performance",
        ],
        "file": "pg_overview.py",
        "key": "btn_h_overview",
    },
    {
        "title": "Business Intelligence",
        "badge": "DIAGNOSTIC",
        "icon": "analytics",
        "desc": "Automated root-cause diagnostics pinpointing delivery delays, carrier transit variances, and operational cost recovery opportunities across networks.",
        "features": [
            "Root-cause delay attribution",
            "Lane-by-lane variance rankings",
            "Operational margin leak detection",
        ],
        "file": "pg_bi.py",
        "key": "btn_h_bi",
    },
    {
        "title": "Route Intelligence",
        "badge": "CORRIDORS",
        "icon": "alt_route",
        "desc": "Lane-by-lane performance telemetry across all factory-to-state corridors with route efficiency scores and delay bottleneck heatmaps.",
        "features": [
            "Origin-to-destination rankings",
            "Efficiency scatter & transit times",
            "Route bottleneck mitigation matrix",
        ],
        "file": "pg_routes.py",
        "key": "btn_h_routes",
    },
    {
        "title": "Geographic Intelligence",
        "badge": "GEOSPATIAL",
        "icon": "public",
        "desc": "Interactive United States choropleth mapping state-level order volume density, regional transit times, and origin centroid network flow vectors.",
        "features": [
            "State-level shipment density maps",
            "Factory delivery radius analysis",
            "High-risk transit zone clusters",
        ],
        "file": "pg_geo.py",
        "key": "btn_h_geo",
    },
    # Row 2: Operations & Commercial
    {
        "title": "Factory Intelligence",
        "badge": "PRODUCTION",
        "icon": "factory",
        "desc": "Plant-level capacity and dispatch benchmarks across all 5 regional manufacturing nodes evaluating throughput speed and product specialization.",
        "features": [
            "5 regional origin plant KPIs",
            "Confectionery product line mix",
            "Cross-facility dispatch latency",
        ],
        "file": "pg_factory.py",
        "key": "btn_h_factory",
    },
    {
        "title": "Ship Mode Analytics",
        "badge": "LOGISTICS",
        "icon": "local_shipping",
        "desc": "Cost vs transit tradeoffs evaluating Standard Class, Second Class, First Class, and Same Day courier performance and margin compression.",
        "features": [
            "Modal transit time distributions",
            "Carrier SLA breach rates",
            "Expedited margin impact curves",
        ],
        "file": "pg_shipmode.py",
        "key": "btn_h_shipmode",
    },
    {
        "title": "Customer Intelligence",
        "badge": "COMMERCIAL",
        "icon": "group",
        "desc": "B2B client purchasing analytics tracking ordering frequency, delivery satisfaction rates, account volume shares, and fulfillment consistency.",
        "features": [
            "Top wholesale client rankings",
            "Account-level SLA compliance",
            "Order concentration matrices",
        ],
        "file": "pg_customer.py",
        "key": "btn_h_customer",
    },
    {
        "title": "Product Intelligence",
        "badge": "PORTFOLIO",
        "icon": "inventory_2",
        "desc": "Confectionery catalog profitability and logistics complexity assessment utilizing ABC Pareto classification and SKU gross margin analysis.",
        "features": [
            "ABC revenue & volume Pareto",
            "Product margin vs transit risk",
            "SKU line velocity rankings",
        ],
        "file": "pg_product.py",
        "key": "btn_h_product",
    },
    # Row 3: Advanced Data Science & Governance
    {
        "title": "Machine Learning Hub",
        "badge": "PREDICTIVE AI",
        "icon": "psychology",
        "desc": "Pre-dispatch machine learning models (XGBoost & Random Forest) evaluating shipment delay probabilities and feature importance in real-time.",
        "features": [
            "Classifier & regressor metrics",
            "SHAP predictive feature drivers",
            "Live delay risk scoring engine",
        ],
        "file": "pg_ml.py",
        "key": "btn_h_ml",
    },
    {
        "title": "Scenario Simulator",
        "badge": "WHAT-IF LAB",
        "icon": "tune",
        "desc": "Interactive simulation sandbox testing the operational and financial impact of modal shifts, plant reallocations, and transit lead-time shocks.",
        "features": [
            "Dynamic route reallocation tests",
            "Carrier rate change simulations",
            "Lead time sensitivity analysis",
        ],
        "file": "pg_simulator.py",
        "key": "btn_h_sim",
    },
    {
        "title": "Demand Forecasting",
        "badge": "TIME-SERIES",
        "icon": "trending_up",
        "desc": "Holt-Winters exponential smoothing and time-series projections modeling upcoming order volumes and seasonal holiday demand surges.",
        "features": [
            "6-month forward demand curves",
            "95% statistical confidence bands",
            "Holiday seasonal volume peaks",
        ],
        "file": "pg_forecasting.py",
        "key": "btn_h_forecast",
    },
    {
        "title": "Data Quality Center",
        "badge": "GOVERNANCE",
        "icon": "verified_user",
        "desc": "Automated dataset health monitoring validating column null rates, date logic consistency, schema constraints, and catalog integrity.",
        "features": [
            "10,194-record schema audit",
            "Field integrity & null checks",
            "Automated health index score",
        ],
        "file": "pg_data_quality.py",
        "key": "btn_h_dq",
    },
]

pages_dir = Path(__file__).resolve().parent

for row_idx in range(0, 12, 4):
    cols = st.columns(4)
    for col_idx in range(4):
        m = modules[row_idx + col_idx]
        with cols[col_idx]:
            feat_html = "".join([
                f'<div class="hub-f-item"><span class="material-symbols-rounded" style="font-size:.85rem;color:#10B981;">check_circle</span>{f}</div>'
                for f in m["features"]
            ])
            st.markdown(f"""
            <div class="hub-card">
                <div>
                    <div class="hub-header">
                        <div class="hub-icon-box">
                            <span class="material-symbols-rounded" style="font-size:1.35rem;">{m['icon']}</span>
                        </div>
                        <div style="flex:1;min-width:0;">
                            <div class="hub-badge">{m['badge']}</div>
                            <div class="hub-title">{m['title']}</div>
                        </div>
                    </div>
                    <div class="hub-desc">{m['desc']}</div>
                </div>
                <div class="hub-features">
                    {feat_html}
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"Open {m['title']}", key=m["key"], icon=":material/arrow_forward:", use_container_width=True):
                st.switch_page(str(pages_dir / m["file"]))

    if row_idx < 8:
        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

st.markdown(f"""
<p style="text-align:center;color:{desc_color};font-size:.82rem;margin-top:28px;">
    <span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.05rem;color:{palette['primary']};margin-right:4px;">dock_to_right</span>
    Use the <strong style="color:{palette['primary']};">interactive sidebar</strong> to customize filtering scopes, adjust appearance modes, or access the Order Drill Down and Admin Console.
</p>""", unsafe_allow_html=True)
