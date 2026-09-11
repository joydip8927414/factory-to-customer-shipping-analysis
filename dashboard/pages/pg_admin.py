"""
pg_admin.py — Enterprise Administration Console (Secure & RBAC Protected)
========================================================================
Comprehensive, enterprise-grade Administration Console protected by session authentication,
Registration ID company validation, role-based access control, and live database sync.

Modules:
1. Secure Authentication & Company Registration ID Onboarding
2. Role-Based Access Control (Administrator, Analyst, Viewer)
3. Dataset Ingestion (CSV / Excel, Replace, Append, Merge, Validation)
4. Interactive Live Data Grid (Add / Edit / Delete rows, Search, Filter, Sort, Undo)
5. Dynamic Business & ML Settings (Factory Coordinates, SKU Maps, Delay SLA, ML Hyperparams)
6. Company Registration ID Governance (Generate UUIDs, Expire, Revoke, Delete, Export)
7. Dataset Version Control (Automated pre-change snapshots, Rollback, Download)
8. Smart AI Admin Assistant (Comprehensive anomaly scanner with individual & Fix-All actions)
9. Immutable Enterprise Audit Trail (Search, Filter, Export)
"""

from __future__ import annotations

import io
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.admin_assistant import analyze_dataset_health, apply_all_recommendations, apply_recommendation_fix
from src.admin_manager import (
    create_dataset_backup,
    get_audit_log_df,
    list_dataset_versions,
    load_business_config,
    recalculate_and_propagate,
    record_audit_event,
    rollback_dataset_version,
    save_business_config,
)
from src.admin_security import (
    DEFAULT_SESSION_TIMEOUT,
    authenticate_user_db,
    get_last_successful_login,
    register_admin_user,
    terminate_session,
    update_admin_password_db,
    validate_active_session,
    validate_registration_id,
)
from src.utils import (
    FACTORY_COORDINATES,
    FEATURED_DATA_FILE,
    PRODUCT_FACTORY_MAP,
    US_STATES,
    format_number,
    get_palette,
)


# ─────────────────────────────────────────────────────────────────────────────
# SESSION & RBAC AUTHENTICATION GATE
# ─────────────────────────────────────────────────────────────────────────────

def check_admin_session() -> bool:
    """Validate current session token, timeout, and role."""
    if not st.session_state.get("admin_authenticated", False):
        return False

    session_token = st.session_state.get("session_token", "")
    last_active = st.session_state.get("admin_last_activity", 0)
    current_time = time.time()
    config = load_business_config()
    timeout = config.get("session_timeout_seconds", DEFAULT_SESSION_TIMEOUT)

    # Inactivity check
    if (current_time - last_active > timeout) and not st.session_state.get("remember_me", False):
        st.session_state["admin_authenticated"] = False
        st.session_state["admin_user"] = None
        st.session_state["user_role"] = None
        st.session_state["session_token"] = None
        record_audit_event(
            user=st.session_state.get("admin_user", "Unknown"),
            action="Session Timeout",
            module="Authentication",
            status="Info",
            details="Session terminated due to 15 minutes of inactivity",
        )
        return False

    # Keep alive
    st.session_state["admin_last_activity"] = current_time
    return True


def render_auth_portal(palette: Dict[str, str], theme: str) -> None:
    """Render unified login and Company Registration ID verification portal."""
    h1_clr = "#0F172A" if theme == "light" else "#E8EAED"
    sub_clr = "#64748B" if theme == "light" else "#9AA0B9"
    card_bg = "#FFFFFF" if theme == "light" else "rgba(30,33,48,0.9)"
    border_clr = "rgba(83,72,232,0.2)" if theme == "light" else "rgba(108,99,255,0.3)"

    st.markdown(f"""
    <div style="max-width:560px;margin:30px auto 16px auto;text-align:center;">
        <div style="display:inline-flex;align-items:center;justify-content:center;width:64px;height:64px;
                    background:linear-gradient(135deg,{palette['primary']},{palette['secondary']});
                    border-radius:18px;box-shadow:0 8px 24px rgba(108,99,255,0.35);margin-bottom:12px;">
            <span class="material-symbols-rounded" style="font-size:2.4rem;color:#FFFFFF;">admin_panel_settings</span>
        </div>
        <h2 style="font-size:1.8rem;font-weight:800;color:{h1_clr};margin:0;letter-spacing:-.02em;">
            Logistics Administration Portal
        </h2>
        <p style="color:{sub_clr};font-size:.85rem;margin-top:6px;">
            Secure Enterprise Gateway. Access restricted to authorized personnel with active credentials or company registration authorization.
        </p>
    </div>
    """, unsafe_allow_html=True)

    c_left, c_center, c_right = st.columns([1, 2.5, 1])
    with c_center:
        st.markdown(f"""
        <div style="background:{card_bg};border:1px solid {border_clr};border-radius:16px;padding:22px 26px;
                    box-shadow:0 12px 32px rgba(0,0,0,0.15);margin-bottom:14px;">
        """, unsafe_allow_html=True)

        auth_tab1, auth_tab2 = st.tabs([":material/key: Administrator Login", ":material/badge: Register with Company ID"])

        # ── TAB 1: LOGIN ──
        with auth_tab1:
            with st.form("admin_login_form"):
                username_input = st.text_input("Username or Official Email", placeholder="e.g. admin or john@nassaucandy.com")
                password_input = st.text_input("Password", type="password", placeholder="Enter your password")
                remember_me = st.checkbox("Remember Me on this device", value=False)
                login_submitted = st.form_submit_button("Secure Sign In", icon=":material/lock:", use_container_width=True, type="primary")

                if login_submitted:
                    success, msg, u_dict = authenticate_user_db(
                        username_input, password_input, remember_me=remember_me
                    )
                    if success and u_dict:
                        st.session_state["admin_authenticated"] = True
                        st.session_state["admin_user"] = u_dict["username"]
                        st.session_state["user_full_name"] = u_dict["full_name"]
                        st.session_state["user_role"] = u_dict["role"]
                        st.session_state["session_token"] = u_dict["session_token"]
                        st.session_state["remember_me"] = remember_me
                        st.session_state["admin_last_activity"] = time.time()
                        st.success(f"Welcome back, {u_dict['full_name']} ({u_dict['role']})!")
                        time.sleep(0.4)
                        st.rerun()
                    else:
                        st.error(msg)

            last_login = get_last_successful_login()
            if last_login:
                st.caption(f'<span class="material-symbols-rounded" style="vertical-align:middle;font-size:.9rem;margin-right:3px;">schedule</span>Recent Login: {last_login.get("timestamp")} (User: {last_login.get("username")})', unsafe_allow_html=True)

        # ── TAB 2: COMPANY REGISTRATION ID ONBOARDING ──
        with auth_tab2:
            st.markdown("""
            <div style="font-size:.78rem;color:#9AA0B9;margin-bottom:10px;">
                Public registration is disabled. You must provide a company-issued <strong>Registration ID</strong> to establish an account.
            </div>
            """, unsafe_allow_html=True)

            with st.form("admin_register_form"):
                reg_id_input = st.text_input("Company Registration ID (Required)", placeholder="e.g. REG-ADMIN-NASSAU-9901")
                new_fullname = st.text_input("Full Name", placeholder="e.g. Sarah Jenkins")
                new_username = st.text_input("Desired Username", placeholder="e.g. sjenkins")
                new_email = st.text_input("Corporate Email", placeholder="e.g. sjenkins@nassaucandy.com")
                new_password = st.text_input("Account Password (min 8 chars)", type="password", placeholder="Choose strong password")
                new_role = st.selectbox("Requested Access Role", ["Administrator", "Analyst", "Viewer"], index=0)

                register_submitted = st.form_submit_button("Validate Key & Register Account", icon=":material/security:", use_container_width=True)

                if register_submitted:
                    if not reg_id_input or not new_username or not new_password or not new_email:
                        st.error("All registration fields are required.")
                    else:
                        reg_ok, reg_msg = register_admin_user(
                            registration_token=reg_id_input,
                            full_name=new_fullname,
                            username=new_username,
                            email=new_email,
                            password=new_password,
                            target_role=new_role,
                        )
                        if reg_ok:
                            st.success(reg_msg)
                            st.info("Registration Key has been redeemed and marked as USED. Please switch to the Login tab.")
                        else:
                            st.error(reg_msg)

        st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ADMIN CONSOLE
# ─────────────────────────────────────────────────────────────────────────────

def render(df: pd.DataFrame) -> None:
    theme = st.session_state.get("theme", "dark")
    palette = get_palette(theme)
    h1_clr = "#0F172A" if theme == "light" else "#E8EAED"
    sub_clr = "#64748B" if theme == "light" else "#9AA0B9"
    card_bg = "#FFFFFF" if theme == "light" else "rgba(30,33,48,0.9)"
    border_clr = "rgba(83,72,232,0.18)" if theme == "light" else "rgba(108,99,255,0.25)"

    # Check authentication
    if not check_admin_session():
        render_auth_portal(palette, theme)
        return

    admin_user = st.session_state.get("admin_user", "Administrator")
    user_role = st.session_state.get("user_role", "Administrator")
    config = load_business_config()

    is_full_admin = (user_role == "Administrator")
    is_analyst = (user_role == "Analyst")

    # Header Bar
    top_c1, top_c2 = st.columns([3, 1.4])
    with top_c1:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
            <span class="material-symbols-rounded" style="font-size:2.2rem;color:{palette['primary']};">admin_panel_settings</span>
            <div>
                <h1 style="font-size:1.85rem;font-weight:800;color:{h1_clr};margin:0;letter-spacing:-.02em;">
                    Enterprise Administration Console
                </h1>
                <div style="display:flex;align-items:center;gap:10px;margin-top:2px;">
                    <span style="background:rgba(67,233,123,0.15);color:{palette['accent']};padding:2px 8px;border-radius:6px;font-size:.72rem;font-weight:700;">
                        ● {user_role.upper()} SESSION
                    </span>
                    <span style="color:{sub_clr};font-size:.8rem;">
                        Logged in as <strong>{admin_user}</strong> • SQLite/PostgreSQL ORM Active
                    </span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with top_c2:
        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("Auto-Sync", icon=":material/sync:", use_container_width=True, help="Recalculate platform KPIs and invalidate cache"):
                recalculate_and_propagate(df, user=admin_user, reason="Manual Console Sync", config=config)
                st.toast("Platform synchronization complete.", icon=":material/check_circle:")
                st.rerun()
        with btn_c2:
            if st.button("Logout", icon=":material/logout:", use_container_width=True):
                sess_tok = st.session_state.get("session_token", "")
                terminate_session(sess_tok, username=admin_user)
                st.session_state["admin_authenticated"] = False
                st.session_state["admin_user"] = None
                st.session_state["user_role"] = None
                st.rerun()

    st.markdown("<hr style='border:none;height:1px;background:rgba(108,99,255,0.2);margin:12px 0 18px 0;'>", unsafe_allow_html=True)

    # Role-based restriction banner if Analyst/Viewer
    if not is_full_admin:
        st.info(f"**Role Restriction**: You are logged in as **{user_role}**. Administrative modifications, key generation, and schema mutations are view-only or restricted to Administrators.", icon=":material/info:")

    # Admin Tabs
    tabs = st.tabs([
        ":material/database: Dataset Management",
        ":material/table_chart: Interactive Data Grid",
        ":material/tune: Business & ML Settings",
        ":material/manage_accounts: Account & Security",
        ":material/history: Version History & Rollback",
        ":material/psychology: AI Admin Assistant",
    ])

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 1: DATASET MANAGEMENT & UPLOAD
    # ─────────────────────────────────────────────────────────────────────────
    with tabs[0]:
        active_master = pd.read_csv(FEATURED_DATA_FILE, encoding="utf-8") if FEATURED_DATA_FILE.exists() else df
        st.markdown(f'<div class="section-header" style="color:{h1_clr};">Dataset Ingestion & Schema Conformance</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle" style="color:{sub_clr};">Upload shipment batches via CSV or Excel (.xlsx/.xls). Supports Replace, Append, and Merge operations with automated pre-backup protection.</div>', unsafe_allow_html=True)

        # Flash notification from previous commit action
        notification = st.session_state.pop("admin_commit_notification", None)
        if notification:
            n_type = notification.get("type", "success")
            n_msg = notification.get("message", "")
            if n_type == "success":
                st.success(n_msg, icon=":material/check_circle:")
            elif n_type == "info":
                st.info(n_msg, icon=":material/info:")
            else:
                st.error(n_msg, icon=":material/error:")

        uploader_key = st.session_state.get("dataset_uploader_key", 0)
        up_c1, up_c2 = st.columns([2, 1.2])
        with up_c1:
            uploaded_file = st.file_uploader(
                "Select Structured Shipment File (CSV / Excel)",
                type=["csv", "xlsx", "xls"],
                key=f"admin_dataset_uploader_{uploader_key}",
                disabled=not is_full_admin,
            )
        with up_c2:
            st.markdown(f"""
            <div style="background:{card_bg};border:1px solid {border_clr};border-radius:12px;padding:14px 16px;margin-top:28px;">
                <div style="font-size:.78rem;font-weight:700;color:{palette['primary']};text-transform:uppercase;letter-spacing:.06em;">Active Master File</div>
                <div style="font-size:1.15rem;font-weight:800;color:{h1_clr};margin:4px 0;">{len(active_master):,} Active Rows</div>
                <div style="font-size:.74rem;color:{sub_clr};">{len(active_master.columns)} logistics attributes • Auto-sync on commit</div>
            </div>
            """, unsafe_allow_html=True)

        if uploaded_file is not None:
            try:
                # Reuse parsed DataFrame from session state if file has not changed
                cached_df = st.session_state.get("staged_upload_df", None)
                cached_filename = st.session_state.get("staged_filename", "")
                cached_size = st.session_state.get("staged_filesize", 0)

                if (
                    cached_df is not None
                    and cached_filename == uploaded_file.name
                    and cached_size == getattr(uploaded_file, "size", 0)
                ):
                    staged_df = cached_df
                else:
                    uploaded_file.seek(0)
                    if uploaded_file.name.endswith(".csv"):
                        try:
                            staged_df = pd.read_csv(uploaded_file, encoding="utf-8")
                        except UnicodeDecodeError:
                            uploaded_file.seek(0)
                            staged_df = pd.read_csv(uploaded_file, encoding="latin1")
                    else:
                        staged_df = pd.read_excel(uploaded_file)

                    st.session_state["staged_upload_df"] = staged_df
                    st.session_state["staged_filename"] = uploaded_file.name
                    st.session_state["staged_filesize"] = getattr(uploaded_file, "size", 0)

                st.markdown(f"""
                <div style="background:rgba(67,233,123,0.08);border:1px solid rgba(67,233,123,0.25);border-radius:10px;padding:12px 16px;margin:14px 0;">
                    <div style="font-weight:700;color:{palette['accent']};font-size:.88rem;">
                        <span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;margin-right:4px;">check_circle</span>Staged File Loaded: {uploaded_file.name} ({len(staged_df):,} rows × {len(staged_df.columns)} columns)
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Schema Validation
                core_expected = ["Order ID", "Ship Mode", "Product Name", "Sales", "Units"]
                missing = [c for c in core_expected if c not in staged_df.columns]

                sc1, sc2, sc3 = st.columns(3)
                with sc1:
                    st.metric("Detected Inbound Records", f"{len(staged_df):,}")
                with sc2:
                    st.metric("Required Schema Fit", f"{len(core_expected) - len(missing)} / {len(core_expected)}")
                with sc3:
                    st.metric("Total Attributes", f"{len(staged_df.columns)}")

                if missing:
                    st.warning(f"Warning: Missing required columns: {', '.join(missing)}", icon=":material/warning:")
                else:
                    st.success("File satisfies core logistics schema requirements.", icon=":material/check_circle:")

                st.markdown("##### Staged Data Preview (First 5 Rows)")
                st.dataframe(staged_df.head(5), use_container_width=True)

                if is_full_admin:
                    st.markdown(f"""
                    <div style="background:rgba(108,99,255,0.12);border:2px solid {palette['primary']};border-radius:12px;padding:16px 20px;margin:18px 0 14px 0;">
                        <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
                            <span class="material-symbols-rounded" style="font-size:1.6rem;color:{palette['primary']};">publish</span>
                            <div style="font-size:1.05rem;font-weight:800;color:{h1_clr};">
                                Ready to Apply Changes: Select a Commit Action Below
                            </div>
                        </div>
                        <div style="font-size:.84rem;color:{sub_clr};">
                            Your file is currently staged in preview. Click <strong>Replace Entire Dataset</strong> to overwrite the platform with this new data sheet, or <strong>Append Dataset</strong> to add these rows to existing data.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown("##### Commit Actions")
                    act_c1, act_c2, act_c3, act_c4 = st.columns(4)
                    with act_c1:
                        if st.button("Append Dataset", icon=":material/add_circle:", use_container_width=True):
                            combined = pd.concat([df, staged_df], ignore_index=True)
                            with st.spinner("Processing & appending records..."):
                                success, msg = recalculate_and_propagate(
                                    combined, user=admin_user, reason=f"Append {len(staged_df):,} rows from {uploaded_file.name}", config=config
                                )
                            if success:
                                st.session_state.pop("staged_upload_df", None)
                                st.session_state.pop("staged_filename", None)
                                st.session_state.pop("staged_filesize", None)
                                st.session_state["dataset_uploader_key"] = uploader_key + 1
                                st.session_state["admin_commit_notification"] = {
                                    "type": "success",
                                    "message": msg or f"Successfully appended {len(staged_df):,} records.",
                                }
                                st.rerun()
                            else:
                                st.error(msg)
                    with act_c2:
                        if st.button("Replace Entire Dataset", icon=":material/swap_horizontal_circle:", use_container_width=True, type="primary"):
                            with st.spinner(f"Replacing entire dataset with {len(staged_df):,} records..."):
                                success, msg = recalculate_and_propagate(
                                    staged_df, user=admin_user, reason=f"Replace master with {uploaded_file.name}", config=config
                                )
                            if success:
                                st.session_state.pop("staged_upload_df", None)
                                st.session_state.pop("staged_filename", None)
                                st.session_state.pop("staged_filesize", None)
                                st.session_state["dataset_uploader_key"] = uploader_key + 1
                                st.session_state["admin_commit_notification"] = {
                                    "type": "success",
                                    "message": msg or f"Platform successfully replaced with {len(staged_df):,} records.",
                                }
                                st.rerun()
                            else:
                                st.error(msg)
                    with act_c3:
                        if st.button("Merge / Update by Order ID", icon=":material/call_merge:", use_container_width=True):
                            if "Order ID" in staged_df.columns and "Order ID" in df.columns:
                                merged = df.copy()
                                merged.set_index("Order ID", inplace=True)
                                staged_idx = staged_df.copy().set_index("Order ID")
                                merged.update(staged_idx)
                                merged.reset_index(inplace=True)
                                with st.spinner("Merging and synchronizing..."):
                                    success, msg = recalculate_and_propagate(
                                        merged, user=admin_user, reason=f"Merged updates from {uploaded_file.name}", config=config
                                    )
                                if success:
                                    st.session_state.pop("staged_upload_df", None)
                                    st.session_state.pop("staged_filename", None)
                                    st.session_state.pop("staged_filesize", None)
                                    st.session_state["dataset_uploader_key"] = uploader_key + 1
                                    st.session_state["admin_commit_notification"] = {
                                        "type": "success",
                                        "message": msg or "Dataset successfully merged and synchronized.",
                                    }
                                    st.rerun()
                                else:
                                    st.error(msg)
                            else:
                                st.error("Both datasets must contain 'Order ID' for merge.")
                    with act_c4:
                        if st.button("Discard Staged Upload", icon=":material/cancel:", use_container_width=True):
                            st.session_state.pop("staged_upload_df", None)
                            st.session_state.pop("staged_filename", None)
                            st.session_state.pop("staged_filesize", None)
                            st.session_state["dataset_uploader_key"] = uploader_key + 1
                            st.session_state["admin_commit_notification"] = {
                                "type": "info",
                                "message": "Staged file upload discarded.",
                            }
                            st.rerun()
                else:
                    st.caption('<span class="material-symbols-rounded" style="vertical-align:middle;font-size:1rem;margin-right:3px;">lock</span>Dataset mutation operations require Administrator privilege.', unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Error parsing uploaded file: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 2: INTERACTIVE LIVE DATA GRID
    # ─────────────────────────────────────────────────────────────────────────
    with tabs[1]:
        st.markdown(f'<div class="section-header" style="color:{h1_clr};">Editable Data Grid & Record Maintenance</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle" style="color:{sub_clr};">In-memory editable grid with search, sort, filter, add/delete rows, and instant platform re-calculation.</div>', unsafe_allow_html=True)

        g_c1, g_c2, g_c3, g_c4 = st.columns([1.5, 1.2, 1.2, 1.2])
        with g_c1:
            q_search = st.text_input("Search Order ID / Product / City", placeholder="e.g. Wonka or CA-2024", key="grid_search")
        with g_c2:
            f_factory = st.selectbox("Factory", ["All"] + sorted(df["Factory"].dropna().unique().tolist()), key="grid_factory")
        with g_c3:
            f_mode = st.selectbox("Ship Mode", ["All"] + sorted(df["Ship Mode"].dropna().unique().tolist()), key="grid_mode")
        with g_c4:
            f_delay = st.selectbox("Delay Flag", ["All", "Delayed Only (True)", "On Time (False)"], key="grid_delay")

        grid_df = df.copy()
        if q_search:
            s_low = q_search.strip().lower()
            mask = (
                grid_df["Order ID"].astype(str).str.lower().str.contains(s_low, na=False) |
                grid_df["Product Name"].astype(str).str.lower().str.contains(s_low, na=False) |
                grid_df["City"].astype(str).str.lower().str.contains(s_low, na=False)
            )
            grid_df = grid_df[mask]
        if f_factory != "All":
            grid_df = grid_df[grid_df["Factory"] == f_factory]
        if f_mode != "All":
            grid_df = grid_df[grid_df["Ship Mode"] == f_mode]
        if f_delay == "Delayed Only (True)":
            grid_df = grid_df[grid_df["Delay Flag"] == True]
        elif f_delay == "On Time (False)":
            grid_df = grid_df[grid_df["Delay Flag"] == False]

        st.caption(f"Showing {len(grid_df):,} matching rows out of {len(df):,} total records.")

        edited_records = st.data_editor(
            grid_df,
            num_rows="dynamic" if is_full_admin else "fixed",
            use_container_width=True,
            height=420,
            disabled=not is_full_admin,
            key="master_data_editor",
        )

        grid_btn1, grid_btn2, grid_btn3 = st.columns([1.6, 1, 1.4])
        with grid_btn1:
            if is_full_admin:
                if st.button("Save Grid Changes & Auto-Synchronize", icon=":material/save:", type="primary", use_container_width=True):
                    try:
                        updated_master = df.copy()
                        if "Row ID" in edited_records.columns and "Row ID" in updated_master.columns:
                            updated_master.set_index("Row ID", inplace=True)
                            ed_idx = edited_records.set_index("Row ID")
                            updated_master.update(ed_idx)
                            updated_master.reset_index(inplace=True)
                        else:
                            updated_master.loc[edited_records.index] = edited_records

                        success, msg = recalculate_and_propagate(
                            updated_master, user=admin_user, reason="Live Grid Edits", config=config
                        )
                        if success:
                            st.success("Changes committed. Platform recalculated.", icon=":material/check_circle:")
                            st.rerun()
                        else:
                            st.error(msg)
                    except Exception as e:
                        st.error(f"Commit failed: {e}")
            else:
                st.caption("Editing disabled for non-administrators.")
        with grid_btn2:
            if st.button("Revert Edits", icon=":material/undo:", use_container_width=True):
                st.info("Uncommitted edits cleared.", icon=":material/info:")
                st.rerun()
        with grid_btn3:
            csv_data = edited_records.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Export Grid View (CSV)",
                data=csv_data,
                file_name="nassau_grid_export.csv",
                mime="text/csv",
                icon=":material/download:",
                use_container_width=True,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 3: BUSINESS & ML SETTINGS
    # ─────────────────────────────────────────────────────────────────────────
    with tabs[2]:
        st.markdown(f'<div class="section-header" style="color:{h1_clr};">Business Rules & ML Configuration</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle" style="color:{sub_clr};">Edit factory coordinates, product-factory mappings, SLA delay thresholds, and ML hyperparameters with automatic cache sync.</div>', unsafe_allow_html=True)

        # Sub-tabs for Business Settings
        s_tab1, s_tab2, s_tab3 = st.tabs([
            ":material/timer: SLA & Model Thresholds",
            ":material/factory: Factory Coordinates & SKU Mapping",
            ":material/trending_up: Forecast & UI Dashboard Settings",
        ])

        with s_tab1:
            with st.form("settings_form"):
                s_col1, s_col2 = st.columns(2)
                with s_col1:
                    st.markdown("##### SLA Delay Thresholds (Days)")
                    slas = config.get("sla_thresholds_days", {})
                    std_sla = st.number_input("Standard Class SLA", value=float(slas.get("Standard Class", 5.0)), min_value=1.0, max_value=15.0, step=0.5, disabled=not is_full_admin)
                    sec_sla = st.number_input("Second Class SLA", value=float(slas.get("Second Class", 3.0)), min_value=1.0, max_value=10.0, step=0.5, disabled=not is_full_admin)
                    fst_sla = st.number_input("First Class SLA", value=float(slas.get("First Class", 2.0)), min_value=0.5, max_value=7.0, step=0.5, disabled=not is_full_admin)
                    smd_sla = st.number_input("Same Day SLA", value=float(slas.get("Same Day", 1.0)), min_value=0.25, max_value=3.0, step=0.25, disabled=not is_full_admin)

                    st.markdown("##### Target KPI Goals")
                    kpis = config.get("kpi_targets", {})
                    target_del = st.slider("Target Maximum Delay Rate (%)", 10.0, 60.0, float(kpis.get("target_delay_rate_pct", 25.0)), step=1.0, disabled=not is_full_admin)
                    target_lt = st.slider("Target Lead Time (Days)", 1.0, 8.0, float(kpis.get("target_avg_lead_time_days", 3.5)), step=0.1, disabled=not is_full_admin)

                with s_col2:
                    st.markdown("##### Route Efficiency Weights")
                    eff_w = config.get("efficiency_weights", {})
                    del_w = st.slider("Delay Rate Penalty (w₁)", 0.0, 1.0, float(eff_w.get("delay_weight", 0.6)), step=0.05, disabled=not is_full_admin)
                    lt_w = round(1.0 - del_w, 2)
                    st.info(f"Complementary Lead Time Weight (w₂): **{lt_w}**")

                    st.markdown("##### Machine Learning Settings")
                    ml_cfg = config.get("ml_settings", {})
                    rf_trees = st.number_input("Random Forest Estimators", value=int(ml_cfg.get("random_forest_estimators", 100)), min_value=10, max_value=500, step=10, disabled=not is_full_admin)
                    test_split = st.slider("Test Split Ratio", 0.1, 0.4, float(ml_cfg.get("test_size", 0.2)), step=0.05, disabled=not is_full_admin)

                st.markdown("---")
                if is_full_admin:
                    save_settings_btn = st.form_submit_button("Save SLA & ML Settings", icon=":material/save:", type="primary", use_container_width=True)
                    if save_settings_btn:
                        config["sla_thresholds_days"] = {
                            "Standard Class": std_sla,
                            "Second Class": sec_sla,
                            "First Class": fst_sla,
                            "Same Day": smd_sla,
                        }
                        config["kpi_targets"] = {
                            "target_delay_rate_pct": target_del,
                            "target_avg_lead_time_days": target_lt,
                            "target_efficiency_score": 0.75,
                        }
                        config["efficiency_weights"] = {
                            "delay_weight": del_w,
                            "lead_time_weight": lt_w,
                        }
                        config["ml_settings"] = {
                            "random_forest_estimators": rf_trees,
                            "test_size": test_split,
                            "random_state": 42,
                        }

                        save_business_config(config, user=admin_user)
                        success, msg = recalculate_and_propagate(
                            df, user=admin_user, reason="Update SLA & ML Settings", config=config
                        )
                        if success:
                            st.success("SLA & ML settings persisted and platform refreshed.", icon=":material/check_circle:")
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.caption("Settings modifications are restricted to Administrators.")

        with s_tab2:
            st.markdown("##### Production Factory GPS Coordinates")
            coords_dict = config.get("factory_coordinates", FACTORY_COORDINATES)
            coords_df = pd.DataFrame([
                {"Factory": f, "Latitude": lat, "Longitude": lon}
                for f, (lat, lon) in coords_dict.items()
            ])
            edited_coords = st.data_editor(
                coords_df,
                num_rows="dynamic" if is_full_admin else "fixed",
                use_container_width=True,
                disabled=not is_full_admin,
                key="editor_factory_coords",
            )

            st.markdown("##### Product to Factory Allocation Mappings")
            prod_map_dict = config.get("product_factory_map", PRODUCT_FACTORY_MAP)
            prod_map_df = pd.DataFrame([
                {"Product Name": p, "Factory": f}
                for p, f in prod_map_dict.items()
            ])
            edited_prod_map = st.data_editor(
                prod_map_df,
                num_rows="dynamic" if is_full_admin else "fixed",
                use_container_width=True,
                disabled=not is_full_admin,
                key="editor_prod_mappings",
            )

            if is_full_admin:
                if st.button("Save Factory & Product Mappings", icon=":material/save:", type="primary", use_container_width=True):
                    new_coords = {}
                    for _, row in edited_coords.iterrows():
                        if pd.notna(row["Factory"]) and str(row["Factory"]).strip():
                            new_coords[str(row["Factory"]).strip()] = [float(row["Latitude"]), float(row["Longitude"])]

                    new_pm = {}
                    for _, row in edited_prod_map.iterrows():
                        if pd.notna(row["Product Name"]) and str(row["Product Name"]).strip():
                            new_pm[str(row["Product Name"]).strip()] = str(row["Factory"]).strip()

                    config["factory_coordinates"] = new_coords
                    config["product_factory_map"] = new_pm
                    save_business_config(config, user=admin_user)

                    success, msg = recalculate_and_propagate(
                        df, user=admin_user, reason="Update Factory & Product Mappings", config=config
                    )
                    if success:
                        st.success("Factory coordinates & product mappings synchronized across pipeline.", icon=":material/check_circle:")
                        st.rerun()
                    else:
                        st.error(msg)

        with s_tab3:
            st.markdown("##### Demand Forecast Settings")
            f_cfg = config.get("forecast_settings", {})
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                f_horizon = st.number_input("Forecast Horizon (Months)", min_value=1, max_value=24, value=int(f_cfg.get("default_horizon_months", 6)), disabled=not is_full_admin)
            with f_col2:
                f_conf = st.slider("Confidence Interval", 0.80, 0.99, float(f_cfg.get("confidence_level", 0.95)), step=0.01, disabled=not is_full_admin)

            st.markdown("##### Dashboard Visualizations")
            v_cfg = config.get("visualization_settings", {})
            v_col1, v_col2 = st.columns(2)
            with v_col1:
                v_sankey = st.checkbox("Enable Sankey Route Diagrams", value=bool(v_cfg.get("enable_sankey", True)), disabled=not is_full_admin)
            with v_col2:
                v_anim = st.checkbox("Enable Chart Micro-animations", value=bool(v_cfg.get("enable_animations", True)), disabled=not is_full_admin)

            if is_full_admin:
                if st.button("Save Forecast & Dashboard Preferences", icon=":material/save:", use_container_width=True):
                    config["forecast_settings"] = {
                        "default_horizon_months": f_horizon,
                        "confidence_level": f_conf,
                    }
                    config["visualization_settings"] = {
                        "enable_sankey": v_sankey,
                        "enable_animations": v_anim,
                        "default_chart_theme": "dark",
                    }
                    save_business_config(config, user=admin_user)
                    st.success("Preferences updated.", icon=":material/check_circle:")
                    st.rerun()

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 4: ACCOUNT & CREDENTIAL SECURITY
    # ─────────────────────────────────────────────────────────────────────────
    with tabs[3]:
        st.markdown(f'<div class="section-header" style="color:{h1_clr};">Administrator Account & Credential Security</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle" style="color:{sub_clr};">Manage your administrator profile, security passphrase, and view authorization status.</div>', unsafe_allow_html=True)

        prof_c1, prof_c2 = st.columns([1.5, 2])
        with prof_c1:
            st.markdown(f"""
            <div style="background:{card_bg};border:1px solid {border_clr};border-radius:12px;padding:20px;margin-bottom:14px;">
                <div style="font-size:1.1rem;font-weight:700;color:{h1_clr};">{st.session_state.get('user_full_name', admin_user)}</div>
                <div style="font-size:.82rem;color:{palette['primary']};font-weight:600;margin-top:2px;">Role: {user_role}</div>
                <hr style="border:none;height:1px;background:rgba(108,99,255,0.2);margin:12px 0;">
                <div style="font-size:.78rem;color:{sub_clr};">Username: <strong>{admin_user}</strong></div>
                <div style="font-size:.78rem;color:{sub_clr};margin-top:4px;">Inactivity Timeout: <strong>15 Minutes</strong></div>
                <div style="font-size:.78rem;color:{sub_clr};margin-top:4px;">Authority Model: <strong>Business Operations</strong></div>
            </div>
            """, unsafe_allow_html=True)

        with prof_c2:
            st.markdown("##### Change Security Passphrase")
            with st.form("admin_change_pwd_form"):
                cur_pwd = st.text_input("Current Password", type="password")
                new_pwd = st.text_input("New Password (min 8 characters)", type="password")
                cfm_pwd = st.text_input("Confirm New Password", type="password")
                pwd_sub = st.form_submit_button("Update Password", icon=":material/lock_reset:", type="primary")

                if pwd_sub:
                    if not cur_pwd or not new_pwd:
                        st.error("All password fields are required.")
                    elif new_pwd != cfm_pwd:
                        st.error("New password and confirmation do not match.")
                    else:
                        ok, msg = update_admin_password_db(
                            username=admin_user,
                            current_password=cur_pwd,
                            new_password=new_pwd,
                            confirm_password=cfm_pwd,
                        )
                        if ok:
                            st.success(msg)
                            # Immediately terminate active session state
                            st.session_state["admin_authenticated"] = False
                            st.session_state["admin_user"] = None
                            st.session_state["session_token"] = None
                            st.info("Please sign in with your updated password.", icon=":material/info:")
                            time.sleep(1.2)
                            st.rerun()
                        else:
                            st.error(msg)

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 5: DATASET VERSION CONTROL & ROLLBACK
    # ─────────────────────────────────────────────────────────────────────────
    with tabs[4]:
        st.markdown(f'<div class="section-header" style="color:{h1_clr};">Dataset Version Control & Historical Snapshots</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle" style="color:{sub_clr};">Automatic pre-change snapshots created before every edit, append, or replace. Supports one-click rollback and version downloads.</div>', unsafe_allow_html=True)

        if is_full_admin:
            snap_c1, snap_c2 = st.columns([3, 1])
            with snap_c1:
                snap_note = st.text_input("Manual Snapshot Description", placeholder="e.g. End of Quarter Logistics Audit Baseline")
            with snap_c2:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                if st.button("Capture Snapshot", icon=":material/camera:", use_container_width=True):
                    note = snap_note.strip() if snap_note else "Manual Snapshot"
                    vid = create_dataset_backup(note, user=admin_user)
                    if vid:
                        st.success(f"Captured snapshot {vid}", icon=":material/check_circle:")
                        st.rerun()

        versions = list_dataset_versions()
        if not versions:
            st.info("No snapshots recorded yet.", icon=":material/info:")
        else:
            for ver in versions:
                v_c1, v_c2, v_c3 = st.columns([3, 1, 1.2])
                with v_c1:
                    st.markdown(f"""
                    <div style="background:{card_bg};border:1px solid {border_clr};border-radius:10px;padding:10px 14px;margin-bottom:6px;">
                        <div style="font-weight:700;color:{palette['primary']};font-size:.85rem;">
                            <span class="material-symbols-rounded" style="vertical-align:middle;font-size:1rem;margin-right:4px;">label</span>{ver.get('version_id')} • <span style="color:{h1_clr};">{ver.get('description')}</span>
                        </div>
                        <div style="font-size:.74rem;color:{sub_clr};margin-top:2px;">
                            Created: <strong>{ver.get('timestamp')}</strong> by {ver.get('author')} • {ver.get('row_count', 0):,} Rows
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                with v_c2:
                    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                    if is_full_admin:
                        if st.button("Rollback", icon=":material/history:", key=f"btn_rb_{ver['version_id']}", use_container_width=True):
                            ok, msg = rollback_dataset_version(ver['version_id'], user=admin_user)
                            if ok:
                                st.success(msg, icon=":material/check_circle:")
                                st.rerun()
                            else:
                                st.error(msg)
                with v_c3:
                    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                    snap_path = ROOT / ver.get('folder', '') / "featured_data.csv"
                    if snap_path.exists():
                        st.download_button(
                            "Download CSV",
                            data=snap_path.read_bytes(),
                            file_name=f"{ver['version_id']}_featured.csv",
                            mime="text/csv",
                            icon=":material/download:",
                            key=f"dl_{ver['version_id']}",
                            use_container_width=True,
                        )

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 6: SMART AI ADMIN ASSISTANT
    # ─────────────────────────────────────────────────────────────────────────
    with tabs[5]:
        st.markdown(f'<div class="section-header" style="color:{h1_clr};">Smart AI Data Quality Diagnostics</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle" style="color:{sub_clr};">Heuristic diagnostic engine detecting missing values, duplicates, date chronology errors, negative lead times, and outliers.</div>', unsafe_allow_html=True)

        health = analyze_dataset_health(df)
        score = health["health_score"]
        summ = health["summary"]

        h_c1, h_c2, h_c3, h_c4 = st.columns(4)
        with h_c1:
            st.metric("Data Quality Score", f"{score} / 100")
        with h_c2:
            st.metric("Total Null Cells", f"{summ.get('total_nulls', 0):,}")
        with h_c3:
            st.metric("Duplicate Records", f"{summ.get('duplicate_count', 0):,}")
        with h_c4:
            st.metric("Inverted Dates", f"{summ.get('date_inversions', 0):,}")

        issues = health.get("issues", [])
        recommendations = health.get("recommendations", [])

        if is_full_admin and recommendations:
            st.markdown("---")
            if st.button("Apply All Recommended Fixes Atomically", icon=":material/bolt:", type="primary", use_container_width=True):
                fixed_df, fix_logs = apply_all_recommendations(df)
                success, msg = recalculate_and_propagate(
                    fixed_df, user=admin_user, reason="AI Batch Remediation (Fix All)", config=config
                )
                if success:
                    st.success(f"Applied fixes: {'; '.join(fix_logs[:3])}. Platform recalculated.", icon=":material/check_circle:")
                    st.rerun()
                else:
                    st.error(msg)

        st.markdown("##### Detected Issues & Anomaly Items")
        if not issues:
            st.success("All logistics records satisfy schema, integrity, and chronological sanity rules.", icon=":material/verified_user:")
        else:
            for iss in issues:
                badge_clr = palette['danger'] if iss['severity'] == "High" else palette['warning']
                st.markdown(f"""
                <div style="background:{card_bg};border:1px solid {border_clr};border-left:4px solid {badge_clr};
                            border-radius:10px;padding:12px 16px;margin-bottom:10px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-weight:700;color:{h1_clr};font-size:.88rem;">{iss['title']}</span>
                        <span style="background:rgba(252,92,125,0.15);color:{badge_clr};padding:2px 8px;border-radius:6px;font-size:.7rem;font-weight:700;">
                            {iss['severity']}
                        </span>
                    </div>
                    <div style="color:{sub_clr};font-size:.8rem;margin:4px 0;">{iss['description']}</div>
                    <div style="color:#9AA0B9;font-size:.75rem;"><strong>Impact:</strong> {iss['impact']}</div>
                </div>
                """, unsafe_allow_html=True)

        if recommendations:
            st.markdown("##### Individual Remediation Actions")
            for rec in recommendations:
                r_c1, r_c2 = st.columns([3, 1])
                with r_c1:
                    st.markdown(f"**{rec['title']}** — *{rec['description']}*")
                with r_c2:
                    if is_full_admin:
                        if st.button("Apply Fix", icon=":material/bolt:", key=f"fix_{rec['id']}", use_container_width=True):
                            f_df, f_msg = apply_recommendation_fix(df, rec['id'])
                            success, p_msg = recalculate_and_propagate(
                                f_df, user=admin_user, reason=f"AI Fix ({rec['title']})", config=config
                            )
                            if success:
                                st.success(f"{f_msg} System synchronized.", icon=":material/check_circle:")
                                st.rerun()
                            else:
                                st.error(p_msg)


# Direct script execution fallback
_df = st.session_state.get("df_filtered", None)
if _df is None:
    from src.utils import ensure_dirs
    ensure_dirs()
    if FEATURED_DATA_FILE.exists():
        _df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])
    else:
        _df = pd.DataFrame()

render(_df)
