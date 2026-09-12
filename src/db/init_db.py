"""
init_db.py
==========
Schema bootstrapper and seeder for the Nassau Candy Administration System.
Initializes normalized SQLite / PostgreSQL tables and populates:
- Standard Roles (Administrator, Analyst, Viewer)
- Initial Master Registration IDs
- Factory GPS coordinates and product mappings
- Delay SLA thresholds & business calculation rules
- Dashboard and ML settings
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import bcrypt
from sqlalchemy import select

from src.db.models import (
    ApiKey,
    BusinessRule,
    DashboardSetting,
    DelayThreshold,
    Developer,
    FactoryCoordinate,
    LicenseInfo,
    MLSetting,
    ProductMapping,
    RegistrationId,
    Role,
    User,
)
from src.db.session import Base, engine, get_db_session
from src.utils import FACTORY_COORDINATES, PRODUCT_FACTORY_MAP, get_logger, get_secret

logger = get_logger(__name__)


def init_database() -> None:
    """Create all tables and seed initial defaults."""
    logger.info("Initializing database schema on engine: %s", engine.url)
    Base.metadata.create_all(bind=engine)

    with get_db_session() as session:
        # 1. Seed Roles
        roles_data = [
            ("Administrator", "Full system access, dataset ingestion, user & config management, ML retraining"),
            ("Analyst", "Dashboard exploration, BI analytics, reporting, and export; no configuration edits"),
            ("Viewer", "Read-only access to scorecards, visualizations, and dynamic filters"),
        ]
        role_map = {}
        for r_name, r_desc in roles_data:
            role = session.execute(select(Role).where(Role.name == r_name)).scalar_one_or_none()
            if not role:
                role = Role(
                    name=r_name,
                    description=r_desc,
                    permissions={"can_edit": r_name == "Administrator", "can_export": r_name in ["Administrator", "Analyst"]},
                )
                session.add(role)
                session.flush()
            role_map[r_name] = role

        # 2. Seed Initial Root Admin if not present
        admin_user = session.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
        if not admin_user:
            salt = bcrypt.gensalt(rounds=12)
            default_pwd = get_secret("ADMIN_PASSWORD", "ChangeMeAdmin2026!").encode("utf-8")
            hashed = bcrypt.hashpw(default_pwd, salt).decode("utf-8")

            admin_user = User(
                username="admin",
                email="admin@nassaucandy.com",
                full_name="Nassau Chief Supply Officer",
                password_hash=hashed,
                role_id=role_map["Administrator"].id,
                is_active=True,
            )
            session.add(admin_user)
            logger.info("Created default administrator: admin / ChangeMeAdmin2026!")

        # 3. Seed Initial Company Registration IDs for registration workflow
        reg_count = session.query(RegistrationId).count()
        if reg_count == 0:
            initial_tokens = [
                ("REG-ADMIN-NASSAU-9901", 90),
                ("REG-ADMIN-NASSAU-9902", 90),
                ("REG-ADMIN-NASSAU-9903", 90),
            ]
            for token_code, days in initial_tokens:
                reg_id = RegistrationId(
                    token=token_code,
                    status="ACTIVE",
                    expiry_date=datetime.utcnow() + timedelta(days=days),
                    created_by="System (Bootstrap)",
                )
                session.add(reg_id)
            logger.info("Seeded %d initial Registration IDs.", len(initial_tokens))

        # 4. Seed Factory Coordinates
        if session.query(FactoryCoordinate).count() == 0:
            for f_name, (lat, lon) in FACTORY_COORDINATES.items():
                session.add(FactoryCoordinate(
                    factory_name=f_name,
                    latitude=float(lat),
                    longitude=float(lon),
                    is_active=True,
                ))

        # 5. Seed Product Mappings
        if session.query(ProductMapping).count() == 0:
            for p_name, f_name in PRODUCT_FACTORY_MAP.items():
                session.add(ProductMapping(
                    product_name=p_name,
                    factory_name=f_name,
                    is_active=True,
                ))

        # 6. Seed Delay SLA Thresholds
        if session.query(DelayThreshold).count() == 0:
            slas = [
                ("Standard Class", 5.0),
                ("Second Class", 3.0),
                ("First Class", 2.0),
                ("Same Day", 1.0),
            ]
            for mode, days in slas:
                session.add(DelayThreshold(ship_mode=mode, threshold_days=days))

        # 7. Seed Business Calculation Rules & Alert Thresholds
        if session.query(BusinessRule).count() == 0:
            default_rules = {
                "efficiency_weights": {"delay_weight": 0.6, "lead_time_weight": 0.4},
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
            }
            for key, val in default_rules.items():
                session.add(BusinessRule(rule_key=key, rule_value=val, category="LOGISTICS"))

        # 8. Seed Dashboard Settings
        if session.query(DashboardSetting).count() == 0:
            session.add(DashboardSetting(
                setting_key="general_ui",
                setting_value={
                    "default_theme": "dark",
                    "enable_animations": True,
                    "enable_sankey": True,
                    "auto_sync_on_save": True,
                }
            ))

        # 9. Seed ML Settings
        if session.query(MLSetting).count() == 0:
            session.add(MLSetting(
                setting_key="default_hyperparameters",
                setting_value={
                    "random_forest_estimators": 100,
                    "test_size": 0.2,
                    "random_state": 42,
                    "forecast_horizon_months": 6,
                    "confidence_level": 0.95,
                }
            ))

        # 10. Seed Initial Root Developer Account
        dev_count = session.query(Developer).count()
        if dev_count == 0:
            dev_salt = bcrypt.gensalt(rounds=12)
            dev_pwd_raw = get_secret("DEV_USER_PASSWORD", "ChangeMeDev2026!")
            dev_pwd_hashed = bcrypt.hashpw(dev_pwd_raw.encode("utf-8"), dev_salt).decode("utf-8")
            dev_user = Developer(
                username="developer",
                email="dev@nassaucandy.com",
                full_name="Lead Infrastructure Engineer",
                password_hash=dev_pwd_hashed,
                is_active=True,
            )
            session.add(dev_user)
            logger.info("Created root developer: developer / ChangeMeDev2026!")

        # 11. Seed License Info
        if session.query(LicenseInfo).count() == 0:
            session.add(LicenseInfo(
                licensee="Nassau Candy Confections Corp",
                license_tier="Enterprise Unlimited",
                license_key="NASSAU-ENT-2026-X998A-INFRA",
                max_nodes=50,
                valid_until=datetime.now() + timedelta(days=365),
                status="ACTIVE",
            ))

        # 12. Seed Sample Developer API Key
        if session.query(ApiKey).count() == 0:
            sample_salt = bcrypt.gensalt(rounds=10)
            sample_hash = bcrypt.hashpw(b"nassau_secret_api_key_prod", sample_salt).decode("utf-8")
            session.add(ApiKey(
                name="WMS Integration Service Key",
                key_prefix="nsk_live_9a",
                key_hash=sample_hash,
                status="ACTIVE",
                created_by="developer",
            ))

    logger.info("Database schema and defaults successfully populated.")


if __name__ == "__main__":
    init_database()
