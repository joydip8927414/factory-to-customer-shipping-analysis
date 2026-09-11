"""pg_product.py — Product Intelligence, ABC Analysis & Portfolio Analytics"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.right_filter_panel import render_right_filter_panel
from src.utils import get_palette
from src.visualization import bar_chart, pie_chart, treemap_chart


def render(df_input: pd.DataFrame) -> None:
    df_full = st.session_state.get("df_full", df_input)
    df = render_right_filter_panel(df_full, current_page="product")
    st.session_state["df_filtered"] = df

    theme = st.session_state.get("theme", "dark")
    palette = get_palette(theme)
    h1_clr = "#0F172A" if theme == "light" else "#E8EAED"
    sub_clr = "#64748B" if theme == "light" else "#9AA0B9"

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
        <span class="material-symbols-rounded" style="font-size:2rem;color:{palette['primary']};">inventory_2</span>
        <h1 style="font-size:1.85rem;font-weight:800;color:{h1_clr};margin:0;letter-spacing:-.02em;">
            Product Intelligence & ABC Portfolio Classification
        </h1>
    </div>
    <p style="color:{sub_clr};font-size:.86rem;margin-bottom:24px;">
        SKU performance analysis, ABC revenue stratification, product line profitability, and factory origin distribution.
    </p>
    """, unsafe_allow_html=True)

    # Product aggregates
    prod_df = df.groupby(["Product Name", "Division", "Factory"]).agg(
        total_sales=("Sales", "sum"),
        total_profit=("Gross Profit", "sum"),
        units_sold=("Units", "sum"),
        orders=("Order ID", "count"),
        avg_lead_time=("Shipping Lead Time", "mean"),
    ).reset_index()

    prod_summary = df.groupby("Product Name").agg(
        total_sales=("Sales", "sum"),
        total_profit=("Gross Profit", "sum"),
        units_sold=("Units", "sum"),
        orders=("Order ID", "count"),
    ).sort_values("total_sales", ascending=False).reset_index()

    # ABC Classification
    prod_summary["cum_sales"] = prod_summary["total_sales"].cumsum()
    tot_sales = prod_summary["total_sales"].sum()
    prod_summary["cum_pct"] = (prod_summary["cum_sales"] / tot_sales) * 100
    prod_summary["abc_class"] = pd.cut(
        prod_summary["cum_pct"],
        bins=[0, 70, 90, 100],
        labels=["A (Core 70%)", "B (Secondary 20%)", "C (Long-Tail 10%)"],
        include_lowest=True
    )
    prod_summary["margin_pct"] = (prod_summary["total_profit"] / prod_summary["total_sales"] * 100).round(1)

    c1, c2, c3, c4 = st.columns(4)
    top_sku = prod_summary.iloc[0]["Product Name"] if not prod_summary.empty else "N/A"
    top_sku_sales = prod_summary.iloc[0]["total_sales"] if not prod_summary.empty else 0
    total_skus = len(prod_summary)
    a_items = (prod_summary["abc_class"] == "A (Core 70%)").sum()

    for col, lbl, val, sub, clr in [
        (c1, "Active SKU Count", f"{total_skus}", "Catalog depth", palette["primary"]),
        (c2, "Top Revenue Driver", f"{top_sku}", f"${top_sku_sales:,.0f} revenue", palette["accent"]),
        (c3, "Class A SKU Focus", f"{a_items} Products", f"Drive 70% of total revenue", palette["secondary"]),
        (c4, "Portfolio Gross Margin", f"{(df['Gross Profit'].sum() / df['Sales'].sum() * 100):.1f}%", "Across all confections", palette["warning"]),
    ]:
        with col:
            st.markdown(f"""
            <div class="kpi-card" style="text-align:left;padding:18px 20px;">
                <div style="font-size:.74rem;font-weight:700;color:{sub_clr};text-transform:uppercase;letter-spacing:.08em;">{lbl}</div>
                <div style="font-size:1.45rem;font-weight:800;color:{clr};margin:4px 0;">{val}</div>
                <div style="font-size:.74rem;color:{sub_clr};">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="styled-divider" style="margin:24px 0;">', unsafe_allow_html=True)

    # ── Treemap & Division Breakdown ──
    col_t, col_p = st.columns([1.3, 1])
    with col_t:
        st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:#6C63FF;">account_tree</span>Confectionery Portfolio Treemap (Division → Product)</div>', unsafe_allow_html=True)
        st.plotly_chart(
            treemap_chart(df, path=["Division", "Product Name"], values="Sales", title="Sales Contribution by Category", height=380),
            use_container_width=True
        )

    with col_p:
        st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:#6C63FF;">pie_chart</span>ABC Classification Breakdown</div>', unsafe_allow_html=True)
        abc_counts = prod_summary["abc_class"].value_counts().reset_index()
        abc_counts.columns = ["Class", "Count"]
        st.plotly_chart(
            pie_chart(abc_counts, names="Class", values="Count", title="Catalog Stratification (SKU Count)", height=380),
            use_container_width=True
        )

    # ── Full Product Performance Table ──
    st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:#6C63FF;">table_chart</span>SKU Performance & Stratification Grid</div>', unsafe_allow_html=True)
    disp = prod_summary.rename(columns={
        "Product Name": "Product SKU",
        "total_sales": "Revenue ($)",
        "total_profit": "Gross Profit ($)",
        "units_sold": "Units Sold",
        "orders": "Orders",
        "margin_pct": "Margin %",
        "abc_class": "ABC Tier",
    })[["Product SKU", "ABC Tier", "Revenue ($)", "Gross Profit ($)", "Margin %", "Units Sold", "Orders"]]
    st.dataframe(disp, use_container_width=True, hide_index=True)


_df = st.session_state.get("df_filtered", None)
if _df is None:
    from src.utils import FEATURED_DATA_FILE, ensure_dirs
    ensure_dirs()
    _df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])

render(_df)
