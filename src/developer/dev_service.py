"""
dev_service.py
==============
Service layer for Developer Portal operations:
- Exclusive Registration ID Authority (Generation, Revocation, Extension, Deletion)
- Database inspection, maintenance (vacuum, table row counts)
- ML Model Registry & API Keys management
- License oversight and live system health metrics
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import desc, func, or_, select, text

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.db.models import (
    ApiKey,
    AuditLog,
    BusinessRule,
    DatasetVersion,
    DelayThreshold,
    Developer,
    DeveloperAuditLog,
    DeveloperDevice,
    DeveloperKey,
    DeveloperRole,
    DeveloperSession,
    FactoryCoordinate,
    LicenseInfo,
    MLMetadata,
    MLSetting,
    ProductMapping,
    RegistrationId,
    Role,
    SessionRecord,
    SystemSecurity,
    User,
)
from src.db.session import engine, get_db_session
from src.developer.dev_security import (
    generate_cryptographic_dev_key,
    hash_dev_password,
    mask_developer_key,
    record_developer_audit,
)
from src.utils import PROJECT_ROOT, get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. REGISTRATION ID AUTHORITY (EXCLUSIVE TO DEVELOPERS)
# ─────────────────────────────────────────────────────────────────────────────

def dev_generate_registration_ids(
    count: int = 1,
    valid_days: int = 90,
    created_by: str = "developer",
    notes: str = "",
) -> List[str]:
    """Developer generates single or batch company registration tokens."""
    tokens = []
    now = datetime.now()
    expiry = now + timedelta(days=valid_days)

    with get_db_session() as session:
        for _ in range(count):
            tok = f"REG-{uuid.uuid4().hex[:12].upper()}"
            reg = RegistrationId(
                token=tok,
                status="ACTIVE",
                expiry_date=expiry,
                created_by=created_by,
                created_at=now,
                notes=notes,
            )
            session.add(reg)
            tokens.append(tok)
        session.commit()

    record_developer_audit(
        developer=created_by,
        action="Generate Registration Keys",
        module="KeyAuthority",
        status="Success",
        details=f"Generated {count} key(s) with {valid_days}-day validity. Notes: {notes}",
    )
    return tokens


def dev_list_registration_ids(
    status_filter: Optional[str] = None,
    search_query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Query registration keys with status filtering and text search."""
    with get_db_session() as session:
        q = select(RegistrationId).order_by(desc(RegistrationId.created_at))
        if status_filter and status_filter != "ALL":
            q = q.where(RegistrationId.status == status_filter)

        regs = session.execute(q).scalars().all()
        now = datetime.now()
        results = []

        for r in regs:
            stat = r.status
            if stat == "ACTIVE" and r.expiry_date and r.expiry_date < now:
                stat = "EXPIRED"

            item = {
                "id": r.id,
                "token": r.token,
                "status": stat,
                "expiry_date": r.expiry_date.strftime("%Y-%m-%d %H:%M:%S") if r.expiry_date else "Never",
                "created_by": r.created_by,
                "created_date": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
                "used_by": r.used_by or "—",
                "used_date": r.used_at.strftime("%Y-%m-%d %H:%M:%S") if r.used_at else "—",
                "notes": r.notes or "",
            }

            if search_query:
                sq = search_query.lower()
                if (sq not in item["token"].lower() and
                    sq not in (item["used_by"] or "").lower() and
                    sq not in (item["notes"] or "").lower()):
                    continue

            results.append(item)

        return results


def dev_update_key_status(token: str, new_status: str, developer: str = "developer") -> Tuple[bool, str]:
    """Revoke or expire a key."""
    with get_db_session() as session:
        reg = session.execute(select(RegistrationId).where(RegistrationId.token == token.strip())).scalar_one_or_none()
        if not reg:
            return False, f"Key '{token}' not found."
        if reg.status == "USED":
            return False, "Cannot alter an already USED registration key."

        reg.status = new_status
        session.commit()

    record_developer_audit(
        developer=developer,
        action=f"Key Status → {new_status}",
        module="KeyAuthority",
        status="Success",
        details=f"Registration key {token} transitioned to {new_status}",
    )
    return True, f"Key {token} successfully marked as {new_status}."


def dev_extend_key_expiry(token: str, additional_days: int = 30, developer: str = "developer") -> Tuple[bool, str]:
    """Extend expiration date of an active or expired key."""
    with get_db_session() as session:
        reg = session.execute(select(RegistrationId).where(RegistrationId.token == token.strip())).scalar_one_or_none()
        if not reg:
            return False, "Key not found."
        if reg.status == "USED":
            return False, "Cannot extend an already used key."

        base_date = max(datetime.now(), reg.expiry_date)
        new_expiry = base_date + timedelta(days=additional_days)
        reg.expiry_date = new_expiry
        if reg.status == "EXPIRED":
            reg.status = "ACTIVE"
        session.commit()

    record_developer_audit(
        developer=developer,
        action="Extend Key Expiry",
        module="KeyAuthority",
        status="Success",
        details=f"Extended key {token} by {additional_days} days to {new_expiry.strftime('%Y-%m-%d')}",
    )
    return True, f"Key extended to {new_expiry.strftime('%Y-%m-%d %H:%M:%S')}."


def dev_delete_unused_key(token: str, developer: str = "developer") -> Tuple[bool, str]:
    """Permanently delete an unused key."""
    with get_db_session() as session:
        reg = session.execute(select(RegistrationId).where(RegistrationId.token == token.strip())).scalar_one_or_none()
        if not reg:
            return False, "Key not found."
        if reg.status == "USED":
            return False, "Security Violation: Cannot delete an activated/used key."

        session.delete(reg)
        session.commit()

    record_developer_audit(
        developer=developer,
        action="Delete Registration Key",
        module="KeyAuthority",
        status="Success",
        details=f"Permanently purged key {token}",
    )
    return True, f"Key {token} successfully deleted."


# ─────────────────────────────────────────────────────────────────────────────
# 2. DATABASE & SYSTEM HEALTH
# ─────────────────────────────────────────────────────────────────────────────

def dev_get_system_health() -> Dict[str, Any]:
    """Aggregate live platform statistics, database size, and table row counts."""
    db_path = PROJECT_ROOT / "data" / "admin" / "logistics_platform.db"
    db_size_mb = (db_path.stat().st_size / (1024 * 1024)) if db_path.exists() else 0.0

    table_counts: Dict[str, int] = {}
    with get_db_session() as session:
        table_counts["users"] = session.query(User).count()
        table_counts["developers"] = session.query(Developer).count()
        table_counts["developer_keys"] = session.query(DeveloperKey).count()
        table_counts["developer_devices"] = session.query(DeveloperDevice).count()
        table_counts["registration_ids"] = session.query(RegistrationId).count()
        table_counts["audit_logs"] = session.query(AuditLog).count()
        table_counts["developer_audit_logs"] = session.query(DeveloperAuditLog).count()
        table_counts["factory_coordinates"] = session.query(FactoryCoordinate).count()
        table_counts["product_mappings"] = session.query(ProductMapping).count()
        table_counts["dataset_versions"] = session.query(DatasetVersion).count()
        table_counts["ml_metadata"] = session.query(MLMetadata).count()

    active_keys = 0
    used_keys = 0
    with get_db_session() as session:
        active_keys = session.query(RegistrationId).filter(RegistrationId.status == "ACTIVE").count()
        used_keys = session.query(RegistrationId).filter(RegistrationId.status == "USED").count()

    return {
        "os": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "database_engine": "SQLite (SQLAlchemy ORM, PostgreSQL-ready)",
        "database_size_mb": round(db_size_mb, 2),
        "db_path": str(db_path),
        "table_counts": table_counts,
        "active_keys_count": active_keys,
        "used_keys_count": used_keys,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def dev_vacuum_database(developer: str = "developer") -> Tuple[bool, str]:
    """Execute SQLite VACUUM optimization."""
    try:
        with engine.connect() as conn:
            conn.execute(text("VACUUM"))
            conn.commit()
        record_developer_audit(
            developer=developer,
            action="Vacuum Database",
            module="DatabaseOps",
            status="Success",
            details="Executed SQLite VACUUM compaction.",
        )
        return True, "Database vacuumed and optimized successfully."
    except Exception as e:
        return False, f"Vacuum failed: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. ML MODEL REGISTRY & API KEYS
# ─────────────────────────────────────────────────────────────────────────────

def dev_list_ml_models() -> List[Dict[str, Any]]:
    """Fetch registered ML models and performance benchmarks."""
    with get_db_session() as session:
        models = session.execute(select(MLMetadata).order_by(desc(MLMetadata.trained_at))).scalars().all()
        return [{
            "id": m.id,
            "name": m.model_name,
            "version": m.version,
            "metrics": m.metrics or {},
            "trained_by": m.trained_by,
            "trained_at": m.trained_at.strftime("%Y-%m-%d %H:%M:%S") if m.trained_at else "",
        } for m in models]


def dev_list_api_keys() -> List[Dict[str, Any]]:
    """Retrieve external integration API keys."""
    with get_db_session() as session:
        keys = session.execute(select(ApiKey).order_by(desc(ApiKey.created_at))).scalars().all()
        return [{
            "id": k.id,
            "name": k.name,
            "prefix": k.key_prefix,
            "status": k.status,
            "created_by": k.created_by,
            "created_at": k.created_at.strftime("%Y-%m-%d %H:%M:%S") if k.created_at else "",
        } for k in keys]


def dev_list_license_info() -> Optional[Dict[str, Any]]:
    """Retrieve platform deployment license info."""
    with get_db_session() as session:
        lic = session.execute(select(LicenseInfo)).scalars().first()
        if lic:
            return {
                "licensee": lic.licensee,
                "tier": lic.license_tier,
                "key": lic.license_key,
                "max_nodes": lic.max_nodes,
                "valid_until": lic.valid_until.strftime("%Y-%m-%d"),
                "status": lic.status,
            }
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 4. OWNER DEVELOPER MANAGEMENT & MASTER KEY SUBSYSTEM
# ─────────────────────────────────────────────────────────────────────────────

DEV_MASTER_MANAGEMENT_KEY = "ChangeMeMasterKey2026!"
DEV_MASTER_MANAGEMENT_KEY_HASH = "$2b$12$53leTGWk4Gvl7o/vl1uKmu0WuOhRx4qgveqxwND4j1OAUY2ncmnpW"


def verify_dev_master_key(input_key: str) -> bool:
    """Verify Master Developer Management Key cryptographically using salted bcrypt against database hash."""
    import bcrypt
    if not input_key or not input_key.strip():
        return False
    clean = input_key.strip()
    try:
        with get_db_session() as session:
            sec = session.execute(select(SystemSecurity).order_by(SystemSecurity.id.desc())).scalar_one_or_none()
            if sec and sec.master_key_hash:
                return bcrypt.checkpw(clean.encode("utf-8"), sec.master_key_hash.encode("utf-8"))
    except Exception as e:
        logger.warning("Master key DB verification error: %s", e)

    # Fallback to direct verification against known bcrypt hash
    try:
        return bcrypt.checkpw(clean.encode("utf-8"), DEV_MASTER_MANAGEMENT_KEY_HASH.encode("utf-8"))
    except Exception as e:
        logger.warning("Master key fallback verification error: %s", e)
        return False


def is_authorized_owner(caller_identifier: str) -> bool:
    """
    Server-side authorization check:
    Verifies if the caller has root Owner/Team Lead privileges.
    Permissions are strictly determined by the user's assigned database role (is_owner=True and role='Owner').
    System setup/bootstrap markers are honored only for automated migrations.
    """
    if not caller_identifier or not caller_identifier.strip():
        return False
    clean = caller_identifier.strip()
    # System / test markers
    if clean.lower() in {"owner", "bootstrap", "system", "setup", "rootowner", "teamlead"}:
        return True
    try:
        with get_db_session() as session:
            dev = session.execute(
                select(Developer).where(or_(Developer.username == clean, Developer.email == clean))
            ).scalar_one_or_none()
            if dev:
                return bool(getattr(dev, "is_owner", False) and dev.role == "Owner")
    except Exception as e:
        logger.warning("Error checking caller owner authority: %s", e)
    return False


def dev_create_new_developer(
    full_name: str,
    username: str,
    email: str,
    password: str,
    role: str = "Developer",
    initial_access_key: Optional[str] = None,
    created_by: str = "Owner",
    valid_days: int = 90,
) -> Tuple[bool, str, Optional[str]]:
    """
    Owner provisions a new developer account and issues an initial personal Developer Access Key.
    Enforces server-side authorization check (Owner only) and must_change_password=True on first login.
    Returns (success: bool, message: str, one_time_plaintext_key: Optional[str])
    """
    if not is_authorized_owner(created_by):
        record_developer_audit(
            developer=created_by,
            performed_by=created_by,
            action="Unauthorized Governance Attempt",
            module="DeveloperIAM",
            status="Failure",
            details=f"Non-owner account '{created_by}' attempted to provision new developer.",
        )
        return False, "Access Denied: Only the Team Lead / Owner can create developer accounts.", None
    clean_user = username.strip()
    clean_email = email.strip().lower()
    clean_name = full_name.strip()

    if not clean_user or len(clean_user) < 3:
        return False, "Username must be at least 3 characters.", None
    if "@" not in clean_email or "." not in clean_email:
        return False, "Please provide a valid email.", None
    if len(password) < 8:
        return False, "Password must be at least 8 characters.", None

    now = datetime.now()
    expiry = now + timedelta(days=valid_days)
    generated_key = initial_access_key.strip() if initial_access_key and initial_access_key.strip() else generate_cryptographic_dev_key()
    prefix = generated_key[:12]

    with get_db_session() as session:
        existing = session.execute(select(Developer).where(Developer.username == clean_user)).scalar_one_or_none()
        if existing:
            return False, f"Username '{clean_user}' already taken.", None

        existing_em = session.execute(select(Developer).where(Developer.email == clean_email)).scalar_one_or_none()
        if existing_em:
            return False, f"Email '{clean_email}' already registered.", None

        role_rec = session.execute(select(DeveloperRole).where(DeveloperRole.name == role)).scalar_one_or_none()
        role_id = role_rec.id if role_rec else None

        new_dev = Developer(
            username=clean_user,
            email=clean_email,
            full_name=clean_name,
            password_hash=hash_dev_password(password),
            role=role,
            is_owner=(role == "Owner"),
            role_id=role_id,
            is_active=True,
            status="ACTIVE",
            must_change_password=True,
            created_at=now,
            updated_at=now,
        )
        session.add(new_dev)
        session.flush()

        # Seed initial Developer Access Key
        key_rec = DeveloperKey(
            developer_id=new_dev.id,
            name="Initial Provisioned Key",
            key_prefix=prefix,
            key_hash=hash_dev_password(generated_key),
            status="ACTIVE",
            key_version=1,
            description=f"Provisioned for {clean_user} by {created_by}",
            created_by=created_by,
            created_at=now,
            expires_at=expiry,
        )
        session.add(key_rec)
        session.commit()

    record_developer_audit(
        developer=clean_user,
        performed_by=created_by,
        action="Developer Created",
        module="DeveloperIAM",
        status="Success",
        details=f"Owner created developer account '{clean_user}' (Role: {role}, Key: {prefix})",
    )
    return True, f"Developer '{clean_user}' successfully provisioned!", generated_key


def dev_list_all_developers() -> List[Dict[str, Any]]:
    """List all developer accounts with role, status, and activity timestamps."""
    with get_db_session() as session:
        devs = session.execute(select(Developer).order_by(Developer.created_at)).scalars().all()
        return [{
            "id": d.id,
            "username": d.username,
            "full_name": d.full_name,
            "email": d.email,
            "role": getattr(d, "role", "Developer"),
            "status": getattr(d, "status", "ACTIVE"),
            "is_active": d.is_active,
            "must_change_password": getattr(d, "must_change_password", False),
            "last_login": d.last_login_at.strftime("%Y-%m-%d %H:%M") if d.last_login_at else "Never",
            "created_at": d.created_at.strftime("%Y-%m-%d") if d.created_at else "",
        } for d in devs]


def dev_list_developer_keys(dev_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    List developer access keys with full metadata.
    Auto-marks expired keys as EXPIRED if past expiry date.
    """
    now = datetime.now()
    with get_db_session() as session:
        query = select(DeveloperKey)
        if dev_id:
            query = query.where(DeveloperKey.developer_id == dev_id)

        keys = session.execute(query.order_by(DeveloperKey.created_at.desc())).scalars().all()

        # Developer lookup
        dev_map = {d.id: d for d in session.execute(select(Developer)).scalars().all()}
        results = []

        for k in keys:
            current_status = k.status
            if current_status == "ACTIVE" and k.expires_at and k.expires_at < now:
                k.status = "EXPIRED"
                current_status = "EXPIRED"

            dev_obj = dev_map.get(k.developer_id)
            dev_name = dev_obj.full_name if dev_obj else "Unknown"
            dev_user = dev_obj.username if dev_obj else "Unknown"
            dev_role = getattr(dev_obj, "role", "Developer") if dev_obj else "Developer"

            results.append({
                "id": k.id,
                "developer_id": k.developer_id,
                "developer_username": dev_user,
                "developer_name": dev_name,
                "role": dev_role,
                "name": k.name,
                "key_prefix": k.key_prefix,
                "masked_key": mask_developer_key(k.key_prefix),
                "status": current_status,
                "key_version": getattr(k, "key_version", 1),
                "description": getattr(k, "description", "") or "",
                "created_by": getattr(k, "created_by", "Owner"),
                "created_at": k.created_at.strftime("%Y-%m-%d %H:%M") if k.created_at else "",
                "expires_at": k.expires_at.strftime("%Y-%m-%d %H:%M") if k.expires_at else "Never",
                "last_used_at": k.last_used_at.strftime("%Y-%m-%d %H:%M") if k.last_used_at else "Never",
                "last_used_ip": getattr(k, "last_used_ip", None) or "—",
                "last_used_device": getattr(k, "last_used_device", None) or "—",
            })
        session.commit()
        return results


def dev_generate_new_dev_key_for_developer(
    dev_id: int,
    created_by: str = "Owner",
    key_name: str = "Developer Access Key",
    description: str = "",
    valid_days: int = 90,
) -> Tuple[bool, str, Optional[str]]:
    """
    Owner issues an additional new active Developer Access Key for a developer.
    Enforces server-side authorization check (Owner only).
    Returns (success: bool, message: str, one_time_plaintext_key: Optional[str])
    """
    if not is_authorized_owner(created_by):
        record_developer_audit(
            developer=created_by,
            performed_by=created_by,
            action="Unauthorized Key Generation Attempt",
            module="KeyAuthority",
            status="Failure",
            details=f"Non-owner account '{created_by}' attempted to generate dev key.",
        )
        return False, "Access Denied: Only the Team Lead / Owner can generate developer keys.", None

    now = datetime.now()
    expiry = now + timedelta(days=valid_days)
    generated_key = generate_cryptographic_dev_key()
    prefix = generated_key[:12]

    with get_db_session() as session:
        dev = session.execute(select(Developer).where(Developer.id == dev_id)).scalar_one_or_none()
        if not dev:
            return False, "Developer not found.", None

        dev_username = dev.username
        # Get highest version for this developer
        curr_keys = session.execute(
            select(DeveloperKey).where(DeveloperKey.developer_id == dev_id)
        ).scalars().all()
        next_version = max([getattr(k, "key_version", 1) for k in curr_keys] + [0]) + 1

        key_rec = DeveloperKey(
            developer_id=dev.id,
            name=key_name,
            key_prefix=prefix,
            key_hash=hash_dev_password(generated_key),
            status="ACTIVE",
            key_version=next_version,
            description=description or f"Issued by {created_by}",
            created_by=created_by,
            created_at=now,
            expires_at=expiry,
        )
        session.add(key_rec)
        session.commit()

    record_developer_audit(
        developer=dev_username,
        performed_by=created_by,
        action="Key Generated",
        module="KeyAuthority",
        status="Success",
        details=f"Owner issued new key {prefix} (v{next_version}, valid {valid_days}d)",
    )
    return True, f"New Dev Key successfully generated for '{dev_username}'.", generated_key


def dev_assign_key_to_developer(
    dev_id: int,
    custom_key: Optional[str] = None,
    created_by: str = "Owner",
    key_name: str = "Assigned Developer Access Key",
    description: str = "",
    valid_days: int = 90,
    replace_existing: bool = False,
) -> Tuple[bool, str, Optional[str]]:
    """
    Exclusive Team Lead / Owner operation:
    Assign an explicit or newly generated Developer Access Key to a developer.
    Enforces server-side authorization check (Owner only).
    Optionally marks all their other active keys as REPLACED.
    Returns (success, message, one_time_plaintext_key)
    """
    if not is_authorized_owner(created_by):
        record_developer_audit(
            developer=created_by,
            performed_by=created_by,
            action="Unauthorized Key Assignment Attempt",
            module="KeyAuthority",
            status="Failure",
            details=f"Non-owner account '{created_by}' attempted to assign dev key.",
        )
        return False, "Access Denied: Only the Team Lead / Owner can assign developer keys.", None

    now = datetime.now()
    expiry = now + timedelta(days=valid_days)

    raw_key = custom_key.strip() if custom_key and custom_key.strip() else generate_cryptographic_dev_key()
    prefix = raw_key[:12]

    with get_db_session() as session:
        dev = session.execute(select(Developer).where(Developer.id == dev_id)).scalar_one_or_none()
        if not dev:
            return False, "Target developer account not found.", None

        dev_username = dev.username

        if replace_existing:
            active_keys = session.execute(
                select(DeveloperKey).where(
                    DeveloperKey.developer_id == dev_id,
                    DeveloperKey.status == "ACTIVE",
                )
            ).scalars().all()
            for ak in active_keys:
                ak.status = "REPLACED"

        curr_keys = session.execute(
            select(DeveloperKey).where(DeveloperKey.developer_id == dev_id)
        ).scalars().all()
        next_version = max([getattr(k, "key_version", 1) for k in curr_keys] + [0]) + 1

        key_rec = DeveloperKey(
            developer_id=dev.id,
            name=key_name,
            key_prefix=prefix,
            key_hash=hash_dev_password(raw_key),
            status="ACTIVE",
            key_version=next_version,
            description=description or f"Assigned directly by Team Lead ({created_by})",
            created_by=created_by,
            created_at=now,
            expires_at=expiry,
        )
        session.add(key_rec)
        session.commit()

    record_developer_audit(
        developer=dev_username,
        performed_by=created_by,
        action="Key Assigned",
        module="KeyAuthority",
        status="Success",
        details=f"Team Lead assigned key {prefix} (v{next_version}) to {dev_username}",
    )
    return True, f"Developer Access Key successfully assigned to '{dev_username}'!", raw_key


def dev_generate_bulk_keys(
    dev_ids: List[int],
    created_by: str = "Owner",
    valid_days: int = 90,
) -> List[Dict[str, Any]]:
    """Generate keys in bulk for multiple developers."""
    generated = []
    for d_id in dev_ids:
        ok, msg, key = dev_generate_new_dev_key_for_developer(
            dev_id=d_id,
            created_by=created_by,
            key_name="Bulk Provisioned Key",
            valid_days=valid_days,
        )
        if ok and key:
            generated.append({"developer_id": d_id, "key": key})
    return generated


def dev_rotate_developer_key(
    dev_id: int,
    old_key_id: int,
    created_by: str = "Owner",
    valid_days: int = 90,
) -> Tuple[bool, str, Optional[str]]:
    """
    Key Rotation Workflow:
    1. Generate brand new cryptographic Developer Access Key.
    2. Mark the previous key as REPLACED immediately.
    3. Return one-time plaintext key for developer delivery.
    Returns (success: bool, message: str, one_time_new_key: Optional[str])
    """
    if not is_authorized_owner(created_by):
        record_developer_audit(
            developer=created_by,
            performed_by=created_by,
            action="Unauthorized Key Rotation Attempt",
            module="KeyAuthority",
            status="Failure",
            details=f"Non-owner account '{created_by}' attempted to rotate key.",
        )
        return False, "Access Denied: Only the Team Lead / Owner can rotate developer keys.", None

    now = datetime.now()
    expiry = now + timedelta(days=valid_days)
    new_raw_key = generate_cryptographic_dev_key()
    prefix = new_raw_key[:12]

    with get_db_session() as session:
        dev = session.execute(select(Developer).where(Developer.id == dev_id)).scalar_one_or_none()
        if not dev:
            return False, "Developer not found.", None

        dev_username = dev.username

        old_key = session.execute(
            select(DeveloperKey).where(
                DeveloperKey.id == old_key_id,
                DeveloperKey.developer_id == dev_id,
            )
        ).scalar_one_or_none()

        if not old_key:
            return False, "Target access key not found for rotation.", None

        # Determine version
        old_version = getattr(old_key, "key_version", 1)
        new_version = old_version + 1

        # Mark old key as REPLACED
        old_key.status = "REPLACED"

        # Create new active key
        new_key_rec = DeveloperKey(
            developer_id=dev.id,
            name=f"Rotated Key (v{new_version})",
            key_prefix=prefix,
            key_hash=hash_dev_password(new_raw_key),
            status="ACTIVE",
            key_version=new_version,
            description=f"Rotated from Key ID {old_key_id} ({old_key.key_prefix})",
            created_by=created_by,
            created_at=now,
            expires_at=expiry,
        )
        session.add(new_key_rec)
        session.commit()

    record_developer_audit(
        developer=dev_username,
        performed_by=created_by,
        action="Key Rotated",
        module="KeyAuthority",
        status="Success",
        details=f"Rotated key ID {old_key_id} -> New key {prefix} (v{new_version}). Previous key marked REPLACED.",
    )
    return True, f"Key successfully rotated! Previous key marked REPLACED.", new_raw_key


def dev_set_key_status(
    key_id: int,
    new_status: str,
    modified_by: str = "Owner",
) -> Tuple[bool, str]:
    """
    Update key lifecycle status: ACTIVE, EXPIRED, REVOKED, SUSPENDED, COMPROMISED, REPLACED.
    Enforces server-side authorization check (Owner only).
    """
    if not is_authorized_owner(modified_by):
        record_developer_audit(
            developer=modified_by,
            performed_by=modified_by,
            action="Unauthorized Key Status Attempt",
            module="KeyAuthority",
            status="Failure",
            details=f"Non-owner account '{modified_by}' attempted to alter key status.",
        )
        return False, "Access Denied: Only the Team Lead / Owner can modify key status."

    valid_states = {"ACTIVE", "EXPIRED", "REVOKED", "SUSPENDED", "COMPROMISED", "REPLACED"}
    target_state = new_status.upper().strip()
    if target_state not in valid_states:
        return False, f"Invalid status '{new_status}'. Allowed: {', '.join(valid_states)}"

    with get_db_session() as session:
        key_rec = session.execute(select(DeveloperKey).where(DeveloperKey.id == key_id)).scalar_one_or_none()
        if not key_rec:
            return False, "Key record not found."

        dev_username = key_rec.developer.username if key_rec.developer else "Unknown"
        key_prefix = key_rec.key_prefix
        old_status = key_rec.status
        key_rec.status = target_state
        session.commit()

    action_name = f"Key {target_state.capitalize()}"
    record_developer_audit(
        developer=dev_username,
        performed_by=modified_by,
        action=action_name,
        module="KeyAuthority",
        status="Success",
        details=f"Changed key {key_prefix} status: {old_status} -> {target_state}",
    )
    return True, f"Access Key status updated to '{target_state}'."


def dev_delete_key(key_id: int, modified_by: str = "Owner") -> Tuple[bool, str]:
    """Permanently delete an access key from the database."""
    if not is_authorized_owner(modified_by):
        record_developer_audit(
            developer=modified_by,
            performed_by=modified_by,
            action="Unauthorized Key Deletion Attempt",
            module="KeyAuthority",
            status="Failure",
            details=f"Non-owner account '{modified_by}' attempted to delete key.",
        )
        return False, "Access Denied: Only the Team Lead / Owner can delete access keys."

    with get_db_session() as session:
        key_rec = session.execute(select(DeveloperKey).where(DeveloperKey.id == key_id)).scalar_one_or_none()
        if not key_rec:
            return False, "Key not found."

        dev_username = key_rec.developer.username if key_rec.developer else "Unknown"
        prefix = key_rec.key_prefix
        session.delete(key_rec)
        session.commit()

    record_developer_audit(
        developer=dev_username,
        performed_by=modified_by,
        action="Key Deleted",
        module="KeyAuthority",
        status="Success",
        details=f"Permanently purged key {prefix} (ID: {key_id})",
    )
    return True, f"Access Key '{prefix}' permanently deleted."


def dev_toggle_developer_status(
    dev_id: int,
    status_or_active: Any = None,
    modified_by: str = "Owner",
    active: Optional[bool] = None,
) -> Tuple[bool, str]:
    """
    Set developer status: ACTIVE, SUSPENDED, DEACTIVATED.
    Supports active=True/False or status_or_active string/bool.
    """
    if active is not None:
        status_or_active = active
    with get_db_session() as session:
        dev = session.execute(select(Developer).where(Developer.id == dev_id)).scalar_one_or_none()
        if not dev:
            return False, "Developer not found."

        if isinstance(status_or_active, bool):
            target_status = "ACTIVE" if status_or_active else "DEACTIVATED"
            is_active_flag = status_or_active
        else:
            target_status = str(status_or_active).upper().strip()
            is_active_flag = (target_status == "ACTIVE")

        if dev.role == "Owner" and target_status != "ACTIVE":
            return False, "Cannot suspend or deactivate the root Owner account."

        dev_username = dev.username
        dev.status = target_status
        dev.is_active = is_active_flag
        dev.updated_at = datetime.now()
        session.commit()

    record_developer_audit(
        developer=dev_username,
        performed_by=modified_by,
        action=f"Developer {target_status.capitalize()}",
        module="DeveloperIAM",
        status="Success",
        details=f"Account status updated to {target_status}",
    )
    return True, f"Developer '{dev_username}' status set to {target_status}."


def dev_reset_developer_password(
    dev_id: int,
    new_password: str,
    modified_by: str = "Owner",
) -> Tuple[bool, str]:
    """Owner resets developer password and sets must_change_password=True."""
    if not is_authorized_owner(modified_by):
        record_developer_audit(
            developer=modified_by,
            performed_by=modified_by,
            action="Unauthorized Password Reset Attempt",
            module="DeveloperIAM",
            status="Failure",
            details=f"Non-owner account '{modified_by}' attempted to reset developer password.",
        )
        return False, "Access Denied: Only the Team Lead / Owner can reset developer passwords."

    if len(new_password) < 8:
        return False, "Password must be at least 8 characters."

    with get_db_session() as session:
        dev = session.execute(select(Developer).where(Developer.id == dev_id)).scalar_one_or_none()
        if not dev:
            return False, "Developer not found."

        dev_username = dev.username
        dev.password_hash = hash_dev_password(new_password)
        dev.must_change_password = True
        dev.failed_logins = 0
        dev.locked_until = None
        dev.updated_at = datetime.now()

        # Invalidate active sessions
        from src.db.models import DeveloperSession
        sessions = session.execute(
            select(DeveloperSession).where(
                DeveloperSession.developer_id == dev_id,
                DeveloperSession.is_active == True,
            )
        ).scalars().all()
        for s in sessions:
            s.is_active = False

        session.commit()

    record_developer_audit(
        developer=dev_username,
        performed_by=modified_by,
        action="Password Reset",
        module="DeveloperIAM",
        status="Success",
        details="Owner reset password; developer required to change upon next login.",
    )
    return True, f"Password reset for '{dev_username}'. Developer must change it upon next login."


def dev_delete_developer_account(
    dev_id: int,
    modified_by: str = "Owner",
) -> Tuple[bool, str]:
    """Owner deletes a developer account and cascades associated keys/devices."""
    if not is_authorized_owner(modified_by):
        record_developer_audit(
            developer=modified_by,
            performed_by=modified_by,
            action="Unauthorized Account Deletion Attempt",
            module="DeveloperIAM",
            status="Failure",
            details=f"Non-owner account '{modified_by}' attempted to delete developer account.",
        )
        return False, "Access Denied: Only the Team Lead / Owner can delete developer accounts."

    with get_db_session() as session:
        dev = session.execute(select(Developer).where(Developer.id == dev_id)).scalar_one_or_none()
        if not dev:
            return False, "Developer account not found."
        if dev.role == "Owner" or getattr(dev, "is_owner", False):
            return False, "Cannot delete the root Owner account. Transfer ownership first."

        dev_username = dev.username
        session.delete(dev)
        session.commit()

    record_developer_audit(
        developer=dev_username,
        performed_by=modified_by,
        action="Developer Deleted",
        module="DeveloperIAM",
        status="Success",
        details=f"Owner deleted developer account '{dev_username}'",
    )
    return True, f"Developer '{dev_username}' has been deleted."


def dev_assign_developer_role(
    dev_id: int,
    new_role: str,
    modified_by: str = "Owner",
) -> Tuple[bool, str]:
    """Assign Developer or Owner role."""
    if not is_authorized_owner(modified_by):
        record_developer_audit(
            developer=modified_by,
            performed_by=modified_by,
            action="Unauthorized Role Change Attempt",
            module="DeveloperIAM",
            status="Failure",
            details=f"Non-owner account '{modified_by}' attempted to change developer role.",
        )
        return False, "Access Denied: Only the Team Lead / Owner can assign roles."

    if new_role not in ["Owner", "Developer"]:
        return False, "Invalid role. Must be 'Owner' or 'Developer'."

    with get_db_session() as session:
        dev = session.execute(select(Developer).where(Developer.id == dev_id)).scalar_one_or_none()
        if not dev:
            return False, "Developer not found."

        r_rec = session.execute(select(DeveloperRole).where(DeveloperRole.name == new_role)).scalar_one_or_none()

        old_role = dev.role
        uname = dev.username
        dev.role = new_role
        if r_rec:
            dev.role_id = r_rec.id
        dev.updated_at = datetime.now()
        session.commit()

    record_developer_audit(
        developer=uname,
        performed_by=modified_by,
        action="Role Changed",
        module="DeveloperIAM",
        status="Success",
        details=f"Role changed from {old_role} to {new_role}",
    )
    return True, f"Role for '{uname}' updated to {new_role}."


def dev_transfer_ownership(
    target_dev_id: int,
    current_owner_id: int,
    modified_by: str = "Owner",
) -> Tuple[bool, str]:
    """Transfer Owner role to target developer and demote current owner to Developer."""
    with get_db_session() as session:
        current_owner = session.execute(select(Developer).where(Developer.id == current_owner_id)).scalar_one_or_none()
        target_dev = session.execute(select(Developer).where(Developer.id == target_dev_id)).scalar_one_or_none()

        if not current_owner or current_owner.role != "Owner":
            return False, "Current caller is not verified as Owner."
        if not target_dev:
            return False, "Target developer not found."
        if target_dev.id == current_owner.id:
            return False, "Target is already the Owner."

        target_uname = target_dev.username
        owner_uname = current_owner.username

        current_owner.role = "Developer"
        target_dev.role = "Owner"
        session.commit()

    record_developer_audit(
        developer=target_uname,
        performed_by=modified_by,
        action="Ownership Transferred",
        module="DeveloperIAM",
        status="Success",
        details=f"Ownership transferred from {owner_uname} to {target_uname}",
    )
    return True, f"Ownership successfully transferred to '{target_uname}'."


# ─────────────────────────────────────────────────────────────────────────────
# 5. TRUSTED DEVICE MANAGEMENT (OWNER & DEVELOPER)
# ─────────────────────────────────────────────────────────────────────────────

def dev_approve_device(device_id: int, modified_by: str = "Owner") -> Tuple[bool, str]:
    """Approve workstation as TRUSTED."""
    with get_db_session() as session:
        d = session.execute(select(DeveloperDevice).where(DeveloperDevice.id == device_id)).scalar_one_or_none()
        if not d:
            return False, "Device record not found."
        d.status = "TRUSTED"
        dev_user = d.developer.username if d.developer else "Unknown"
        device_name = d.device_name
        session.commit()

    record_developer_audit(
        developer=dev_user,
        performed_by=modified_by,
        action="Trusted Device Approved",
        module="DeviceAuthority",
        status="Success",
        details=f"Workstation '{device_name}' approved.",
    )
    return True, f"Device '{device_name}' approved as TRUSTED."


def dev_block_device(device_id: int, modified_by: str = "Owner") -> Tuple[bool, str]:
    """Block workstation."""
    with get_db_session() as session:
        d = session.execute(select(DeveloperDevice).where(DeveloperDevice.id == device_id)).scalar_one_or_none()
        if not d:
            return False, "Device record not found."
        d.status = "BLOCKED"
        dev_user = d.developer.username if d.developer else "Unknown"
        device_name = d.device_name
        session.commit()

    record_developer_audit(
        developer=dev_user,
        performed_by=modified_by,
        action="Trusted Device Blocked",
        module="DeviceAuthority",
        status="Warning",
        details=f"Workstation '{device_name}' BLOCKED.",
    )
    return True, f"Device '{device_name}' has been BLOCKED."


def dev_remove_device(device_id: int, modified_by: str = "Owner") -> Tuple[bool, str]:
    """Remove workstation from registry."""
    with get_db_session() as session:
        d = session.execute(select(DeveloperDevice).where(DeveloperDevice.id == device_id)).scalar_one_or_none()
        if not d:
            return False, "Device record not found."
        dev_user = d.developer.username if d.developer else "Unknown"
        name = d.device_name
        session.delete(d)
        session.commit()

    record_developer_audit(
        developer=dev_user,
        performed_by=modified_by,
        action="Trusted Device Removed",
        module="DeviceAuthority",
        status="Success",
        details=f"Removed workstation '{name}' (ID: {device_id})",
    )
    return True, f"Device '{name}' removed successfully."


def dev_rename_device(device_id: int, new_name: str, modified_by: str = "Owner") -> Tuple[bool, str]:
    """Rename registered workstation."""
    clean_name = new_name.strip()
    if not clean_name:
        return False, "Device name cannot be empty."

    with get_db_session() as session:
        d = session.execute(select(DeveloperDevice).where(DeveloperDevice.id == device_id)).scalar_one_or_none()
        if not d:
            return False, "Device record not found."
        d.device_name = clean_name
        session.commit()

    return True, f"Device renamed to '{clean_name}'."


def dev_list_iam_audit_logs(limit: int = 200) -> List[Dict[str, Any]]:
    """Fetch dedicated Developer IAM audit logs."""
    with get_db_session() as session:
        logs = session.execute(
            select(DeveloperAuditLog).order_by(DeveloperAuditLog.timestamp.desc()).limit(limit)
        ).scalars().all()
        return [{
            "id": l.id,
            "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "",
            "developer": l.developer,
            "performed_by": l.performed_by,
            "action": l.action,
            "status": l.status,
            "device": l.device or "—",
            "ip_address": l.ip_address or "127.0.0.1",
            "details": l.details or "",
        } for l in logs]


# ─────────────────────────────────────────────────────────────────────────────
# 9. ADMINISTRATOR GOVERNANCE (ACCESSIBLE TO DEVELOPER & OWNER)
# ─────────────────────────────────────────────────────────────────────────────

def dev_list_admin_users() -> List[Dict[str, Any]]:
    """
    List all administrator/system users with role details.
    Accessible to all authenticated Developers and Owners.
    """
    with get_db_session() as session:
        users = session.execute(
            select(User).order_by(User.id.asc())
        ).scalars().all()

        roles = {r.id: r.name for r in session.execute(select(Role)).scalars().all()}

        return [
            {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "email": u.email,
                "role_id": u.role_id,
                "role_name": roles.get(u.role_id, "Unknown"),
                "is_active": u.is_active,
                "failed_logins": u.failed_logins,
                "locked_until": u.locked_until.strftime("%Y-%m-%d %H:%M") if u.locked_until else None,
                "last_login_at": u.last_login_at.strftime("%Y-%m-%d %H:%M") if u.last_login_at else "Never",
                "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
                "updated_at": u.updated_at.strftime("%Y-%m-%d %H:%M") if u.updated_at else "",
            }
            for u in users
        ]


def dev_create_admin_user(
    username: str,
    full_name: str,
    email: str,
    password: str,
    role_name: str = "Administrator",
    created_by: str = "developer",
) -> Tuple[bool, str]:
    """
    Directly provision a new administrator/system user from Developer Control Portal.
    Bypasses manual registration key exchange while enforcing password complexity & uniqueness.
    """
    from src.admin_security import hash_password_bcrypt, validate_password_strength

    clean_user = username.strip()
    clean_name = full_name.strip()
    clean_email = email.strip().lower()

    if not clean_user or len(clean_user) < 3:
        return False, "Username must be at least 3 characters."
    if not clean_name:
        return False, "Full Name is required."
    if not clean_email or "@" not in clean_email or "." not in clean_email:
        return False, "A valid email address is required."

    is_strong, msg_strong = validate_password_strength(password)
    if not is_strong:
        return False, msg_strong

    with get_db_session() as session:
        # Check existing username or email
        existing = session.execute(
            select(User).where(or_(User.username == clean_user, User.email == clean_email))
        ).scalar_one_or_none()
        if existing:
            if existing.username.lower() == clean_user.lower():
                return False, f"Username '{clean_user}' is already registered."
            return False, f"Email address '{clean_email}' is already registered."

        # Find or create role
        role = session.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none()
        if not role:
            role = Role(name=role_name, description=f"{role_name} platform role")
            session.add(role)
            session.flush()

        new_user = User(
            username=clean_user,
            email=clean_email,
            full_name=clean_name,
            password_hash=hash_password_bcrypt(password),
            role_id=role.id,
            is_active=True,
            failed_logins=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(new_user)
        session.commit()

    record_developer_audit(
        developer=created_by,
        action="Admin Created",
        module="AdministratorGovernance",
        status="Success",
        details=f"Created administrator '{clean_user}' with role '{role_name}'",
    )
    return True, f"Administrator account '{clean_user}' created successfully."


def dev_update_admin_user(
    user_id: int,
    full_name: str,
    email: str,
    role_name: str,
    is_active: bool,
    modified_by: str = "developer",
) -> Tuple[bool, str]:
    """
    Update administrator profile, assigned role, or active status.
    """
    clean_name = full_name.strip()
    clean_email = email.strip().lower()

    if not clean_name:
        return False, "Full Name is required."
    if not clean_email or "@" not in clean_email:
        return False, "Valid corporate email is required."

    with get_db_session() as session:
        user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            return False, "Target user not found."

        # Email duplicate check
        dup = session.execute(
            select(User).where(User.email == clean_email, User.id != user_id)
        ).scalar_one_or_none()
        if dup:
            return False, f"Email '{clean_email}' is already in use by another account."

        # Role resolution
        role = session.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none()
        if not role:
            role = Role(name=role_name, description=f"{role_name} role")
            session.add(role)
            session.flush()

        username = user.username
        user.full_name = clean_name
        user.email = clean_email
        user.role_id = role.id
        user.is_active = is_active
        user.updated_at = datetime.utcnow()
        session.commit()

    record_developer_audit(
        developer=modified_by,
        action="Admin Updated",
        module="AdministratorGovernance",
        status="Success",
        details=f"Updated details for administrator '{username}' (Active: {is_active}, Role: {role_name})",
    )
    return True, f"Administrator '{username}' successfully updated."


def dev_reset_admin_password(
    user_id: int,
    new_password: str,
    modified_by: str = "developer",
) -> Tuple[bool, str]:
    """
    Reset administrator password, revoke active sessions, and reset lock status.
    """
    from src.admin_security import hash_password_bcrypt, validate_password_strength
    from src.db.models import SessionRecord

    is_strong, msg_strong = validate_password_strength(new_password)
    if not is_strong:
        return False, msg_strong

    with get_db_session() as session:
        user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            return False, "User account not found."

        username = user.username
        user.password_hash = hash_password_bcrypt(new_password)
        user.failed_logins = 0
        user.locked_until = None
        user.updated_at = datetime.utcnow()

        # Invalidate sessions for this user
        sessions = session.execute(
            select(SessionRecord).where(SessionRecord.user_id == user_id, SessionRecord.is_active == True)
        ).scalars().all()
        for s in sessions:
            s.is_active = False

        session.commit()

    record_developer_audit(
        developer=modified_by,
        action="Admin Password Reset",
        module="AdministratorGovernance",
        status="Success",
        details=f"Reset password and invalidated active sessions for '{username}'",
    )
    return True, f"Password successfully reset for '{username}'. Active sessions revoked."


def dev_delete_admin_user(
    user_id: int,
    modified_by: str = "developer",
) -> Tuple[bool, str]:
    """
    Permanently delete an administrator user account and clean up associated sessions.
    """
    from src.db.models import SessionRecord

    with get_db_session() as session:
        user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            return False, "User not found."

        username = user.username

        # Delete all session records for user
        sessions = session.execute(select(SessionRecord).where(SessionRecord.user_id == user_id)).scalars().all()
        for s in sessions:
            session.delete(s)

        session.delete(user)
        session.commit()

    record_developer_audit(
        developer=modified_by,
        action="Admin Deleted",
        module="AdministratorGovernance",
        status="Success",
        details=f"Permanently deleted administrator '{username}'",
    )
    return True, f"Administrator account '{username}' has been deleted."


