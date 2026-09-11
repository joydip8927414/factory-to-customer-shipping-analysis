"""pg_customer.py — Customer Analytics & Enterprise B2B Segmentation"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.right_filter_panel import render_right_filter_panel
from src.utils import get_palette
from src.visualization import bar_chart, pie_chart, scatter_chart


def render(df_input: pd.DataFrame) -> None:
    df_full = st.session_state.get("df_full", df_input)
    df = render_right_filter_panel(df_full, current_page="customer")
    st.session_state["df_filtered"] = df

    theme = st.session_state.get("theme", "dark")
    palette = get_palette(theme)
    h1_clr = "#0F172A" if theme == "light" else "#E8EAED"
    sub_clr = "#64748B" if theme == "light" else "#9AA0B9"

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
        <span class="material-symbols-rounded" style="font-size:2rem;color:{palette['primary']};">group</span>
        <h1 style="font-size:1.85rem;font-weight:800;color:{h1_clr};margin:0;letter-spacing:-.02em;">
            Customer Intelligence & Account Analytics
        </h1>
    </div>
    <p style="color:{sub_clr};font-size:.86rem;margin-bottom:24px;">
        Commercial account behavior, B2B purchasing frequency, repeat customer share, and margin generation.
    </p>
    """, unsafe_allow_html=True)

    # Customer aggregates
    cust_df = df.groupby("Customer ID").agg(
        orders=("Order ID", "nunique"),
        total_sales=("Sales", "sum"),
        total_profit=("Gross Profit", "sum"),
        avg_lead_time=("Shipping Lead Time", "mean"),
        delays=("Delay Flag", "sum"),
    ).reset_index()
    cust_df["margin_pct"] = (cust_df["total_profit"] / cust_df["total_sales"] * 100).fillna(0)
    cust_df["repeat_buyer"] = cust_df["orders"] > 1

    total_cust = len(cust_df)
    repeat_cust = cust_df["repeat_buyer"].sum()
    repeat_pct = (repeat_cust / total_cust * 100) if total_cust else 0
    avg_rev_per_cust = cust_df["total_sales"].mean() if total_cust else 0

    c1, c2, c3, c4 = st.columns(4)
    for col, lbl, val, sub, clr in [
        (c1, "Total Active Accounts", f"{total_cust:,}", "Unique business clients", palette["primary"]),
        (c2, "Repeat Client Rate", f"{repeat_pct:.1f}%", f"{repeat_cust:,} recurring buyers", palette["accent"]),
        (c3, "Avg Client Revenue", f"${avg_rev_per_cust:,.0f}", "Annualized sales run-rate", palette["secondary"]),
        (c4, "Top Account Share", f"{(cust_df['total_sales'].nlargest(10).sum() / cust_df['total_sales'].sum() * 100):.1f}%", "Concentration across Top 10", palette["warning"]),
    ]:
        with col:
            st.markdown(f"""
            <div class="kpi-card" style="text-align:left;padding:18px 20px;">
                <div style="font-size:.74rem;font-weight:700;color:{sub_clr};text-transform:uppercase;letter-spacing:.08em;">{lbl}</div>
                <div style="font-size:1.6rem;font-weight:800;color:{clr};margin:4px 0;">{val}</div>
                <div style="font-size:.74rem;color:{sub_clr};">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="styled-divider" style="margin:24px 0;">', unsafe_allow_html=True)

    # ── Top Customers Leaderboard & Margin Scatter ──
    col_l, col_r = st.columns([1.2, 1])
    with col_l:
        st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">military_tech</span>Top 10 Accounts by Revenue</div>', unsafe_allow_html=True)
        top_10 = cust_df.sort_values("total_sales", ascending=False).head(10)
        st.plotly_chart(
            bar_chart(top_10, x="total_sales", y="Customer ID", orientation="h",
                      title="Top 10 Accounts (Total Sales $)", height=380),
            use_container_width=True
        )

    with col_r:
        st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">diamond</span>Account Revenue vs Profit Margin</div>', unsafe_allow_html=True)
        st.plotly_chart(
            scatter_chart(cust_df.head(250), x="total_sales", y="margin_pct", size="orders",
                          title="Account Margin vs Sales (Size = Order Count)", height=380),
            use_container_width=True
        )

    # ── Account Drill Table ──
    st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">table_chart</span>Account Performance Matrix</div>', unsafe_allow_html=True)
    disp = cust_df.sort_values("total_sales", ascending=False).rename(columns={
        "Customer ID": "Account ID",
        "orders": "Orders",
        "total_sales": "Total Sales ($)",
        "total_profit": "Gross Profit ($)",
        "margin_pct": "Margin %",
        "avg_lead_time": "Avg Lead Time (d)",
        "delays": "Delayed Shipments",
    })
    st.dataframe(disp.head(100), use_container_width=True, hide_index=True)


_df = st.session_state.get("df_filtered", None)
if _df is None:
    from src.utils import FEATURED_DATA_FILE, ensure_dirs
    ensure_dirs()
    _df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])

render(_df)
