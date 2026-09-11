"""pg_simulator.py — Real-Time What-If Logistics Scenario Simulator"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.right_filter_panel import render_right_filter_panel
from src.utils import FACTORY_COORDINATES, SHIP_MODES_ORDERED, get_palette


def render(df_input: pd.DataFrame) -> None:
    df_full = st.session_state.get("df_full", df_input)
    df = render_right_filter_panel(df_full, current_page="simulator")
    st.session_state["df_filtered"] = df

    theme = st.session_state.get("theme", "dark")
    palette = get_palette(theme)
    h1_clr = "#0F172A" if theme == "light" else "#E8EAED"
    sub_clr = "#64748B" if theme == "light" else "#9AA0B9"
    card_bg = "#FFFFFF" if theme == "light" else "rgba(26,30,46,0.95)"
    card_border = "rgba(83,72,232,0.2)" if theme == "light" else "rgba(108,99,255,0.25)"

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
        <span class="material-symbols-rounded" style="font-size:2rem;color:{palette['primary']};">tune</span>
        <h1 style="font-size:1.85rem;font-weight:800;color:{h1_clr};margin:0;letter-spacing:-.02em;">
            Live What-If Logistics Scenario Simulator
        </h1>
    </div>
    <p style="color:{sub_clr};font-size:.86rem;margin-bottom:24px;">
        Test hypothetical shipment variables (origin plant, destination, order size, delivery speed) to predict lead times, delay risk, and profitability.
    </p>
    """, unsafe_allow_html=True)

    # ── Train or Load ML Models ──
    @st.cache_resource(show_spinner="Preparing simulation inference engine…")
    def get_models(n: int, _data: pd.DataFrame):
        from src.model import DelayClassifier, LeadTimeRegressor
        clf = DelayClassifier(_data)
        clf.train_all()
        reg = LeadTimeRegressor(_data)
        reg.train_all()
        return clf, reg

    clf, reg = get_models(len(df), df)

    # ── Simulator Controls ──
    st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">tune</span>Scenario Parameters</div>', unsafe_allow_html=True)

    col_s1, col_s2, col_s3 = st.columns(3)
    factories = sorted(df["Factory"].dropna().unique())
    states = sorted(df["State/Province"].dropna().unique())
    divisions = sorted(df["Division"].dropna().unique())
    modes = [m for m in SHIP_MODES_ORDERED if m in df["Ship Mode"].unique()]

    with col_s1:
        sim_factory = st.selectbox("Origin Factory", factories, index=0)
        sim_division = st.selectbox("Product Division", divisions, index=0)
    with col_s2:
        sim_state = st.selectbox("Destination State", states, index=0)
        sim_mode = st.selectbox("Ship Mode", modes, index=0)
    with col_s3:
        sim_units = st.slider("Order Units", 1, 15, 3)
        sim_sales = st.slider("Expected Sales ($)", 5.0, 150.0, 25.0, step=2.5)

    st.markdown('<hr class="styled-divider" style="margin:20px 0;">', unsafe_allow_html=True)

    # ── Inference Execution ──
    # Build feature record matching pipeline
    fac_coords = FACTORY_COORDINATES.get(sim_factory, (39.5, -98.35))
    input_dict = {
        "Ship Mode": sim_mode,
        "Division": sim_division,
        "State/Province": sim_state,
        "Factory": sim_factory,
        "Units": sim_units,
        "Sales": sim_sales,
        "Factory Latitude": fac_coords[0],
        "Factory Longitude": fac_coords[1],
        "Cost": sim_sales * 0.35,  # Estimated baseline cost ratio
        "Gross Profit": sim_sales * 0.65,
        "Shipment Month": 6,
        "Shipment Quarter": 2,
        "Shipment Day of Week": 2,
    }
    input_row = pd.DataFrame([input_dict])

    try:
        best_reg = reg.models.get("rf", list(reg.models.values())[0])
        pred_days = float(best_reg.predict(input_row)[0])
    except Exception:
        pred_days = float(df[df["Ship Mode"] == sim_mode]["Shipping Lead Time"].median())

    try:
        best_clf = clf.models.get("rf", list(clf.models.values())[0])
        prob_delay = float(best_clf.predict_proba(input_row)[0][1]) * 100
    except Exception:
        prob_delay = float((df[df["State/Province"] == sim_state]["Delay Flag"].mean() or 0.44) * 100)

    est_cost = sim_sales * 0.35
    est_margin = ((sim_sales - est_cost) / sim_sales) * 100

    # ── Prediction Results Scorecard ──
    st.markdown(f'<div class="section-header" style="color:{h1_clr};"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">online_prediction</span>Real-Time Simulated Outcomes</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)

    delay_clr = palette["accent"] if prob_delay < 35 else (palette["warning"] if prob_delay < 60 else palette["danger"])

    for col, lbl, val, sub, clr in [
        (c1, "Predicted Lead Time", f"{pred_days:.0f} Days", f"Historical median: {df['Shipping Lead Time'].median():.0f}d", palette["primary"]),
        (c2, "Delay Risk Probability", f"{prob_delay:.1f}%", "Risk of transit bottleneck", delay_clr),
        (c3, "Estimated Gross Profit", f"${(sim_sales - est_cost):,.2f}", f"{est_margin:.1f}% profit margin", palette["accent"]),
        (c4, "Simulated Route", f"{sim_factory[:12]} → {sim_state}", f"Delivery Class: {sim_mode}", palette["info"]),
    ]:
        with col:
            st.markdown(f"""
            <div class="kpi-card" style="background:{card_bg};border:1px solid {card_border};text-align:left;padding:18px 20px;">
                <div style="font-size:.74rem;font-weight:700;color:{sub_clr};text-transform:uppercase;letter-spacing:.08em;">{lbl}</div>
                <div style="font-size:1.6rem;font-weight:800;color:{clr};margin:4px 0;">{val}</div>
                <div style="font-size:.74rem;color:{sub_clr};">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div class="insight-box" style="margin-top:20px;">
        <div class="insight-title" style="color:{palette['primary']};">Decision Recommendation</div>
        Simulated dispatch from <strong>{sim_factory}</strong> to <strong>{sim_state}</strong> via <strong>{sim_mode}</strong> 
        yields an expected transit timeline of <strong>{pred_days:.0f} days</strong> with <strong>{prob_delay:.1f}% delay probability</strong>.
        {'<span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;color:#FC5C7D;margin-right:4px;">warning</span>Suggest upgrading to First Class or allocating safety stock buffer.' if prob_delay >= 50 else '<span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;color:#00C896;margin-right:4px;">check_circle</span>Transit timeline meets enterprise fulfillment SLA targets.'}
    </div>
    """, unsafe_allow_html=True)


_df = st.session_state.get("df_filtered", None)
if _df is None:
    from src.utils import FEATURED_DATA_FILE, ensure_dirs
    ensure_dirs()
    _df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])

render(_df)
