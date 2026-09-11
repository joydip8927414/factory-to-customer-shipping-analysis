"""pg_routes.py — Route Efficiency Page"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.kpi import KPICalculator
from src.right_filter_panel import render_right_filter_panel
from src.route_analysis import RouteAnalyzer
from src.utils import FACTORY_COLOURS, PALETTE, get_palette
from src.visualization import bar_chart, route_leaderboard_chart, scatter_chart


def render(df_input: pd.DataFrame) -> None:
    df_full = st.session_state.get("df_full", df_input)
    df = render_right_filter_panel(df_full, current_page="routes")
    st.session_state["df_filtered"] = df

    analyzer = RouteAnalyzer(df)
    calc = KPICalculator(df)
    theme = st.session_state.get("theme", "dark")
    h1_clr = "#0F172A" if theme == "light" else "#E8EAED"
    sub_clr = "#64748B" if theme == "light" else "#9AA0B9"

    palette = get_palette(theme)

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
        <span class="material-symbols-rounded" style="font-size:2rem;color:{palette['primary']};">alt_route</span>
        <h1 style="font-size:1.85rem;font-weight:800;color:{h1_clr};margin:0;letter-spacing:-.02em;">
            Route Intelligence & Performance Leaderboard
        </h1>
    </div>
    <p style="color:{sub_clr};font-size:.88rem;margin-bottom:24px;">
        Origin Plant → Customer State shipping corridor efficiency, transit bottleneck detection, and consistency scoring.
    </p>""", unsafe_allow_html=True)

    route_perf = calc.route_performance()

    # ── Route KPIs ─────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    items = [
        (c1, f"{df['Factory \u2192 State Route'].nunique():,}", "Unique Active Routes",       "#6C63FF"),
        (c2, f"{route_perf['avg_efficiency_score'].mean():.3f}", "Avg Efficiency Index",     "#43E97B"),
        (c3, f"{route_perf['delay_rate_pct'].mean():.1f}%",      "Route Delay Frequency",     "#FC5C7D"),
        (c4, f"{route_perf['avg_lead_time'].mean():.0f}d",       "Mean Corridor Lead Time",   "#F7B731"),
    ]
    for col, val, lbl, clr in items:
        with col:
            st.markdown(f'<div class="kpi-card"><div class="kpi-value" style="color:{clr};">{val}</div>'
                        f'<div class="kpi-label">{lbl}</div></div>', unsafe_allow_html=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Leaderboard Tabs ───────────────────────────────────────────────────────
    st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:{palette["accent"]};">leaderboard</span>Route Efficiency Leaderboard</div>', unsafe_allow_html=True)
    t1, t2, t3, t4 = st.tabs(["Top 10 Benchmark Routes", "Top 10 High-Delay Corridors", "Most Consistent (Low CV)", "Most Variable (High Risk)"])

    with t1:
        top10 = analyzer.top_routes(10)
        col_l, col_r = st.columns([3, 2])
        with col_l:
            st.plotly_chart(route_leaderboard_chart(top10, title="Top 10 Most Efficient Routes"),
                            use_container_width=True)
        with col_r:
            d = top10[["route","shipments","avg_lead_time","delay_rate_pct","avg_efficiency_score","rank"]].copy()
            d["route"] = d["route"].str.replace("\u2192", "->")
            st.dataframe(d.rename(columns={"route":"Route","shipments":"Ships","avg_lead_time":"Lead",
                                           "delay_rate_pct":"Delay%","avg_efficiency_score":"Score","rank":"Rank"}),
                         use_container_width=True, hide_index=True, height=430)

    with t2:
        worst10 = analyzer.worst_routes(10)
        col_l, col_r = st.columns([3, 2])
        with col_l:
            st.plotly_chart(route_leaderboard_chart(worst10, title="Top 10 Worst Routes", ascending=True),
                            use_container_width=True)
        with col_r:
            d = worst10[["route","shipments","avg_lead_time","delay_rate_pct","avg_efficiency_score"]].copy()
            d["route"] = d["route"].str.replace("\u2192", "->")
            st.dataframe(d.rename(columns={"route":"Route","shipments":"Ships","avg_lead_time":"Lead",
                                           "delay_rate_pct":"Delay%","avg_efficiency_score":"Score"}),
                         use_container_width=True, hide_index=True, height=430)

    with t3:
        cons = analyzer.most_consistent_routes(10, min_shipments=5)
        cons_d = cons.copy(); cons_d["route"] = cons_d["route"].str.replace("\u2192", "->")
        st.plotly_chart(bar_chart(cons_d, x="lead_time_cv", y="route", orientation="h",
                                  title="Most Consistent Routes (Lowest Lead Time CV)", height=430),
                        use_container_width=True)

    with t4:
        var = analyzer.most_variable_routes(10, min_shipments=5)
        var_d = var.copy(); var_d["route"] = var_d["route"].str.replace("\u2192", "->")
        st.plotly_chart(bar_chart(var_d, x="lead_time_cv", y="route", orientation="h",
                                  title="Most Variable Routes (Highest Lead Time CV)", height=430),
                        use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Scatter: Lead Time vs Delay Rate ───────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:#6C63FF;">scatter_plot</span>Route Efficiency Scatter</div>', unsafe_allow_html=True)
    all_routes = analyzer.route_summary("state")
    all_routes["route_display"] = all_routes["route"].str.replace("\u2192", "->")
    st.plotly_chart(scatter_chart(all_routes, x="avg_lead_time", y="delay_rate_pct",
                                  color="Factory", size="shipments",
                                  hover_data=["route_display","shipments","avg_efficiency_score"],
                                  color_map=FACTORY_COLOURS,
                                  title="Route Lead Time vs Delay Rate (bubble = volume)", height=480),
                    use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Bottlenecks ────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:#EF4444;">warning</span>Bottleneck Routes (Delay ≥ 50%)</div>', unsafe_allow_html=True)
    bn = analyzer.bottleneck_routes(delay_threshold=50.0, min_shipments=5)
    if bn.empty:
        st.success("No bottleneck routes detected with current filters.", icon=":material/check_circle:")
    else:
        st.warning(f"{len(bn)} bottleneck routes detected", icon=":material/warning:")
        bn_d = bn.head(15).copy(); bn_d["route"] = bn_d["route"].str.replace("\u2192", "->")
        st.plotly_chart(bar_chart(bn_d, x="delay_rate_pct", y="route", orientation="h",
                                  title="Bottleneck Routes (Delay %)", height=420),
                        use_container_width=True)
        st.dataframe(bn_d[["route","shipments","avg_lead_time","delay_rate_pct","avg_efficiency_score"]],
                     use_container_width=True, hide_index=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Region Routes ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">public</span>Region-Level Routes</div>', unsafe_allow_html=True)
    reg_routes = analyzer.route_summary("region")
    reg_routes["route_display"] = reg_routes["route"].str.replace("\u2192", "->")
    st.plotly_chart(bar_chart(reg_routes, x="avg_efficiency_score", y="route_display",
                              color="Factory", color_map=FACTORY_COLOURS, orientation="h",
                              title="Efficiency by Factory -> Region",
                              height=max(400, len(reg_routes)*28)),
                    use_container_width=True)

    csv = all_routes.assign(route=all_routes["route"].str.replace("\u2192","->")).to_csv(index=False)
    st.download_button("⬇️ Download Route Analysis", data=csv,
                       file_name="route_analysis.csv", mime="text/csv")

# ── Auto-run when executed as a Streamlit page ─────────────────────────────────
_df = st.session_state.get("df_filtered", None)
if _df is None:
    from src.utils import FEATURED_DATA_FILE, ensure_dirs
    ensure_dirs()
    _df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])

render(_df)
