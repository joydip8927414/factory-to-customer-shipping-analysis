"""pg_factory.py — Factory Analysis Page"""
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
from src.utils import FACTORY_COLOURS, FACTORY_PRODUCTS, PALETTE, get_palette
from src.visualization import bar_chart, box_chart, pie_chart


def render(df_input: pd.DataFrame) -> None:
    df_full = st.session_state.get("df_full", df_input)
    df = render_right_filter_panel(df_full, current_page="factory")
    st.session_state["df_filtered"] = df

    calc = KPICalculator(df)
    analyzer = RouteAnalyzer(df)
    theme = st.session_state.get("theme", "dark")
    h1_clr = "#0F172A" if theme == "light" else "#E8EAED"
    sub_clr = "#64748B" if theme == "light" else "#9AA0B9"

    palette = get_palette(theme)

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
        <span class="material-symbols-rounded" style="font-size:2rem;color:{palette['primary']};">factory</span>
        <h1 style="font-size:1.85rem;font-weight:800;color:{h1_clr};margin:0;letter-spacing:-.02em;">
            Factory Intelligence & Node Performance
        </h1>
    </div>
    <p style="color:{sub_clr};font-size:.88rem;margin-bottom:24px;">
        Per-plant dispatch volume, product specialization, delivery cycle consistency, and facility head-to-head metrics.
    </p>""", unsafe_allow_html=True)

    factory_perf = calc.factory_performance()

    # ── Factory Comparison Tabs ────────────────────────────────────────────────
    st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:{palette["accent"]};">compare_arrows</span>Production Node Comparisons</div>', unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["Volume & Sales", "Logistics Consistency", "Profitability Margins"])

    with t1:
        col_l, col_r = st.columns(2)
        with col_l:
            st.plotly_chart(bar_chart(factory_perf, x="Factory", y="shipments", color="Factory",
                                      color_map=FACTORY_COLOURS, title="Shipments by Factory", height=340),
                            use_container_width=True)
        with col_r:
            st.plotly_chart(bar_chart(factory_perf, x="Factory", y="total_sales", color="Factory",
                                      color_map=FACTORY_COLOURS, title="Total Sales ($)", height=340),
                            use_container_width=True)
    with t2:
        col_l, col_r = st.columns(2)
        with col_l:
            st.plotly_chart(bar_chart(factory_perf, x="Factory", y="avg_lead_time", color="Factory",
                                      color_map=FACTORY_COLOURS, title="Avg Lead Time (days)", height=340),
                            use_container_width=True)
        with col_r:
            st.plotly_chart(bar_chart(factory_perf, x="Factory", y="delay_rate_pct", color="Factory",
                                      color_map=FACTORY_COLOURS, title="Delay Rate %", height=340),
                            use_container_width=True)
    with t3:
        col_l, col_r = st.columns(2)
        with col_l:
            st.plotly_chart(bar_chart(factory_perf, x="Factory", y="total_profit", color="Factory",
                                      color_map=FACTORY_COLOURS, title="Total Profit ($)", height=340),
                            use_container_width=True)
        with col_r:
            st.plotly_chart(bar_chart(factory_perf, x="Factory", y="profit_margin_pct", color="Factory",
                                      color_map=FACTORY_COLOURS, title="Profit Margin %", height=340),
                            use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Efficiency Ranking ─────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">bolt</span>Route Efficiency Score by Factory</div>', unsafe_allow_html=True)
    eff = factory_perf.sort_values("avg_efficiency_score", ascending=True)
    fig = bar_chart(eff, x="avg_efficiency_score", y="Factory", color="Factory",
                    orientation="h", color_map=FACTORY_COLOURS,
                    title="Avg Route Efficiency Score (higher = better)", height=300)
    fig.update_xaxes(range=[0, 1])
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Per-Factory Deep Dive ──────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">search</span>Factory Deep Dive</div>', unsafe_allow_html=True)
    factories_avail = sorted(df["Factory"].unique())
    selected = st.selectbox("Select a Factory", options=factories_avail, index=0)

    df_f = df[df["Factory"] == selected].copy()
    fcolor = FACTORY_COLOURS.get(selected, PALETTE["primary"])

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="kpi-card" style="border-color:{fcolor}50;">'
                    f'<div class="kpi-value" style="color:{fcolor};">{len(df_f):,}</div>'
                    f'<div class="kpi-label">Total Shipments</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="kpi-card"><div class="kpi-value" style="color:#4FC3F7;">'
                    f'{df_f["Shipping Lead Time"].mean():.0f}d</div>'
                    f'<div class="kpi-label">Avg Lead Time</div></div>', unsafe_allow_html=True)
    with c3:
        dp = df_f["Delay Flag"].mean() * 100
        st.markdown(f'<div class="kpi-card"><div class="kpi-value" style="color:#FC5C7D;">'
                    f'{dp:.1f}%</div><div class="kpi-label">Delay Rate</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2)

    with col_l:
        prod_df = (df_f.groupby("Product Name")
                   .agg(shipments=("Row ID","count"), sales=("Sales","sum"))
                   .reset_index())
        st.plotly_chart(pie_chart(prod_df, names="Product Name", values="shipments",
                                  title=f"Product Mix — {selected}", hole=0.4, height=360),
                        use_container_width=True)
    with col_r:
        fr = analyzer.route_summary("state", df=df_f).head(10)
        fr["route_display"] = fr["route"].str.replace("\u2192", "->")
        st.plotly_chart(bar_chart(fr.sort_values("avg_efficiency_score"),
                                  x="avg_efficiency_score", y="route_display", orientation="h",
                                  title=f"Top Routes — {selected}", height=360),
                        use_container_width=True)

    st.plotly_chart(box_chart(df_f, x="Ship Mode", y="Shipping Lead Time", color="Ship Mode",
                              title=f"Lead Time by Ship Mode — {selected}",
                              points="outliers", height=340), use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Products Catalogue ─────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">inventory_2</span>Products by Factory</div>', unsafe_allow_html=True)
    prod_cols = st.columns(len(factories_avail))
    for col, factory in zip(prod_cols, factories_avail):
        color = FACTORY_COLOURS.get(factory, PALETTE["primary"])
        products = FACTORY_PRODUCTS.get(factory, [])
        with col:
            prods_html = "".join([f'<div style="font-size:.72rem;color:#9AA0B9;padding:2px 0;">• {p}</div>'
                                   for p in products])
            st.markdown(f"""<div style="background:rgba(30,33,48,.6);border:1px solid {color}40;
                border-radius:12px;padding:14px;">
                <div style="font-size:.78rem;font-weight:700;color:{color};margin-bottom:8px;">{factory}</div>
                {prods_html}</div>""", unsafe_allow_html=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Full Table ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">table_chart</span>Factory Performance Table</div>', unsafe_allow_html=True)
    disp = factory_perf[["Factory","shipments","total_units","total_sales","total_profit",
                          "avg_lead_time","delay_rate_pct","avg_efficiency_score"]].rename(columns={
        "shipments":"Shipments","total_units":"Units","total_sales":"Sales ($)","total_profit":"Profit ($)",
        "avg_lead_time":"Avg Lead","delay_rate_pct":"Delay %","avg_efficiency_score":"Efficiency"})
    st.dataframe(disp, use_container_width=True, hide_index=True)
    st.download_button("Download Factory Data", data=factory_perf.to_csv(index=False),
                       file_name="factory_analysis.csv", mime="text/csv", icon=":material/download:")

    best_f = factory_perf.loc[factory_perf["avg_efficiency_score"].idxmax()]
    worst_f = factory_perf.loc[factory_perf["avg_efficiency_score"].idxmin()]
    st.markdown(f"""<div class="insight-box">
        <div class="insight-title"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:5px;">lightbulb</span>Factory Insight</div>
        <strong>{best_f['Factory']}</strong> is top performer (efficiency {best_f['avg_efficiency_score']:.3f},
        delay {best_f['delay_rate_pct']:.1f}%). <strong>{worst_f['Factory']}</strong> needs improvement
        (efficiency {worst_f['avg_efficiency_score']:.3f}, delay {worst_f['delay_rate_pct']:.1f}%).
    </div>""", unsafe_allow_html=True)

# ── Auto-run when executed as a Streamlit page ─────────────────────────────────
_df = st.session_state.get("df_filtered", None)
if _df is None:
    from src.utils import FEATURED_DATA_FILE, ensure_dirs
    ensure_dirs()
    _df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])

render(_df)
