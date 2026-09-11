"""
scripts/seed_production_db.py
==============================
Production Database Clean Seeder & Optimization Script.
Prepares Nassau Candy database for production deployment by:
1. Ensuring tables and constraints are created.
2. Seeding default roles (Administrator, Analyst, Viewer).
3. Seeding production Administrator account (admin / ChangeMeAdmin2026!).
4. Seeding company registration IDs (REG-ADMIN-NASSAU-9901..9903).
5. Seeding Developer Portal Root Owner (JOYDIP DAS / joydip_icy).
6. Cleaning out transient test artifacts from previous test runs.
7. Running SQLite VACUUM optimization for minimal deployment footprint.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bcrypt
from sqlalchemy import select, text

from src.db.models import (
    AuditLog,
    Developer,
    DeveloperAuditLog,
    DeveloperDevice,
    DeveloperKey,
    DeveloperRole,
    RegistrationId,
    Role,
    SystemSecurity,
    User,
)
from src.db.session import Base, engine, get_db_session
from src.developer.dev_security import (
    DEFAULT_MASTER_KEY,
    DEFAULT_OWNER_EMAIL,
    DEFAULT_OWNER_NAME,
    DEFAULT_OWNER_PASSWORD,
    DEFAULT_OWNER_USERNAME,
    ensure_root_owner_and_system_security,
    hash_dev_password,
)
from src.utils import get_logger

logger = get_logger("ProductionSeeder")


def clean_test_artifacts(session) -> int:
    """Purge temporary unit test accounts created during development."""
    deleted = 0
    # Remove test users
    test_users = session.query(User).filter(
        (User.username.like("testadmin_%")) |
        (User.username.like("branch_admin_%")) |
        (User.username.like("user_%"))
    ).all()
    for u in test_users:
        session.delete(u)
        deleted += 1

    # Remove test developers
    test_devs = session.query(Developer).filter(
        (Developer.username.like("test_%")) |
        (Developer.username.like("dev_%")) |
        (Developer.username.like("owner_%")) |
        (Developer.username.like("toggle_%")) |
        (Developer.username.like("keydev_%")) |
        (Developer.username.like("nonowner_%"))
    ).all()
    for d in test_devs:
        # Delete related keys and devices first
        session.query(DeveloperKey).filter(DeveloperKey.developer_id == d.id).delete()
        session.query(DeveloperDevice).filter(DeveloperDevice.developer_id == d.id).delete()
        session.delete(d)
        deleted += 1

    session.commit()
    return deleted


def seed_production(clean_tests: bool = True) -> None:
    print("=" * 60)
    print("NASSAU CANDY — PRODUCTION DATABASE SEEDER")
    print("=" * 60)

    # 1. Create tables
    print("[1/5] Initializing tables on engine...")
    Base.metadata.create_all(bind=engine)

    with get_db_session() as session:
        # 2. Clean temporary test accounts if requested
        if clean_tests:
            print("[2/5] Cleaning transient test accounts...")
            purged = clean_test_artifacts(session)
            print(f"      Purged {purged} temporary test records.")

        # 3. Seed roles & admin
        print("[3/5] Seeding core roles and Administrator...")
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

        admin_user = session.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
        if not admin_user:
            salt = bcrypt.gensalt(rounds=12)
            default_pwd = b"ChangeMeAdmin2026!"
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
            print("      Created production Administrator: admin / ChangeMeAdmin2026!")
        else:
            print("      Production Administrator 'admin' verified active.")

        # 4. Seed clean registration IDs
        print("[4/5] Checking Company Registration Keys...")
        active_regs = session.query(RegistrationId).filter(RegistrationId.status == "ACTIVE").count()
        if active_regs == 0:
            for token_code, days in [
                ("REG-ADMIN-NASSAU-9901", 90),
                ("REG-ADMIN-NASSAU-9902", 90),
                ("REG-ADMIN-NASSAU-9903", 90),
            ]:
                session.add(RegistrationId(
                    token=token_code,
                    role="Administrator",
                    status="ACTIVE",
                    created_by="ProductionSeeder",
                    created_at=datetime.now(),
                ))
            print("      Provisioned default Registration Keys: REG-ADMIN-NASSAU-9901..9903")
        else:
            print(f"      {active_regs} active Registration Keys available.")

        session.commit()

    # 5. Seed Developer Portal Root Owner
    print("[5/5] Ensuring Root Owner for Developer Portal (:8600)...")
    ensure_root_owner_and_system_security()
    print(f"      Root Owner verified: {DEFAULT_OWNER_USERNAME} ({DEFAULT_OWNER_NAME})")

    # 6. SQLite VACUUM optimization
    try:
        with engine.connect() as conn:
            conn.execute(text("VACUUM"))
            conn.commit()
        print("      Database optimized and compacted (VACUUM complete).")
    except Exception as e:
        print(f"      Note: VACUUM skipped ({e})")

    print("=" * 60)
    print("PRODUCTION SEEDING COMPLETE — ALL CREDENTIALS READY")
    print("=" * 60)


if __name__ == "__main__":
    seed_production(clean_tests=True)
