"""pg_shipmode.py — Ship Mode Analysis Page"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.right_filter_panel import render_right_filter_panel
from src.ship_mode_analysis import ShipModeAnalyzer
from src.utils import PALETTE, SHIP_MODE_COLOURS, get_palette
from src.visualization import bar_chart, box_chart, line_chart, pie_chart, scatter_chart


def render(df_input: pd.DataFrame) -> None:
    df_full = st.session_state.get("df_full", df_input)
    df = render_right_filter_panel(df_full, current_page="shipmode")
    st.session_state["df_filtered"] = df

    analyzer = ShipModeAnalyzer(df)
    theme = st.session_state.get("theme", "dark")
    h1_clr = "#0F172A" if theme == "light" else "#E8EAED"
    sub_clr = "#64748B" if theme == "light" else "#9AA0B9"

    palette = get_palette(theme)

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
        <span class="material-symbols-rounded" style="font-size:2rem;color:{palette['primary']};">local_shipping</span>
        <h1 style="font-size:1.85rem;font-weight:800;color:{h1_clr};margin:0;letter-spacing:-.02em;">
            Ship Mode Intelligence & Trade-Off Analytics
        </h1>
    </div>
    <p style="color:{sub_clr};font-size:.86rem;margin-bottom:24px;">
        Comparative service level benchmarks across Standard, Second, First Class, and Same Day logistics modes.
    </p>""", unsafe_allow_html=True)

    summary = analyzer.mode_summary()

    # ── Mode KPI cards ────────────────────────────────────────────────────────
    cols = st.columns(len(summary))
    for col, (_, row) in zip(cols, summary.iterrows()):
        color = SHIP_MODE_COLOURS.get(row["Ship Mode"], PALETTE["primary"])
        with col:
            st.markdown(f"""<div class="kpi-card" style="border-color:{color}40;">
                <div style="font-size:.85rem;font-weight:700;color:{color};margin-bottom:8px;">{row['Ship Mode']}</div>
                <div class="kpi-value" style="font-size:1.35rem;">{row['shipments']:,}</div>
                <div class="kpi-label">Shipments</div>
                <div style="margin-top:8px;font-size:.75rem;color:#9AA0B9;">
                    Delay: <span style="color:#FC5C7D;font-weight:600;">{row['delay_rate_pct']:.1f}%</span> |
                    Lead: <span style="color:#4FC3F7;font-weight:600;">{row['avg_lead_time']:.0f}d</span>
                </div>
            </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Volume & Sales ────────────────────────────────────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(pie_chart(summary, names="Ship Mode", values="shipments",
                                  title="Shipment Share by Mode", color_map=SHIP_MODE_COLOURS,
                                  hole=0.4, height=360), use_container_width=True)
    with col_r:
        st.plotly_chart(bar_chart(summary, x="Ship Mode", y="total_sales", color="Ship Mode",
                                  color_map=SHIP_MODE_COLOURS, title="Total Sales by Mode ($)",
                                  height=360), use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Lead Time Distribution ────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">schedule</span>Lead Time Distribution</div>', unsafe_allow_html=True)
    lt_dist = analyzer.lead_time_distribution()
    st.plotly_chart(box_chart(lt_dist, x="Ship Mode", y="Shipping Lead Time", color="Ship Mode",
                              color_map=SHIP_MODE_COLOURS,
                              title="Lead Time Distribution by Ship Mode (days)",
                              points="outliers", height=400), use_container_width=True)

    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(bar_chart(summary, x="Ship Mode", y="avg_lead_time", color="Ship Mode",
                                  color_map=SHIP_MODE_COLOURS, title="Avg Lead Time (days)", height=340),
                        use_container_width=True)
    with col_r:
        st.plotly_chart(bar_chart(summary, x="Ship Mode", y="median_lead_time", color="Ship Mode",
                                  color_map=SHIP_MODE_COLOURS, title="Median Lead Time (days)", height=340),
                        use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Delay Analysis ────────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">warning</span>Delay Analysis</div>', unsafe_allow_html=True)
    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(bar_chart(summary, x="Ship Mode", y="delay_rate_pct", color="Ship Mode",
                                  color_map=SHIP_MODE_COLOURS, title="Delay Rate % by Mode", height=340),
                        use_container_width=True)
    with col_r:
        ot = analyzer.on_time_vs_delayed()
        ot_m = ot.melt(id_vars="Ship Mode", value_vars=["on_time","delayed"],
                       var_name="Status", value_name="Count")
        ot_m["Status"] = ot_m["Status"].map({"on_time":"On Time","delayed":"Delayed"})
        st.plotly_chart(bar_chart(ot_m, x="Ship Mode", y="Count", color="Status",
                                  title="On-Time vs Delayed by Mode",
                                  color_map={"On Time": PALETTE["accent"], "Delayed": PALETTE["danger"]},
                                  barmode="stack", height=340), use_container_width=True)

    # ── Delay by Mode + Region ────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">public</span>Delay by Mode & Region</div>', unsafe_allow_html=True)
    dr = analyzer.delay_by_mode_and_region()
    st.plotly_chart(bar_chart(dr, x="Region", y="delay_rate_pct", color="Ship Mode",
                              color_map=SHIP_MODE_COLOURS,
                              title="Delay Rate % by Region & Ship Mode",
                              barmode="group", height=380), use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Cost-Time Trade-off ────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">balance</span>Cost-Time-Profit Trade-off</div>', unsafe_allow_html=True)
    tradeoff = analyzer.cost_time_tradeoff()
    st.plotly_chart(scatter_chart(tradeoff, x="avg_lead_time", y="avg_cost", color="Ship Mode",
                              size="shipments", hover_data=["delay_rate_pct","profit_margin_pct"],
                              color_map=SHIP_MODE_COLOURS,
                              title="Cost vs Lead Time (bubble = volume)", height=400),
                    use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Profit metrics ────────────────────────────────────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(bar_chart(summary, x="Ship Mode", y="profit_per_shipment", color="Ship Mode",
                                  color_map=SHIP_MODE_COLOURS, title="Profit per Shipment ($)", height=320),
                        use_container_width=True)
    with col_r:
        st.plotly_chart(bar_chart(summary, x="Ship Mode", y="profit_margin_pct", color="Ship Mode",
                                  color_map=SHIP_MODE_COLOURS, title="Profit Margin % by Mode", height=320),
                        use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Monthly Trend ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">trending_up</span>Monthly Volume Trend by Mode</div>', unsafe_allow_html=True)
    monthly = analyzer.monthly_mode_trend()
    monthly["period"] = (monthly["Shipment Year"].astype(str) + "-"
                         + monthly["Shipment Month"].astype(str).str.zfill(2))
    st.plotly_chart(line_chart(monthly, x="period", y="shipments", color="Ship Mode",
                               title="Monthly Shipments by Mode", markers=False, height=360),
                    use_container_width=True)

    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    # ── Summary Table ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">table_chart</span>Full Ship Mode Summary</div>', unsafe_allow_html=True)
    disp = summary[["Ship Mode","shipments","total_sales","total_profit","avg_lead_time",
                    "delay_rate_pct","avg_cost","profit_per_shipment","volume_share_pct"]].rename(columns={
        "Ship Mode":"Mode","shipments":"Shipments","total_sales":"Sales ($)","total_profit":"Profit ($)",
        "avg_lead_time":"Avg Lead","delay_rate_pct":"Delay %","avg_cost":"Avg Cost",
        "profit_per_shipment":"Profit/Ship","volume_share_pct":"Share %"})
    st.dataframe(disp, use_container_width=True, hide_index=True)
    st.download_button("Download Ship Mode Data", data=summary.to_csv(index=False),
                       file_name="ship_mode_analysis.csv", mime="text/csv", icon=":material/download:")

    best = summary.loc[summary["delay_rate_pct"].idxmin(), "Ship Mode"]
    worst = summary.loc[summary["delay_rate_pct"].idxmax(), "Ship Mode"]
    st.markdown(f"""<div class="insight-box">
        <div class="insight-title"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:5px;">lightbulb</span>Ship Mode Insight</div>
        <strong>{best}</strong> has the lowest delay rate.
        <strong>{worst}</strong> has the highest — review capacity for this mode.
    </div>""", unsafe_allow_html=True)

# ── Auto-run when executed as a Streamlit page ─────────────────────────────────
_df = st.session_state.get("df_filtered", None)
if _df is None:
    from src.utils import FEATURED_DATA_FILE, ensure_dirs
    ensure_dirs()
    _df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])

render(_df)
