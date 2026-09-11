"""pg_ml.py — Machine Learning Insights & Real-Time What-If Prediction"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.right_filter_panel import render_right_filter_panel
from src.utils import FACTORY_COORDINATES, SHIP_MODES_ORDERED, get_palette
from src.visualization import bar_chart, feature_importance_chart


def render(df_input: pd.DataFrame) -> None:
    df_full = st.session_state.get("df_full", df_input)
    df = render_right_filter_panel(df_full, current_page="ml")
    st.session_state["df_filtered"] = df

    theme = st.session_state.get("theme", "dark")
    palette = get_palette(theme)
    card_bg = "#FFFFFF" if theme == "light" else "rgba(30,33,48,.8)"
    card_border = "rgba(83,72,232,.2)" if theme == "light" else "rgba(108,99,255,.25)"
    text_color = "#0F172A" if theme == "light" else "#E8EAED"
    muted_color = "#64748B" if theme == "light" else "#9AA0B9"

    st.markdown(f"""
    <h1 style="font-size:1.9rem;font-weight:800;color:{text_color};letter-spacing:-.03em;margin-bottom:4px;">
        Machine Learning Intelligence & What-If Simulator
    </h1>
    <p style="color:{muted_color};font-size:.88rem;margin-bottom:20px;">
        Predictive classification of shipment delays, lead time regression forecasting, and interactive simulator.
    </p>""", unsafe_allow_html=True)

    tab_eval, tab_sim = st.tabs([":material/analytics: Model Benchmark & Feature Importance", ":material/tune: Live What-If Route Simulator"])

    # ── Train / Cache models ────────────────────────────────────────────────────
    @st.cache_resource(show_spinner="Training delay classifier…")
    def train_clf(n_rows: int, _df: pd.DataFrame):
        from src.model import DelayClassifier
        clf = DelayClassifier(_df)
        clf.train_all()
        return clf

    @st.cache_resource(show_spinner="Training lead time regressor…")
    def train_reg(n_rows: int, _df: pd.DataFrame):
        from src.model import LeadTimeRegressor
        reg = LeadTimeRegressor(_df)
        reg.train_all()
        return reg

    with st.spinner("Initializing ML engines…"):
        clf = train_clf(len(df), df)
        reg = train_reg(len(df), df)

    clf_results = clf.get_results_df()
    reg_results = reg.get_results_df()

    with tab_eval:
        st.markdown(f'<div style="font-size:.78rem;font-weight:700;color:{palette["primary"]};text-transform:uppercase;letter-spacing:.08em;margin:8px 0;">Select Predictive Algorithm</div>', unsafe_allow_html=True)
        algo_label = st.radio("Algorithm", ["Random Forest (RF)", "Gradient Boosting (GBM)", "XGBoost (XGB)"],
                              horizontal=True, label_visibility="collapsed")
        algo_key = {"Random Forest (RF)": "rf", "Gradient Boosting (GBM)": "gbm", "XGBoost (XGB)": "xgb"}[algo_label]

        # ── Classification Results ─────────────────────────────────────────────
        st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">crisis_alert</span>Delay Classification Results</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-subtitle">Identifies high-risk shipments exceeding historical median transit times</div>',
                    unsafe_allow_html=True)

        if algo_key in clf.results:
            m = clf.results[algo_key]
            c1, c2, c3, c4, c5 = st.columns(5)
            for col, val, lbl, clr in [
                (c1, f"{m.get('accuracy',0):.3f}",  "Accuracy",  palette["primary"]),
                (c2, f"{m.get('precision',0):.3f}", "Precision", palette["accent"]),
                (c3, f"{m.get('recall',0):.3f}",    "Recall",    palette["warning"]),
                (c4, f"{m.get('f1',0):.3f}",        "F1 Score",  palette["info"]),
                (c5, f"{m.get('roc_auc',0):.3f}",   "ROC AUC",   palette["danger"]),
            ]:
                with col:
                    st.markdown(f'<div class="kpi-card"><div class="kpi-value" style="color:{clr};">{val}</div>'
                                f'<div class="kpi-label">{lbl}</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown(f"**Classification Model Comparison ({len(clf_results)} Models)**")
            st.dataframe(clf_results, use_container_width=True, hide_index=True)
        with col_r:
            if algo_key in clf.models:
                fi = clf.feature_importance(algo_key)
                st.plotly_chart(feature_importance_chart(fi, title=f"Feature Importance ({algo_label.split('(')[0].strip()})"),
                                use_container_width=True)

        if not clf_results.empty:
            m_melt = clf_results.melt(id_vars="algorithm", var_name="Metric", value_name="Score")
            st.plotly_chart(bar_chart(m_melt, x="algorithm", y="Score", color="Metric",
                                      title="Classifier Metrics by Algorithm", barmode="group", height=320),
                            use_container_width=True)

        # ── Regression Results ─────────────────────────────────────────────────
        st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)
        st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;">straighten</span>Lead Time Regression Benchmarks</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-subtitle">Predicts expected shipping duration across transportation corridors</div>', unsafe_allow_html=True)

        if algo_key in reg.results:
            rm = reg.results[algo_key]
            c1, c2, c3 = st.columns(3)
            for col, val, lbl, clr in [
                (c1, f"{rm.get('mae',0):.2f}d",  "MAE (days)",  palette["primary"]),
                (c2, f"{rm.get('rmse',0):.2f}d", "RMSE (days)", palette["danger"]),
                (c3, f"{rm.get('r2',0):.4f}",    "R² Score",    palette["accent"]),
            ]:
                with col:
                    st.markdown(f'<div class="kpi-card"><div class="kpi-value" style="color:{clr};">{val}</div>'
                                f'<div class="kpi-label">{lbl}</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("**All Regression Model Comparison**")
            st.dataframe(reg_results, use_container_width=True, hide_index=True)
        with col_r:
            if algo_key in reg.models:
                fi_r = reg.feature_importance(algo_key)
                st.plotly_chart(feature_importance_chart(fi_r, title=f"Feature Importance ({algo_label.split('(')[0].strip()})"),
                                use_container_width=True)

        st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

        # Save & Export
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Save Trained Models to Disk", icon=":material/save:", use_container_width=True):
                with st.spinner("Saving models to outputs/models/…"):
                    try:
                        clf.save_models()
                        reg.save_models()
                        st.success("Models saved to `outputs/models/`", icon=":material/check_circle:")
                    except Exception as e:
                        st.error(f"Error: {e}")
        with col2:
            if not clf_results.empty:
                c1 = clf_results.copy(); c1["model_type"] = "classifier"
                c2 = reg_results.copy(); c2["model_type"] = "regressor"
                all_r = pd.concat([c1, c2], ignore_index=True)
                st.download_button("⬇️ Download Model Evaluation Results (CSV)", data=all_r.to_csv(index=False),
                                   file_name="nassau_ml_benchmarks.csv", mime="text/csv", use_container_width=True)

    # ── Interactive Simulator Tab ─────────────────────────────────────────────
    with tab_sim:
        st.markdown('<div class="section-header"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:6px;color:#6C63FF;">tune</span>Interactive What-If Shipping Predictor</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-subtitle">Select hypothetical order variables and click "Run Prediction" to forecast delay probability and transit lead time using machine learning.</div>', unsafe_allow_html=True)

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            sim_factory = st.selectbox("Origin Factory", list(FACTORY_COORDINATES.keys()), index=0)
            sim_mode = st.selectbox("Ship Mode", SHIP_MODES_ORDERED, index=0)
            sim_region = st.selectbox("Destination Region", sorted(df["Region"].dropna().unique()), index=0)
        with sc2:
            sim_division = st.selectbox("Division", sorted(df["Division"].dropna().unique()), index=0)
            sim_month = st.slider("Shipment Month", 1, 12, 6)
            sim_units = st.number_input("Order Units", min_value=1, max_value=200, value=5)
        with sc3:
            sim_sales = st.number_input("Order Value / Sales ($)", min_value=1.0, max_value=50000.0, value=250.0, step=25.0)
            sim_profit = st.number_input("Gross Profit ($)", min_value=-500.0, max_value=20000.0, value=65.0, step=10.0)
            sim_cost = sim_sales - sim_profit

        if st.button("Run Real-Time ML Prediction", icon=":material/bolt:", type="primary", use_container_width=True):
            coords = FACTORY_COORDINATES.get(sim_factory, (35.0, -90.0))
            quarter = (sim_month - 1) // 3 + 1
            day_of_week = 2  # Wednesday typical
            week_num = min(sim_month * 4, 52)

            # Build synthetic feature row
            input_dict = {
                "Shipment Month": sim_month,
                "Shipment Quarter": quarter,
                "Shipment Day of Week": day_of_week,
                "Shipment Week": week_num,
                "Units": sim_units,
                "Sales": sim_sales,
                "Gross Profit": sim_profit,
                "Cost": sim_cost,
                "Factory Latitude": coords[0],
                "Factory Longitude": coords[1],
                "Ship Mode": sim_mode,
                "Factory": sim_factory,
                "Region": sim_region,
                "Division": sim_division,
            }
            sim_df = pd.DataFrame([input_dict])

            try:
                # Prepare features via model pipeline
                from src.model import prepare_features
                X_sim = prepare_features(sim_df)

                pred_model = clf.models.get("rf")
                reg_model = reg.models.get("rf")

                if pred_model is not None and reg_model is not None:
                    prob_delayed = pred_model.predict_proba(X_sim)[0][1] if hasattr(pred_model, "predict_proba") else 0.5
                    is_delayed = prob_delayed >= 0.5
                    pred_lead_time = float(reg_model.predict(X_sim)[0])

                    st.markdown("<br>", unsafe_allow_html=True)
                    r1, r2, r3 = st.columns(3)
                    with r1:
                        status_str = '<span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.4rem;margin-right:4px;">warning</span>Delayed Likely' if is_delayed else '<span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.4rem;margin-right:4px;">check_circle</span>On Time Expected'
                        status_clr = palette["danger"] if is_delayed else palette["accent"]
                        st.markdown(f"""<div class="kpi-card" style="border-color:{status_clr};">
                            <div class="kpi-label">Predicted Delay Status</div>
                            <div class="kpi-value" style="color:{status_clr};font-size:1.6rem;">{status_str}</div>
                            <div style="font-size:.78rem;color:{muted_color};margin-top:6px;">Confidence: <strong>{max(prob_delayed, 1-prob_delayed)*100:.1f}%</strong></div>
                        </div>""", unsafe_allow_html=True)
                    with r2:
                        st.markdown(f"""<div class="kpi-card">
                            <div class="kpi-label">Delay Probability</div>
                            <div class="kpi-value" style="color:{palette['warning']};font-size:1.6rem;">{prob_delayed*100:.1f}%</div>
                            <div style="font-size:.78rem;color:{muted_color};margin-top:6px;">Threshold: 50.0%</div>
                        </div>""", unsafe_allow_html=True)
                    with r3:
                        st.markdown(f"""<div class="kpi-card">
                            <div class="kpi-label">Predicted Lead Time</div>
                            <div class="kpi-value" style="color:{palette['info']};font-size:1.6rem;">{pred_lead_time:.0f} days</div>
                            <div style="font-size:.78rem;color:{muted_color};margin-top:6px;">Mode: {sim_mode}</div>
                        </div>""", unsafe_allow_html=True)
                else:
                    st.warning("Random Forest models are being initialized. Please try again.")
            except Exception as e:
                st.error(f"Prediction error: {e}")

    st.markdown(f"""<div class="insight-box" style="margin-top:24px;">
        <div class="insight-title"><span class="material-symbols-rounded" style="vertical-align:middle;margin-right:5px;">lightbulb</span>Strategic Recommendation</div>
        Leverage Random Forest classification to flag at-risk orders upon placement. High-volume shipments during peak quarters can be routed via faster alternative modes (e.g. First Class) before delays propagate to end customers.
    </div>""", unsafe_allow_html=True)

# ── Auto-run when executed as a Streamlit page ─────────────────────────────────
_df = st.session_state.get("df_filtered", None)
if _df is None:
    from src.utils import FEATURED_DATA_FILE, ensure_dirs
    ensure_dirs()
    _df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])

render(_df)
