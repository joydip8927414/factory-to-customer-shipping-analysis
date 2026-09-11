"""
admin_manager.py
================
Enterprise administration manager handling:
- Dynamic business configurations (factory coords, mappings, SLA delay thresholds, KPI targets)
- Database-backed Registration ID management (UUID generation, revocation, deletion, expiry)
- Dataset version control (automatic pre-change backups, rollback, diff, restore)
- Immutable enterprise audit logging in SQLite/PostgreSQL with JSON fallback
- Automatic pipeline recalculation, ML feature recalibration, and global cache invalidation
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import desc, select

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_preprocessing import PRODUCT_NAME_CORRECTIONS
from src.db.models import (
    AuditLog,
    BusinessRule,
    DashboardSetting,
    DatasetVersion,
    DelayThreshold,
    FactoryCoordinate,
    MLMetadata,
    MLSetting,
    ProductMapping,
    RegistrationId,
    Role,
    User,
)
from src.db.session import get_db_session
from src.utils import (
    CLEANED_DATA_FILE,
    FACTORY_COORDINATES,
    FEATURED_DATA_FILE,
    PRODUCT_FACTORY_MAP,
    PROJECT_ROOT,
    RAW_DATA_FILE,
    compute_efficiency_score,
    get_logger,
)

logger = get_logger(__name__)

ADMIN_DIR = PROJECT_ROOT / "data" / "admin"
CONFIG_FILE = ADMIN_DIR / "business_config.json"
AUDIT_FILE = ADMIN_DIR / "audit_log.json"
VERSIONS_DIR = PROJECT_ROOT / "data" / "versions"


def ensure_manager_dirs() -> None:
    ADMIN_DIR.mkdir(parents=True, exist_ok=True)
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# 1. BUSINESS CONFIGURATION MANAGEMENT (DB-FIRST WITH JSON FALLBACK)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_CONFIG: Dict[str, Any] = {
    "factory_coordinates": FACTORY_COORDINATES,
    "product_factory_map": PRODUCT_FACTORY_MAP,
    "sla_thresholds_days": {
        "Standard Class": 5.0,
        "Second Class": 3.0,
        "First Class": 2.0,
        "Same Day": 1.0,
    },
    "efficiency_weights": {
        "delay_weight": 0.6,
        "lead_time_weight": 0.4,
    },
    "alert_thresholds": {
        "bottleneck_delay_rate_pct": 50.0,
        "min_shipments_for_evaluation": 5,
        "lead_time_outlier_days": 10.0,
    },
    "kpi_targets": {
        "target_delay_rate_pct": 25.0,
        "target_avg_lead_time_days": 3.5,
        "target_efficiency_score": 0.75,
    },
    "ml_settings": {
        "random_forest_estimators": 100,
        "test_size": 0.2,
        "random_state": 42,
    },
    "forecast_settings": {
        "default_horizon_months": 6,
        "confidence_level": 0.95,
    },
    "visualization_settings": {
        "default_chart_theme": "dark",
        "enable_sankey": True,
        "enable_animations": True,
    },
}


def load_business_config() -> Dict[str, Any]:
    """Load configuration from database tables, falling back to JSON config if needed."""
    cfg = DEFAULT_CONFIG.copy()
    try:
        with get_db_session() as session:
            # 1. Factory Coordinates
            fc_rows = session.execute(select(FactoryCoordinate).where(FactoryCoordinate.is_active == True)).scalars().all()
            if fc_rows:
                cfg["factory_coordinates"] = {r.factory_name: [r.latitude, r.longitude] for r in fc_rows}

            # 2. Product Mappings
            pm_rows = session.execute(select(ProductMapping).where(ProductMapping.is_active == True)).scalars().all()
            if pm_rows:
                cfg["product_factory_map"] = {r.product_name: r.factory_name for r in pm_rows}

            # 3. Delay Thresholds
            dt_rows = session.execute(select(DelayThreshold)).scalars().all()
            if dt_rows:
                cfg["sla_thresholds_days"] = {r.ship_mode: float(r.threshold_days) for r in dt_rows}

            # 4. Business Rules
            br_rows = session.execute(select(BusinessRule)).scalars().all()
            for br in br_rows:
                if br.rule_key in cfg:
                    cfg[br.rule_key] = br.rule_value

            # 5. ML Settings
            ml_s = session.execute(select(MLSetting).where(MLSetting.setting_key == "default_hyperparameters")).scalar_one_or_none()
            if ml_s and isinstance(ml_s.setting_value, dict):
                cfg["ml_settings"] = ml_s.setting_value

            return cfg
    except Exception as e:
        logger.warning("Could not read config from database, falling back to local JSON: %s", e)

    # Fallback to JSON
    ensure_manager_dirs()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for k, v in saved.items():
                    cfg[k] = v
        except Exception:
            pass
    return cfg


def save_business_config(config: Dict[str, Any], user: str = "Administrator") -> None:
    """Save business configuration into database and sync to JSON file."""
    ensure_manager_dirs()

    # 1. Update Database
    try:
        with get_db_session() as session:
            # Delay thresholds
            if "sla_thresholds_days" in config:
                for mode, days in config["sla_thresholds_days"].items():
                    dt = session.execute(select(DelayThreshold).where(DelayThreshold.ship_mode == mode)).scalar_one_or_none()
                    if dt:
                        dt.threshold_days = float(days)
                    else:
                        session.add(DelayThreshold(ship_mode=mode, threshold_days=float(days)))

            # Factory coordinates
            if "factory_coordinates" in config:
                for fname, coords in config["factory_coordinates"].items():
                    fc = session.execute(select(FactoryCoordinate).where(FactoryCoordinate.factory_name == fname)).scalar_one_or_none()
                    if fc:
                        fc.latitude = coords[0]
                        fc.longitude = coords[1]
                    else:
                        session.add(FactoryCoordinate(factory_name=fname, latitude=coords[0], longitude=coords[1]))

            # Product mappings
            if "product_factory_map" in config:
                for pname, fname in config["product_factory_map"].items():
                    pm = session.execute(select(ProductMapping).where(ProductMapping.product_name == pname)).scalar_one_or_none()
                    if pm:
                        pm.factory_name = fname
                    else:
                        session.add(ProductMapping(product_name=pname, factory_name=fname))

            # Rules
            for rule_k in ["efficiency_weights", "alert_thresholds", "kpi_targets"]:
                if rule_k in config:
                    br = session.execute(select(BusinessRule).where(BusinessRule.rule_key == rule_k)).scalar_one_or_none()
                    if br:
                        br.rule_value = config[rule_k]
                        br.updated_by = user
                        br.updated_at = datetime.now()
                    else:
                        session.add(BusinessRule(rule_key=rule_k, rule_value=config[rule_k], updated_by=user))

            # ML Settings
            if "ml_settings" in config:
                mls = session.execute(select(MLSetting).where(MLSetting.setting_key == "default_hyperparameters")).scalar_one_or_none()
                if mls:
                    mls.setting_value = config["ml_settings"]
                    mls.updated_at = datetime.now()
                else:
                    session.add(MLSetting(setting_key="default_hyperparameters", setting_value=config["ml_settings"]))

            session.commit()
    except Exception as e:
        logger.error("Failed to save config to DB: %s", e)

    # 2. Sync to JSON file for offline reliability
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    record_audit_event(
        user=user,
        action="Update Business Configuration",
        module="Configuration",
        status="Success",
        details="Updated business rules, SLA thresholds, factory mappings, or ML settings",
    )
    logger.info("Saved business configuration by %s", user)


# ─────────────────────────────────────────────────────────────────────────────
# 2. AUDIT LOGGING SUBSYSTEM
# ─────────────────────────────────────────────────────────────────────────────

def record_audit_event(
    user: str,
    action: str,
    module: str,
    status: str = "Success",
    details: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Record an audit trail event in the database and JSON fallback."""
    now = datetime.now()

    # DB persistence
    try:
        with get_db_session() as session:
            session.add(AuditLog(
                timestamp=now,
                administrator=user or "System",
                module=module,
                action=action,
                status=status,
                description=details,
                metadata_json=metadata,
            ))
            session.commit()
    except Exception as e:
        logger.warning("Failed to write audit event to DB: %s", e)

    # JSON fallback file persistence
    ensure_manager_dirs()
    events = []
    if AUDIT_FILE.exists():
        try:
            with open(AUDIT_FILE, "r", encoding="utf-8") as f:
                events = json.load(f)
        except Exception:
            events = []

    record = {
        "Timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "Administrator": user or "System",
        "Action": action,
        "Affected Module": module,
        "Status": status,
        "Details": details,
    }
    events.insert(0, record)
    events = events[:1000]

    with open(AUDIT_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)


def get_audit_log_df() -> pd.DataFrame:
    """Retrieve audit log as a pandas DataFrame from database, falling back to JSON."""
    try:
        with get_db_session() as session:
            logs = session.execute(
                select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(500)
            ).scalars().all()
            if logs:
                data = [{
                    "Timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "",
                    "Administrator": l.administrator,
                    "Action": l.action,
                    "Affected Module": l.module,
                    "Status": l.status,
                    "Details": l.description,
                } for l in logs]
                return pd.DataFrame(data)
    except Exception as e:
        logger.warning("Could not read audit log from DB: %s", e)

    # JSON fallback
    ensure_manager_dirs()
    if not AUDIT_FILE.exists():
        return pd.DataFrame(columns=["Timestamp", "Administrator", "Action", "Affected Module", "Status", "Details"])
    try:
        with open(AUDIT_FILE, "r", encoding="utf-8") as f:
            events = json.load(f)
        return pd.DataFrame(events)
    except Exception as e:
        logger.error("Failed to parse audit log: %s", e)
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 3. REGISTRATION ID MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def create_registration_ids(
    count: int = 1,
    valid_days: int = 90,
    created_by: str = "Administrator",
) -> List[str]:
    """Generate company registration ID UUID tokens."""
    generated_tokens: List[str] = []
    now = datetime.now()
    expiry = now + timedelta(days=valid_days)

    with get_db_session() as session:
        for _ in range(count):
            token_str = f"REG-{uuid.uuid4().hex[:12].upper()}"
            reg = RegistrationId(
                token=token_str,
                status="ACTIVE",
                expiry_date=expiry,
                created_by=created_by,
                created_at=now,
            )
            session.add(reg)
            generated_tokens.append(token_str)
        session.commit()

    record_audit_event(
        user=created_by,
        action="Generate Registration IDs",
        module="Registration Management",
        status="Success",
        details=f"Generated {count} Registration Key(s) valid for {valid_days} days",
    )
    return generated_tokens


def list_registration_ids(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve list of registration IDs."""
    with get_db_session() as session:
        q = select(RegistrationId).order_by(desc(RegistrationId.created_at))
        if status_filter and status_filter != "ALL":
            q = q.where(RegistrationId.status == status_filter)
        regs = session.execute(q).scalars().all()

        now = datetime.now()
        results = []
        for r in regs:
            # Auto-flag expired
            stat = r.status
            if stat == "ACTIVE" and r.expiry_date and r.expiry_date < now:
                stat = "EXPIRED"

            results.append({
                "id": r.id,
                "token": r.token,
                "status": stat,
                "expiry": r.expiry_date.strftime("%Y-%m-%d %H:%M:%S") if r.expiry_date else "Never",
                "created_by": r.created_by,
                "created_date": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
                "used_by": r.used_by or "—",
                "used_date": r.used_at.strftime("%Y-%m-%d %H:%M:%S") if r.used_at else "—",
            })
        return results


def update_registration_id_status(token: str, new_status: str, admin_user: str = "Administrator") -> Tuple[bool, str]:
    """Disable or revoke a registration ID."""
    with get_db_session() as session:
        reg = session.execute(select(RegistrationId).where(RegistrationId.token == token.strip())).scalar_one_or_none()
        if not reg:
            return False, "Registration ID not found."
        if reg.status == "USED":
            return False, "Cannot modify an already used Registration ID."

        reg.status = new_status
        session.commit()

    record_audit_event(
        user=admin_user,
        action=f"Registration Key {new_status}",
        module="Registration Management",
        status="Success",
        details=f"Key {token} updated to {new_status}",
    )
    return True, f"Registration ID {token} successfully marked as {new_status}."


def delete_unused_registration_id(token: str, admin_user: str = "Administrator") -> Tuple[bool, str]:
    """Delete an unused registration key."""
    with get_db_session() as session:
        reg = session.execute(select(RegistrationId).where(RegistrationId.token == token.strip())).scalar_one_or_none()
        if not reg:
            return False, "Registration ID not found."
        if reg.status == "USED":
            return False, "Cannot delete a Registration ID that has already been redeemed."

        session.delete(reg)
        session.commit()

    record_audit_event(
        user=admin_user,
        action="Delete Registration Key",
        module="Registration Management",
        status="Success",
        details=f"Permanently deleted unused key {token}",
    )
    return True, f"Registration ID {token} deleted successfully."


# ─────────────────────────────────────────────────────────────────────────────
# 4. DATASET VERSION CONTROL & ROLLBACK
# ─────────────────────────────────────────────────────────────────────────────

VERSIONS_METADATA_FILE = VERSIONS_DIR / "versions_index.json"


def list_dataset_versions() -> List[Dict[str, Any]]:
    """List all dataset versions sorted by timestamp descending."""
    ensure_manager_dirs()
    # Try DB first
    try:
        with get_db_session() as session:
            rows = session.execute(select(DatasetVersion).order_by(desc(DatasetVersion.timestamp))).scalars().all()
            if rows:
                return [{
                    "version_id": r.version_id,
                    "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.timestamp else "",
                    "author": r.author,
                    "description": r.description,
                    "row_count": r.row_count,
                    "col_count": r.col_count,
                    "folder": r.backup_path,
                } for r in rows]
    except Exception:
        pass

    # JSON fallback
    if not VERSIONS_METADATA_FILE.exists():
        return []
    try:
        with open(VERSIONS_METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def create_dataset_backup(description: str, user: str = "Administrator") -> Optional[str]:
    """Take an automated backup of current active featured and cleaned datasets."""
    ensure_manager_dirs()
    if not FEATURED_DATA_FILE.exists():
        return None

    version_id = datetime.now().strftime("v_%Y%m%d_%H%M%S")
    version_folder = VERSIONS_DIR / version_id
    version_folder.mkdir(parents=True, exist_ok=True)

    # Copy active files
    shutil.copy2(FEATURED_DATA_FILE, version_folder / "featured_data.csv")
    if CLEANED_DATA_FILE.exists():
        shutil.copy2(CLEANED_DATA_FILE, version_folder / "cleaned_data.csv")

    try:
        df = pd.read_csv(FEATURED_DATA_FILE)
        row_count = len(df)
        cols_count = len(df.columns)
    except Exception:
        row_count = 0
        cols_count = 0

    rel_folder = str(version_folder.relative_to(PROJECT_ROOT))

    # Persist in DB
    try:
        with get_db_session() as session:
            dv = DatasetVersion(
                version_id=version_id,
                timestamp=datetime.now(),
                author=user,
                description=description,
                row_count=row_count,
                col_count=cols_count,
                backup_path=rel_folder,
                is_active=False,
            )
            session.add(dv)
            session.commit()
    except Exception as e:
        logger.warning("Could not write version to DB: %s", e)

    # Persist to JSON index
    record = {
        "version_id": version_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "author": user,
        "description": description,
        "row_count": row_count,
        "col_count": cols_count,
        "folder": rel_folder,
    }
    versions = list_dataset_versions()
    # Check if duplicate in list
    if not any(v.get("version_id") == version_id for v in versions):
        versions.insert(0, record)
        with open(VERSIONS_METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(versions, f, indent=2)

    record_audit_event(
        user=user,
        action="Backup Created",
        module="Version Control",
        status="Success",
        details=f"Snapshot {version_id} ({row_count:,} rows): {description}",
    )
    logger.info("Created dataset version backup %s", version_id)
    return version_id


def rollback_dataset_version(version_id: str, user: str = "Administrator") -> Tuple[bool, str]:
    """Rollback active dataset to a specified snapshot."""
    version_folder = VERSIONS_DIR / version_id
    feat_src = version_folder / "featured_data.csv"
    if not feat_src.exists():
        return False, f"Version {version_id} snapshot file not found."

    # Backup current state first before replacing
    create_dataset_backup(description=f"Auto-backup before rollback to {version_id}", user=user)

    shutil.copy2(feat_src, FEATURED_DATA_FILE)
    clean_src = version_folder / "cleaned_data.csv"
    if clean_src.exists():
        shutil.copy2(clean_src, CLEANED_DATA_FILE)

    # Load new df and invalidate platform
    df = pd.read_csv(FEATURED_DATA_FILE)
    invalidate_and_refresh_platform(df)

    record_audit_event(
        user=user,
        action="Dataset Rollback",
        module="Version Control",
        status="Success",
        details=f"Restored dataset to snapshot {version_id}",
    )
    return True, f"Successfully rolled back to version {version_id}."


# ─────────────────────────────────────────────────────────────────────────────
# 5. AUTOMATED PIPELINE RECALCULATION & CACHE SYNCHRONIZATION
# ─────────────────────────────────────────────────────────────────────────────

def recalculate_and_propagate(
    df: pd.DataFrame,
    user: str = "Administrator",
    reason: str = "Data Update",
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """
    Validates, re-runs feature engineering using active business rules,
    persists datasets, clears cache, updates database metadata, and notifies downstream views.
    """
    if config is None:
        config = load_business_config()

    try:
        df = df.copy()

        # 1. Take automated backup before applying changes
        create_dataset_backup(description=f"Auto-backup before {reason}", user=user)

        # Standardize strings and product names (e.g. fix raw data hyphen typos)
        if "Product Name" in df.columns:
            df["Product Name"] = df["Product Name"].astype(str).str.strip()
            for wrong, correct in PRODUCT_NAME_CORRECTIONS.items():
                df["Product Name"] = df["Product Name"].replace(wrong, correct)

        for str_col in ["Ship Mode", "Country/Region", "City", "State/Province", "Division", "Region"]:
            if str_col in df.columns:
                df[str_col] = df[str_col].astype(str).str.strip()

        # Sanitize numeric columns (handles currency symbols, commas, strings, any non-numeric dtype)
        numeric_float_cols = ["Sales", "Gross Profit", "Cost"]
        for col in numeric_float_cols:
            if col in df.columns:
                if not pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = (
                        df[col]
                        .astype(str)
                        .str.replace(r"[^\d.-]", "", regex=True)
                        .str.strip()
                    )
                df[col] = pd.to_numeric(df[col], errors="coerce")
                if df[col].isna().any():
                    df[col] = df[col].fillna(df[col].median() if not df[col].dropna().empty else 0.0)

        if "Units" in df.columns:
            if not pd.api.types.is_numeric_dtype(df["Units"]):
                df["Units"] = (
                    df["Units"]
                    .astype(str)
                    .str.replace(r"[^\d.-]", "", regex=True)
                    .str.strip()
                )
            df["Units"] = pd.to_numeric(df["Units"], errors="coerce")
            if df["Units"].isna().any():
                df["Units"] = df["Units"].fillna(df["Units"].median() if not df["Units"].dropna().empty else 1)
            df["Units"] = df["Units"].astype(int)

        # 2. Parse dates (supports DD-MM-YYYY as well as ISO YYYY-MM-DD formats)
        if "Order Date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["Order Date"]):
            parsed_od = pd.to_datetime(df["Order Date"], dayfirst=True, errors="coerce")
            # If dayfirst couldn't parse all, try standard fallback
            if parsed_od.isna().sum() > 0:
                parsed_fallback = pd.to_datetime(df["Order Date"], errors="coerce")
                parsed_od = parsed_od.fillna(parsed_fallback)
            df["Order Date"] = parsed_od

        if "Ship Date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["Ship Date"]):
            parsed_sd = pd.to_datetime(df["Ship Date"], dayfirst=True, errors="coerce")
            if parsed_sd.isna().sum() > 0:
                parsed_fallback = pd.to_datetime(df["Ship Date"], errors="coerce")
                parsed_sd = parsed_sd.fillna(parsed_fallback)
            df["Ship Date"] = parsed_sd

        # 3. Calculate Shipping Lead Time
        if "Order Date" in df.columns and "Ship Date" in df.columns:
            df["Shipping Lead Time"] = (df["Ship Date"] - df["Order Date"]).dt.total_seconds() / 86400.0
            df["Shipping Lead Time"] = df["Shipping Lead Time"].clip(lower=0.5).round(2)

        # 4. Map Factory Coordinates & Products from dynamic config
        prod_map = config.get("product_factory_map", PRODUCT_FACTORY_MAP)
        factory_coords = config.get("factory_coordinates", FACTORY_COORDINATES)

        if "Product Name" in df.columns:
            df["Factory"] = df["Product Name"].map(prod_map).fillna("Unknown Factory")

        if "Factory" in df.columns:
            # Provide both naming conventions for full compatibility with models & maps
            df["Factory Latitude"] = df["Factory"].apply(
                lambda f: factory_coords.get(f, (39.5, -98.35))[0] if isinstance(factory_coords.get(f), (list, tuple)) else 39.5
            )
            df["Factory Longitude"] = df["Factory"].apply(
                lambda f: factory_coords.get(f, (39.5, -98.35))[1] if isinstance(factory_coords.get(f), (list, tuple)) else -98.35
            )
            df["Factory_Lat"] = df["Factory Latitude"]
            df["Factory_Lon"] = df["Factory Longitude"]

        # 5. Calculate Delay Flag using dynamic SLA thresholds
        sla_thresholds = config.get("sla_thresholds_days", {
            "Standard Class": 5.0, "Second Class": 3.0, "First Class": 2.0, "Same Day": 1.0
        })

        median_lt = df["Shipping Lead Time"].median() if "Shipping Lead Time" in df.columns and not df.empty else 0
        if median_lt > 50.0:
            mode_medians = df.groupby("Ship Mode")["Shipping Lead Time"].median().to_dict()
            df["Delay Flag"] = df.apply(
                lambda row: bool(row["Shipping Lead Time"] > mode_medians.get(row.get("Ship Mode"), float("inf"))),
                axis=1,
            )
        else:
            def is_delayed(row):
                mode = row.get("Ship Mode", "Standard Class")
                lt = row.get("Shipping Lead Time", 0.0)
                threshold = sla_thresholds.get(mode, 4.0)
                return bool(lt > threshold)
            df["Delay Flag"] = df.apply(is_delayed, axis=1)

        # 6. Route Identifiers
        if "Factory" in df.columns and "State/Province" in df.columns:
            df["Factory → State Route"] = df["Factory"] + " → " + df["State/Province"].astype(str)
            df["Route"] = df["Factory → State Route"]
            df["Route ID"] = (
                df["Factory"].astype(str).str.replace(r"[^A-Za-z0-9]", "_", regex=True)
                + "_to_"
                + df["State/Province"].astype(str).str.replace(r"[^A-Za-z0-9]", "_", regex=True)
            )
        if "Factory" in df.columns and "Region" in df.columns:
            df["Factory → Region Route"] = df["Factory"] + " → " + df["Region"].astype(str)
            df["Factory_Region_Route"] = df["Factory → Region Route"]

        # 7. Temporal Features (Ship Date and Order Date)
        if "Ship Date" in df.columns:
            sd = df["Ship Date"]
            # Standard feature names
            df["Shipment Year"] = sd.dt.year
            df["Shipment Month"] = sd.dt.month
            df["Shipment Month Name"] = sd.dt.strftime("%b")
            df["Shipment Quarter"] = sd.dt.quarter
            df["Shipment Week"] = sd.dt.isocalendar().week.astype(int)
            df["Shipment Day"] = sd.dt.day
            df["Shipment Day of Week"] = sd.dt.dayofweek  # 0=Mon, 6=Sun
            # Aliases for backwards compatibility
            df["Ship Year"] = df["Shipment Year"]
            df["Ship Month"] = df["Shipment Month"]
            df["Ship Month Name"] = df["Shipment Month Name"]
            df["Ship Quarter"] = df["Shipment Quarter"]
            df["Ship Day of Week"] = sd.dt.day_name()

        if "Order Date" in df.columns:
            od = df["Order Date"]
            df["Order Year"] = od.dt.year
            df["Order Month"] = od.dt.month
            df["Order Month Name"] = od.dt.strftime("%b")
            df["Order Day"] = od.dt.day
            df["Order Day of Week"] = od.dt.dayofweek

        # 8. Route Efficiency Score
        delay_w = config.get("efficiency_weights", {}).get("delay_weight", 0.6)
        lt_w = config.get("efficiency_weights", {}).get("lead_time_weight", 0.4)

        route_col = "Factory → State Route" if "Factory → State Route" in df.columns else ("Route" if "Route" in df.columns else None)
        if route_col and route_col in df.columns:
            route_stats = df.groupby(route_col).agg(
                delay_rate=("Delay Flag", "mean"),
                mean_lt=("Shipping Lead Time", "mean"),
            ).reset_index()

            min_lt = route_stats["mean_lt"].min()
            max_lt = route_stats["mean_lt"].max()
            span = (max_lt - min_lt) if (max_lt - min_lt) > 0 else 1.0
            route_stats["norm_lt"] = (route_stats["mean_lt"] - min_lt) / span
            route_stats["Route Efficiency Score"] = compute_efficiency_score(
                delay_rate=route_stats["delay_rate"],
                normalised_lead_time=route_stats["norm_lt"],
                delay_weight=delay_w,
                lead_time_weight=lt_w,
            )
            df = df.drop(columns=["Route Efficiency Score"], errors="ignore")
            df = df.merge(route_stats[[route_col, "Route Efficiency Score"]], on=route_col, how="left")
            df["Route Efficiency Score"] = df["Route Efficiency Score"].fillna(0.5).round(4)

        # 9. Save dataset to processed CSV
        FEATURED_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(FEATURED_DATA_FILE, index=False, encoding="utf-8")

        # Sync base 18 logistics columns to cleaned_data.csv if available
        base_cols = [
            "Row ID", "Order ID", "Order Date", "Ship Date", "Ship Mode",
            "Customer ID", "Country/Region", "City", "State/Province",
            "Postal Code", "Division", "Region", "Product ID", "Product Name",
            "Sales", "Units", "Gross Profit", "Cost"
        ]
        present_base_cols = [c for c in base_cols if c in df.columns]
        if len(present_base_cols) >= 10:
            df[present_base_cols].to_csv(CLEANED_DATA_FILE, index=False, encoding="utf-8")

        # 10. Update ML Metadata in Database
        try:
            with get_db_session() as session:
                meta = session.execute(select(MLMetadata).where(MLMetadata.model_name == "RouteEfficiencyEngine")).scalar_one_or_none()
                summary_metrics = {
                    "record_count": len(df),
                    "overall_delay_rate": float(df["Delay Flag"].mean()) if "Delay Flag" in df.columns else 0.0,
                    "mean_lead_time_days": float(df["Shipping Lead Time"].mean()) if "Shipping Lead Time" in df.columns else 0.0,
                    "updated_by": user,
                    "reason": reason,
                }
                if meta:
                    meta.metrics = summary_metrics
                    meta.trained_at = datetime.now()
                else:
                    session.add(MLMetadata(
                        model_name="RouteEfficiencyEngine",
                        version="2.4",
                        metrics=summary_metrics,
                        trained_by=user,
                    ))
                session.commit()
        except Exception as e:
            logger.warning("Could not record ML metadata: %s", e)

        # 11. Clear Streamlit Cache and update active session state
        invalidate_and_refresh_platform(df)

        record_audit_event(
            user=user,
            action=f"System Synchronized ({reason})",
            module="Pipeline & Data Engine",
            status="Success",
            details=f"Recalculated KPIs, Route Efficiency, and SLA delays for {len(df):,} records.",
        )
        return True, f"System synchronized successfully with {len(df):,} active records."

    except Exception as e:
        logger.error("Error during pipeline recalculation: %s", e, exc_info=True)
        record_audit_event(
            user=user,
            action="System Update Failed",
            module="Pipeline & Data Engine",
            status="Failure",
            details=str(e),
        )
        return False, f"Recalculation failed: {str(e)}"


def invalidate_and_refresh_platform(new_df: Optional[pd.DataFrame] = None) -> None:
    """Clear Streamlit cache and reload session state dataframes."""
    try:
        st.cache_data.clear()
    except Exception:
        pass

    # Reset any stale filters from previous dataset session
    if "global_filters" in st.session_state:
        st.session_state["global_filters"] = {}
    if "quick_order_year" in st.session_state:
        st.session_state["quick_order_year"] = "All"
    for k in list(st.session_state.keys()):
        if k.startswith("f_"):
            st.session_state.pop(k, None)

    # Invalidation tokens so app.py and views always re-read
    st.session_state["data_mtime"] = time.time()
    st.session_state["data_version_token"] = str(uuid.uuid4())

    if new_df is not None:
        st.session_state["df_full"] = new_df
        st.session_state["df_filtered"] = new_df
    elif FEATURED_DATA_FILE.exists():
        try:
            df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"], encoding="utf-8")
            st.session_state["df_full"] = df
            st.session_state["df_filtered"] = df
        except Exception:
            pass
