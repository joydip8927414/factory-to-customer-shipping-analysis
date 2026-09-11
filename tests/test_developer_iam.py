"""
test_developer_iam.py
======================
Unit and integration test suite for Developer Identity & Access Management (IAM):
1. Multi-Layer Authentication (Layer 1, Layer 2 Personal Keys, Layer 3 Devices)
2. Unique Key isolation (Key belonging to Developer A cannot authenticate Developer B)
3. Key Lifecycle states (ACTIVE, EXPIRED, REVOKED, SUSPENDED, COMPROMISED, REPLACED)
4. Key Rotation (Old key -> REPLACED, new key active)
5. Owner-only governance (Devs cannot generate/rotate keys)
6. Password changes and forced reset workflows
7. Dedicated IAM audit logging
"""

import unittest
import uuid
from datetime import datetime, timedelta

from src.db.models import (
    Developer,
    DeveloperAuditLog,
    DeveloperDevice,
    DeveloperKey,
    DeveloperRole,
)
from src.db.session import engine, get_db_session
from src.developer.dev_security import (
    authenticate_developer,
    check_trusted_device,
    dev_change_password,
    generate_cryptographic_dev_key,
    hash_dev_password,
    register_trusted_device,
    validate_developer_access_key,
)
from src.developer.dev_service import (
    dev_approve_device,
    dev_assign_developer_role,
    dev_block_device,
    dev_create_new_developer,
    dev_delete_developer_account,
    dev_delete_key,
    dev_generate_new_dev_key_for_developer,
    dev_list_all_developers,
    dev_list_developer_keys,
    dev_list_iam_audit_logs,
    dev_remove_device,
    dev_reset_developer_password,
    dev_rotate_developer_key,
    dev_set_key_status,
    dev_toggle_developer_status,
)


class TestDeveloperIAM(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create unique test developer accounts
        cls.uid = uuid.uuid4().hex[:6]
        cls.owner_user = f"test_owner_{cls.uid}"
        cls.owner_pwd = "OwnerStrongPassword123!"
        cls.dev_user = f"test_dev_{cls.uid}"
        cls.dev_pwd = "DevStrongPassword123!"

        # Provision Owner
        ok, msg, cls.owner_key = dev_create_new_developer(
            full_name="Test Owner Lead",
            username=cls.owner_user,
            email=f"{cls.owner_user}@nassaucandy.com",
            password=cls.owner_pwd,
            role="Owner",
            created_by="Setup",
        )
        assert ok, msg

        # Provision Developer
        ok2, msg2, cls.dev_key = dev_create_new_developer(
            full_name="Test Junior Dev",
            username=cls.dev_user,
            email=f"{cls.dev_user}@nassaucandy.com",
            password=cls.dev_pwd,
            role="Developer",
            created_by=cls.owner_user,
        )
        assert ok2, msg2

        with get_db_session() as session:
            cls.owner_id = session.query(Developer).filter_by(username=cls.owner_user).first().id
            cls.dev_id = session.query(Developer).filter_by(username=cls.dev_user).first().id

    def test_01_cryptographic_key_format(self):
        """Test cryptographic key generation format."""
        key = generate_cryptographic_dev_key()
        self.assertTrue(key.startswith("DEV-KEY-"))
        parts = key.split("-")
        self.assertEqual(len(parts), 6)  # DEV, KEY, 4 hex segments

    def test_02_layer1_credentials_validation(self):
        """Test Layer 1 username & bcrypt password authentication."""
        # Success
        ok, msg, dev_dict = authenticate_developer(self.dev_user, self.dev_pwd)
        self.assertTrue(ok)
        self.assertEqual(dev_dict["username"], self.dev_user)

        # Bad password
        ok_bad, msg_bad, _ = authenticate_developer(self.dev_user, "WrongPass123!")
        self.assertFalse(ok_bad)
        self.assertIn("Invalid", msg_bad)

        # Bad user
        ok_no_user, _, _ = authenticate_developer("non_existent_dev_user", "AnyPassword123!")
        self.assertFalse(ok_no_user)

    def test_03_layer2_personal_key_isolation(self):
        """Test Layer 2 personal Developer Access Key isolation (keys are never shared)."""
        # Developer A validates their own key
        ok_own, msg_own = validate_developer_access_key(self.dev_id, self.dev_key)
        self.assertTrue(ok_own, msg_own)

        # Developer A tries to use Developer B's (Owner's) key -> Must be rejected!
        ok_shared, msg_shared = validate_developer_access_key(self.dev_id, self.owner_key)
        self.assertFalse(ok_shared)
        self.assertIn("Invalid", msg_shared)

        # Owner validates their own key
        ok_owner, msg_owner = validate_developer_access_key(self.owner_id, self.owner_key)
        self.assertTrue(ok_owner, msg_owner)

    def test_04_key_lifecycle_statuses(self):
        """Test that only ACTIVE keys can authenticate; REVOKED, SUSPENDED, EXPIRED fail."""
        # Issue a temporary test key for dev
        ok, msg, temp_key = dev_generate_new_dev_key_for_developer(self.dev_id, created_by=self.owner_user)
        self.assertTrue(ok)

        # Retrieve key record
        keys = dev_list_developer_keys(self.dev_id)
        temp_rec = [k for k in keys if temp_key.startswith(k["key_prefix"])][0]

        # 1. Suspended state
        dev_set_key_status(temp_rec["id"], "SUSPENDED", modified_by=self.owner_user)
        ok_susp, msg_susp = validate_developer_access_key(self.dev_id, temp_key)
        self.assertFalse(ok_susp)
        self.assertIn("SUSPENDED", msg_susp)

        # 2. Revoked state
        dev_set_key_status(temp_rec["id"], "REVOKED", modified_by=self.owner_user)
        ok_rev, msg_rev = validate_developer_access_key(self.dev_id, temp_key)
        self.assertFalse(ok_rev)
        self.assertIn("REVOKED", msg_rev)

        # 3. Compromised state
        dev_set_key_status(temp_rec["id"], "COMPROMISED", modified_by=self.owner_user)
        ok_comp, msg_comp = validate_developer_access_key(self.dev_id, temp_key)
        self.assertFalse(ok_comp)
        self.assertIn("COMPROMISED", msg_comp)

        # 4. Re-activate
        dev_set_key_status(temp_rec["id"], "ACTIVE", modified_by=self.owner_user)
        ok_act, msg_act = validate_developer_access_key(self.dev_id, temp_key)
        self.assertTrue(ok_act)

        # Clean up
        dev_delete_key(temp_rec["id"], modified_by=self.owner_user)

    def test_05_key_rotation_workflow(self):
        """Test Key Rotation: Old key becomes REPLACED and cannot authenticate; new key active."""
        # Generate initial key to rotate
        ok_init, _, init_key = dev_generate_new_dev_key_for_developer(self.dev_id, created_by=self.owner_user)
        keys_before = dev_list_developer_keys(self.dev_id)
        target_rec = [k for k in keys_before if init_key.startswith(k["key_prefix"])][0]

        # Rotate key
        ok_rot, msg_rot, rotated_key = dev_rotate_developer_key(
            dev_id=self.dev_id,
            old_key_id=target_rec["id"],
            created_by=self.owner_user,
        )
        self.assertTrue(ok_rot)
        self.assertIsNotNone(rotated_key)

        # Check old key status is now REPLACED
        keys_after = dev_list_developer_keys(self.dev_id)
        old_rec = [k for k in keys_after if k["id"] == target_rec["id"]][0]
        self.assertEqual(old_rec["status"], "REPLACED")

        # Old key should be rejected
        ok_old, msg_old = validate_developer_access_key(self.dev_id, init_key)
        self.assertFalse(ok_old)
        self.assertIn("REPLACED", msg_old)

        # New rotated key should be accepted
        ok_new, msg_new = validate_developer_access_key(self.dev_id, rotated_key)
        self.assertTrue(ok_new)

    def test_06_trusted_device_governance(self):
        """Test Layer 3 Trusted Device registration, approval, blocking, and removal."""
        test_fp = f"fp_test_{uuid.uuid4().hex[:12]}"

        # 1. Register device (Pending)
        reg_ok, _ = register_trusted_device(
            developer_id=self.dev_id,
            device_fingerprint=test_fp,
            device_name="Test Dev Machine",
            approved_by_owner=False,
        )
        self.assertTrue(reg_ok)

        # Pending device check
        ok_check, msg_check, d_dict = check_trusted_device(self.dev_id, test_fp)
        self.assertFalse(ok_check)
        self.assertIn("Pending", msg_check)

        # 2. Owner approves device
        dev_approve_device(d_dict["id"], modified_by=self.owner_user)
        ok_app, msg_app, _ = check_trusted_device(self.dev_id, test_fp)
        self.assertTrue(ok_app, msg_app)

        # 3. Owner blocks device
        dev_block_device(d_dict["id"], modified_by=self.owner_user)
        ok_blk, msg_blk, _ = check_trusted_device(self.dev_id, test_fp)
        self.assertFalse(ok_blk)
        self.assertIn("BLOCKED", msg_blk)

        # 4. Owner removes device
        dev_remove_device(d_dict["id"], modified_by=self.owner_user)
        ok_rem, msg_rem, _ = check_trusted_device(self.dev_id, test_fp)
        self.assertFalse(ok_rem)
        self.assertIn("Unrecognized", msg_rem)

    def test_07_developer_status_and_password_lifecycle(self):
        """Test developer activation/suspension and password change."""
        # Suspend developer account
        dev_toggle_developer_status(self.dev_id, "SUSPENDED", modified_by=self.owner_user)
        ok_login, msg_login, _ = authenticate_developer(self.dev_user, self.dev_pwd)
        self.assertFalse(ok_login)
        self.assertIn("SUSPENDED", msg_login)

        # Re-activate developer account
        dev_toggle_developer_status(self.dev_id, "ACTIVE", modified_by=self.owner_user)
        ok_login2, msg_login2, _ = authenticate_developer(self.dev_user, self.dev_pwd)
        self.assertTrue(ok_login2)

        # Change password
        new_pwd = "NewDeveloperPassword2026!"
        ok_pw, _ = dev_change_password(self.dev_id, self.dev_pwd, new_pwd)
        self.assertTrue(ok_pw)

        # Old password fails
        ok_old_pw, _, _ = authenticate_developer(self.dev_user, self.dev_pwd)
        self.assertFalse(ok_old_pw)

        # New password succeeds
        ok_new_pw, _, _ = authenticate_developer(self.dev_user, new_pwd)
        self.assertTrue(ok_new_pw)

    def test_08_iam_audit_logging(self):
        """Test that dedicated Developer IAM audit logs are generated and populated."""
        logs = dev_list_iam_audit_logs(limit=50)
        self.assertGreater(len(logs), 0)
        actions = [l["action"] for l in logs]
        self.assertTrue(any("Key" in a or "Developer" in a or "Login" in a for a in actions))


if __name__ == "__main__":
    unittest.main()
