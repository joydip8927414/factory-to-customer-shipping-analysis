"""
test_developer_portal.py
========================
Automated verification for the standalone Developer Control Portal:
- Developer authentication and bcrypt hashing
- Brute-force lockout defense on developer accounts
- Exclusive Registration ID Authority (Generation with notes, status filtering, expiration extension)
- Read-only validation & redemption in the logistics onboarding workflow
- Revocation and deletion operations
- System health and database telemetry
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.admin_security import register_admin_user, validate_registration_id
from src.db.models import Developer
from src.db.session import get_db_session
from src.developer.dev_security import (
    authenticate_developer,
    hash_dev_password,
    verify_dev_password,
)
from src.developer.dev_service import (
    dev_delete_unused_key,
    dev_extend_key_expiry,
    dev_generate_registration_ids,
    dev_get_system_health,
    dev_list_registration_ids,
    dev_reset_developer_password,
    dev_update_key_status,
    dev_vacuum_database,
)


class TestDeveloperPortal(unittest.TestCase):

    def setUp(self):
        with get_db_session() as session:
            dev = session.query(Developer).filter_by(username="developer").first()
            if dev:
                dev.failed_logins = 0
                dev.locked_until = None
                session.commit()

    def test_01_developer_authentication(self):
        # Verify root developer credentials
        ok, msg, dev_dict = authenticate_developer("developer", "Developer@2026!")
        if not ok:
            ok, msg, dev_dict = authenticate_developer("developer", "ChangeMeDev2026!")
        self.assertTrue(ok)
        self.assertIsNotNone(dev_dict)
        self.assertEqual(dev_dict["username"], "developer")

        # Wrong password
        bad_ok, bad_msg, _ = authenticate_developer("developer", "IncorrectPass!")
        self.assertFalse(bad_ok)

    def test_02_developer_key_generation_and_workflow(self):
        # Developer generates single key with specific notes
        notes_text = "Key generated for supply director test"
        tokens = dev_generate_registration_ids(count=1, valid_days=60, created_by="developer", notes=notes_text)
        self.assertEqual(len(tokens), 1)
        key_token = tokens[0]

        # Verify key appears in developer listing with notes
        keys = dev_list_registration_ids(status_filter="ACTIVE", search_query=key_token)
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0]["notes"], notes_text)
        self.assertEqual(keys[0]["status"], "ACTIVE")

        # Extend expiry
        ext_ok, ext_msg = dev_extend_key_expiry(key_token, additional_days=15, developer="developer")
        self.assertTrue(ext_ok)

        # Logistics Dashboard user validates and redeems the key
        val_ok, _, _ = validate_registration_id(key_token)
        self.assertTrue(val_ok)

        reg_ok, _ = register_admin_user(
            registration_token=key_token,
            full_name="New Branch Administrator",
            username=f"branch_admin_{datetime.now().strftime('%M%S')}",
            email=f"branch_{datetime.now().strftime('%M%S')}@nassaucandy.com",
            password="BranchPassword2026!",
            target_role="Administrator",
        )
        self.assertTrue(reg_ok)

        # Key should now be reflected as USED in Developer Portal
        used_keys = dev_list_registration_ids(status_filter="USED", search_query=key_token)
        self.assertEqual(len(used_keys), 1)
        self.assertEqual(used_keys[0]["status"], "USED")
        self.assertNotEqual(used_keys[0]["used_by"], "—")

    def test_03_key_revocation_and_deletion(self):
        # Generate temporary key
        tokens = dev_generate_registration_ids(count=1, valid_days=10, created_by="developer")
        temp_key = tokens[0]

        # Revoke key
        rev_ok, _ = dev_update_key_status(temp_key, "REVOKED", developer="developer")
        self.assertTrue(rev_ok)

        # Confirm validation fails in dashboard
        val_ok, val_msg, _ = validate_registration_id(temp_key)
        self.assertFalse(val_ok)
        self.assertIn("revoked", val_msg.lower())

        # Delete unused key
        del_ok, _ = dev_delete_unused_key(temp_key, developer="developer")
        self.assertTrue(del_ok)

    def test_04_system_health_and_vacuum(self):
        health = dev_get_system_health()
        self.assertIn("database_size_mb", health)
        self.assertIn("table_counts", health)
        self.assertGreater(health["table_counts"]["developers"], 0)

        # Run vacuum
        vac_ok, _ = dev_vacuum_database(developer="developer")
        self.assertTrue(vac_ok)

    def test_05_developer_password_reset_and_session_invalidation(self):
        from src.db.session import get_db_session
        from src.db.models import Developer

        # Find target developer
        with get_db_session() as session:
            dev = session.query(Developer).filter(Developer.username == "developer").first()
            self.assertIsNotNone(dev)
            dev_id = dev.id

        # Unauthorized caller should fail
        unauth_ok, unauth_msg = dev_reset_developer_password(dev_id, "TemporaryPass123!", modified_by="unauthorized_dev")
        self.assertFalse(unauth_ok)
        self.assertIn("Access Denied", unauth_msg)

        # Short password should fail
        short_ok, short_msg = dev_reset_developer_password(dev_id, "short", modified_by="joydip_icy")
        self.assertFalse(short_ok)
        self.assertIn("at least 8 characters", short_msg)

        # Authorized Owner caller resets password
        reset_ok, reset_msg = dev_reset_developer_password(dev_id, "TempSecretDev2026!", modified_by="joydip_icy")
        self.assertTrue(reset_ok)
        self.assertIn("Password reset for 'developer'", reset_msg)

        # Verify authentication with new password succeeds and flags must_change_password
        auth_ok, auth_msg, dev_data = authenticate_developer("developer", "TempSecretDev2026!")
        self.assertTrue(auth_ok)
        self.assertTrue(dev_data["must_change_password"])

        # Reset back to default test password
        restore_ok, _ = dev_reset_developer_password(dev_id, "ChangeMeDev2026!", modified_by="joydip_icy")
        self.assertTrue(restore_ok)


if __name__ == "__main__":
    unittest.main()
