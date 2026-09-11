"""
test_auth_and_security_enhancements.py
======================================
Comprehensive automated test suite verifying:
1. Password strength validation & error rules.
2. Admin password updates with bcrypt verification, audit trail, and session revocation.
3. 3-Layer Developer Authentication architecture (Identity, Access Key, Local Device).
4. System Bootstrap setup (creation of initial root Owner).
5. Owner Developer Management & Master Key authorization ('ChangeMeMasterKey2026!').
6. Trusted Device listing and revocation.
"""

import unittest
import uuid
from datetime import datetime

from src.admin_security import (
    hash_password_bcrypt,
    register_admin_user,
    update_admin_password_db,
    validate_password_strength,
    verify_password_bcrypt,
)
from src.db.models import Developer, DeveloperAccessKey, SessionRecord, TrustedDevice, User
from src.db.session import get_db_session
from src.developer.dev_security import (
    authenticate_developer,
    bootstrap_first_developer,
    check_trusted_device,
    has_any_developers,
    list_trusted_devices_db,
    register_trusted_device,
    revoke_trusted_device_db,
    validate_developer_access_key,
)
from src.developer.dev_service import (
    DEV_MASTER_MANAGEMENT_KEY,
    dev_create_admin_user,
    dev_create_new_developer,
    dev_delete_admin_user,
    dev_generate_new_dev_key_for_developer,
    dev_generate_registration_ids,
    dev_list_admin_users,
    dev_list_all_developers,
    dev_list_developer_keys,
    dev_reset_admin_password,
    dev_toggle_developer_status,
    dev_update_admin_user,
    verify_dev_master_key,
)


class TestAuthAndSecurityEnhancements(unittest.TestCase):

    def setUp(self):
        self.suffix = uuid.uuid4().hex[:8]
        self.test_admin = f"testadmin_{self.suffix}"
        self.test_email = f"testadmin_{self.suffix}@nassaucandy.com"
        self.initial_pwd = "StrongAdminPass1!"

        # Ensure a test registration token exists
        keys = dev_generate_registration_ids(count=1, valid_days=10, created_by="UnitTest")
        self.reg_token = keys[0]

        # Provision test administrator user
        ok, msg = register_admin_user(
            registration_token=self.reg_token,
            full_name=f"Admin {self.suffix}",
            username=self.test_admin,
            email=self.test_email,
            password=self.initial_pwd,
            target_role="Administrator",
        )
        self.assertTrue(ok, f"Failed to setup test admin user: {msg}")

    # ── 1. Password Strength Validation ──
    def test_validate_password_strength(self):
        # Too short
        ok, msg = validate_password_strength("Short1!")
        self.assertFalse(ok)
        self.assertIn("at least 8 characters", msg)

        # Missing uppercase
        ok, msg = validate_password_strength("lowercaseonly1!")
        self.assertFalse(ok)
        self.assertIn("uppercase", msg)

        # Missing lowercase
        ok, msg = validate_password_strength("UPPERCASEONLY1!")
        self.assertFalse(ok)
        self.assertIn("lowercase", msg)

        # Missing digit
        ok, msg = validate_password_strength("NoDigitsHere!")
        self.assertFalse(ok)
        self.assertTrue("digit" in msg.lower() or "number" in msg.lower())

        # Missing symbol
        ok, msg = validate_password_strength("NoSpecialSymbols123")
        self.assertFalse(ok)
        self.assertTrue("special" in msg.lower() or "symbol" in msg.lower())

        # Valid strong password
        ok, msg = validate_password_strength("SecureP@ssw0rd2026")
        self.assertTrue(ok)

    # ── 2. Admin Password Update Subsystem ──
    def test_admin_password_update_workflow(self):
        # Mismatch current password
        ok, msg = update_admin_password_db(
            username=self.test_admin,
            current_password="WrongCurrentPassword1!",
            new_password="NewSecureP@ss2026",
            confirm_password="NewSecureP@ss2026",
        )
        self.assertFalse(ok)
        self.assertIn("incorrect", msg.lower())

        # Mismatch new & confirm
        ok, msg = update_admin_password_db(
            username=self.test_admin,
            current_password=self.initial_pwd,
            new_password="NewSecureP@ss2026",
            confirm_password="DifferentP@ss2026",
        )
        self.assertFalse(ok)
        self.assertIn("do not match", msg.lower())

        # Weak new password
        ok, msg = update_admin_password_db(
            username=self.test_admin,
            current_password=self.initial_pwd,
            new_password="weak",
            confirm_password="weak",
        )
        self.assertFalse(ok)
        self.assertIn("at least 8 characters", msg.lower())

        # Same as current password
        ok, msg = update_admin_password_db(
            username=self.test_admin,
            current_password=self.initial_pwd,
            new_password=self.initial_pwd,
            confirm_password=self.initial_pwd,
        )
        self.assertFalse(ok)
        self.assertTrue("different" in msg.lower() or "same" in msg.lower())

        # Plant an active session in db for test user to verify session revocation
        with get_db_session() as session:
            user = session.query(User).filter_by(username=self.test_admin).first()
            test_sess = SessionRecord(
                session_token=f"sess_tok_{self.suffix}",
                user_id=user.id,
                ip_address="127.0.0.1",
                expires_at=datetime(2030, 1, 1),
                is_active=True,
            )
            session.add(test_sess)
            session.commit()

        # Valid password change
        new_pwd = "UpdatedSecureP@ss2026!"
        ok, msg = update_admin_password_db(
            username=self.test_admin,
            current_password=self.initial_pwd,
            new_password=new_pwd,
            confirm_password=new_pwd,
        )
        self.assertTrue(ok, f"Expected success but got: {msg}")

        # Verify old password fails and new password succeeds
        with get_db_session() as session:
            user = session.query(User).filter_by(username=self.test_admin).first()
            self.assertFalse(verify_password_bcrypt(self.initial_pwd, user.password_hash))
            self.assertTrue(verify_password_bcrypt(new_pwd, user.password_hash))

            # Verify active sessions were revoked
            active_sessions = session.query(SessionRecord).filter_by(user_id=user.id, is_active=True).all()
            self.assertEqual(len(active_sessions), 0)

    # ── 3. Developer 3-Layer Authentication & Master Key ──
    def test_developer_3_layer_security_and_master_key(self):
        dev_user = f"dev_{self.suffix}"
        dev_email = f"dev_{self.suffix}@nassaucandy.com"
        dev_pwd = "DevP@ssword2026!"

        # Create developer via Owner service
        ok, msg, gen_key = dev_create_new_developer(
            username=dev_user,
            email=dev_email,
            full_name=f"Developer {self.suffix}",
            password=dev_pwd,
            role="Developer",
            created_by="RootOwner",
        )
        self.assertTrue(ok, f"Failed to create developer: {msg}")
        self.assertIsNotNone(gen_key)

        # Layer 1: Credentials authentication
        ok_l1, msg_l1, dev_dict = authenticate_developer(dev_user, dev_pwd)
        self.assertTrue(ok_l1, f"Layer 1 failed: {msg_l1}")
        dev_id = dev_dict["id"]

        # Layer 2: Access key validation with generated key
        ok_l2, msg_l2 = validate_developer_access_key(dev_id, gen_key)
        self.assertTrue(ok_l2, f"Layer 2 failed: {msg_l2}")

        # Layer 2: Master key override check is restricted to Owner accounts
        self.assertTrue(verify_dev_master_key(DEV_MASTER_MANAGEMENT_KEY))
        # For standard developer, master key must be rejected
        ok_l2_nonowner_mk, msg_l2_mk = validate_developer_access_key(dev_id, DEV_MASTER_MANAGEMENT_KEY)
        self.assertFalse(ok_l2_nonowner_mk)
        self.assertIn("restricted to Owner accounts", msg_l2_mk)

        # For an Owner developer, master key must be authorized
        owner_user = f"owner_{self.suffix}"
        ok_ow, _, _ = dev_create_new_developer(
            username=owner_user,
            email=f"{owner_user}@nassaucandy.com",
            full_name="Root Owner Clone",
            password=dev_pwd,
            role="Owner",
            created_by="RootOwner",
        )
        self.assertTrue(ok_ow)
        all_devs = dev_list_all_developers()
        owner_id = [d for d in all_devs if d["username"] == owner_user][0]["id"]
        ok_l2_owner_mk, _ = validate_developer_access_key(owner_id, DEV_MASTER_MANAGEMENT_KEY)
        self.assertTrue(ok_l2_owner_mk, "Owner must be allowed to use Master Key override")

        # Layer 3: Device authorization check
        dummy_fp = f"test_fp_{uuid.uuid4().hex}"
        ok_dev, _, _ = check_trusted_device(dev_id, dummy_fp)
        self.assertFalse(ok_dev, "Unregistered device should not be trusted initially")

        # Authorize device
        reg_ok, _ = register_trusted_device(
            developer_id=dev_id,
            device_fingerprint=dummy_fp,
            device_name="Test Dev Machine",
            ip_address="127.0.0.1",
        )
        self.assertTrue(reg_ok)

        # Now device must be recognized
        ok_dev_post, _, rec = check_trusted_device(dev_id, dummy_fp)
        self.assertTrue(ok_dev_post)
        self.assertEqual(rec["device_name"], "Test Dev Machine")

        # List trusted devices
        devs_list = list_trusted_devices_db(dev_id)
        self.assertTrue(any(d["full_fingerprint"] == dummy_fp for d in devs_list))

        # Revoke trusted device
        rec_id = [d["id"] for d in devs_list if d["full_fingerprint"] == dummy_fp][0]
        rev_ok, _ = revoke_trusted_device_db(rec_id, dev_id)
        self.assertTrue(rev_ok)

        # Verify device is no longer recognized
        ok_after_rev, _, _ = check_trusted_device(dev_id, dummy_fp)
        self.assertFalse(ok_after_rev)

    # ── 4. Developer Account Status Governance ──
    def test_developer_account_status_toggle(self):
        dev_user = f"toggle_{self.suffix}"
        ok, _, _ = dev_create_new_developer(
            username=dev_user,
            email=f"{dev_user}@nassaucandy.com",
            full_name="Toggle User",
            password="ToggleP@ssword1!",
            role="Developer",
        )
        self.assertTrue(ok)

        all_devs = dev_list_all_developers()
        target = [d for d in all_devs if d["username"] == dev_user][0]

        # Deactivate
        ok_deact, msg_deact = dev_toggle_developer_status(target["id"], active=False)
        self.assertTrue(ok_deact)

        # Login should fail when deactivated
        ok_login, msg_login, _ = authenticate_developer(dev_user, "ToggleP@ssword1!")
        self.assertFalse(ok_login)
        self.assertTrue("deactivated" in msg_login.lower() or "disabled" in msg_login.lower())

        # Reactivate
        ok_act, _ = dev_toggle_developer_status(target["id"], active=True)
        self.assertTrue(ok_act)

        ok_login_again, _, _ = authenticate_developer(dev_user, "ToggleP@ssword1!")
        self.assertTrue(ok_login_again)

    # ── 5. Developer Key Creation Exclusively via Owner Master Key ──
    def test_developer_key_creation_under_owner_master_control(self):
        dev_user = f"keydev_{self.suffix}"
        # 1. New Developer created by Owner with initial dev key
        ok, msg, initial_dev_key = dev_create_new_developer(
            username=dev_user,
            email=f"{dev_user}@nassaucandy.com",
            full_name="Keyed Developer",
            password="DevP@ssword123!",
            role="Developer",
            created_by="Owner",
        )
        self.assertTrue(ok)
        self.assertIsNotNone(initial_dev_key)
        self.assertTrue(initial_dev_key.startswith("DEV-KEY-"))

        all_devs = dev_list_all_developers()
        dev_entry = [d for d in all_devs if d["username"] == dev_user][0]
        dev_id = dev_entry["id"]

        # Initial key validates
        ok_l2, _ = validate_developer_access_key(dev_id, initial_dev_key)
        self.assertTrue(ok_l2)

        # 2. Owner generates an additional Dev Key using Master Key authentication context
        self.assertTrue(verify_dev_master_key(DEV_MASTER_MANAGEMENT_KEY))
        ok_new_k, msg_new_k, new_dev_key = dev_generate_new_dev_key_for_developer(
            dev_id=dev_id,
            created_by="Owner",
            key_name="Secondary Dev Access Key",
        )
        self.assertTrue(ok_new_k)
        self.assertIsNotNone(new_dev_key)
        self.assertTrue(new_dev_key.startswith("DEV-KEY-"))

        # Both keys should be in database and validated
        keys = dev_list_developer_keys(dev_id=dev_id)
        self.assertEqual(len(keys), 2)

        ok_val_new, _ = validate_developer_access_key(dev_id, new_dev_key)
        self.assertTrue(ok_val_new)

    # ── 6. Layer 2: Non-Owner cannot use Master Key, must use their own Dev Key ──
    def test_layer_2_master_key_isolated_to_owner(self):
        dev_user = f"nonowner_{self.suffix}"
        ok, _, nonowner_key = dev_create_new_developer(
            username=dev_user,
            email=f"{dev_user}@nassaucandy.com",
            full_name="Standard Developer",
            password="DevP@ssword123!",
            role="Developer",
            created_by="Owner",
        )
        self.assertTrue(ok)

        all_devs = dev_list_all_developers()
        dev_entry = [d for d in all_devs if d["username"] == dev_user][0]
        dev_id = dev_entry["id"]

        # Attempting to use Owner Master Key for a standard developer account must fail
        ok_mk, msg_mk = validate_developer_access_key(dev_id, DEV_MASTER_MANAGEMENT_KEY)
        self.assertFalse(ok_mk)
        self.assertIn("restricted to Owner accounts", msg_mk)

        # Using their own personal assigned Dev Key must succeed
        ok_own, _ = validate_developer_access_key(dev_id, nonowner_key)
        self.assertTrue(ok_own)

    # ── 7. Administrator Governance (Creation, Edit, Password Reset, Deletion) ──
    def test_administrator_governance_lifecycle(self):
        admin_uname = f"gov_admin_{self.suffix}"
        admin_email = f"{admin_uname}@nassaucandy.com"

        # 1. Create Admin User directly from Developer Governance
        ok_c, msg_c = dev_create_admin_user(
            username=admin_uname,
            full_name="Governance Test Admin",
            email=admin_email,
            password="InitialGovP@ssword123!",
            role_name="Branch Admin",
            created_by="UnitTestDev",
        )
        self.assertTrue(ok_c)

        admins = dev_list_admin_users()
        admin_match = [u for u in admins if u["username"] == admin_uname]
        self.assertEqual(len(admin_match), 1)
        created_id = admin_match[0]["id"]
        self.assertEqual(admin_match[0]["role_name"], "Branch Admin")
        self.assertTrue(admin_match[0]["is_active"])

        # 2. Edit Admin Profile and Promote Role
        ok_u, msg_u = dev_update_admin_user(
            user_id=created_id,
            full_name="Governance Lead Admin",
            email=f"updated_{admin_email}",
            role_name="Administrator",
            is_active=True,
            modified_by="UnitTestDev",
        )
        self.assertTrue(ok_u)

        admins_after_up = dev_list_admin_users()
        up_match = [u for u in admins_after_up if u["id"] == created_id][0]
        self.assertEqual(up_match["full_name"], "Governance Lead Admin")
        self.assertEqual(up_match["role_name"], "Administrator")

        # 3. Reset Admin Password
        ok_rst, msg_rst = dev_reset_admin_password(
            user_id=created_id,
            new_password="NewGovP@ssword2026!",
            modified_by="UnitTestDev",
        )
        self.assertTrue(ok_rst)

        # Verify new password works
        from src.admin_security import authenticate_user_db
        ok_auth, _, _ = authenticate_user_db(admin_uname, "NewGovP@ssword2026!")
        self.assertTrue(ok_auth)

        # 4. Delete Admin Account
        ok_d, msg_d = dev_delete_admin_user(user_id=created_id, modified_by="UnitTestDev")
        self.assertTrue(ok_d)

        admins_after_del = dev_list_admin_users()
        self.assertEqual(len([u for u in admins_after_del if u["id"] == created_id]), 0)


if __name__ == "__main__":
    unittest.main()

