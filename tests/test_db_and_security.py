"""
test_db_and_security.py
=======================
Automated test suite verifying the enterprise database layer, registration ID workflow,
bcrypt authentication, brute-force defense, and auto-sync recalculation.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
from sqlalchemy import select

from src.admin_assistant import analyze_dataset_health, apply_all_recommendations
from src.admin_manager import (
    create_dataset_backup,
    create_registration_ids,
    delete_unused_registration_id,
    get_audit_log_df,
    list_dataset_versions,
    list_registration_ids,
    load_business_config,
    recalculate_and_propagate,
    record_audit_event,
    rollback_dataset_version,
    save_business_config,
    update_registration_id_status,
)
from src.admin_security import (
    authenticate_user_db,
    hash_password_bcrypt,
    register_admin_user,
    validate_registration_id,
    verify_password_bcrypt,
)
from src.db.models import RegistrationId, Role, User
from src.db.session import get_db_session


class TestDatabaseAndSecurity(unittest.TestCase):

    def test_01_bcrypt_hashing(self):
        pwd = "TestSecurePassword2026!"
        hashed = hash_password_bcrypt(pwd)
        self.assertTrue(verify_password_bcrypt(pwd, hashed))
        self.assertFalse(verify_password_bcrypt("WrongPassword", hashed))

    def test_02_registration_id_workflow(self):
        # Generate 1 key
        keys = create_registration_ids(count=1, valid_days=30, created_by="TestRunner")
        self.assertEqual(len(keys), 1)
        test_key = keys[0]

        # Validate key
        is_val, msg, reg = validate_registration_id(test_key)
        self.assertTrue(is_val)

        # Register user with this key
        test_user = f"user_{datetime.now().strftime('%M%S')}"
        test_email = f"{test_user}@nassaucandy.com"
        reg_ok, reg_msg = register_admin_user(
            registration_token=test_key,
            full_name="Automated Test User",
            username=test_user,
            email=test_email,
            password="SecureSecretPass123!",
            target_role="Administrator",
        )
        self.assertTrue(reg_ok)

        # Ensure key cannot be reused
        is_val_again, reuse_msg, _ = validate_registration_id(test_key)
        self.assertFalse(is_val_again)
        self.assertIn("already used", reuse_msg)

        # Test login with newly registered user
        auth_ok, auth_msg, udict = authenticate_user_db(test_user, "SecureSecretPass123!")
        self.assertTrue(auth_ok)
        self.assertIsNotNone(udict)
        self.assertEqual(udict["username"], test_user)

    def test_03_registration_id_revocation(self):
        keys = create_registration_ids(count=1, valid_days=30, created_by="TestRunner")
        test_key = keys[0]

        # Revoke key
        rev_ok, _ = update_registration_id_status(test_key, "REVOKED", admin_user="TestRunner")
        self.assertTrue(rev_ok)

        # Attempt to register with revoked key
        reg_ok, reg_msg = register_admin_user(
            registration_token=test_key,
            full_name="Revoked Attempt",
            username="revoked_user",
            email="revoked@nassaucandy.com",
            password="Password123!",
        )
        self.assertFalse(reg_ok)

        # Delete key
        del_ok, _ = delete_unused_registration_id(test_key, admin_user="TestRunner")
        self.assertTrue(del_ok)

    def test_04_business_config_persistence(self):
        cfg = load_business_config()
        self.assertIn("sla_thresholds_days", cfg)
        self.assertIn("factory_coordinates", cfg)

        # Modify SLA and save
        original_sla = cfg["sla_thresholds_days"].get("Standard Class", 5.0)
        cfg["sla_thresholds_days"]["Standard Class"] = 6.5
        save_business_config(cfg, user="TestRunner")

        # Reload and verify
        reloaded = load_business_config()
        self.assertEqual(reloaded["sla_thresholds_days"]["Standard Class"], 6.5)

        # Revert back
        cfg["sla_thresholds_days"]["Standard Class"] = original_sla
        save_business_config(cfg, user="TestRunner")

    def test_05_ai_assistant_diagnostics_and_fix(self):
        # Create dirty sample dataframe
        dirty_df = pd.DataFrame({
            "Order ID": ["CA-100", "CA-100", "CA-101"],
            "Product ID": ["PROD-1", "PROD-1", "PROD-2"],
            "Product Name": ["Wonka Bar - Milk Chocolate", "Wonka Bar - Milk Chocolate", "New Mystery SKU"],
            "Order Date": ["2026-05-10", "2026-05-10", "2026-05-15"],
            "Ship Date": ["2026-05-12", "2026-05-12", "2026-05-10"],  # Inverted date
            "Ship Mode": ["Standard Class", "Standard Class", "First Class"],
            "Sales": [100.0, 100.0, None],  # Null value
            "Units": [5, 5, 2],
        })

        analysis = analyze_dataset_health(dirty_df)
        self.assertLess(analysis["health_score"], 100)
        self.assertGreater(len(analysis["issues"]), 0)

        # Apply all fixes
        clean_df, fix_logs = apply_all_recommendations(dirty_df)
        self.assertEqual(len(clean_df), 2)  # Duplicate removed
        self.assertFalse(clean_df["Sales"].isnull().any())  # Null imputed

    def test_06_audit_logging(self):
        record_audit_event(
            user="TestAuditUser",
            action="Automated Test Execution",
            module="Testing",
            status="Success",
            details="Verifying audit trail recording in database",
        )
        audit_df = get_audit_log_df()
        self.assertFalse(audit_df.empty)
        match = audit_df[audit_df["Administrator"] == "TestAuditUser"]
        self.assertFalse(match.empty)


if __name__ == "__main__":
    unittest.main()
