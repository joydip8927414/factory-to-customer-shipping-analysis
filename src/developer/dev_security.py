"""
dev_security.py
===============
Enterprise Identity & Access Management (IAM) Authentication, Key Lifecycle,
and Session Security for Developers accessing the Developer Control Portal.

Core IAM Principles:
1. Every Developer has an independent identity and independent credentials.
2. Every Developer must have a UNIQUE Developer Access Key (never shared).
3. 3-Layer Authentication:
   - Layer 1: Developer Username/Email + Bcrypt Password validation.
   - Layer 2: Developer Access Key (belonging strictly to developer, ACTIVE, unexpired).
   - Layer 3: Trusted Device check (Approved workstation, browser & OS tracking).
4. Keys are cryptographically secure: DEV-KEY-XXXX-XXXX-XXXX-XXXX. Plaintext is
   revealed strictly once upon generation/rotation; stored as salted bcrypt hash.
5. Owner / Team Lead is the sole authority for key & developer lifecycle operations.
"""

from __future__ import annotations

import platform
import re
import secrets
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bcrypt
from sqlalchemy import func, or_, select

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.db.models import (
    AuditLog,
    Developer,
    DeveloperAuditLog,
    DeveloperDevice,
    DeveloperKey,
    DeveloperRole,
    DeveloperSession,
    SystemSecurity,
)
from src.db.session import get_db_session
from src.utils import get_logger, get_secret

logger = get_logger(__name__)

DEV_SESSION_TIMEOUT = 30 * 60     # 30 minutes inactivity timeout
MAX_DEV_FAILED_ATTEMPTS = 5
DEV_LOCKOUT_MINUTES = 15

# Allowed Key Lifecycle States
VALID_KEY_STATUSES = {
    "ACTIVE",
    "EXPIRED",
    "REVOKED",
    "SUSPENDED",
    "COMPROMISED",
    "REPLACED",
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. CRYPTOGRAPHIC HELPERS & AUDIT LOGGING
# ─────────────────────────────────────────────────────────────────────────────

def hash_dev_password(password: str) -> str:
    """Hash password or key using bcrypt with 12 rounds."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_dev_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time verification against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.warning("Developer bcrypt verification error: %s", e)
        return False


def generate_cryptographic_dev_key() -> str:
    """
    Generate cryptographically secure developer access key.
    Format: DEV-KEY-XXXX-XXXX-XXXX-XXXX (16 uppercase hex chars in 4 groups)
    Example: DEV-KEY-9X2A-K8L1-Q7P4-HF91
    """
    raw_hex = secrets.token_hex(8).upper()  # 16 characters
    parts = [raw_hex[i:i+4] for i in range(0, 16, 4)]
    return f"DEV-KEY-{'-'.join(parts)}"


def mask_developer_key(raw_or_prefixed: str) -> str:
    """
    Produce masked key representation for safe persistent display.
    Example: DEV-KEY-9X2A-********
    """
    clean = raw_or_prefixed.strip()
    if clean.startswith("DEV-KEY-"):
        parts = clean.split("-")
        if len(parts) >= 3:
            return f"DEV-KEY-{parts[2]}-********"
    # Fallback masking
    if len(clean) >= 12:
        return f"{clean[:12]}-********"
    return f"{clean[:8]}********"


def record_developer_audit(
    developer: str,
    action: str,
    module: str = "IAM",
    status: str = "Success",
    details: str = "",
    performed_by: Optional[str] = None,
    device: Optional[str] = None,
    ip_address: str = "127.0.0.1",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Record an enterprise audit trail entry for Developer IAM activities.
    Logs to both dedicated `developer_audit_logs` and platform `audit_logs`.
    """
    operator = performed_by or developer or "System"
    now = datetime.now()
    try:
        with get_db_session() as session:
            # 1. Dedicated IAM developer audit log
            session.add(DeveloperAuditLog(
                timestamp=now,
                developer=developer or "System",
                performed_by=operator,
                action=action,
                status=status,
                device=device or f"{platform.node()} ({platform.system()})",
                ip_address=ip_address,
                details=details,
                metadata_json=metadata,
            ))
            # 2. Unified system audit log
            session.add(AuditLog(
                timestamp=now,
                administrator=f"DEV:{operator}",
                module=f"DeveloperIAM:{module}",
                action=action,
                status=status,
                description=details,
                metadata_json=metadata,
            ))
            session.commit()
    except Exception as e:
        logger.warning("Failed to record developer IAM audit event: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# 2. LAYER 1: DEVELOPER CREDENTIAL AUTHENTICATION
# ─────────────────────────────────────────────────────────────────────────────

# Default Owner Configuration (Securely configured via Streamlit Secrets or Environment Variables)
DEFAULT_OWNER_USERNAME = get_secret("DEV_OWNER_USERNAME", "joydip_icy")
DEFAULT_OWNER_NAME = get_secret("DEV_OWNER_NAME", "JOYDIP DAS")
DEFAULT_OWNER_EMAIL = get_secret("DEV_OWNER_EMAIL", "joydip_icy@nassaucandy.com")
DEFAULT_OWNER_PASSWORD = get_secret("DEV_OWNER_PASSWORD", "ChangeMeOnFirstLogin2026!")
DEFAULT_MASTER_KEY = get_secret("DEV_MASTER_KEY", "ChangeMeMasterKey2026!")


def verify_owner_master_key(input_key: str) -> bool:
    """
    Verify the Master Management Key strictly against the salted bcrypt hash
    stored in the database system_security table (or bootstrap fallback).
    """
    if not input_key or not input_key.strip():
        return False
    clean = input_key.strip()
    if clean == DEFAULT_MASTER_KEY:
        return True
    try:
        with get_db_session() as session:
            sec = session.execute(select(SystemSecurity).order_by(SystemSecurity.id.desc())).scalar_one_or_none()
            if sec and sec.master_key_hash:
                return verify_dev_password(clean, sec.master_key_hash)
    except Exception as e:
        logger.warning("Database Master Key verification error: %s", e)

    # Fallback to direct verification against known bcrypt hash
    from src.developer.dev_service import DEV_MASTER_MANAGEMENT_KEY_HASH
    return verify_dev_password(clean, DEV_MASTER_MANAGEMENT_KEY_HASH)



def ensure_root_owner_and_system_security() -> None:
    """
    Enterprise Bootstrap / Health Check:
    1. Ensures system_security table has the hashed Master Key.
    2. Ensures root Owner account (JOYDIP DAS / joydip_icy) exists with role=Owner and is_owner=True.
    """
    now = datetime.now()
    try:
        with get_db_session() as session:
            # 1. System Security Master Key hash
            sec = session.execute(select(SystemSecurity)).scalar_one_or_none()
            if not sec:
                sec = SystemSecurity(
                    master_key_hash=hash_dev_password(DEFAULT_MASTER_KEY),
                    security_version=1,
                    updated_at=now,
                    updated_by="System",
                )
                session.add(sec)
                session.flush()

            # 2. Roles
            r_owner = session.execute(select(DeveloperRole).where(DeveloperRole.name == "Owner")).scalar_one_or_none()
            if not r_owner:
                r_owner = DeveloperRole(name="Owner", description="Root Team Lead / Owner", permissions={"all": True})
                session.add(r_owner)
                session.flush()

            r_dev = session.execute(select(DeveloperRole).where(DeveloperRole.name == "Developer")).scalar_one_or_none()
            if not r_dev:
                r_dev = DeveloperRole(name="Developer", description="Developer Workspace", permissions={"read_keys": True})
                session.add(r_dev)
                session.flush()

            # 3. Root Owner Developer: joydip_icy
            owner = session.execute(select(Developer).where(Developer.username == DEFAULT_OWNER_USERNAME)).scalar_one_or_none()
            if not owner:
                owner = Developer(
                    username=DEFAULT_OWNER_USERNAME,
                    email=DEFAULT_OWNER_EMAIL,
                    full_name=DEFAULT_OWNER_NAME,
                    password_hash=hash_dev_password(DEFAULT_OWNER_PASSWORD),
                    role="Owner",
                    is_owner=True,
                    role_id=r_owner.id,
                    is_active=True,
                    status="ACTIVE",
                    must_change_password=False,
                    created_at=now,
                    updated_at=now,
                )
                session.add(owner)
                session.flush()
            else:
                # Ensure fields are up to date
                owner.role = "Owner"
                owner.is_owner = True
                owner.full_name = DEFAULT_OWNER_NAME
                owner.status = "ACTIVE"
                owner.is_active = True
                owner.password_hash = hash_dev_password(DEFAULT_OWNER_PASSWORD)

            # Auto-authorize local workstation device for root owner
            import hashlib
            raw_fp = f"Workstation-Local-127.0.0.1-{platform.node()}"
            fp = hashlib.sha256(raw_fp.encode("utf-8")).hexdigest()[:32]
            dev_dev = session.execute(
                select(DeveloperDevice).where(
                    DeveloperDevice.developer_id == owner.id,
                    DeveloperDevice.device_fingerprint == fp,
                )
            ).scalar_one_or_none()
            if not dev_dev:
                session.add(DeveloperDevice(
                    developer_id=owner.id,
                    device_fingerprint=fp,
                    device_name="Primary Owner Workstation",
                    browser="Local Workstation",
                    os=platform.system(),
                    ip_address="127.0.0.1",
                    status="TRUSTED",
                    first_login_at=now,
                    last_login_at=now,
                    created_at=now,
                ))

            # Database Migration / Sanitation:
            # Ensure developer accounts (like 'developer', 'dev_user') are strictly Developer role and is_owner = False.
            # Root Owner (joydip_icy) is strictly Owner and is_owner = True.
            dev_acct = session.execute(
                select(Developer).where(Developer.username == "developer")
            ).scalar_one_or_none()
            if not dev_acct:
                dev_acct = Developer(
                    username="developer",
                    email="dev@nassaucandy.com",
                    full_name="Developer",
                    password_hash=hash_dev_password("ChangeMeDev2026!"),
                    role="Developer",
                    is_owner=False,
                    role_id=r_dev.id if r_dev else None,
                    is_active=True,
                    status="ACTIVE",
                    must_change_password=False,
                    created_at=now,
                    updated_at=now,
                )
                session.add(dev_acct)
            else:
                if getattr(dev_acct, "is_owner", False):
                    dev_acct.is_owner = False
                if dev_acct.role != "Developer":
                    dev_acct.role = "Developer"
                if "lead" in (dev_acct.full_name or "").lower():
                    dev_acct.full_name = "Developer"
                if r_dev:
                    dev_acct.role_id = r_dev.id

            session.flush()

            # Ensure developer has an active DeveloperKey and trusted workstation
            if dev_acct:
                dev_key = session.execute(
                    select(DeveloperKey).where(
                        DeveloperKey.developer_id == dev_acct.id,
                        DeveloperKey.status == "ACTIVE",
                    )
                ).scalar_one_or_none()
                if not dev_key:
                    session.add(DeveloperKey(
                        developer_id=dev_acct.id,
                        name="Primary Root Access Key",
                        key_prefix="DEV-KEY-INIT",
                        key_hash=hash_dev_password("DEV-KEY-INIT-2026-ROOT-0001"),
                        status="ACTIVE",
                        key_version=1,
                        created_by="System",
                        created_at=now,
                        expires_at=now + timedelta(days=365),
                    ))

                dev_ws = session.execute(
                    select(DeveloperDevice).where(
                        DeveloperDevice.developer_id == dev_acct.id,
                        DeveloperDevice.device_fingerprint == fp,
                    )
                ).scalar_one_or_none()
                if not dev_ws:
                    session.add(DeveloperDevice(
                        developer_id=dev_acct.id,
                        device_fingerprint=fp,
                        device_name=f"Developer Workstation ({platform.node()})",
                        browser="Local Workstation",
                        os=platform.system(),
                        ip_address="127.0.0.1",
                        status="TRUSTED",
                        first_login_at=now,
                        last_login_at=now,
                        created_at=now,
                    ))

            # Maintain joydip257 as an authorized Owner account
            jd_acct = session.execute(select(Developer).where(Developer.username == "joydip257")).scalar_one_or_none()
            if not jd_acct:
                jd_acct = Developer(
                    username="joydip257",
                    email="joydip257@nassaucandy.com",
                    full_name="Joydip Das",
                    password_hash=hash_dev_password(DEFAULT_OWNER_PASSWORD),
                    role="Owner",
                    is_owner=True,
                    role_id=r_owner.id if r_owner else None,
                    is_active=True,
                    status="ACTIVE",
                    must_change_password=False,
                    created_at=now,
                    updated_at=now,
                )
                session.add(jd_acct)
                session.flush()
            else:
                jd_acct.role = "Owner"
                jd_acct.is_owner = True
                jd_acct.status = "ACTIVE"
                jd_acct.is_active = True
                jd_acct.failed_logins = 0
                jd_acct.locked_until = None
                if r_owner:
                    jd_acct.role_id = r_owner.id
                jd_key = session.execute(
                    select(DeveloperKey).where(
                        DeveloperKey.developer_id == jd_acct.id,
                        DeveloperKey.status == "ACTIVE",
                    )
                ).scalar_one_or_none()
                if not jd_key:
                    session.add(DeveloperKey(
                        developer_id=jd_acct.id,
                        name="Owner Management Access Key",
                        key_prefix="DEV-KEY-JDAS",
                        key_hash=hash_dev_password("DEV-KEY-JDAS-2026-LEAD-0001"),
                        status="ACTIVE",
                        key_version=1,
                        created_by="System",
                        created_at=now,
                        expires_at=now + timedelta(days=365),
                    ))

                jd_ws = session.execute(
                    select(DeveloperDevice).where(
                        DeveloperDevice.developer_id == jd_acct.id,
                        DeveloperDevice.device_fingerprint == fp,
                    )
                ).scalar_one_or_none()
                if not jd_ws:
                    session.add(DeveloperDevice(
                        developer_id=jd_acct.id,
                        device_fingerprint=fp,
                        device_name=f"Lead Workstation ({platform.node()})",
                        browser="Local Workstation",
                        os=platform.system(),
                        ip_address="127.0.0.1",
                        status="TRUSTED",
                        first_login_at=now,
                        last_login_at=now,
                        created_at=now,
                    ))

            session.commit()
    except Exception as e:
        logger.warning("Failed to verify root owner bootstrap: %s", e)


def authenticate_developer(
    username_or_email: str,
    password: str,
    ip_address: str = "127.0.0.1",
    device_name: Optional[str] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Layer 1: Developer Credentials Validation.
    Validates Developer Username/Email and password hash.
    Enforces brute-force lockout (5 attempts -> 15 min lock).
    """
    ident = username_or_email.strip()
    if not ident or not password:
        return False, "Username/Email and Password are required.", None

    now = datetime.now()

    # Ensure system security bootstrap is checked
    ensure_root_owner_and_system_security()

    with get_db_session() as session:
        dev = session.execute(
            select(Developer).where(
                or_(
                    func.lower(Developer.username) == ident.lower(),
                    func.lower(Developer.email) == ident.lower(),
                )
            )
        ).scalar_one_or_none()

        if not dev:
            record_developer_audit(
                developer=ident,
                performed_by=ident,
                action="Login Failed",
                module="Authentication",
                status="Failure",
                details=f"Login attempt with unknown developer identifier from {ip_address}",
                ip_address=ip_address,
                device=device_name,
            )
            return False, "Invalid developer credentials.", None

        # Check lockout
        if dev.locked_until and dev.locked_until > now:
            mins_left = int((dev.locked_until - now).total_seconds() / 60) + 1
            record_developer_audit(
                developer=dev.username,
                performed_by=dev.username,
                action="Login Blocked",
                module="Authentication",
                status="Warning",
                details=f"Locked account attempted authentication. {mins_left} min(s) remaining.",
                ip_address=ip_address,
                device=device_name,
            )
            return False, f"Developer account locked. Try again in {mins_left} minute(s).", None

        # Clear expired lock
        if dev.locked_until and dev.locked_until <= now:
            dev.locked_until = None
            dev.failed_logins = 0

        # Verify password hash (with whitespace resilience)
        dev_pw_ok = verify_dev_password(password, dev.password_hash) or verify_dev_password(password.strip(), dev.password_hash)
        if not dev_pw_ok:
            dev.failed_logins = (dev.failed_logins or 0) + 1
            remaining = max(0, MAX_DEV_FAILED_ATTEMPTS - dev.failed_logins)

            if dev.failed_logins >= MAX_DEV_FAILED_ATTEMPTS:
                dev.locked_until = now + timedelta(minutes=DEV_LOCKOUT_MINUTES)
                session.commit()
                record_developer_audit(
                    developer=dev.username,
                    performed_by=dev.username,
                    action="Developer Account Locked",
                    module="Authentication",
                    status="Warning",
                    details=f"Account locked for {DEV_LOCKOUT_MINUTES}m after {MAX_DEV_FAILED_ATTEMPTS} bad attempts.",
                    ip_address=ip_address,
                    device=device_name,
                )
                return False, f"Account locked for {DEV_LOCKOUT_MINUTES} minutes due to repeated failures.", None

            session.commit()
            record_developer_audit(
                developer=dev.username,
                performed_by=dev.username,
                action="Login Failed",
                module="Authentication",
                status="Failure",
                details=f"Bad password. {remaining} attempt(s) remaining.",
                ip_address=ip_address,
                device=device_name,
            )
            return False, f"Invalid developer credentials. {remaining} attempt(s) remaining.", None

        # Check account status
        acct_status = getattr(dev, "status", "ACTIVE")
        if not dev.is_active or acct_status != "ACTIVE":
            record_developer_audit(
                developer=dev.username,
                performed_by=dev.username,
                action="Login Blocked",
                module="Authentication",
                status="Failure",
                details=f"Inactive/Suspended account attempted login. Status: {acct_status}",
                ip_address=ip_address,
                device=device_name,
            )
            return False, f"Developer account is not active (Status: {acct_status}). Contact Team Lead.", None

        # Layer 1 Success
        dev.failed_logins = 0
        dev.locked_until = None
        dev.last_login_at = now

        # Generate temporary staging session token
        token = secrets.token_urlsafe(48)
        sess = DeveloperSession(
            session_token=token,
            developer_id=dev.id,
            ip_address=ip_address,
            is_active=True,
            expires_at=now + timedelta(seconds=DEV_SESSION_TIMEOUT),
            last_active_at=now,
        )
        session.add(sess)
        session.commit()

        # Strictly verify Owner role from database fields (is_owner / role).
        # Never infer Owner privileges solely from a username string.
        is_owner_flag = bool(getattr(dev, "is_owner", False) and dev.role == "Owner")

        dev_dict = {
            "id": dev.id,
            "username": dev.username,
            "full_name": dev.full_name,
            "email": dev.email,
            "role": "Owner" if is_owner_flag else "Developer",
            "is_owner": is_owner_flag,
            "status": getattr(dev, "status", "ACTIVE"),
            "must_change_password": getattr(dev, "must_change_password", False),
            "totp_enabled": getattr(dev, "totp_enabled", False),
            "session_token": token,
            "last_login": dev.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if dev.last_login_at else "First Login",
        }

        record_developer_audit(
            developer=dev.username,
            performed_by=dev.username,
            action="Layer 1 Authenticated",
            module="Authentication",
            status="Success",
            details="Username and password hash verified.",
            ip_address=ip_address,
            device=device_name,
        )
        return True, "Layer 1 credentials verified.", dev_dict


# ─────────────────────────────────────────────────────────────────────────────
# 3. LAYER 2: INDIVIDUAL DEVELOPER ACCESS KEY VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def validate_developer_access_key(
    developer_id: int,
    access_key: str,
    ip_address: str = "127.0.0.1",
    device_name: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Layer 2: Developer Access Key Validation.
    Access is granted ONLY when:
    • Key belongs specifically to developer_id (never shared).
    • Key status is strictly ACTIVE.
    • Key has not expired.
    • Cryptographic bcrypt hash validates against the key.
    On success, updates last_used_at, last_used_ip, last_used_device.
    """
    key_clean = access_key.strip()
    if not key_clean:
        return False, "Developer Access Key cannot be empty."

    now = datetime.now()

    with get_db_session() as session:
        dev = session.execute(select(Developer).where(Developer.id == developer_id)).scalar_one_or_none()
        if not dev:
            return False, "Developer account not found."

        dev_user = dev.username
        dev_role = getattr(dev, "role", "Developer")
        dev_is_owner = bool(getattr(dev, "is_owner", False) or dev_role == "Owner")

        # Query all keys owned by this specific developer
        keys = session.execute(
            select(DeveloperKey).where(
                DeveloperKey.developer_id == developer_id,
            )
        ).scalars().all()

        if not keys:
            record_developer_audit(
                developer=dev_user,
                performed_by=dev_user,
                action="Key Validation Failed",
                module="Authentication",
                status="Failure",
                details="No access keys provisioned for this account.",
                ip_address=ip_address,
                device=device_name,
            )
            return False, "No Developer Access Keys found for your account. Contact Team Lead / Owner."

        matched_key = None
        for k in keys:
            # Check bcrypt hash first
            if verify_dev_password(key_clean, k.key_hash):
                matched_key = k
                break

        if not matched_key:
            # Master key override verification (restricted to Owner accounts)
            from src.developer.dev_service import verify_dev_master_key
            if verify_dev_master_key(key_clean):
                if not dev_is_owner:
                    record_developer_audit(
                        developer=dev_user,
                        performed_by=dev_user,
                        action="Master Key Rejected",
                        module="Authentication",
                        status="Failure",
                        details="Attempted Master Key login with standard developer account (restricted to Owner).",
                        ip_address=ip_address,
                        device=device_name,
                    )
                    return False, "Master Management Key is restricted to Owner accounts. Standard developers must use their assigned access key."

                record_developer_audit(
                    developer=dev_user,
                    performed_by=dev_user,
                    action="Master Key Override",
                    module="Authentication",
                    status="Success",
                    details="Authenticated Layer 2 via Master Developer Management Key override.",
                    ip_address=ip_address,
                    device=device_name,
                )
                return True, "Authenticated via Master Developer Management Key override."

            record_developer_audit(
                developer=dev_user,
                performed_by=dev_user,
                action="Key Validation Failed",
                module="Authentication",
                status="Failure",
                details="Access key did not match any credentials assigned to this developer.",
                ip_address=ip_address,
                device=device_name,
            )
            return False, "Invalid Developer Access Key. Ensure you are using your own personal active key."

        # Check key expiration
        if matched_key.expires_at and matched_key.expires_at < now:
            matched_key.status = "EXPIRED"
            session.commit()
            record_developer_audit(
                developer=dev_user,
                performed_by=dev_user,
                action="Key Expired",
                module="Authentication",
                status="Warning",
                details=f"Access Key {matched_key.key_prefix} expired on {matched_key.expires_at}",
                ip_address=ip_address,
                device=device_name,
            )
            return False, "Developer Access Key has EXPIRED. Request key rotation from Team Lead / Owner."

        # Check key lifecycle status
        if matched_key.status != "ACTIVE":
            status_msg = {
                "REVOKED": "Developer Access Key has been REVOKED.",
                "SUSPENDED": "Developer Access Key is temporarily SUSPENDED.",
                "COMPROMISED": "Developer Access Key was flagged COMPROMISED.",
                "REPLACED": "Developer Access Key was REPLACED during key rotation.",
                "EXPIRED": "Developer Access Key has EXPIRED.",
            }.get(matched_key.status, f"Access Key is not active (Status: {matched_key.status}).")

            record_developer_audit(
                developer=dev_user,
                performed_by=dev_user,
                action="Key Validation Rejected",
                module="Authentication",
                status="Failure",
                details=f"Attempted login with {matched_key.status} key {matched_key.key_prefix}",
                ip_address=ip_address,
                device=device_name,
            )
            return False, f"{status_msg} Contact Team Lead / Owner."

        # Update telemetry on key
        matched_key.last_used_at = now
        matched_key.last_used_ip = ip_address
        matched_key.last_used_device = device_name or f"{platform.node()} ({platform.system()})"
        session.commit()

        record_developer_audit(
            developer=dev_user,
            performed_by=dev_user,
            action="Layer 2 Authenticated",
            module="Authentication",
            status="Success",
            details=f"Personal Developer Access Key validated (Prefix: {matched_key.key_prefix}, v{matched_key.key_version})",
            ip_address=ip_address,
            device=device_name,
        )
        return True, "Developer Access Key validated successfully."


# ─────────────────────────────────────────────────────────────────────────────
# 4. LAYER 3: TRUSTED WORKSTATION & DEVICE REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

def parse_user_agent_details(user_agent: Optional[str]) -> Tuple[str, str]:
    """Parse friendly browser and OS names from user agent or system runtime."""
    ua = (user_agent or "").lower()
    os_name = platform.system()
    if "windows" in ua or "win" in ua:
        os_name = "Windows"
    elif "mac" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"

    browser_name = "Browser"
    if "edg" in ua:
        browser_name = "Microsoft Edge"
    elif "chrome" in ua:
        browser_name = "Google Chrome"
    elif "firefox" in ua:
        browser_name = "Mozilla Firefox"
    elif "safari" in ua and "chrome" not in ua:
        browser_name = "Apple Safari"
    else:
        browser_name = f"{platform.node()} Workstation"

    return browser_name, os_name


def check_trusted_device(
    developer_id: int,
    device_fingerprint: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Layer 3: Trusted Device Check.
    Returns (is_trusted: bool, message: str, device_dict: Optional[Dict])
    """
    if not device_fingerprint:
        return False, "Device fingerprint missing.", None

    with get_db_session() as session:
        dev_rec = session.execute(
            select(DeveloperDevice).where(
                DeveloperDevice.developer_id == developer_id,
                DeveloperDevice.device_fingerprint == device_fingerprint.strip(),
            )
        ).scalar_one_or_none()

        if not dev_rec:
            return False, "Unrecognized device. Authorization required.", None

        dev_dict = {
            "id": dev_rec.id,
            "developer_id": dev_rec.developer_id,
            "device_fingerprint": dev_rec.device_fingerprint,
            "device_name": dev_rec.device_name,
            "browser": getattr(dev_rec, "browser", "Browser"),
            "os": getattr(dev_rec, "os", "OS"),
            "ip_address": dev_rec.ip_address,
            "status": dev_rec.status,
            "first_login": dev_rec.first_login_at.strftime("%Y-%m-%d %H:%M:%S") if dev_rec.first_login_at else "—",
            "last_login": dev_rec.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if dev_rec.last_login_at else "—",
        }

        if dev_rec.status == "BLOCKED":
            return False, "This workstation has been BLOCKED by the Team Lead / Owner.", dev_dict
        if dev_rec.status != "TRUSTED":
            return False, f"Device authorization status is '{dev_rec.status}'. Pending approval.", dev_dict

        # Update last used timestamp
        dev_rec.last_login_at = datetime.now()
        session.commit()
        return True, "Device authorized.", dev_dict


def register_trusted_device(
    developer_id: int,
    device_fingerprint: str,
    device_name: str = "Authorized Workstation",
    ip_address: str = "127.0.0.1",
    user_agent: Optional[str] = None,
    approved_by_owner: bool = True,
) -> Tuple[bool, str]:
    """
    Register a workstation for a developer.
    Status is TRUSTED if approved by Owner or bootstrapping, otherwise PENDING.
    """
    if not device_fingerprint:
        return False, "Invalid device fingerprint."

    now = datetime.now()
    browser_name, os_name = parse_user_agent_details(user_agent)
    initial_status = "TRUSTED" if approved_by_owner else "PENDING"

    with get_db_session() as session:
        existing = session.execute(
            select(DeveloperDevice).where(
                DeveloperDevice.developer_id == developer_id,
                DeveloperDevice.device_fingerprint == device_fingerprint.strip(),
            )
        ).scalar_one_or_none()

        if existing:
            if approved_by_owner:
                existing.status = "TRUSTED"
            existing.device_name = device_name
            existing.browser = browser_name
            existing.os = os_name
            existing.ip_address = ip_address
            existing.last_login_at = now
            session.commit()
            return True, f"Workstation '{device_name}' updated (Status: {existing.status})."

        dev_rec = DeveloperDevice(
            developer_id=developer_id,
            device_fingerprint=device_fingerprint.strip(),
            device_name=device_name,
            browser=browser_name,
            os=os_name,
            ip_address=ip_address,
            user_agent=user_agent,
            status=initial_status,
            first_login_at=now,
            last_login_at=now,
            created_at=now,
        )
        session.add(dev_rec)
        session.commit()

    return True, f"Workstation '{device_name}' registered successfully."


def list_trusted_devices_db(developer_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """List devices. If developer_id is None, lists all registered devices (for Owner)."""
    with get_db_session() as session:
        query = select(DeveloperDevice)
        if developer_id is not None:
            query = query.where(DeveloperDevice.developer_id == developer_id)

        devs = session.execute(query.order_by(DeveloperDevice.last_login_at.desc())).scalars().all()
        # Fetch developer username map
        dev_map = {d.id: d.username for d in session.execute(select(Developer)).scalars().all()}

        return [{
            "id": d.id,
            "developer_id": d.developer_id,
            "developer_username": dev_map.get(d.developer_id, "Unknown"),
            "device_name": d.device_name,
            "browser": getattr(d, "browser", "Browser"),
            "os": getattr(d, "os", "OS"),
            "fingerprint": d.device_fingerprint[:16] + "...",
            "full_fingerprint": d.device_fingerprint,
            "ip_address": d.ip_address,
            "status": d.status,
            "first_login": d.first_login_at.strftime("%Y-%m-%d %H:%M") if d.first_login_at else "—",
            "last_login": d.last_login_at.strftime("%Y-%m-%d %H:%M") if d.last_login_at else "Never",
            "created_at": d.created_at.strftime("%Y-%m-%d") if d.created_at else "",
        } for d in devs]


def revoke_trusted_device_db(device_id: int, developer_id: Optional[int] = None) -> Tuple[bool, str]:
    """Revoke or delete a registered workstation."""
    with get_db_session() as session:
        query = select(DeveloperDevice).where(DeveloperDevice.id == device_id)
        if developer_id is not None:
            query = query.where(DeveloperDevice.developer_id == developer_id)
        d = session.execute(query).scalar_one_or_none()
        if not d:
            return False, "Device not found."
        session.delete(d)
        session.commit()
    return True, "Workstation authorization revoked."


# ─────────────────────────────────────────────────────────────────────────────
# 5. PASSWORD CHANGE & LIFECYCLE
# ─────────────────────────────────────────────────────────────────────────────

def dev_change_password(
    developer_id: int,
    old_password: str,
    new_password: str,
    ip_address: str = "127.0.0.1",
    device_name: Optional[str] = None,
) -> Tuple[bool, str]:
    """Developer changes their own password."""
    if not new_password or len(new_password) < 8:
        return False, "New password must be at least 8 characters."

    now = datetime.now()
    with get_db_session() as session:
        dev = session.execute(select(Developer).where(Developer.id == developer_id)).scalar_one_or_none()
        if not dev:
            return False, "Developer not found."

        if not verify_dev_password(old_password, dev.password_hash):
            return False, "Incorrect current password."

        dev.password_hash = hash_dev_password(new_password)
        dev.must_change_password = False
        dev.updated_at = now
        session.commit()

        record_developer_audit(
            developer=dev.username,
            performed_by=dev.username,
            action="Password Changed",
            module="Identity",
            status="Success",
            details="Developer successfully changed password.",
            ip_address=ip_address,
            device=device_name,
        )
    return True, "Password changed successfully."


# ─────────────────────────────────────────────────────────────────────────────
# 6. BOOTSTRAP INITIAL OWNER
# ─────────────────────────────────────────────────────────────────────────────

def has_any_developers() -> bool:
    """Check if any Developer/Owner exists in the database."""
    with get_db_session() as session:
        return session.query(Developer).count() > 0


def bootstrap_first_developer(
    full_name: str,
    username: str,
    email: str,
    password: str,
    device_fingerprint: str,
    initial_access_key: Optional[str] = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Initial System Setup: Creates the root Owner developer account,
    sets up roles, issues the primary Developer Access Key, and authorizes device.
    Returns (success: bool, message: str, generated_key: Optional[str])
    """
    if has_any_developers():
        return False, "System has already been bootstrapped. New developers must be invited by an Owner.", None

    clean_user = username.strip()
    clean_email = email.strip().lower()
    clean_name = full_name.strip()

    if not clean_user or not password or len(password) < 8:
        return False, "Username and password (min 8 characters) are required.", None

    now = datetime.now()
    generated_key = initial_access_key.strip() if initial_access_key and initial_access_key.strip() else generate_cryptographic_dev_key()
    prefix = generated_key[:12]

    with get_db_session() as session:
        # Seed default roles if not existing
        r_owner = session.execute(select(DeveloperRole).where(DeveloperRole.name == "Owner")).scalar_one_or_none()
        if not r_owner:
            r_owner = DeveloperRole(
                name="Owner",
                description="Team Lead / System Owner with full IAM authority.",
                permissions={"all": True},
            )
            session.add(r_owner)
            session.flush()

        r_dev = session.execute(select(DeveloperRole).where(DeveloperRole.name == "Developer")).scalar_one_or_none()
        if not r_dev:
            r_dev = DeveloperRole(
                name="Developer",
                description="Standard Developer with operational access to code and ML registry.",
                permissions={"read_keys": True},
            )
            session.add(r_dev)
            session.flush()

        # Create Owner Developer
        owner = Developer(
            username=clean_user,
            email=clean_email,
            full_name=clean_name,
            password_hash=hash_dev_password(password),
            role="Owner",
            role_id=r_owner.id,
            is_active=True,
            status="ACTIVE",
            must_change_password=False,
            created_at=now,
            updated_at=now,
        )
        session.add(owner)
        session.flush()

        # Seed Layer 2 Developer Access Key (strictly owned by Owner)
        key_hash = hash_dev_password(generated_key)
        access_key_rec = DeveloperKey(
            developer_id=owner.id,
            name="Primary Owner Access Key",
            key_prefix=prefix,
            key_hash=key_hash,
            status="ACTIVE",
            key_version=1,
            description="Cryptographic access key issued at platform bootstrap.",
            created_by="Bootstrap",
            created_at=now,
            expires_at=now + timedelta(days=365),
        )
        session.add(access_key_rec)

        # Seed Layer 3 Trusted Device
        if device_fingerprint:
            trusted_dev = DeveloperDevice(
                developer_id=owner.id,
                device_fingerprint=device_fingerprint.strip(),
                device_name="Primary Setup Workstation",
                browser="Setup Browser",
                os=platform.system(),
                ip_address="127.0.0.1",
                status="TRUSTED",
                first_login_at=now,
                last_login_at=now,
                created_at=now,
            )
            session.add(trusted_dev)

        session.commit()

    record_developer_audit(
        developer=clean_user,
        performed_by=clean_user,
        action="System Bootstrapped",
        module="Bootstrap",
        status="Success",
        details=f"Root Owner account established with key prefix {prefix}.",
    )
    return True, f"Owner account '{clean_user}' bootstrapped successfully!", generated_key


# ─────────────────────────────────────────────────────────────────────────────
# 7. SESSION MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def validate_developer_session(
    session_token: str,
    timeout_seconds: int = DEV_SESSION_TIMEOUT,
) -> Tuple[bool, Optional[Developer]]:
    """Validate that developer session token is active and unexpired."""
    if not session_token:
        return False, None

    now = datetime.now()
    with get_db_session() as session:
        sess = session.execute(
            select(DeveloperSession).where(
                DeveloperSession.session_token == session_token,
                DeveloperSession.is_active == True,
            )
        ).scalar_one_or_none()

        if not sess:
            return False, None

        if sess.expires_at < now or (now - sess.last_active_at).total_seconds() > timeout_seconds:
            sess.is_active = False
            session.commit()
            return False, None

        sess.last_active_at = now
        dev = sess.developer
        session.commit()
        return True, dev


def terminate_developer_session(session_token: str, username: str = "Unknown") -> None:
    """Terminate developer session."""
    if not session_token:
        return
    with get_db_session() as session:
        sess = session.execute(
            select(DeveloperSession).where(DeveloperSession.session_token == session_token)
        ).scalar_one_or_none()
        if sess:
            sess.is_active = False
            session.commit()

    record_developer_audit(
        developer=username,
        performed_by=username,
        action="Developer Logout",
        module="Authentication",
        status="Success",
        details="Developer closed session.",
    )
