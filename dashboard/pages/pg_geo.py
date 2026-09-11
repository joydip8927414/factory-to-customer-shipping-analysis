"""pg_geo.py — Geographic Analysis Page"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.geographic_analysis import GeoAnalyzer
from src.right_filter_panel import render_right_filter_panel
from src.utils import PALETTE, REGION_COLOURS, get_palette
from src.visualization import bar_chart, choropleth_map, pie_chart, scattergeo_map


def render(df_input: pd.DataFrame) -> None:
    df_full = st.session_state.get("df_full", df_input)
    df = render_right_filter_panel(df_full, current_page="geo")
    st.session_state["df_filtered"] = df

    geo = GeoAnalyzer(df)
    theme = st.session_state.get("theme", "dark")
    h1_clr = "#0F172A" if theme == "light" else "#E8EAED"
    sub_clr = "#64748B" if theme == "light" else "#9AA0B9"

    palette = get_palette(theme)

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
        <span class="material-symbols-rounded" style="font-size:2rem;color:{palette['primary']};">public</span>
        <h1 style="font-size:1.85rem;font-weight:800;color:{h1_clr};margin:0;letter-spacing:-.02em;">
            Geographic Intelligence & Flow Network
        </h1>
    </div>
    <p style="color:{sub_clr};font-size:.88rem;margin-bottom:24px;">
        State-level delivery density, factory distribution radius, origin-destination flow lines, and regional risk profiling.
    </p>""", unsafe_allow_html=True)

    state_perf = geo.state_performance()
    region_perf = geo.region_performance()
    factory_cov = geo.factory_coverage()

    # ── Geo KPIs ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl, clr in [
        (c1, f"{len(state_perf):,}", "States Fulfilled", "#6C63FF"),
        (c2, f"{int(state_perf['shipments'].max()):,}", "Peak State Volume", "#43E97B"),
        (c3, f"{state_perf['delay_rate_pct'].mean():.1f}%", "Mean State Delay Rate", "#FC5C7D"),
        (c4, f"{int(factory_cov['states_served'].max()):,}", "Peak Plant Reach (States)", "#F7B731"),
    ]:
        with col:
            st.markdown(f'<div class="kpi-card"><div class="kpi-value" style="color:{clr};">{val}</div>'
                        f'<div class="kpi-label">{lbl}</div></div>', unsafe_allow_html=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Geographic Visualization Tabs ──────────────────────────────────────────
    st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:{palette["accent"]};">map</span>Geospatial Distribution & Supply Chain Flow</div>', unsafe_allow_html=True)
    tab_net, tab_flow = st.tabs(["Interactive Network Lines", "Sankey Flow (Factory → Region)"])
    with tab_net:
        route_lines = geo.route_line_data(min_shipments=3)
        st.plotly_chart(scattergeo_map(factory_df=factory_cov, route_df=route_lines,
                                       title="Nassau Candy Factory-to-Customer Shipping Network", height=540),
                        use_container_width=True)
    with tab_flow:
        from src.visualization import sankey_diagram
        st.plotly_chart(sankey_diagram(df, source_col="Factory", target_col="Region", value_col="Sales",
                                       title="Factory Dispatch Volume to Geographic Regions", height=500),
                        use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Choropleth Maps ────────────────────────────────────────────────────────
    st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:{palette["primary"]};">layers</span>US State Performance Choropleths</div>', unsafe_allow_html=True)
    us = state_perf[state_perf["state_abbrev"].notna()].copy()

    m1, m2, m3, m4 = st.tabs([":material/inventory_2: Volume", ":material/schedule: Lead Time", ":material/warning: Delay %", ":material/payments: Sales"])
    with m1:
        st.plotly_chart(choropleth_map(us, "state_abbrev", "shipments",
                                       title="Shipment Volume by State", colorscale="Plasma",
                                       hover_data=["state","shipments","delay_rate_pct"]),
                        use_container_width=True)
    with m2:
        st.plotly_chart(choropleth_map(us, "state_abbrev", "avg_lead_time",
                                       title="Average Lead Time by State (days)", colorscale="RdYlGn_r",
                                       hover_data=["state","avg_lead_time","shipments"]),
                        use_container_width=True)
    with m3:
        st.plotly_chart(choropleth_map(us, "state_abbrev", "delay_rate_pct",
                                       title="Delay Rate % by State", colorscale="Reds",
                                       hover_data=["state","delay_rate_pct","shipments"]),
                        use_container_width=True)
    with m4:
        st.plotly_chart(choropleth_map(us, "state_abbrev", "total_sales",
                                       title="Total Sales by State ($)", colorscale="Viridis",
                                       hover_data=["state","total_sales","shipments"]),
                        use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Regional Performance ───────────────────────────────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">public</span>Regional Shipments</div>', unsafe_allow_html=True)
        st.plotly_chart(bar_chart(region_perf, x="Region", y="shipments", color="Region",
                                  color_map=REGION_COLOURS, title="Shipments by Region", height=340),
                        use_container_width=True)
    with col_r:
        st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">warning</span>Regional Delay Rates</div>', unsafe_allow_html=True)
        st.plotly_chart(bar_chart(region_perf, x="Region", y="delay_rate_pct", color="Region",
                                  color_map=REGION_COLOURS, title="Delay Rate % by Region", height=340),
                        use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Top States & Bottlenecks ───────────────────────────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">inventory_2</span>Top 15 States by Volume</div>', unsafe_allow_html=True)
        st.plotly_chart(bar_chart(state_perf.head(15), x="shipments", y="state", orientation="h",
                                  title="Top 15 States by Shipment Volume", height=480),
                        use_container_width=True)
    with col_r:
        st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">warning</span>Bottleneck States (Delay ≥ 50%)</div>', unsafe_allow_html=True)
        bn = geo.bottleneck_states(delay_threshold=50.0, min_shipments=5)
        if bn.empty:
            st.success("No bottleneck states detected.", icon=":material/check_circle:")
        else:
            st.plotly_chart(bar_chart(bn.head(15), x="delay_rate_pct", y="state", orientation="h",
                                      title=f"Bottleneck States ({len(bn)} found)", height=480),
                            use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Factory Coverage ───────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">factory</span>Factory Geographic Coverage</div>', unsafe_allow_html=True)
    cov_d = factory_cov[["Factory","shipments","states_served","regions_served",
                          "avg_lead_time","delay_rate_pct"]].rename(columns={
        "shipments":"Shipments","states_served":"States","regions_served":"Regions",
        "avg_lead_time":"Avg Lead Time","delay_rate_pct":"Delay %"})
    st.dataframe(cov_d, use_container_width=True, hide_index=True)

    with st.expander("Full State Performance Table", icon=":material/table_chart:"):
        st.dataframe(state_perf[["state","shipments","total_sales","total_profit",
                                  "avg_lead_time","delay_rate_pct"]],
                     use_container_width=True, hide_index=True)
        st.download_button("Download State Data",
                           data=state_perf.to_csv(index=False),
                           file_name="state_performance.csv", mime="text/csv", icon=":material/download:")

    # ── Insights ───────────────────────────────────────────────────────────────
    top_state = state_perf.iloc[0]
    worst = state_perf.sort_values("delay_rate_pct", ascending=False).iloc[0]
    st.markdown(f"""<div class="insight-box">
        <div class="insight-title"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:5px;">lightbulb</span>Geographic Insight</div>
        <strong>{top_state['state']}</strong> is the highest-volume destination with {top_state['shipments']:,} shipments.
        Worst delay: <strong>{worst['state']}</strong> at {worst['delay_rate_pct']:.1f}%.
    </div>""", unsafe_allow_html=True)

# ── Auto-run when executed as a Streamlit page ─────────────────────────────────
_df = st.session_state.get("df_filtered", None)
if _df is None:
    from src.utils import FEATURED_DATA_FILE, ensure_dirs
    ensure_dirs()
    _df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])

render(_df)
