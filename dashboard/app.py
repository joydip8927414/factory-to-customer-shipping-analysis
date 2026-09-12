"""
app.py — Nassau Candy Shipping Analytics Dashboard
====================================================
Uses st.navigation() with file-path-based st.Page() objects for
explicit, collision-free URL routing in Streamlit 1.36+.
Supports Dark/Light theme switching, advanced Year/Month/Day filters,
and premium enterprise branding with logo assets.
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = Path(__file__).resolve().parent / "pages"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_FILE = ASSETS_DIR / "logo.png"
sys.path.insert(0, str(ROOT))

from src.db.session import ensure_db_ready
from src.utils import (
    FACTORY_COLOURS,
    FEATURED_DATA_FILE,
    PALETTE,
    PALETTE_DARK,
    PALETTE_LIGHT,
    REGION_COLOURS,
    SHIP_MODE_COLOURS,
    SHIP_MODES_ORDERED,
    ensure_dirs,
    get_logger,
)

logger = get_logger(__name__)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Nassau Candy | Shipping Analytics",
    page_icon=":material/local_shipping:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Enforce permanent dark mode as default
st.session_state["theme"] = "dark"
theme = "dark"

# ── Dynamic CSS Injection based on active theme ────────────────────────────────
if theme == "light":
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
    .material-symbols-rounded {
        font-family: 'Material Symbols Rounded' !important;
        font-weight: normal;
        font-style: normal;
        font-size: 20px;
        line-height: 1;
        letter-spacing: normal;
        text-transform: none;
        display: inline-block;
        white-space: nowrap;
        word-wrap: normal;
        direction: ltr;
        vertical-align: middle;
        -webkit-font-smoothing: antialiased;
    }
    html, [class*="css"], body {
        font-family: 'Plus Jakarta Sans', 'Inter', sans-serif !important;
        color: #0F172A !important;
    }
    .stApp {
        background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 50%, #E2E8F0 100%) !important;
        color: #0F172A !important;
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
        color: #0F172A !important;
    }
    .stApp p {
        color: #475569;
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%) !important;
        border-right: 1px solid rgba(83, 72, 232, 0.15) !important;
        box-shadow: 4px 0 24px rgba(0, 0, 0, 0.03) !important;
    }
    section[data-testid="stSidebar"] * {
        color: #1E293B !important;
    }
    section[data-testid="stSidebar"] label {
        color: #475569 !important;
        font-size: .76rem !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: .08em !important;
    }
    .kpi-card {
        background: #FFFFFF !important;
        border: 1px solid rgba(83, 72, 232, 0.16) !important;
        border-radius: 16px !important;
        padding: 20px 22px !important;
        text-align: center !important;
        box-shadow: 0 4px 16px rgba(83, 72, 232, 0.06) !important;
        transition: all .25s ease !important;
        position: relative !important;
        overflow: hidden !important;
        margin-bottom: 8px !important;
    }
    .kpi-card:hover {
        border-color: rgba(83, 72, 232, 0.45) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(83, 72, 232, 0.14) !important;
    }
    .kpi-value {
        font-size: clamp(1.25rem, 1.5vw, 1.85rem) !important;
        font-weight: 800 !important;
        color: #0F172A !important;
        letter-spacing: -.02em !important;
        white-space: nowrap !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }
    .kpi-label {
        font-size: .72rem !important;
        color: #64748B !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: .09em !important;
        margin-top: 6px !important;
    }
    .section-header {
        font-size: 1.25rem !important;
        font-weight: 800 !important;
        color: #0F172A !important;
        letter-spacing: -.02em !important;
        margin-bottom: 4px !important;
    }
    .section-subtitle {
        font-size: .84rem !important;
        color: #64748B !important;
        margin-bottom: 16px !important;
    }
    .styled-divider {
        height: 1px !important;
        background: linear-gradient(90deg, transparent, rgba(83, 72, 232, 0.3), transparent) !important;
        margin: 24px 0 !important;
        border: none !important;
    }
    .insight-box {
        background: linear-gradient(135deg, rgba(83, 72, 232, 0.06), rgba(16, 185, 129, 0.06)) !important;
        border: 1px solid rgba(83, 72, 232, 0.2) !important;
        border-left: 4px solid #5348E8 !important;
        border-radius: 0 12px 12px 0 !important;
        padding: 14px 18px !important;
        margin: 12px 0 !important;
        font-size: .86rem !important;
        color: #1E293B !important;
        line-height: 1.6 !important;
    }
    .insight-title {
        font-weight: 700 !important;
        color: #5348E8 !important;
        font-size: .78rem !important;
        text-transform: uppercase !important;
        letter-spacing: .08em !important;
        margin-bottom: 6px !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px !important;
        background: #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 4px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: .82rem !important;
        color: #475569 !important;
    }
    .stTabs [aria-selected="true"] {
        background: #FFFFFF !important;
        color: #5348E8 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
    }
    [data-testid="metric-container"] {
        background: #FFFFFF !important;
        border: 1px solid rgba(83, 72, 232, 0.16) !important;
        border-radius: 12px !important;
        padding: 14px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
    }
    .stDownloadButton > button {
        background: linear-gradient(135deg, #5348E8, #6366F1) !important;
        border: none !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: .82rem !important;
        box-shadow: 0 4px 12px rgba(83, 72, 232, 0.25) !important;
    }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #F1F5F9; border-radius: 3px; }
    ::-webkit-scrollbar-thumb { background: rgba(83, 72, 232, 0.4); border-radius: 3px; }
    </style>
    """, unsafe_allow_html=True)
elif theme == "system":
    # Adaptive CSS relying on CSS variables and media queries
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
    html, [class*="css"], body {
        font-family: 'Plus Jakarta Sans', 'Inter', sans-serif !important;
    }
    .kpi-card {
        background: var(--background-color, rgba(26, 30, 46, 0.95)) !important;
        border: 1px solid rgba(108, 99, 255, 0.25) !important;
        border-radius: 16px !important;
        padding: 20px 24px !important;
        text-align: center !important;
        transition: all .3s ease !important;
        margin-bottom: 6px !important;
    }
    .kpi-card:hover {
        border-color: rgba(108, 99, 255, 0.6) !important;
        transform: translateY(-2px) !important;
    }
    .section-header {
        font-size: 1.25rem !important;
        font-weight: 800 !important;
        letter-spacing: -.01em !important;
        margin-bottom: 4px !important;
    }
    .section-subtitle {
        font-size: .84rem !important;
        color: #9AA0B9 !important;
        margin-bottom: 16px !important;
    }
    .styled-divider {
        height: 1px !important;
        background: linear-gradient(90deg, transparent, rgba(108, 99, 255, 0.4), transparent) !important;
        margin: 24px 0 !important;
        border: none !important;
    }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
    .material-symbols-rounded {
        font-family: 'Material Symbols Rounded' !important;
        font-weight: normal;
        font-style: normal;
        font-size: 20px;
        line-height: 1;
        letter-spacing: normal;
        text-transform: none;
        display: inline-block;
        white-space: nowrap;
        word-wrap: normal;
        direction: ltr;
        vertical-align: middle;
        -webkit-font-smoothing: antialiased;
    }
    html, [class*="css"], body {
        font-family: 'Plus Jakarta Sans', 'Inter', sans-serif !important;
    }
    .stApp {
        background: linear-gradient(135deg, #090B10 0%, #0F1118 50%, #131622 100%) !important;
        color: #E8EAED !important;
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
        color: #E8EAED !important;
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111422 0%, #0C0E17 100%) !important;
        border-right: 1px solid rgba(108, 99, 255, 0.2) !important;
    }
    section[data-testid="stSidebar"] label {
        color: #9AA0B9 !important;
        font-size: .76rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: .08em !important;
    }
    .kpi-card {
        background: linear-gradient(135deg, rgba(26, 30, 46, 0.95), rgba(17, 20, 32, 0.95)) !important;
        border: 1px solid rgba(108, 99, 255, 0.25) !important;
        border-radius: 16px !important;
        padding: 20px 24px !important;
        text-align: center !important;
        transition: all .3s ease !important;
        position: relative !important;
        overflow: hidden !important;
        margin-bottom: 6px !important;
    }
    .kpi-card:hover {
        border-color: rgba(108, 99, 255, 0.6) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 32px rgba(108, 99, 255, 0.2) !important;
    }
    .kpi-value {
        font-size: clamp(1.25rem, 1.5vw, 1.85rem) !important;
        font-weight: 800 !important;
        color: #E8EAED !important;
        letter-spacing: -.02em !important;
        white-space: nowrap !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }
    .kpi-label {
        font-size: .72rem !important;
        color: #9AA0B9 !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: .1em !important;
        margin-top: 6px !important;
    }
    .section-header {
        font-size: 1.25rem !important;
        font-weight: 800 !important;
        color: #E8EAED !important;
        letter-spacing: -.01em !important;
        margin-bottom: 4px !important;
    }
    .section-subtitle {
        font-size: .84rem !important;
        color: #9AA0B9 !important;
        margin-bottom: 16px !important;
    }
    .styled-divider {
        height: 1px !important;
        background: linear-gradient(90deg, transparent, rgba(108, 99, 255, 0.4), transparent) !important;
        margin: 24px 0 !important;
        border: none !important;
    }
    .insight-box {
        background: linear-gradient(135deg, rgba(108, 99, 255, 0.08), rgba(67, 233, 123, 0.05)) !important;
        border: 1px solid rgba(108, 99, 255, 0.2) !important;
        border-left: 3px solid #6C63FF !important;
        border-radius: 0 12px 12px 0 !important;
        padding: 14px 18px !important;
        margin: 12px 0 !important;
        font-size: .85rem !important;
        color: #E8EAED !important;
        line-height: 1.6 !important;
    }
    .insight-title {
        font-weight: 700 !important;
        color: #6C63FF !important;
        font-size: .78rem !important;
        text-transform: uppercase !important;
        letter-spacing: .08em !important;
        margin-bottom: 6px !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px !important;
        background: rgba(15, 17, 23, 0.6) !important;
        border-radius: 12px !important;
        padding: 4px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: .82rem !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(108, 99, 255, 0.3) !important;
        color: #6C63FF !important;
    }
    [data-testid="metric-container"] {
        background: rgba(30, 33, 48, 0.6) !important;
        border: 1px solid rgba(108, 99, 255, 0.2) !important;
        border-radius: 12px !important;
        padding: 12px !important;
    }
    .stDownloadButton > button {
        background: linear-gradient(135deg, rgba(108, 99, 255, 0.25), rgba(108, 99, 255, 0.15)) !important;
        border: 1px solid rgba(108, 99, 255, 0.5) !important;
        color: #8B85FF !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: .82rem !important;
    }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: rgba(30, 33, 48, 0.5); border-radius: 3px; }
    ::-webkit-scrollbar-thumb { background: rgba(108, 99, 255, 0.4); border-radius: 3px; }
    </style>
    """, unsafe_allow_html=True)


# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading shipment data…")
def _load_data_cached(file_mtime: float, file_size: int) -> pd.DataFrame:
    try:
        df = pd.read_csv(FEATURED_DATA_FILE, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(FEATURED_DATA_FILE, encoding="latin1")
    # Parse dates with dayfirst support
    if "Order Date" in df.columns:
        df["Order Date"] = pd.to_datetime(df["Order Date"], dayfirst=True, errors="coerce")
    if "Ship Date" in df.columns:
        df["Ship Date"] = pd.to_datetime(df["Ship Date"], dayfirst=True, errors="coerce")
    return df


def load_data() -> pd.DataFrame:
    ensure_dirs()
    if not FEATURED_DATA_FILE.exists():
        st.error(
            "Featured dataset not found. Run the pipeline first:\n\n"
            "```\npython src/data_preprocessing.py\npython src/feature_engineering.py\n```",
            icon=":material/warning:",
        )
        st.stop()
    stat = FEATURED_DATA_FILE.stat()
    return _load_data_cached(stat.st_mtime, stat.st_size)


# ── Left Sidebar: Pure Branding, Controls, Help & Settings ───────────────────
def render_left_sidebar_controls() -> None:
    with st.sidebar:
        # Official Nassau Candy Brand Header
        official_logo = ASSETS_DIR / "nassau_candy_official_logo.png"
        logo_file_to_use = official_logo if official_logo.exists() else LOGO_FILE
        logo_html = ""
        if logo_file_to_use.exists():
            try:
                b64_logo = base64.b64encode(logo_file_to_use.read_bytes()).decode()
                logo_html = (
                    f'<a href="https://www.nassaucandy.com/" target="_blank" title="Visit Nassau Candy Official Website" style="text-decoration:none;">'
                    f'<div style="background:#FFFFFF;border-radius:12px;padding:8px 14px;display:inline-block;'
                    f'box-shadow:0 4px 16px rgba(0,0,0,0.12);border:1px solid rgba(179,139,78,0.3);margin-bottom:8px;'
                    f'transition:transform .2s ease;">'
                    f'<img src="data:image/png;base64,{b64_logo}" style="max-width:180px;height:auto;display:block;margin:0 auto;">'
                    f'</div></a>'
                )
            except Exception:
                logo_html = '<div style="font-size:2.2rem;margin-bottom:6px;"><span class="material-symbols-rounded" style="font-size:2.5rem;color:#B38B4E;">inventory_2</span></div>'
        else:
            logo_html = '<div style="font-size:2.2rem;margin-bottom:6px;"><span class="material-symbols-rounded" style="font-size:2.5rem;color:#B38B4E;">inventory_2</span></div>'

        st.markdown(f"""
        <div style="text-align:center;padding:8px 0 10px;
            border-bottom:1px solid rgba(108,99,255,.2);margin-bottom:12px;">
            {logo_html}
            <div style="font-size:.78rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#B38B4E;margin-top:2px;">
                Specialty Confections & Fine Foods
            </div>
            <div style="font-size:.7rem;color:#9AA0B9;margin-top:6px;display:flex;align-items:center;justify-content:center;gap:10px;">
                <a href="https://www.nassaucandy.com/" target="_blank" style="color:#6C63FF;text-decoration:none;font-weight:600;display:inline-flex;align-items:center;gap:3px;" title="Official Nassau Candy Website">
                    <span class="material-symbols-rounded" style="font-size:.85rem;">language</span> Website
                </a>
                <span style="color:rgba(154,160,185,0.4);">•</span>
                <a href="https://github.com/joydip257/factory-to-customer-shipping-analysis" target="_blank" style="color:#6C63FF;text-decoration:none;font-weight:600;display:inline-flex;align-items:center;gap:4px;" title="View Source on GitHub">
                    <svg height="12" width="12" viewBox="0 0 16 16" fill="currentColor" style="vertical-align:middle;"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg> GitHub
                </a>
            </div>
        </div>""", unsafe_allow_html=True)

        # ── General Platform Controls (No Data Filters) ──
        with st.expander("System Controls", icon=":material/settings:", expanded=False):
            st.caption("Platform Diagnostics & Cache")
            if st.button("Clear App Cache", icon=":material/refresh:", use_container_width=True):
                st.cache_data.clear()
                st.toast("Application cache flushed.", icon=":material/mop:")
                st.rerun()

        with st.expander("Help & User Guide", icon=":material/help:", expanded=False):
            st.markdown("""
            **Navigation Overview:**
            - **Executive Command**: Strategic scorecards & automated BI.
            - **Operations**: Route, geographic, and factory analysis.
            - **Portfolio**: B2B customer metrics and ABC catalog Pareto.
            - **Data Science**: ML prediction and Holt's demand forecasting.
            - **Governance**: Data quality auditing and order export.
            
            *Tip: Use the Dynamic Filter Drawer on the right of any page to scope analytics instantly.*
            """)

        with st.expander("About & GitHub Source", icon=":material/info:", expanded=False):
            st.markdown("""
            **Nassau Candy Distributor**
            Enterprise Shipping Route Efficiency Analysis
            - **Project by**: JOYDIP DAS
            - **GitHub Repository**: [joydip257/factory-to-customer-shipping-analysis](https://github.com/joydip257/factory-to-customer-shipping-analysis)
            - **Version**: 2.4.0 Enterprise
            - **Architecture**: Dual-Sidebar with Dynamic Contextual Filters
            - **Security**: PBKDF2-SHA256 authenticated Admin Console
            """)

        # Admin/User status badge
        if st.session_state.get("admin_authenticated", False):
            user_role = st.session_state.get("user_role", "Administrator")
            admin_user = st.session_state.get("admin_user", "Admin")
            st.markdown(f"""
            <div style="background:rgba(67,233,123,0.12);border:1px solid rgba(67,233,123,0.3);border-radius:8px;padding:8px;text-align:center;margin-top:10px;">
                <span style="font-size:.72rem;font-weight:700;color:#43E97B;"><span class="material-symbols-rounded" style="vertical-align:middle;font-size:.9rem;margin-right:4px;">verified_user</span>{user_role.upper()} SESSION ACTIVE</span>
                <div style="font-size:.68rem;color:#9AA0B9;margin-top:2px;">User: {admin_user}</div>
            </div>
            """, unsafe_allow_html=True)


# ── Main Enterprise Navigation Registration ────────────────────────────────────
def main() -> None:
    ensure_db_ready()
    df_full = load_data()
    render_left_sidebar_controls()

    # Track file modification time and force update if dataset was replaced/modified
    stat = FEATURED_DATA_FILE.stat() if FEATURED_DATA_FILE.exists() else None
    current_mtime = stat.st_mtime if stat else 0
    prev_mtime = st.session_state.get("app_data_mtime", None)

    prev_len = len(st.session_state["df_full"]) if "df_full" in st.session_state and st.session_state["df_full"] is not None else 0
    mtime_changed = (prev_mtime is not None and prev_mtime != current_mtime)

    st.session_state["app_data_mtime"] = current_mtime
    st.session_state["df_full"] = df_full

    if "df_filtered" not in st.session_state or st.session_state["df_filtered"] is None or len(df_full) != prev_len or mtime_changed:
        st.session_state["df_filtered"] = df_full

    is_admin = st.session_state.get("admin_authenticated", False)

    # Build navigation groups
    nav_dict = {
        "Executive Command": [
            st.Page(str(PAGES_DIR / "pg_home.py"),
                    title="Executive Hub", icon=":material/hub:", url_path="home", default=True),
            st.Page(str(PAGES_DIR / "pg_overview.py"),
                    title="Overview Scorecards", icon=":material/dashboard:", url_path="overview"),
            st.Page(str(PAGES_DIR / "pg_bi.py"),
                    title="Business Intelligence", icon=":material/analytics:", url_path="bi"),
        ],
        "Supply Chain Operations": [
            st.Page(str(PAGES_DIR / "pg_routes.py"),
                    title="Route Intelligence", icon=":material/alt_route:", url_path="routes"),
            st.Page(str(PAGES_DIR / "pg_geo.py"),
                    title="Geographic Intelligence", icon=":material/public:", url_path="geographic"),
            st.Page(str(PAGES_DIR / "pg_shipmode.py"),
                    title="Ship Mode Analytics", icon=":material/local_shipping:", url_path="shipmode"),
            st.Page(str(PAGES_DIR / "pg_factory.py"),
                    title="Factory Intelligence", icon=":material/factory:", url_path="factory"),
        ],
        "Commercial & Portfolio": [
            st.Page(str(PAGES_DIR / "pg_customer.py"),
                    title="Customer Intelligence", icon=":material/group:", url_path="customer"),
            st.Page(str(PAGES_DIR / "pg_product.py"),
                    title="Product Intelligence", icon=":material/inventory_2:", url_path="product"),
        ],
        "Data Science & What-If": [
            st.Page(str(PAGES_DIR / "pg_ml.py"),
                    title="ML Intelligence & Benchmarks", icon=":material/psychology:", url_path="ml"),
            st.Page(str(PAGES_DIR / "pg_simulator.py"),
                    title="Live What-If Simulator", icon=":material/tune:", url_path="simulator"),
            st.Page(str(PAGES_DIR / "pg_forecasting.py"),
                    title="Demand Forecasting", icon=":material/trending_up:", url_path="forecasting"),
        ],
        "Governance & Audit": [
            st.Page(str(PAGES_DIR / "pg_orders.py"),
                    title="Order Drill Down & CSV", icon=":material/search:", url_path="orders"),
            st.Page(str(PAGES_DIR / "pg_data_quality.py"),
                    title="Data Quality Center", icon=":material/verified_user:", url_path="quality"),
            st.Page(str(PAGES_DIR / "pg_admin.py"),
                    title="Admin Console & Rules", icon=":material/admin_panel_settings:", url_path="admin"),
        ],
    }

    nav = st.navigation(nav_dict)
    nav.run()


if __name__ == "__main__":
    main()


