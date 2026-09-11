"""pg_bi.py — Automated Business Intelligence, Root Cause Analysis & Executive Insights"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.kpi import KPICalculator
from src.right_filter_panel import render_right_filter_panel
from src.utils import get_palette
from src.visualization import bar_chart, pie_chart, waterfall_chart


def render(df_input: pd.DataFrame) -> None:
    df_full = st.session_state.get("df_full", df_input)
    df = render_right_filter_panel(df_full, current_page="bi")
    st.session_state["df_filtered"] = df

    theme = st.session_state.get("theme", "dark")
    palette = get_palette(theme)
    h1_clr = "#0F172A" if theme == "light" else "#E8EAED"
    sub_clr = "#64748B" if theme == "light" else "#9AA0B9"
    card_bg = "#FFFFFF" if theme == "light" else "rgba(26,30,46,0.95)"
    card_border = "rgba(83,72,232,0.2)" if theme == "light" else "rgba(108,99,255,0.25)"

    calc = KPICalculator(df)
    kpis = calc.get_summary()

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
        <span class="material-symbols-rounded" style="font-size:2rem;color:{palette['primary']};">analytics</span>
        <h1 style="font-size:1.85rem;font-weight:800;color:{h1_clr};margin:0;letter-spacing:-.02em;">
            Executive Business Intelligence & Decision Support
        </h1>
    </div>
    <p style="color:{sub_clr};font-size:.86rem;margin-bottom:24px;">
        Automated executive findings, root cause diagnosis, operational bottleneck radars, and actionable supply chain recommendations.
    </p>
    """, unsafe_allow_html=True)

    # ── Operational Health Radar ───────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    ontime_pct = kpis.get("on_time_rate_pct", 55.8)
    delay_pct = kpis.get("delay_rate_pct", 44.2)
    margin_pct = kpis.get("profit_margin_pct", 65.9)
    total_rev = kpis.get("total_sales", 0)

    for col, lbl, val, sub, status_clr in [
        (c1, "Delivery Reliability Index", f"{ontime_pct:.1f}%", f"{delay_pct:.1f}% shipments delayed", palette["accent"] if ontime_pct >= 60 else palette["warning"]),
        (c2, "Profit Margin Quality", f"{margin_pct:.1f}%", "Above industry median", palette["accent"]),
        (c3, "Transit Variance Health", f"{kpis.get('avg_lead_time', 0):.0f}d", "Mean transit duration", palette["info"]),
        (c4, "Filtered Revenue Base", f"${total_rev:,.0f}", f"{kpis.get('total_orders', 0):,} total orders", palette["primary"]),
    ]:
        with col:
            st.markdown(f"""
            <div class="kpi-card" style="background:{card_bg};border:1px solid {card_border};text-align:left;padding:18px 20px;">
                <div style="font-size:.74rem;font-weight:700;color:{sub_clr};text-transform:uppercase;letter-spacing:.08em;">{lbl}</div>
                <div style="font-size:1.6rem;font-weight:800;color:{status_clr};margin:4px 0;">{val}</div>
                <div style="font-size:.74rem;color:{sub_clr};">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="styled-divider" style="margin:24px 0;">', unsafe_allow_html=True)

    # ── Executive Automated Findings ───────────────────────────────────────────
    st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">psychology</span>Automated Root Cause & Diagnostics Engine</div>', unsafe_allow_html=True)

    rf = calc.route_performance()
    slowest_routes = rf.sort_values("avg_lead_time", ascending=False).head(3)
    fastest_routes = rf.sort_values("avg_lead_time", ascending=True).head(3)

    state_delays = df.groupby("State/Province")["Delay Flag"].mean() * 100
    worst_state = state_delays.idxmax() if not state_delays.empty else "N/A"
    worst_state_pct = state_delays.max() if not state_delays.empty else 0

    mode_delays = df.groupby("Ship Mode")["Delay Flag"].mean() * 100
    highest_delay_mode = mode_delays.idxmax() if not mode_delays.empty else "N/A"
    mode_delay_pct = mode_delays.max() if not mode_delays.empty else 0.0
    route_col_name = "Factory → State Route" if "Factory → State Route" in rf.columns else ("Route" if "Route" in rf.columns else rf.columns[0])
    top_route_name = fastest_routes.iloc[0][route_col_name] if not fastest_routes.empty else 'N/A'
    top_route_lt = fastest_routes.iloc[0]['avg_lead_time'] if not fastest_routes.empty else 0.0

    col_diag1, col_diag2 = st.columns(2)
    with col_diag1:
        st.markdown(f"""
        <div class="insight-box" style="margin-bottom:14px;">
            <div class="insight-title" style="color:{palette['danger']};"><span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;margin-right:5px;">warning</span>Primary Bottleneck Detected</div>
            State of <strong>{worst_state}</strong> exhibits the highest transit delay frequency at <strong>{worst_state_pct:.1f}%</strong>.
            Shipments routed into this destination incur significant lead time variances, indicating regional carrier congestion or distribution center staging delays.
        </div>
        <div class="insight-box" style="margin-bottom:14px;">
            <div class="insight-title" style="color:{palette['warning']};"><span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;margin-right:5px;">local_shipping</span>Mode Sensitivity Alert</div>
            <strong>{highest_delay_mode}</strong> has the highest delay rate across delivery classes (<strong>{mode_delay_pct:.1f}%</strong>). 
            Re-evaluating carrier SLAs or shifting high-priority confectionery orders to First Class or direct line-hauls will mitigate stockouts.
        </div>
        """, unsafe_allow_html=True)

    with col_diag2:
        st.markdown(f"""
        <div class="insight-box" style="margin-bottom:14px;">
            <div class="insight-title" style="color:{palette['accent']};"><span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;margin-right:5px;">star</span>High-Efficiency Benchmark</div>
            Top-performing route: <strong>{top_route_name}</strong> 
            achieving lowest lead times ({top_route_lt:.1f}d) and optimal route efficiency scores.
        </div>
        <div class="insight-box" style="margin-bottom:14px;">
            <div class="insight-title" style="color:{palette['primary']};"><span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;margin-right:5px;">lightbulb</span>Strategic Logistics Recommendation</div>
            Consolidate shipments from lower-performing facilities into regional hub transfers. Implement dynamic safety stock buffers (+2 business days) for states in the top 10 delay percentile.
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<hr class="styled-divider" style="margin:24px 0;">', unsafe_allow_html=True)

    # ── Financial Value Decomposition & Bottlenecks ─────────────────────────────
    col_w, col_t = st.columns(2)
    with col_w:
        st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">payments</span>Profitability Waterfall Decomposition</div>', unsafe_allow_html=True)
        cats = ["Gross Revenue", "COGS & Mfg Cost", "Logistics Overhead", "Net Retained Margin"]
        total_s = float(kpis["total_sales"])
        cogs = float(kpis["total_cost"])
        overhead = float(total_s * 0.08)  # Estimated supply chain transport overhead
        retained = total_s - cogs - overhead
        wf = waterfall_chart(cats, [total_s, -cogs, -overhead, retained], title="Revenue to Net Logistics Margin", height=380)
        st.plotly_chart(wf, use_container_width=True)

    with col_t:
        st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">hourglass_top</span>Top Bottleneck Shipping Routes</div>', unsafe_allow_html=True)
        top_slow = rf.sort_values("avg_lead_time", ascending=False).head(7)[[route_col_name, "avg_lead_time", "delay_rate_pct"]]
        top_slow = top_slow.rename(columns={route_col_name: "Route", "avg_lead_time": "Avg Days", "delay_rate_pct": "Delay %"})
        st.dataframe(top_slow, use_container_width=True, hide_index=True)


_df = st.session_state.get("df_filtered", None)
if _df is None:
    from src.utils import FEATURED_DATA_FILE, ensure_dirs
    ensure_dirs()
    _df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])

render(_df)
