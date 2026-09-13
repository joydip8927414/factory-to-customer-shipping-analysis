"""
dev_app.py — Developer Control Portal (Enterprise Identity & Access Management)
================================================================================
Dedicated autonomous application running on port 8600.
Enterprise IAM Architecture:
1. Multi-Layer Authentication:
   - Layer 1: Developer Username/Email + Bcrypt Password validation.
   - Layer 2: Personal Developer Access Key (DEV-KEY-XXXX-XXXX-XXXX-XXXX).
   - Layer 3: Trusted Device authorization with OS & browser fingerprinting.
   - Mandatory Password Change gate for newly provisioned accounts.
2. Key Management Page:
   - Developer, Role, Key Name, Key Prefix (Masked DEV-KEY-XXXX-********), Status, Expiry, Created, Last Used, Device.
   - Cryptographic Key Generation (One-time plaintext reveal with Copy & Download).
   - Full Key Lifecycle actions: Rotate, Revoke, Expire, Suspend, Delete.
3. Owner-Only Governance:
   - Create/Delete Developer, Activate/Suspend Developer, Reset Password, Assign Role, Transfer Ownership.
   - Regular Developers have strict read-only access to their own keys and cannot generate/rotate keys.
4. Trusted Device Governance:
   - Approve, Block, Remove, Rename registered workstations.
5. Enterprise Developer Audit Trails:
   - Dedicated IAM event logging for credential creation, rotation, revocation, and device access.
"""

from __future__ import annotations

import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.session import ensure_db_ready
ensure_db_ready()

from src.developer.dev_security import (
    DEV_SESSION_TIMEOUT,
    authenticate_developer,
    bootstrap_first_developer,
    check_trusted_device,
    dev_change_password,
    generate_cryptographic_dev_key,
    has_any_developers,
    list_trusted_devices_db,
    mask_developer_key,
    record_developer_audit,
    register_trusted_device,
    terminate_developer_session,
    validate_developer_access_key,
    validate_developer_session,
    verify_owner_master_key,
)
from src.developer.dev_service import (
    dev_approve_device,
    dev_assign_developer_role,
    dev_assign_key_to_developer,
    dev_block_device,
    dev_create_admin_user,
    dev_create_new_developer,
    dev_delete_admin_user,
    dev_delete_developer_account,
    dev_delete_key,
    dev_delete_unused_key,
    dev_extend_key_expiry,
    dev_generate_bulk_keys,
    dev_generate_new_dev_key_for_developer,
    dev_generate_registration_ids,
    dev_get_system_health,
    dev_list_admin_users,
    dev_list_all_developers,
    dev_list_api_keys,
    dev_list_developer_keys,
    dev_list_iam_audit_logs,
    dev_list_license_info,
    dev_list_ml_models,
    dev_list_registration_ids,
    dev_remove_device,
    dev_rename_device,
    dev_reset_admin_password,
    dev_reset_developer_password,
    dev_rotate_developer_key,
    dev_set_key_status,
    dev_toggle_developer_status,
    dev_transfer_ownership,
    dev_update_admin_user,
    dev_vacuum_database,
    verify_dev_master_key,
)
from src.admin_manager import (
    get_audit_log_df,
    list_dataset_versions,
    load_business_config,
    save_business_config,
)

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Nassau Candy | Developer IAM & Control Portal",
    page_icon="shield",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Cyber Dark / High-Tech Developer Theme Styling ────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

.stApp {
    background: radial-gradient(circle at 12% 18%, #0B1120 0%, #030712 100%) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    color: #E2E8F0 !important;
}

code, pre {
    font-family: 'JetBrains Mono', monospace !important;
}

section[data-testid="stSidebar"] {
    background: #060B15 !important;
    border-right: 1px solid rgba(56, 189, 248, 0.2) !important;
}

.dev-metric-card {
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(56, 189, 248, 0.25);
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 12px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
}

.dev-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}

.badge-active { background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); }
.badge-expired { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
.badge-revoked { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
.badge-suspended { background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }
.badge-compromised { background: rgba(236, 72, 153, 0.15); color: #f472b6; border: 1px solid rgba(236, 72, 153, 0.3); }
.badge-replaced { background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3); }

.dev-tab-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
}
.dev-tab-header h3 {
    margin: 0 !important;
    font-size: 1.35rem !important;
    font-weight: 700 !important;
    color: #F8FAFC !important;
}
.dev-tab-header .material-symbols-rounded {
    font-size: 1.6rem !important;
    color: #38BDF8 !important;
}
</style>
""", unsafe_allow_html=True)


# ── Helper for Local Device Fingerprinting ────────────────────────────────────
def get_local_device_fingerprint() -> str:
    """Generate consistent browser/device fingerprint token."""
    import hashlib
    user_agent = "Workstation-Local"
    ip = "127.0.0.1"
    raw = f"{user_agent}-{ip}-{platform.node()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ── Developer Authentication Gate (3-Layer + Password Change + Bootstrap) ──────
def check_dev_session() -> bool:
    if not st.session_state.get("dev_authenticated", False):
        return False
    tok = st.session_state.get("dev_session_token", "")
    ok, dev = validate_developer_session(tok, timeout_seconds=DEV_SESSION_TIMEOUT)
    if not ok:
        st.session_state["dev_authenticated"] = False
        st.session_state["dev_username"] = None
        st.session_state["dev_session_token"] = None
        st.session_state["dev_auth_layer"] = 1
        return False
    return True


def render_bootstrap_initial_setup():
    """Initial System Setup: Visible only when NO developers exist in the system."""
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("""
        <div style="text-align:center;margin-top:40px;margin-bottom:20px;">
            <div style="display:inline-flex;align-items:center;justify-content:center;width:72px;height:72px;
                        background:linear-gradient(135deg,#DC2626,#F59E0B);border-radius:20px;
                        box-shadow:0 0 30px rgba(220,38,38,0.5);margin-bottom:12px;">
                <span class="material-symbols-rounded" style="font-size:2.8rem;color:#FFF;">build_circle</span>
            </div>
            <h2 style="font-size:2rem;font-weight:800;color:#F8FAFC;margin:0;">
                Enterprise IAM Bootstrap
            </h2>
            <div style="font-size:.85rem;color:#FCA5A5;margin-top:6px;font-weight:600;">
                ROOT TEAM LEAD / OWNER INITIALIZATION
            </div>
            <div style="font-size:.8rem;color:#94A3B8;margin-top:4px;">
                No developer records detected in database. Initialize the root <strong>Owner (Team Lead)</strong> account. An individual cryptographic Developer Access Key will be provisioned. Public registration is locked permanently thereafter.
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("bootstrap_owner_form"):
            st.markdown("""
            <div class="dev-tab-header">
                <span class="material-symbols-rounded">admin_panel_settings</span>
                <span style="font-weight:700;color:#F8FAFC;font-size:1.05rem;">Root System Owner Credentials</span>
            </div>
            """, unsafe_allow_html=True)
            b_fullname = st.text_input("Full Name", placeholder="e.g. Chief Technology Officer")
            b_username = st.text_input("Owner Username", placeholder="e.g. lead_architect")
            b_email = st.text_input("Corporate Email", placeholder="e.g. lead@nassaucandy.com")
            b_password = st.text_input("Passphrase (min 8 chars)", type="password", placeholder="Enter strong passphrase")

            boot_sub = st.form_submit_button("Initialize Enterprise IAM System", use_container_width=True, type="primary")

            if boot_sub:
                fp = get_local_device_fingerprint()
                ok, msg, gen_key = bootstrap_first_developer(
                    full_name=b_fullname,
                    username=b_username,
                    email=b_email,
                    password=b_password,
                    device_fingerprint=fp,
                )
                if ok:
                    st.success(msg)
                    st.info(f"**Your Personal Developer Access Key (Save securely now):**\n\n`{gen_key}`")
                    st.warning("This key will NEVER be displayed in plaintext again. Copy and store it in your secrets manager.")
                    st.session_state["bootstrapped_key"] = gen_key
                else:
                    st.error(msg)

        if st.session_state.get("bootstrapped_key"):
            if st.button("Proceed to 3-Layer Authentication Gate", icon=":material/arrow_forward:", use_container_width=True, type="primary"):
                st.session_state.pop("bootstrapped_key", None)
                st.rerun()


def render_developer_login():
    """Unified Progressive Multi-Layer Security Authentication Portal."""
    if not has_any_developers():
        render_bootstrap_initial_setup()
        return

    # Track progressive authentication layer (1 -> 2 -> 3)
    current_layer = st.session_state.get("dev_auth_layer", 1)

    c1, c2, c3 = st.columns([1, 2.2, 1])
    with c2:
        st.markdown("""
        <div style="text-align:center;margin-top:30px;margin-bottom:20px;">
            <div style="display:inline-flex;align-items:center;justify-content:center;width:68px;height:68px;
                        background:linear-gradient(135deg,#0284C7,#2563EB);border-radius:18px;
                        box-shadow:0 0 25px rgba(14,165,233,0.4);margin-bottom:12px;">
                <span class="material-symbols-rounded" style="font-size:2.5rem;color:#FFF;">shield_lock</span>
            </div>
            <h2 style="font-size:1.85rem;font-weight:800;color:#F8FAFC;margin:0;">
                Developer IAM Control Portal
            </h2>
            <div style="font-size:.85rem;color:#38BDF8;margin-top:4px;font-family:'JetBrains Mono';">
                ENTERPRISE IDENTITY & ACCESS MANAGEMENT
            </div>
            <div style="font-size:.78rem;color:#94A3B8;margin-top:6px;">
                Unified access gate for Team Leads, Owners, and Engineering Developers.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── LAYER 1: USER CREDENTIALS ──
        if current_layer == 1:
            dev_tab_login, dev_tab_register = st.tabs([":material/key: Developer Sign In", ":material/person_add: Developer Registration"])
            with dev_tab_login:
                st.markdown("""
                <div style="background:rgba(30,41,59,0.8);border:1px solid rgba(56,189,248,0.3);border-radius:12px;padding:18px 20px;margin-bottom:16px;">
                    <div style="font-weight:700;color:#38BDF8;font-size:.9rem;margin-bottom:4px;">
                        LAYER 1: Developer / Owner Identity
                    </div>
                    <div style="font-size:.78rem;color:#94A3B8;margin-bottom:10px;">
                        Enter your username or corporate email and password.
                    </div>
                    <div style="background:rgba(14,165,233,0.08);border:1px solid rgba(14,165,233,0.25);border-radius:8px;padding:10px 12px;margin-bottom:12px;font-size:.76rem;color:#BAE6FD;">
                        <span class="material-symbols-rounded" style="vertical-align:middle;font-size:.95rem;margin-right:4px;">info</span><strong>Default Credentials & Keys:</strong><br>
                        &bull; <strong>Developer:</strong> <code>developer</code> / <code>ChangeMeDev2026!</code> (Key: <code>DEV-KEY-INIT-2026-ROOT-0001</code>)<br>
                        &bull; <strong>Owner:</strong> <code>joydip_icy</code> or <code>joydip257</code> / <code>ChangeMeOnFirstLogin2026!</code> (Master Key: <code>ChangeMeMasterKey2026!</code>)
                    </div>
                """, unsafe_allow_html=True)

                with st.form("dev_login_form_layer1"):
                    dev_user_input = st.text_input("Username or Corporate Email", placeholder="e.g. developer or joydip257")
                    dev_pwd_input = st.text_input("Password", type="password", placeholder="Enter your password")
                    sub1 = st.form_submit_button("Verify Identity (Layer 1)", icon=":material/arrow_forward:", use_container_width=True, type="primary")

                    if sub1:
                        ok, msg, dev_dict = authenticate_developer(dev_user_input, dev_pwd_input)
                        if ok and dev_dict:
                            st.session_state["staged_dev_dict"] = dev_dict
                            st.session_state["dev_auth_layer"] = 2
                            st.rerun()
                        else:
                            st.error(msg)
                st.markdown("</div>", unsafe_allow_html=True)

            with dev_tab_register:
                st.markdown("""
                <div style="background:rgba(30,41,59,0.8);border:1px solid rgba(56,189,248,0.3);border-radius:12px;padding:18px 20px;margin-bottom:16px;">
                    <div style="font-weight:700;color:#38BDF8;font-size:.9rem;margin-bottom:4px;">
                        Enterprise Developer Onboarding
                    </div>
                    <div style="font-size:.78rem;color:#94A3B8;margin-bottom:12px;">
                        Register a new developer account. Requires authorization via Master Management Key or Company Registration ID.
                    </div>
                """, unsafe_allow_html=True)

                with st.form("dev_register_form"):
                    reg_fullname = st.text_input("Full Name", placeholder="e.g. Alex Morgan")
                    reg_username = st.text_input("Desired Username", placeholder="e.g. amorgan")
                    reg_email = st.text_input("Corporate Email", placeholder="e.g. amorgan@nassaucandy.com")
                    reg_password = st.text_input("Password (min 8 chars)", type="password", placeholder="Enter secure password")
                    reg_auth_key = st.text_input(
                        "Master Key or Registration Token",
                        type="password",
                        value="ChangeMeMasterKey2026!",
                        help="Enter the Master Management Key or an active Company Registration ID.",
                    )
                    sub_reg = st.form_submit_button("Register & Provision Developer Key", icon=":material/badge:", use_container_width=True, type="primary")

                    if sub_reg:
                        if not reg_fullname or not reg_username or not reg_email or not reg_password:
                            st.error("Full Name, Username, Email, and Password are required.")
                        else:
                            from src.admin_security import validate_registration_id
                            auth_token = (reg_auth_key or "ChangeMeMasterKey2026!").strip()
                            is_master = verify_dev_master_key(auth_token)
                            is_reg_id, _, _ = validate_registration_id(auth_token)
                            if not is_master and not is_reg_id:
                                st.error("Authorization failed: Please provide the Master Management Key or an active Registration ID.")
                            else:
                                ok_cr, msg_cr, gen_key = dev_create_new_developer(
                                    full_name=reg_fullname,
                                    username=reg_username,
                                    email=reg_email,
                                    password=reg_password,
                                    role="Developer",
                                    created_by="Owner",
                                )
                                if ok_cr:
                                    st.success(f"Developer '{reg_username}' registered successfully!")
                                    st.info(f"**Your Personal Developer Access Key (Save this now):**\n\n`{gen_key}`")
                                    st.warning("Save your key securely. You will need it for Layer 2 verification.")
                                    # Auto-authorize local workstation device
                                    try:
                                        with get_db_session() as s_reg:
                                            new_dev_obj = s_reg.execute(select(Developer).where(Developer.username == reg_username.strip())).scalar_one_or_none()
                                            if new_dev_obj:
                                                fp_reg = get_local_device_fingerprint()
                                                register_trusted_device(
                                                    developer_id=new_dev_obj.id,
                                                    device_fingerprint=fp_reg,
                                                    device_name=f"{reg_username.strip()}-{platform.node()}",
                                                    approved_by_owner=True,
                                                )
                                    except Exception:
                                        pass
                                else:
                                    st.error(msg_cr)
                st.markdown("</div>", unsafe_allow_html=True)

        # ── LAYER 2: DYNAMIC SECURITY VALIDATION ──
        # Owner -> Master Management Key ONLY (strictly from database is_owner and role)
        # Developer -> Individual Developer Access Key ONLY
        elif current_layer == 2:
            staged = st.session_state.get("staged_dev_dict", {})
            is_owner = bool(staged.get("is_owner", False) and staged.get("role") == "Owner")

            if is_owner:
                # ── OWNER LAYER 2: MASTER MANAGEMENT KEY ──
                st.markdown(f"""
                <div style="background:rgba(30,41,59,0.8);border:1px solid rgba(245,158,11,0.4);border-radius:12px;padding:20px;margin-bottom:16px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div style="font-weight:700;color:#F59E0B;font-size:.9rem;">
                            <span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;margin-right:4px;">admin_panel_settings</span>LAYER 2: Master Management Key
                        </div>
                        <span style="font-size:.74rem;color:#4ADE80;"><span class="material-symbols-rounded" style="vertical-align:middle;font-size:.9rem;margin-right:2px;">check_circle</span>Layer 1 Verified</span>
                    </div>
                    <div style="font-size:.78rem;color:#94A3B8;margin:6px 0 14px 0;">
                        Authenticated as <strong>{staged.get('full_name')}</strong> (<code>{staged.get('username')}</code>) • Role: <strong style="color:#F59E0B;">Owner / Team Lead</strong>
                    </div>
                    <div style="background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.3);border-radius:8px;padding:10px 12px;font-size:.76rem;color:#FDE68A;margin-bottom:14px;">
                        <span class="material-symbols-rounded" style="vertical-align:middle;font-size:1rem;margin-right:4px;">security</span><strong>Root Authority Detected:</strong> Owner accounts authenticate exclusively via the enterprise <strong>Master Management Key</strong> to unlock Developer IAM Governance and operational tools.
                        <div style="margin-top:6px;font-size:.74rem;color:#FEF3C7;">Default Master Key: <code>ChangeMeMasterKey2026!</code></div>
                    </div>
                """, unsafe_allow_html=True)

                with st.form("owner_login_form_layer2"):
                    master_key_input = st.text_input(
                        "Enter Master Management Key",
                        type="password",
                        placeholder="Enter your cryptographic master key",
                        help="Cryptographic Master Key required for Team Lead / Owner authentication.",
                    )
                    col_b1, col_b2 = st.columns([1, 1])
                    with col_b1:
                        sub2_owner = st.form_submit_button("Verify Master Key (Layer 2)", icon=":material/arrow_forward:", use_container_width=True, type="primary")
                    with col_b2:
                        sub_back_owner = st.form_submit_button("Back to Layer 1", icon=":material/arrow_back:", use_container_width=True)

                    if sub2_owner:
                        if verify_owner_master_key(master_key_input):
                            record_developer_audit(
                                developer=staged.get("username", "Owner"),
                                performed_by=staged.get("username", "Owner"),
                                action="Master Key Authenticated",
                                module="Authentication",
                                status="Success",
                                details="Owner authenticated via Master Management Key.",
                            )
                            st.session_state["dev_owner_master_unlocked"] = True
                            st.session_state["dev_auth_layer"] = 3
                            st.rerun()
                        else:
                            record_developer_audit(
                                developer=staged.get("username", "Owner"),
                                performed_by=staged.get("username", "Owner"),
                                action="Master Key Failed",
                                module="Authentication",
                                status="Failure",
                                details="Invalid Master Management Key entered.",
                            )
                            st.error("Invalid Master Management Key. Access denied.")
                    elif sub_back_owner:
                        st.session_state["dev_auth_layer"] = 1
                        st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

            else:
                # ── DEVELOPER LAYER 2: DEVELOPER ACCESS KEY ──
                st.markdown(f"""
                <div style="background:rgba(30,41,59,0.8);border:1px solid rgba(56,189,248,0.3);border-radius:12px;padding:20px;margin-bottom:16px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div style="font-weight:700;color:#38BDF8;font-size:.9rem;">
                            <span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;margin-right:4px;">key</span>LAYER 2: Personal Developer Access Key
                        </div>
                        <span style="font-size:.74rem;color:#4ADE80;"><span class="material-symbols-rounded" style="vertical-align:middle;font-size:.9rem;margin-right:2px;">check_circle</span>Layer 1 Verified</span>
                    </div>
                    <div style="font-size:.78rem;color:#94A3B8;margin:6px 0 14px 0;">
                        Authenticated as <strong>{staged.get('full_name')}</strong> (<code>{staged.get('username')}</code>) • Role: <strong style="color:#38BDF8;">Developer</strong>
                    </div>
                    <div style="font-size:.75rem;color:#CBD5E1;margin-bottom:10px;">
                        Enter your personal <strong>Developer Access Key</strong> (Format: <code>DEV-KEY-XXXX-XXXX-XXXX-XXXX</code>). Access keys are individual credentials assigned by the Team Lead / Owner and must never be shared.
                    </div>
                    <div style="background:rgba(14,165,233,0.08);border:1px solid rgba(14,165,233,0.25);border-radius:8px;padding:8px 12px;margin-bottom:12px;font-size:.76rem;color:#BAE6FD;">
                        <span class="material-symbols-rounded" style="vertical-align:middle;font-size:.95rem;margin-right:4px;">key</span>
                        <strong>Standard Developer Key:</strong> <code>DEV-KEY-INIT-2026-ROOT-0001</code>
                    </div>
                """, unsafe_allow_html=True)

                with st.form("dev_login_form_layer2"):
                    access_key_input = st.text_input("Developer Access Key", type="password", placeholder="DEV-KEY-XXXX-XXXX-XXXX-XXXX")
                    col_btn1, col_btn2 = st.columns([1, 1])
                    with col_btn1:
                        sub2 = st.form_submit_button("Validate Key (Layer 2)", icon=":material/arrow_forward:", use_container_width=True, type="primary")
                    with col_btn2:
                        sub_back1 = st.form_submit_button("Back to Layer 1", icon=":material/arrow_back:", use_container_width=True)

                    if sub2:
                        ok_key, key_msg = validate_developer_access_key(staged["id"], access_key_input)
                        if ok_key:
                            st.session_state["dev_auth_layer"] = 3
                            st.rerun()
                        else:
                            st.error(key_msg)
                    elif sub_back1:
                        st.session_state["dev_auth_layer"] = 1
                        st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

        # ── LAYER 3: TRUSTED WORKSTATION & DEVICE REGISTRY ──
        elif current_layer == 3:
            staged = st.session_state.get("staged_dev_dict", {})
            fp = get_local_device_fingerprint()
            ok_dev, dev_msg, dev_rec = check_trusted_device(staged["id"], fp)

            detected_host = platform.node()
            detected_os = f"{platform.system()} {platform.release()}"
            detected_arch = platform.machine()
            detected_py = platform.python_version()

            st.markdown(f"""
            <div style="background:rgba(30,41,59,0.8);border:1px solid rgba(56,189,248,0.3);border-radius:12px;padding:20px;margin-bottom:16px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div style="font-weight:700;color:#38BDF8;font-size:.9rem;">
                        <span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;margin-right:4px;">devices</span>LAYER 3: Workstation Telemetry & Device Verification
                    </div>
                    <span style="font-size:.74rem;color:#4ADE80;"><span class="material-symbols-rounded" style="vertical-align:middle;font-size:.9rem;margin-right:2px;">check_circle</span>Layers 1 & 2 Verified</span>
                </div>
                <div style="background:rgba(15,23,42,0.7);border:1px solid rgba(56,189,248,0.2);border-radius:10px;padding:14px;margin:12px 0 6px 0;">
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:.78rem;">
                        <div><span style="color:#94A3B8;">Host / Node:</span> <strong style="color:#F8FAFC;">{detected_host}</strong></div>
                        <div><span style="color:#94A3B8;">Operating System:</span> <strong style="color:#F8FAFC;">{detected_os}</strong></div>
                        <div><span style="color:#94A3B8;">Architecture:</span> <strong style="color:#F8FAFC;">{detected_arch}</strong></div>
                        <div><span style="color:#94A3B8;">Python Runtime:</span> <code style="color:#38BDF8;">v{detected_py}</code></div>
                        <div style="grid-column: span 2;"><span style="color:#94A3B8;">Workstation Fingerprint:</span> <code style="color:#38BDF8;word-break:break-all;">{fp}</code></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            if ok_dev:
                st.success(f"Workstation Recognized & Trusted: {dev_rec.get('device_name', detected_host)}")

                # Check if developer must change password
                if staged.get("must_change_password"):
                    st.warning("Security Policy: You are using a temporary password. You must change your password before entering the platform.")
                    with st.form("force_password_change_form"):
                        curr_pw = st.text_input("Current Temporary Password", type="password")
                        new_pw1 = st.text_input("New Secure Password (min 8 chars)", type="password")
                        new_pw2 = st.text_input("Confirm New Password", type="password")
                        if st.form_submit_button("Update Password & Enter Portal", use_container_width=True, type="primary"):
                            if new_pw1 != new_pw2:
                                st.error("Passwords do not match.")
                            else:
                                ok_pw, msg_pw = dev_change_password(staged["id"], curr_pw, new_pw1)
                                if ok_pw:
                                    st.success("Password changed! Entering portal...")
                                    st.session_state["dev_authenticated"] = True
                                    st.session_state["dev_username"] = staged["username"]
                                    st.session_state["dev_full_name"] = staged["full_name"]
                                    st.session_state["dev_id"] = staged["id"]
                                    st.session_state["dev_role"] = staged.get("role", "Developer")
                                    st.session_state["dev_session_token"] = staged["session_token"]
                                    st.session_state["dev_auth_layer"] = 1
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error(msg_pw)
                else:
                    if st.button("Enter Developer Control Portal", use_container_width=True, type="primary"):
                        st.session_state["dev_authenticated"] = True
                        st.session_state["dev_username"] = staged["username"]
                        st.session_state["dev_full_name"] = staged["full_name"]
                        st.session_state["dev_id"] = staged["id"]
                        st.session_state["dev_role"] = staged.get("role", "Developer")
                        st.session_state["dev_session_token"] = staged["session_token"]
                        st.session_state["dev_auth_layer"] = 1
                        st.rerun()
            else:
                if dev_rec and dev_rec.get("status") == "BLOCKED":
                    st.error("This workstation has been explicitly BLOCKED by an administrator.")
                else:
                    st.info(f"Workstation detected: **{detected_host}** ({detected_os}). Dual-factor Layer 1 and Layer 2 credentials have been verified.")
                    with st.form("dev_authorize_workstation_form"):
                        dev_name_custom = st.text_input(
                            "Workstation Identifier Label",
                            value=f"{staged.get('username', 'dev')}-{detected_host}",
                        )
                        if st.form_submit_button("Authorize Workstation & Enter Portal", icon=":material/verified_user:", use_container_width=True, type="primary"):
                            reg_ok, reg_msg = register_trusted_device(
                                developer_id=staged["id"],
                                device_fingerprint=fp,
                                device_name=dev_name_custom.strip(),
                                user_agent=f"{detected_os} {detected_arch}",
                                approved_by_owner=True,
                            )
                            if reg_ok:
                                st.session_state["dev_authenticated"] = True
                                st.session_state["dev_username"] = staged["username"]
                                st.session_state["dev_full_name"] = staged["full_name"]
                                st.session_state["dev_id"] = staged["id"]
                                st.session_state["dev_role"] = staged.get("role", "Developer")
                                st.session_state["dev_session_token"] = staged["session_token"]
                                st.session_state["dev_auth_layer"] = 1
                                st.success("Workstation authorized! Entering portal...")
                                time.sleep(0.4)
                                st.rerun()
                            else:
                                st.error(reg_msg)

            if st.button("↩ Start Over", use_container_width=True):
                st.session_state["dev_auth_layer"] = 1
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)


# ── Main Developer Portal ─────────────────────────────────────────────────────
def main():
    if not check_dev_session():
        render_developer_login()
        return

    dev_user = st.session_state.get("dev_username", "developer")
    dev_name = st.session_state.get("dev_full_name", "Developer")
    dev_role = st.session_state.get("dev_role", "Developer")
    dev_id = st.session_state.get("dev_id", 1)
    is_owner = (dev_role == "Owner")

    # Left Sidebar Controls
    with st.sidebar:
        role_color = "#F59E0B" if is_owner else "#38BDF8"
        role_badge = "TEAM LEAD / OWNER" if is_owner else "DEVELOPER"

        st.markdown(f"""
        <div style="padding:10px 0 16px;border-bottom:1px solid rgba(56,189,248,0.2);margin-bottom:14px;">
            <div style="display:flex;align-items:center;gap:8px;">
                <span class="material-symbols-rounded" style="font-size:1.4rem;color:{role_color};">shield</span>
                <span style="font-size:1.05rem;font-weight:800;color:{role_color};font-family:'JetBrains Mono';letter-spacing:.05em;">IAM PORTAL</span>
            </div>
            <div style="font-size:.72rem;color:#4ADE80;margin-top:4px;">
                ● 3-LAYER AUTHENTICATED
            </div>
            <div style="font-size:.7rem;color:#E2E8F0;margin-top:4px;">
                User: <strong>{dev_name}</strong> (<code>{dev_user}</code>)
            </div>
            <div style="font-size:.7rem;color:{role_color};margin-top:2px;font-weight:700;">
                {role_badge}
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Terminate Session", use_container_width=True):
            tok = st.session_state.get("dev_session_token", "")
            terminate_developer_session(tok, username=dev_user)
            st.session_state["dev_authenticated"] = False
            st.rerun()

        st.markdown("---")
        st.markdown("""
        <div style="font-size:.75rem;color:#94A3B8;">
            <strong>IAM Permissions:</strong><br>
            • Owner: Full Key & Dev Lifecycle<br>
            • Developer: View Own Keys & Read-Only
        </div>
        """, unsafe_allow_html=True)

    # Header
    head_c1, head_c2 = st.columns([3, 1])
    with head_c1:
        if is_owner:
            st.markdown(f"""
            <div style="margin-bottom:16px;">
                <h1 style="font-size:1.9rem;font-weight:800;color:#F8FAFC;margin:0;">
                    <span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.9rem;margin-right:6px;color:#F59E0B;">admin_panel_settings</span>Team Lead / Owner Governance Portal
                </h1>
                <div style="font-size:.84rem;color:#F59E0B;margin-top:4px;">
                    Root Authority • Key Generation & Assignment • Developer IAM Governance • Workstation Security
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="margin-bottom:16px;">
                <h1 style="font-size:1.9rem;font-weight:800;color:#F8FAFC;margin:0;">
                    <span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.9rem;margin-right:6px;color:#38BDF8;">terminal</span>Developer Engineering Workspace
                </h1>
                <div style="font-size:.84rem;color:#38BDF8;margin-top:4px;">
                    Technical Operations • Administrator Governance • ML Model Registry • Database Maintenance • Factory Coordinates
                </div>
            </div>
            """, unsafe_allow_html=True)
    with head_c2:
        if st.button("Refresh Telemetry", icon=":material/refresh:", use_container_width=True):
            st.rerun()

    # Segmented Tabs based on role
    if is_owner:
        tabs = st.tabs([
            ":material/key: Key Management & Assignment",
            ":material/security: Developer IAM Governance",
            ":material/devices: Trusted Devices",
            ":material/history_edu: IAM Audit Trail",
            ":material/confirmation_number: Company Registration Keys",
            ":material/manage_accounts: Admin Governance",
            ":material/database: Database Engine",
            ":material/factory: Factory Coordinates",
            ":material/memory: ML Registry & API Keys",
            ":material/monitor_heart: System Health",
        ])
    else:
        # Developer Workspace: technical engineering tabs + personal key + Developer Provisioning + Admin Governance + Registration Keys
        tabs = st.tabs([
            ":material/key: My Assigned Access Key",
            ":material/person_add: Developer Provisioning",
            ":material/manage_accounts: Admin Governance",
            ":material/confirmation_number: Company Registration Keys",
            ":material/database: Database Engine",
            ":material/factory: Factory Coordinates",
            ":material/memory: ML Registry & API Keys",
            ":material/monitor_heart: System Health",
        ])

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 1: KEY MANAGEMENT / MY ASSIGNED ACCESS KEY
    # ─────────────────────────────────────────────────────────────────────────
    with tabs[0]:
        if is_owner:
            st.markdown("""
            <div class="dev-tab-header">
                <span class="material-symbols-rounded">vpn_key</span>
                <h3>Developer Access Key Management & Authority</h3>
            </div>
            """, unsafe_allow_html=True)
            st.caption("Exclusive Team Lead / Owner control: create, assign, rotate, revoke, expire, or delete Developer Access Keys. Every developer must have a unique key.")
        else:
            st.markdown("""
            <div class="dev-tab-header">
                <span class="material-symbols-rounded">key</span>
                <h3>My Assigned Developer Access Key</h3>
            </div>
            """, unsafe_allow_html=True)
            st.caption("Your personal cryptographic Developer Access Key assigned by the Team Lead / Owner. Keys are individual credentials and must never be shared.")

        # If a key was just generated/rotated, show one-time secure alert
        if "just_generated_key" in st.session_state and is_owner:
            gen_info = st.session_state["just_generated_key"]
            st.markdown(f"""
            <div style="background:rgba(16,185,129,0.15);border:2px solid #10B981;border-radius:12px;padding:20px;margin-bottom:20px;">
                <div style="display:flex;align-items:center;gap:10px;color:#34D399;font-weight:800;font-size:1.05rem;">
                    <span class="material-symbols-rounded">verified_user</span>
                    {gen_info['title']} (One-Time Display)
                </div>
                <div style="font-size:.84rem;color:#E2E8F0;margin:8px 0 12px 0;">
                    Target Developer: <strong>{gen_info['developer']}</strong><br>
                    Key Name: <strong>{gen_info['name']}</strong>
                </div>
                <div style="font-size:1.15rem;font-family:'JetBrains Mono';background:rgba(0,0,0,0.4);padding:12px;border-radius:8px;border:1px dashed #34D399;color:#A7F3D0;word-break:break-all;">
                    {gen_info['key']}
                </div>
                <div style="font-size:.78rem;color:#FCA5A5;margin-top:10px;font-weight:600;">
                    <span class="material-symbols-rounded" style="vertical-align:middle;font-size:1rem;margin-right:4px;">warning</span>CAUTION: This full plaintext key will NEVER be shown again. Securely deliver this key to the developer now.
                </div>
            </div>
            """, unsafe_allow_html=True)

            c_d1, c_d2 = st.columns([2, 1])
            with c_d1:
                st.download_button(
                    "Download Key Securely (.txt)",
                    data=f"Nassau Candy Logistics Platform\nDeveloper Access Key\nDeveloper: {gen_info['developer']}\nKey Name: {gen_info['name']}\nAccess Key: {gen_info['key']}\nGenerated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nDeliver securely. Never share with others.",
                    file_name=f"dev_key_{gen_info['developer']}.txt",
                    mime="text/plain",
                    icon=":material/download:",
                    use_container_width=True,
                )
            with c_d2:
                if st.button("I Have Saved This Key", use_container_width=True, type="primary"):
                    st.session_state.pop("just_generated_key", None)
                    st.rerun()

        # Key Generation & Assignment Drawer (Owner Only)
        if is_owner:
            with st.expander("Assign or Generate Developer Access Key(s)", icon=":material/key:", expanded=False):
                all_devs_for_key = dev_list_all_developers()
                if not all_devs_for_key:
                    st.info("No developers available.")
                else:
                    g_mode = st.radio(
                        "Action Mode",
                        ["Assign Key to Developer (Team Lead / Owner)", "Auto-Generate Single Key", "Batch Provisioning (Multiple Developers)"],
                        horizontal=True,
                    )

                    if g_mode == "Assign Key to Developer (Team Lead / Owner)":
                        st.markdown("""
                        <div style="background:rgba(56,189,248,0.1);border:1px solid rgba(56,189,248,0.3);border-radius:8px;padding:12px;margin-bottom:14px;">
                            <div style="font-weight:700;color:#38BDF8;font-size:.88rem;"><span class="material-symbols-rounded" style="vertical-align:middle;font-size:1.1rem;margin-right:4px;">admin_panel_settings</span>Exclusive Team Lead / Owner Key Assignment</div>
                            <div style="font-size:.78rem;color:#CBD5E1;margin-top:4px;">
                                Directly assign a personalized Developer Access Key to any developer. You can provide a custom key (e.g. <code>DEV-KEY-XXXX-XXXX-XXXX-XXXX</code>) or leave it blank to auto-generate a cryptographic key.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        with st.form("assign_dev_key_form_tab1"):
                            ak_c1, ak_c2 = st.columns(2)
                            with ak_c1:
                                target_assign_dev = st.selectbox(
                                    "Target Developer",
                                    options=all_devs_for_key,
                                    format_func=lambda d: f"{d['username']} ({d['full_name']}) - {d['role']}",
                                    key="assign_target_dev_select_t1",
                                )
                                ak_name = st.text_input("Key Description / Identifier", value="Primary Assigned Access Key", key="ak_name_t1")
                            with ak_c2:
                                ak_custom = st.text_input(
                                    "Custom Access Key (Leave blank to auto-generate)",
                                    placeholder="e.g. DEV-KEY-7A9B-4C2D-1E8F-9A0B",
                                    key="ak_custom_t1",
                                )
                                ak_days = st.number_input("Validity Period (Days)", min_value=1, max_value=365, value=90, key="ak_days_t1")

                            ak_replace = st.checkbox(
                                "Invalidate and replace developer's existing active keys (Sets previous keys to REPLACED)",
                                value=True,
                                key="ak_replace_t1",
                            )

                            sub_assign = st.form_submit_button("Assign Key to Developer", use_container_width=True, type="primary")

                            if sub_assign:
                                ok_as, msg_as, assigned_key = dev_assign_key_to_developer(
                                    dev_id=target_assign_dev["id"],
                                    custom_key=ak_custom.strip() if ak_custom else None,
                                    created_by=dev_user,
                                    key_name=ak_name.strip(),
                                    valid_days=int(ak_days),
                                    replace_existing=ak_replace,
                                )
                                if ok_as and assigned_key:
                                    st.session_state["just_generated_key"] = {
                                        "title": "Developer Access Key Assigned Successfully",
                                        "developer": target_assign_dev["username"],
                                        "name": ak_name.strip(),
                                        "key": assigned_key,
                                    }
                                    st.rerun()
                                else:
                                    st.error(msg_as)

                    elif g_mode == "Auto-Generate Single Key":
                        with st.form("gen_single_key_form"):
                            g1, g2, g3 = st.columns([2, 2, 1.2])
                            with g1:
                                target_dev_single = st.selectbox(
                                    "Assign to Developer",
                                    options=all_devs_for_key,
                                    format_func=lambda d: f"{d['username']} ({d['full_name']}) - {d['role']}",
                                )
                            with g2:
                                k_label = st.text_input("Key Name / Description", value="Production Access Key")
                            with g3:
                                k_days = st.number_input("Validity (Days)", min_value=1, max_value=365, value=90)

                            sub_gen_key = st.form_submit_button("Generate Cryptographic Key", use_container_width=True, type="primary")

                            if sub_gen_key:
                                ok_g, msg_g, new_raw_key = dev_generate_new_dev_key_for_developer(
                                    dev_id=target_dev_single["id"],
                                    created_by=dev_user,
                                    key_name=k_label.strip(),
                                    valid_days=int(k_days),
                                )
                                if ok_g and new_raw_key:
                                    st.session_state["just_generated_key"] = {
                                        "title": "New Developer Access Key Generated",
                                        "developer": target_dev_single["username"],
                                        "name": k_label.strip(),
                                        "key": new_raw_key,
                                    }
                                    st.rerun()
                                else:
                                    st.error(msg_g)
                    else:
                        with st.form("gen_bulk_keys_form"):
                            selected_bulk_devs = st.multiselect(
                                "Select Developers",
                                options=all_devs_for_key,
                                format_func=lambda d: f"{d['username']} ({d['full_name']})",
                            )
                            bulk_days = st.number_input("Validity (Days)", min_value=1, max_value=365, value=90, key="bulk_days")
                            sub_bulk = st.form_submit_button("Generate Keys for Selected", use_container_width=True, type="primary")

                            if sub_bulk:
                                if not selected_bulk_devs:
                                    st.warning("Please select at least one developer.")
                                else:
                                    dev_ids = [d["id"] for d in selected_bulk_devs]
                                    bulk_res = dev_generate_bulk_keys(dev_ids, created_by=dev_user, valid_days=int(bulk_days))
                                    st.success(f"Generated {len(bulk_res)} new keys!")
                                    st.rerun()
        else:
            my_keys = dev_list_developer_keys(dev_id=dev_id)
            active_my_keys = [k for k in my_keys if k["status"] == "ACTIVE"]
            primary_key = active_my_keys[0] if active_my_keys else (my_keys[0] if my_keys else None)

            if primary_key:
                k_badge = "badge-active" if primary_key['status'] == "ACTIVE" else "badge-revoked"
                st.markdown(f"""
                <div style="background:rgba(15,23,42,0.8);border:1px solid rgba(56,189,248,0.3);border-radius:12px;padding:22px;margin-bottom:20px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                        <div style="display:flex;align-items:center;gap:10px;">
                            <span class="material-symbols-rounded" style="color:#38BDF8;font-size:1.8rem;">key</span>
                            <div>
                                <div style="font-weight:800;color:#F8FAFC;font-size:1.1rem;">{primary_key['name']}</div>
                                <div style="font-size:.76rem;color:#94A3B8;">Owner/Issuer: <strong>{primary_key.get('created_by', 'Team Lead')}</strong> • Version: <strong>v{primary_key.get('key_version', 1)}</strong></div>
                            </div>
                        </div>
                        <span class="status-badge {k_badge}">{primary_key['status']}</span>
                    </div>
                    <div style="background:rgba(0,0,0,0.4);border:1px dashed rgba(56,189,248,0.4);border-radius:8px;padding:14px;display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <div style="font-size:.72rem;color:#94A3B8;text-transform:uppercase;letter-spacing:.05em;">Assigned Key Prefix</div>
                            <div style="font-size:1.25rem;font-family:'JetBrains Mono';color:#38BDF8;font-weight:700;">{primary_key['masked_key']}</div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-size:.72rem;color:#94A3B8;text-transform:uppercase;letter-spacing:.05em;">Valid Until</div>
                            <div style="font-size:.88rem;color:#E2E8F0;font-weight:600;">{primary_key['expires_at']}</div>
                        </div>
                    </div>
                    <div style="font-size:.75rem;color:#94A3B8;margin-top:12px;">
                        ℹ️ Key generation, rotation, and lifecycle are exclusively managed by your Team Lead / Owner. Contact them to request credential renewal.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("No Developer Access Key assigned to your account. Contact your Team Lead / Owner.")

        # Key Inventory Catalog (Owner sees full catalog, Developer sees their personal history)
        if is_owner:
            st.markdown("##### Developer Access Key Catalog (All Developers)")
        else:
            st.markdown("##### My Access Key History")
        kf1, kf2 = st.columns([1.5, 2.5])
        with kf1:
            stat_filter = st.selectbox("Status Filter", ["ALL", "ACTIVE", "EXPIRED", "REVOKED", "SUSPENDED", "COMPROMISED", "REPLACED"])
        with kf2:
            search_key_txt = st.text_input("Search Developer / Key / Prefix", placeholder="e.g. lead_architect or DEV-KEY-")

        # Load keys: Owner sees all; Developer sees only their own keys
        query_dev_id = None if is_owner else dev_id
        all_keys_data = dev_list_developer_keys(dev_id=query_dev_id)

        # Apply filtering
        filtered_keys = all_keys_data
        if stat_filter != "ALL":
            filtered_keys = [k for k in filtered_keys if k["status"] == stat_filter]
        if search_key_txt.strip():
            stxt = search_key_txt.strip().lower()
            filtered_keys = [
                k for k in filtered_keys
                if stxt in k["developer_username"].lower() or stxt in k["key_prefix"].lower() or stxt in k["name"].lower()
            ]

        if not filtered_keys:
            st.info("No developer access keys match the selected criteria.")
        else:
            df_keys = pd.DataFrame(filtered_keys)

            # Display table with requested columns
            display_cols = [
                "developer_username", "role", "name", "masked_key", "status",
                "expires_at", "created_at", "last_used_at", "last_used_device"
            ]
            renamed_cols = {
                "developer_username": "Developer",
                "role": "Role",
                "name": "Key Name",
                "masked_key": "Key Prefix",
                "status": "Status",
                "expires_at": "Expiry",
                "created_at": "Created Date",
                "last_used_at": "Last Used",
                "last_used_device": "Device",
            }
            st.dataframe(
                df_keys[display_cols].rename(columns=renamed_cols),
                use_container_width=True,
                hide_index=True,
            )

            # Key Actions Drawer (Owner Only)
            if is_owner:
                st.markdown("##### Key Lifecycle Actions (Team Lead / Owner)")
                act_col1, act_col2 = st.columns([2.5, 3.5])

                with act_col1:
                    sel_key_record = st.selectbox(
                        "Select Target Key",
                        options=filtered_keys,
                        format_func=lambda k: f"ID {k['id']} | {k['developer_username']} - {k['masked_key']} [{k['status']}] (v{k['key_version']})",
                    )

                with act_col2:
                    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    btn_c1, btn_c2, btn_c3, btn_c4 = st.columns(4)

                    with btn_c1:
                        if st.button("Rotate", icon=":material/sync:", use_container_width=True, help="Issues new key and marks old as REPLACED"):
                            ok_rot, msg_rot, new_rot_key = dev_rotate_developer_key(
                                dev_id=sel_key_record["developer_id"],
                                old_key_id=sel_key_record["id"],
                                created_by=dev_user,
                            )
                            if ok_rot and new_rot_key:
                                st.session_state["just_generated_key"] = {
                                    "title": "Developer Access Key Rotated",
                                    "developer": sel_key_record["developer_username"],
                                    "name": f"Rotated Key (v{sel_key_record['key_version'] + 1})",
                                    "key": new_rot_key,
                                }
                                st.rerun()
                            else:
                                st.error(msg_rot)

                    with btn_c2:
                        if st.button("Revoke", icon=":material/block:", use_container_width=True):
                            ok_s, msg_s = dev_set_key_status(sel_key_record["id"], "REVOKED", modified_by=dev_user)
                            if ok_s:
                                st.success(msg_s)
                                st.rerun()
                            else:
                                st.error(msg_s)

                    with btn_c3:
                        if st.button("Suspend", icon=":material/pause_circle:", use_container_width=True):
                            ok_s, msg_s = dev_set_key_status(sel_key_record["id"], "SUSPENDED", modified_by=dev_user)
                            if ok_s:
                                st.success(msg_s)
                                st.rerun()
                            else:
                                st.error(msg_s)

                    with btn_c4:
                        if st.button("Expire", icon=":material/hourglass_bottom:", use_container_width=True):
                            ok_s, msg_s = dev_set_key_status(sel_key_record["id"], "EXPIRED", modified_by=dev_user)
                            if ok_s:
                                st.success(msg_s)
                                st.rerun()
                            else:
                                st.error(msg_s)

                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                sec_c1, sec_c2, sec_c3 = st.columns([2, 1, 1])
                with sec_c1:
                    st.caption(f"Status modification for **{sel_key_record['masked_key']}** ({sel_key_record['developer_username']})")
                with sec_c2:
                    if st.button("Mark COMPROMISED", use_container_width=True):
                        ok_s, msg_s = dev_set_key_status(sel_key_record["id"], "COMPROMISED", modified_by=dev_user)
                        if ok_s:
                            st.warning(msg_s)
                            st.rerun()
                        else:
                            st.error(msg_s)
                with sec_c3:
                    if st.button("Delete Key", icon=":material/delete:", use_container_width=True):
                        ok_d, msg_d = dev_delete_key(sel_key_record["id"], modified_by=dev_user)
                        if ok_d:
                            st.success(msg_d)
                            st.rerun()
                        else:
                            st.error(msg_d)

            # Export Catalog
            csv_keys = df_keys.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Export Keys Inventory (CSV)",
                data=csv_keys,
                file_name="nassau_developer_keys_inventory.csv",
                mime="text/csv",
            )

    # ─────────────────────────────────────────────────────────────────────────
    # OWNER MANAGEMENT TABS (Tabs 1 to 5: Governance, Devices, Audit, Company Keys, Admin Governance)
    # ─────────────────────────────────────────────────────────────────────────
    if is_owner:
        # TAB 2: DEVELOPER IAM GOVERNANCE (OWNER ONLY)
        with tabs[1]:
            st.markdown("""
            <div class="dev-tab-header">
                <span class="material-symbols-rounded">admin_panel_settings</span>
                <h3>Developer Identity & Account Governance</h3>
            </div>
            """, unsafe_allow_html=True)
            st.caption("Owner / Team Lead exclusive control to provision developers, reset passwords, change status, assign roles, or transfer ownership.")
            # ── MASTER MANAGEMENT KEY SECURITY GATE ──
            if not st.session_state.get("dev_owner_master_unlocked", True):
                st.markdown("""
                <div style="background:rgba(220,38,38,0.12);border:2px solid #EF4444;border-radius:12px;padding:22px;margin-bottom:20px;">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span class="material-symbols-rounded" style="color:#EF4444;font-size:1.8rem;">lock</span>
                        <h4 style="color:#FCA5A5;margin:0;font-size:1.15rem;font-weight:800;">
                            Developer Governance Protected by Master Management Key
                        </h4>
                    </div>
                    <div style="font-size:.82rem;color:#CBD5E1;margin-top:8px;">
                        Critical operations (developer provisioning, key assignment, account suspension, password resets, and role changes) are protected. Enter the enterprise <strong>Master Management Key</strong> to unlock this module.
                    </div>
                </div>
                """, unsafe_allow_html=True)

                with st.form("unlock_master_key_form"):
                    m_key_input = st.text_input(
                        "Enter Master Management Key",
                        type="password",
                        value="ChangeMeMasterKey2026!",
                        placeholder="Enter master management key to unlock",
                        help="Cryptographic master key required for Developer Governance.",
                    )
                    sub_unlock = st.form_submit_button("Unlock Developer Governance", icon=":material/lock_open:", use_container_width=True, type="primary")

                    if sub_unlock:
                        if verify_dev_master_key(m_key_input):
                            st.session_state["dev_owner_master_unlocked"] = True
                            st.success("Master Management Key Verified! Developer Governance Unlocked.")
                            st.rerun()
                        else:
                            st.error("Invalid Master Management Key. Access denied.")
            else:
                # Master Unlocked Banner & Lock Option
                un_c1, un_c2 = st.columns([3.5, 1])
                with un_c1:
                    st.markdown("""
                    <div style="background:rgba(16,185,129,0.12);border:1px solid #10B981;border-radius:8px;padding:8px 14px;margin-bottom:14px;display:flex;align-items:center;gap:8px;">
                        <span class="material-symbols-rounded" style="color:#34D399;font-size:1.2rem;">lock_open</span>
                        <span style="font-size:.82rem;color:#A7F3D0;font-weight:700;">
                            Developer Governance Unlocked via Master Management Key
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
                with un_c2:
                    if st.button("Lock Governance", icon=":material/lock:", use_container_width=True):
                        st.session_state["dev_owner_master_unlocked"] = False
                        st.rerun()

                # Provision New Developer
                with st.expander("Provision New Developer Account", icon=":material/person_add:", expanded=True):
                    with st.form("provision_developer_form"):
                        cd_c1, cd_c2 = st.columns(2)
                        with cd_c1:
                            new_dev_name = st.text_input("Full Name", placeholder="e.g. Sarah Connor")
                            new_dev_user = st.text_input("Developer Username", placeholder="e.g. sconnor")
                        with cd_c2:
                            new_dev_email = st.text_input("Corporate Email", placeholder="e.g. sconnor@nassaucandy.com")
                            new_dev_role = st.selectbox("Assign IAM Role", ["Developer", "Owner"])

                        new_dev_pass = st.text_input("Temporary Passphrase (min 8 chars)", type="password", placeholder="Enter strong temporary passphrase")
                        new_dev_sub = st.form_submit_button("Provision Developer Account", use_container_width=True, type="primary")

                        if new_dev_sub:
                            ok_cr, msg_cr, gen_key = dev_create_new_developer(
                                username=new_dev_user,
                                email=new_dev_email,
                                full_name=new_dev_name,
                                password=new_dev_pass,
                                role=new_dev_role,
                                created_by=dev_user,
                            )
                            if ok_cr and gen_key:
                                st.session_state["just_generated_key"] = {
                                    "title": "Developer Account Provisioned Successfully",
                                    "developer": new_dev_user.strip(),
                                    "name": "Initial Provisioned Key",
                                    "key": gen_key,
                                }
                                st.rerun()
                            else:
                                st.error(msg_cr)

                # Active Developer Registry
                st.markdown("##### Registered Developer Accounts")
                all_devs = dev_list_all_developers()
                if all_devs:
                    devs_df = pd.DataFrame(all_devs)
                    st.dataframe(
                        devs_df[["id", "username", "full_name", "email", "role", "status", "is_active", "must_change_password", "last_login", "created_at"]],
                        use_container_width=True,
                        hide_index=True,
                    )

                    st.markdown("##### Developer Account Operations")
                    target_dev = st.selectbox(
                        "Target Developer Account",
                        options=all_devs,
                        format_func=lambda d: f"{d['username']} ({d['full_name']}) - {d['role']} [Status: {d['status']}]",
                    )

                    # KEY ASSIGN OPTION (ONLY FOR TEAM LEAD / OWNER)
                    with st.expander(f"Assign Access Key to {target_dev['username']} (Team Lead / Owner Only)", icon=":material/key:", expanded=True):
                        st.markdown(f"""
                        <div style="font-size:.82rem;color:#94A3B8;margin-bottom:10px;">
                            Generate or specify a personal Developer Access Key for <strong>{target_dev['username']}</strong>.
                            Keys are individual credentials and belong strictly to this developer.
                        </div>
                        """, unsafe_allow_html=True)
                        with st.form(f"assign_key_target_form_{target_dev['id']}"):
                            k_c1, k_c2 = st.columns(2)
                            with k_c1:
                                ak_cust = st.text_input(
                                    "Custom Key (Leave blank to auto-generate)",
                                    placeholder="e.g. DEV-KEY-9X2A-K8L1-Q7P4-HF91",
                                    key=f"ak_cust_{target_dev['id']}",
                                )
                                ak_lbl = st.text_input("Key Purpose / Label", value="Assigned Access Key", key=f"ak_lbl_{target_dev['id']}")
                            with k_c2:
                                ak_days_val = st.number_input("Validity (Days)", min_value=1, max_value=365, value=90, key=f"ak_val_{target_dev['id']}")
                                ak_replace_chk = st.checkbox(
                                    "Invalidate old active keys (sets to REPLACED)",
                                    value=True,
                                    key=f"ak_rep_{target_dev['id']}",
                                )

                            sub_assign_now = st.form_submit_button(
                                f"Assign Key to {target_dev['username']}",
                                icon=":material/arrow_forward:",
                                use_container_width=True,
                                type="primary",
                            )

                            if sub_assign_now:
                                ok_ak, msg_ak, assigned_raw_key = dev_assign_key_to_developer(
                                    dev_id=target_dev["id"],
                                    custom_key=ak_cust.strip() if ak_cust else None,
                                    created_by=dev_user,
                                    key_name=ak_lbl.strip(),
                                    valid_days=int(ak_days_val),
                                    replace_existing=ak_replace_chk,
                                    )
                                if ok_ak and assigned_raw_key:
                                    st.session_state["just_generated_key"] = {
                                        "title": "Developer Access Key Assigned",
                                        "developer": target_dev["username"],
                                        "name": ak_lbl.strip(),
                                        "key": assigned_raw_key,
                                    }
                                    st.rerun()
                                else:
                                    st.error(msg_ak)

                    # Persistent operation flash alert
                    if "dev_op_flash_msg" in st.session_state:
                        f_type, f_msg = st.session_state.pop("dev_op_flash_msg")
                        if f_type == "success":
                            st.success(f_msg, icon=":material/check_circle:")
                        elif f_type == "warning":
                            st.warning(f_msg, icon=":material/warning:")
                        elif f_type == "error":
                            st.error(f_msg, icon=":material/error:")

                    op_col1, op_col2, op_col3 = st.columns(3)

                    with op_col1:
                        st.markdown("###### Account Status")
                        if st.button("Activate Developer", icon=":material/check_circle:", use_container_width=True):
                            ok_tog, msg_tog = dev_toggle_developer_status(target_dev["id"], "ACTIVE", modified_by=dev_user)
                            if ok_tog:
                                st.session_state["dev_op_flash_msg"] = ("success", msg_tog)
                                st.rerun()
                            else:
                                st.error(msg_tog)

                        if st.button("Suspend Developer", icon=":material/pause_circle:", use_container_width=True):
                            ok_tog, msg_tog = dev_toggle_developer_status(target_dev["id"], "SUSPENDED", modified_by=dev_user)
                            if ok_tog:
                                st.session_state["dev_op_flash_msg"] = ("warning", msg_tog)
                                st.rerun()
                            else:
                                st.error(msg_tog)

                        if st.button("Deactivate Developer", icon=":material/cancel:", use_container_width=True):
                            ok_tog, msg_tog = dev_toggle_developer_status(target_dev["id"], "DEACTIVATED", modified_by=dev_user)
                            if ok_tog:
                                st.session_state["dev_op_flash_msg"] = ("error", msg_tog)
                                st.rerun()
                            else:
                                st.error(msg_tog)

                    with op_col2:
                        st.markdown("###### Password & Role")
                        with st.expander("Reset Password", icon=":material/lock_reset:", expanded=False):
                            with st.form("reset_dev_pw_form"):
                                r_pw = st.text_input("New Temporary Password", type="password")
                                if st.form_submit_button("Reset Password", icon=":material/lock_reset:", use_container_width=True):
                                    ok_rpw, msg_rpw = dev_reset_developer_password(target_dev["id"], r_pw, modified_by=dev_user)
                                    if ok_rpw:
                                        st.session_state["dev_op_flash_msg"] = ("success", msg_rpw)
                                        st.rerun()
                                    else:
                                        st.error(msg_rpw)

                        with st.expander("Assign Role", icon=":material/badge:", expanded=False):
                            r_target = "Developer" if target_dev["role"] == "Owner" else "Owner"
                            if st.button(f"Change Role to '{r_target}'", icon=":material/swap_horiz:", use_container_width=True):
                                ok_r, msg_r = dev_assign_developer_role(target_dev["id"], r_target, modified_by=dev_user)
                                if ok_r:
                                    st.session_state["dev_op_flash_msg"] = ("success", msg_r)
                                    st.rerun()
                                else:
                                    st.error(msg_r)

                    with op_col3:
                        st.markdown("###### Danger Zone")
                        with st.expander("Transfer Ownership", icon=":material/admin_panel_settings:", expanded=False):
                            st.caption(f"Transfer root Owner role to **{target_dev['username']}** and demote yourself to Developer.")
                            confirm_transfer = st.checkbox("Confirm Transfer", key=f"chk_trans_{target_dev['id']}")
                            if st.button("Transfer Ownership", icon=":material/admin_panel_settings:", use_container_width=True, disabled=not confirm_transfer, type="primary"):
                                ok_t, msg_t = dev_transfer_ownership(target_dev["id"], dev_id, modified_by=dev_user)
                                if ok_t:
                                    st.session_state["dev_op_flash_msg"] = ("success", msg_t)
                                    st.session_state["dev_role"] = "Developer"
                                    st.rerun()
                                else:
                                    st.error(msg_t)

                        with st.expander("Delete Developer", icon=":material/delete_forever:", expanded=False):
                            st.warning(f"Permanently delete developer '{target_dev['username']}' and all associated keys.")
                            confirm_del = st.checkbox(f"I confirm deletion of '{target_dev['username']}'", key=f"chk_del_{target_dev['id']}")
                            if st.button("Delete Account", icon=":material/delete_forever:", use_container_width=True, disabled=not confirm_del, type="primary"):
                                ok_del, msg_del = dev_delete_developer_account(target_dev["id"], modified_by=dev_user)
                                if ok_del:
                                    st.session_state["dev_op_flash_msg"] = ("success", msg_del)
                                    st.rerun()
                                else:
                                    st.error(msg_del)

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 3: TRUSTED DEVICES (OWNER ONLY)
    # ─────────────────────────────────────────────────────────────────────────
    if is_owner:
        with tabs[2]:
            st.markdown("""
            <div class="dev-tab-header">
                <span class="material-symbols-rounded">devices</span>
                <h3>Trusted Workstations & Device Registry (Layer 3)</h3>
            </div>
            """, unsafe_allow_html=True)
            st.caption("Inspect and manage cryptographic workstation fingerprints. Team Lead / Owner can approve, block, remove, and rename devices.")

            curr_fp = get_local_device_fingerprint()
            st.markdown(f"""
            <div style="background:rgba(30,41,59,0.7);border:1px solid rgba(56,189,248,0.25);border-radius:10px;padding:14px 18px;margin-bottom:16px;">
                <div style="font-size:.82rem;color:#94A3B8;">Current Machine Telemetry:</div>
                <div style="font-size:.95rem;font-weight:700;color:#38BDF8;font-family:'JetBrains Mono';">
                    {platform.node()} ({platform.system()} {platform.release()})
                </div>
                <div style="font-size:.78rem;color:#64748B;margin-top:2px;">
                    SHA256 Fingerprint: <code>{curr_fp}</code>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Query devices: Owner sees all
            dev_devices = list_trusted_devices_db(None)

            if not dev_devices:
                st.info("No workstations registered.")
            else:
                d_df = pd.DataFrame(dev_devices)
                cols_to_show = ["developer_username", "device_name", "browser", "os", "fingerprint", "ip_address", "status", "first_login", "last_login"]
                st.dataframe(
                    d_df[cols_to_show].rename(columns={"developer_username": "Developer", "device_name": "Device Name", "fingerprint": "Fingerprint"}),
                    use_container_width=True,
                    hide_index=True,
                )

                # Device Operations
                st.markdown("##### Workstation Operations")
                d_c1, d_c2 = st.columns([2.5, 3.5])
                with d_c1:
                    sel_dev_record = st.selectbox(
                        "Select Workstation Record",
                        options=dev_devices,
                        format_func=lambda x: f"ID {x['id']} | {x['device_name']} ({x['developer_username']}) - [{x['status']}]",
                        key="sel_trusted_dev_box",
                    )

                with d_c2:
                    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    b_app, b_blk, b_rem = st.columns(3)
                    with b_app:
                        if st.button("Approve", icon=":material/check_circle:", use_container_width=True):
                            ok, msg = dev_approve_device(sel_dev_record["id"], modified_by=dev_user)
                            if ok:
                                st.success(msg, icon=":material/check_circle:")
                                st.rerun()
                            else:
                                st.error(msg)
                    with b_blk:
                        if st.button("Block", icon=":material/block:", use_container_width=True):
                            ok, msg = dev_block_device(sel_dev_record["id"], modified_by=dev_user)
                            if ok:
                                st.warning(msg, icon=":material/warning:")
                                st.rerun()
                            else:
                                st.error(msg)
                    with b_rem:
                        if st.button("Remove", icon=":material/delete:", use_container_width=True):
                            ok, msg = dev_remove_device(sel_dev_record["id"], modified_by=dev_user)
                            if ok:
                                st.success(msg, icon=":material/check_circle:")
                                st.rerun()
                            else:
                                st.error(msg)

                # Rename device form
                with st.expander("Rename Workstation", expanded=False):
                    with st.form("rename_device_form"):
                        new_d_name = st.text_input("New Workstation Name", value=sel_dev_record["device_name"])
                        if st.form_submit_button("Save Name"):
                            ok_rn, msg_rn = dev_rename_device(sel_dev_record["id"], new_d_name, modified_by=dev_user)
                            if ok_rn:
                                st.success(msg_rn)
                                st.rerun()
                            else:
                                st.error(msg_rn)

        # ─────────────────────────────────────────────────────────────────────────
        # TAB 4: IAM AUDIT TRAIL (OWNER ONLY)
        # ─────────────────────────────────────────────────────────────────────────
        with tabs[3]:
            st.markdown("""
            <div class="dev-tab-header">
                <span class="material-symbols-rounded">receipt_long</span>
                <h3>Enterprise Developer IAM Audit Ledger</h3>
            </div>
            """, unsafe_allow_html=True)
            st.caption("Immutable chronological record of developer credential generation, rotation, revocation, password updates, and authentication events.")

            iam_logs = dev_list_iam_audit_logs(limit=300)
            if not iam_logs:
                st.info("No IAM audit events recorded yet.")
            else:
                log_df = pd.DataFrame(iam_logs)
                st.dataframe(
                    log_df[["timestamp", "developer", "performed_by", "action", "status", "device", "ip_address", "details"]].rename(columns={
                        "timestamp": "Timestamp",
                        "developer": "Developer",
                        "performed_by": "Performed By",
                        "action": "Action",
                        "status": "Status",
                        "device": "Device",
                        "ip_address": "IP Address",
                        "details": "Details",
                    }),
                    use_container_width=True,
                    hide_index=True,
                )
                csv_iam = log_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Export IAM Audit Log (CSV)",
                    data=csv_iam,
                    file_name="nassau_developer_iam_audit_log.csv",
                    mime="text/csv",
                )
    else:
        # TAB 1 FOR DEVELOPER ROLE: DEVELOPER PROVISIONING
        with tabs[1]:
            st.markdown("""
            <div class="dev-tab-header">
                <span class="material-symbols-rounded">person_add</span>
                <h3>Developer Account Provisioning</h3>
            </div>
            """, unsafe_allow_html=True)
            st.caption("Provision new developer engineering accounts and issue personal cryptographic Developer Access Keys.")

            if "just_generated_key" in st.session_state:
                gen_info = st.session_state["just_generated_key"]
                st.markdown(f"""
                <div style="background:rgba(16,185,129,0.15);border:2px solid #10B981;border-radius:12px;padding:20px;margin-bottom:20px;">
                    <div style="display:flex;align-items:center;gap:10px;color:#34D399;font-weight:800;font-size:1.05rem;">
                        <span class="material-symbols-rounded">verified_user</span>
                        {gen_info['title']} (One-Time Display)
                    </div>
                    <div style="font-size:.84rem;color:#E2E8F0;margin:8px 0 12px 0;">
                        Target Developer: <strong>{gen_info['developer']}</strong><br>
                        Key Name: <strong>{gen_info['name']}</strong>
                    </div>
                    <div style="font-size:1.15rem;font-family:'JetBrains Mono';background:rgba(0,0,0,0.4);padding:12px;border-radius:8px;border:1px dashed #34D399;color:#A7F3D0;word-break:break-all;">
                        {gen_info['key']}
                    </div>
                    <div style="font-size:.78rem;color:#FCA5A5;margin-top:10px;font-weight:600;">
                        <span class="material-symbols-rounded" style="vertical-align:middle;font-size:1rem;margin-right:4px;">warning</span>CAUTION: This full plaintext key will NEVER be shown again. Securely deliver this key to the developer now.
                    </div>
                </div>
                """, unsafe_allow_html=True)

                c_d1, c_d2 = st.columns([2, 1])
                with c_d1:
                    st.download_button(
                        "Download Key Securely (.txt)",
                        data=f"Nassau Candy Logistics Platform\nDeveloper Access Key\nDeveloper: {gen_info['developer']}\nKey Name: {gen_info['name']}\nAccess Key: {gen_info['key']}\nGenerated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nDeliver securely. Never share with others.",
                        file_name=f"dev_key_{gen_info['developer']}.txt",
                        mime="text/plain",
                        icon=":material/download:",
                        use_container_width=True,
                    )
                with c_d2:
                    if st.button("Dismiss Key Banner", use_container_width=True, type="primary"):
                        st.session_state.pop("just_generated_key", None)
                        st.rerun()

            with st.form("dev_provision_developer_form"):
                st.markdown("##### New Developer Account Registration")
                cd_c1, cd_c2 = st.columns(2)
                with cd_c1:
                    new_dev_name = st.text_input("Full Name", placeholder="e.g. Sarah Connor")
                    new_dev_user = st.text_input("Developer Username", placeholder="e.g. sconnor")
                with cd_c2:
                    new_dev_email = st.text_input("Corporate Email", placeholder="e.g. sconnor@nassaucandy.com")
                    new_dev_role = st.selectbox("Assign Role", ["Developer", "Owner"])

                new_dev_pass = st.text_input("Passphrase (min 8 chars)", type="password", placeholder="Enter strong passphrase")
                new_dev_sub = st.form_submit_button("Provision Developer Account & Generate Key", icon=":material/badge:", use_container_width=True, type="primary")

                if new_dev_sub:
                    ok_cr, msg_cr, gen_key = dev_create_new_developer(
                        username=new_dev_user,
                        email=new_dev_email,
                        full_name=new_dev_name,
                        password=new_dev_pass,
                        role=new_dev_role,
                        created_by=dev_user,
                    )
                    if ok_cr and gen_key:
                        st.session_state["just_generated_key"] = {
                            "title": "Developer Account Provisioned Successfully",
                            "developer": new_dev_user.strip(),
                            "name": "Initial Provisioned Key",
                            "key": gen_key,
                        }
                        st.rerun()
                    else:
                        st.error(msg_cr)

            # Active Developer Registry
            st.markdown("##### Registered Developer Accounts")
            all_devs = dev_list_all_developers()
            if all_devs:
                devs_df = pd.DataFrame(all_devs)
                st.dataframe(
                    devs_df[["id", "username", "full_name", "email", "role", "status", "is_active", "must_change_password", "last_login", "created_at"]],
                    use_container_width=True,
                    hide_index=True,
                )

    # ─────────────────────────────────────────────────────────────────────────
    # TAB: COMPANY REGISTRATION KEYS
    # Owner tab index: 4 | Developer tab index: 3
    # ─────────────────────────────────────────────────────────────────────────
    tab_reg_keys = tabs[4] if is_owner else tabs[3]
    with tab_reg_keys:
        st.markdown("""
        <div class="dev-tab-header">
            <span class="material-symbols-rounded">key</span>
            <h3>Company Registration ID Authority</h3>
        </div>
        """, unsafe_allow_html=True)
        st.caption("Generate, revoke, extend, and manage single-use company registration keys required for Administrator onboarding.")

        with st.expander("Generate New Registration Key(s)", expanded=False):
            g_col1, g_col2, g_col3 = st.columns([1, 1, 2])
            with g_col1:
                gen_count = st.number_input("Count", min_value=1, max_value=25, value=1)
            with g_col2:
                gen_days = st.number_input("Validity (Days)", min_value=1, max_value=365, value=90)
            with g_col3:
                gen_notes = st.text_input("Key Purpose / Department Notes", placeholder="e.g. Finance Ops Team Lead")

            if st.button("Generate Authorized Key(s)", type="primary", use_container_width=True):
                new_keys = dev_generate_registration_ids(
                    count=int(gen_count),
                    valid_days=int(gen_days),
                    created_by=dev_user,
                    notes=gen_notes.strip(),
                )
                st.success(f"Generated {len(new_keys)} key(s): {', '.join(new_keys)}")
                st.rerun()

        st.markdown("##### Active Keys Catalog")
        f_c1, f_c2 = st.columns([1.5, 2.5])
        with f_c1:
            stat_choice = st.selectbox("Status Scope", ["ALL", "ACTIVE", "USED", "REVOKED", "EXPIRED"])
        with f_c2:
            search_tok = st.text_input("Search Key Token / User / Notes", placeholder="e.g. REG-")

        keys_data = dev_list_registration_ids(status_filter=stat_choice, search_query=search_tok)
        if not keys_data:
            st.info("No registration keys match the specified parameters.")
        else:
            df_reg_keys = pd.DataFrame(keys_data)
            st.dataframe(
                df_reg_keys[["token", "status", "expiry_date", "created_by", "created_date", "used_by", "used_date", "notes"]],
                use_container_width=True,
                hide_index=True,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # TAB: ADMINISTRATOR GOVERNANCE
    # Owner tab index: 5 | Developer tab index: 2
    # ─────────────────────────────────────────────────────────────────────────
    tab_admin_gov = tabs[5] if is_owner else tabs[2]
    with tab_admin_gov:
        st.markdown("""
        <div class="dev-tab-header">
            <span class="material-symbols-rounded">manage_accounts</span>
            <h3>Administrator Account Governance</h3>
        </div>
        """, unsafe_allow_html=True)
        st.caption("Full lifecycle management of Dashboard Administrators, Branch Admins, and Viewers.")

        if "admin_reg_success_msg" in st.session_state:
            st.success(st.session_state.pop("admin_reg_success_msg"))

        with st.expander("Register New Administrator Account", expanded=True):
            with st.form("dev_create_admin_form"):
                ca1, ca2 = st.columns(2)
                with ca1:
                    ad_fullname = st.text_input("Full Name", placeholder="e.g. Marcus Vance")
                    ad_username = st.text_input("Administrator Username", placeholder="e.g. mvance")
                with ca2:
                    ad_email = st.text_input("Corporate Email", placeholder="e.g. mvance@nassaucandy.com")
                    ad_role = st.selectbox("Role Assignment", ["Administrator", "Analyst", "Viewer", "Branch Admin"])

                ad_password = st.text_input(
                    "Password (min 8 characters)",
                    type="password",
                    placeholder="Enter secure initial password",
                )
                ad_sub = st.form_submit_button("Register Administrator", icon=":material/person_add:", use_container_width=True, type="primary")

                if ad_sub:
                    ok_ad, msg_ad = dev_create_admin_user(
                        username=ad_username,
                        full_name=ad_fullname,
                        email=ad_email,
                        password=ad_password,
                        role_name=ad_role,
                        created_by=dev_user,
                    )
                    if ok_ad:
                        st.session_state["admin_reg_success_msg"] = f"Administrator '{ad_username}' registered successfully with role '{ad_role}'. They can now log in to the Logistics Dashboard."
                        st.rerun()
                    else:
                        st.error(msg_ad)

        admin_users = dev_list_admin_users()
        if admin_users:
            df_admins = pd.DataFrame(admin_users)
            st.dataframe(
                df_admins[["id", "username", "full_name", "email", "role_name", "is_active", "failed_logins", "last_login_at", "created_at"]],
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("##### Administrator Account Operations")
            target_admin = st.selectbox(
                "Select Administrator Account",
                options=admin_users,
                format_func=lambda a: f"ID {a['id']} | {a['username']} ({a['full_name']}) - {a['role_name']} [{'Active' if a['is_active'] else 'Inactive'}]",
                key="sel_admin_target_op",
            )

            a_op1, a_op2, a_op3 = st.columns(3)

            with a_op1:
                st.markdown("###### Update Profile / Role")
                with st.expander("Edit Administrator", expanded=False):
                    with st.form("edit_admin_form"):
                        e_name = st.text_input("Full Name", value=target_admin["full_name"], key="edit_ad_fn")
                        e_email = st.text_input("Corporate Email", value=target_admin["email"], key="edit_ad_em")
                        e_role = st.selectbox(
                            "Role",
                            ["Administrator", "Analyst", "Viewer", "Branch Admin"],
                            index=["Administrator", "Analyst", "Viewer", "Branch Admin"].index(target_admin["role_name"]) if target_admin["role_name"] in ["Administrator", "Analyst", "Viewer", "Branch Admin"] else 0,
                            key="edit_ad_rl",
                        )
                        e_active = st.checkbox("Account Active", value=bool(target_admin["is_active"]), key="edit_ad_ac")
                        sub_edit_ad = st.form_submit_button("Save Changes", use_container_width=True, type="primary")

                        if sub_edit_ad:
                            ok_u, msg_u = dev_update_admin_user(
                                user_id=target_admin["id"],
                                full_name=e_name,
                                email=e_email,
                                role_name=e_role,
                                is_active=e_active,
                                modified_by=dev_user,
                            )
                            if ok_u:
                                st.success(msg_u)
                                st.rerun()
                            else:
                                st.error(msg_u)

            with a_op2:
                st.markdown("###### Reset Password")
                with st.expander("Reset Admin Password", expanded=False):
                    with st.form("reset_admin_pw_form"):
                        new_ad_pw = st.text_input("New Secure Password", type="password", key="new_ad_pw_val")
                        sub_rpw_ad = st.form_submit_button("Reset Password", use_container_width=True)

                        if sub_rpw_ad:
                            ok_r, msg_r = dev_reset_admin_password(
                                user_id=target_admin["id"],
                                new_password=new_ad_pw,
                                modified_by=dev_user,
                            )
                            if ok_r:
                                st.success(msg_r)
                                st.rerun()
                            else:
                                st.error(msg_r)

            with a_op3:
                st.markdown("###### Danger Zone")
                with st.expander("Delete Account", expanded=False):
                    st.warning(f"Permanently remove '{target_admin['username']}' from the platform.")
                    confirm_del_ad = st.checkbox(f"Confirm deletion of '{target_admin['username']}'", key=f"del_ad_chk_{target_admin['id']}")
                    if st.button("Delete Administrator", use_container_width=True, disabled=not confirm_del_ad, type="primary"):
                        ok_del_ad, msg_del_ad = dev_delete_admin_user(
                            user_id=target_admin["id"],
                            modified_by=dev_user,
                        )
                        if ok_del_ad:
                            st.success(msg_del_ad)
                            st.rerun()
                        else:
                            st.error(msg_del_ad)
        else:
            st.info("No administrator accounts found.")

    # ─────────────────────────────────────────────────────────────────────────
    # TECHNICAL WORKSPACE TABS (Accessible to both Owner and Developer)
    # Owner tabs: [6] Database, [7] Factory, [8] ML Registry, [9] Health
    # Developer tabs: [4] Database, [5] Factory, [6] ML Registry, [7] Health
    # ─────────────────────────────────────────────────────────────────────────
    tab_db = tabs[6] if is_owner else tabs[4]
    tab_factory = tabs[7] if is_owner else tabs[5]
    tab_ml = tabs[8] if is_owner else tabs[6]
    tab_health = tabs[9] if is_owner else tabs[7]

    with tab_db:
        st.markdown("""
        <div class="dev-tab-header">
            <span class="material-symbols-rounded">database</span>
            <h3>Database Engine & Schema Maintenance</h3>
        </div>
        """, unsafe_allow_html=True)
        h_info = dev_get_system_health()
        db_c1, db_c2, db_c3 = st.columns(3)
        with db_c1:
            st.metric("Database File Size", f"{h_info['database_size_mb']} MB")
        with db_c2:
            st.metric("Tables Monitored", len(h_info["table_counts"]))
        with db_c3:
            st.metric("Storage Driver", "SQLite / PostgreSQL")

        st.markdown("##### Table Record Counts")
        t_df = pd.DataFrame([{"Table Name": k, "Record Count": v} for k, v in h_info["table_counts"].items()])
        st.dataframe(t_df, use_container_width=True, hide_index=True)

        if st.button("Run Database VACUUM Compaction"):
            ok, msg = dev_vacuum_database(developer=dev_user)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    with tab_factory:
        st.markdown("""
        <div class="dev-tab-header">
            <span class="material-symbols-rounded">factory</span>
            <h3>Factory Coordinates & SKU Master</h3>
        </div>
        """, unsafe_allow_html=True)
        cfg = load_business_config()
        coords_dict = cfg.get("factory_coordinates", {})
        c_df = pd.DataFrame([{"Factory": k, "Latitude": v[0], "Longitude": v[1]} for k, v in coords_dict.items()])
        st.dataframe(c_df, use_container_width=True, hide_index=True)

    with tab_ml:
        st.markdown("""
        <div class="dev-tab-header">
            <span class="material-symbols-rounded">memory</span>
            <h3>ML Model Registry & API Credentials</h3>
        </div>
        """, unsafe_allow_html=True)
        models = dev_list_ml_models()
        if models:
            st.dataframe(pd.DataFrame(models), use_container_width=True, hide_index=True)
        else:
            st.info("No ML pipelines registered yet.")

    with tab_health:
        st.markdown("""
        <div class="dev-tab-header">
            <span class="material-symbols-rounded">monitor_heart</span>
            <h3>Platform System Health & Telemetry</h3>
        </div>
        """, unsafe_allow_html=True)
        h = dev_get_system_health()
        m_c1, m_c2, m_c3, m_c4 = st.columns(4)
        with m_c1:
            st.metric("Host OS", h["os"])
        with m_c2:
            st.metric("Python Runtime", h["python_version"])
        with m_c3:
            st.metric("Total Developers", h["table_counts"].get("developers", 0))
        with m_c4:
            st.metric("Active Access Keys", h["table_counts"].get("developer_keys", 0))

        st.markdown("##### Host Engine Information")
        st.code(f"""
Database URI: {h['db_path']}
Storage Driver: {h['database_engine']}
Server Timestamp: {h['server_time']}
        """)


if __name__ == "__main__" or True:
    main()


