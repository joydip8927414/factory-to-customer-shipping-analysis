"""
admin_security.py
=================
Enterprise security, authentication, and role-based access subsystem
for the Nassau Candy Logistics Intelligence Platform.

Provides:
- Bcrypt salted password hashing and constant-time verification (work factor 12)
- Database-backed user management and role-based permissions (Administrator, Analyst, Viewer)
- Secure single-use Registration ID validation and activation workflow
- Brute-force protection: Failed login tracking, account locking (5 attempts, 15 min lock)
- Session authentication with Remember Me token support and inactivity timeout
- Security audit event integration
"""

from __future__ import annotations

import secrets
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bcrypt
from sqlalchemy import func, or_, select

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.models import RegistrationId, Role, SessionRecord, User
from src.db.session import get_db_session
from src.utils import get_logger

logger = get_logger(__name__)

# Security parameters
DEFAULT_SESSION_TIMEOUT = 15 * 60  # 15 minutes inactivity timeout
REMEMBER_ME_DAYS = 30              # 30 days session token for Remember Me
MAX_FAILED_ATTEMPTS = 5            # Lock account after 5 consecutive failures
LOCKOUT_MINUTES = 15               # Account lockout duration


# ─────────────────────────────────────────────────────────────────────────────
# 1. BCRYPT PASSWORD HASHING
# ─────────────────────────────────────────────────────────────────────────────

def hash_password_bcrypt(password: str) -> str:
    """Hash a plaintext password using bcrypt with work factor 12."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password_bcrypt(plain_password: str, hashed_password: str) -> bool:
    """Constant-time verification of password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.warning("Bcrypt verification failed: %s", e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 2. USER AUTHENTICATION & BRUTE FORCE DEFENSE
# ─────────────────────────────────────────────────────────────────────────────

def authenticate_user_db(
    username_or_email: str,
    password: str,
    ip_address: str = "127.0.0.1",
    remember_me: bool = False,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Authenticate user against database with brute-force protection and lockout enforcement.

    Returns:
        (success: bool, message: str, user_dict: Optional[Dict])
    """
    from src.admin_manager import record_audit_event

    ident = username_or_email.strip()
    if not ident or not password:
        return False, "Username/Email and Password are required.", None

    now = datetime.now()

    with get_db_session() as session:
        user = session.execute(
            select(User).where(
                or_(
                    func.lower(User.username) == ident.lower(),
                    func.lower(User.email) == ident.lower(),
                )
            )
        ).scalar_one_or_none()

        if not user:
            record_audit_event(
                user=ident,
                action="Login Failed",
                module="Authentication",
                status="Failure",
                details=f"Login attempt with non-existent identity from IP: {ip_address}",
            )
            return False, "Invalid username or password.", None

        # Check if account is currently locked
        if user.locked_until and user.locked_until > now:
            mins_left = int((user.locked_until - now).total_seconds() / 60) + 1
            record_audit_event(
                user=user.username,
                action="Login Blocked",
                module="Authentication",
                status="Warning",
                details=f"Locked account attempted login. Lockout remaining: {mins_left} min(s)",
            )
            return False, f"Account is locked due to repeated failed logins. Please try again in {mins_left} minute(s).", None

        # If locked_until has passed, clear the lockout and reset counter
        if user.locked_until and user.locked_until <= now:
            user.locked_until = None
            user.failed_logins = 0

        # Verify password (with whitespace resilience)
        pw_ok = verify_password_bcrypt(password, user.password_hash) or verify_password_bcrypt(password.strip(), user.password_hash)
        if not pw_ok:
            user.failed_logins = (user.failed_logins or 0) + 1
            attempts_remaining = max(0, MAX_FAILED_ATTEMPTS - user.failed_logins)

            if user.failed_logins >= MAX_FAILED_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                record_audit_event(
                    user=user.username,
                    action="Account Locked",
                    module="Authentication",
                    status="Warning",
                    details=f"Account locked after {MAX_FAILED_ATTEMPTS} consecutive failures from IP {ip_address}",
                )
                session.commit()
                return False, f"Account has been locked for {LOCKOUT_MINUTES} minutes due to excessive failed attempts.", None

            record_audit_event(
                user=user.username,
                action="Login Failed",
                module="Authentication",
                status="Failure",
                details=f"Invalid password. Remaining attempts before lock: {attempts_remaining}",
            )
            session.commit()
            return False, f"Invalid username or password. {attempts_remaining} attempt(s) remaining before lockout.", None

        # Check account activation status
        if not user.is_active:
            return False, "Account is disabled. Contact your system administrator.", None

        # Successful login: reset failed counters
        user.failed_logins = 0
        user.locked_until = None
        user.last_login_at = now

        # Create session record
        session_token = secrets.token_urlsafe(48)
        expiry_delta = timedelta(days=REMEMBER_ME_DAYS) if remember_me else timedelta(seconds=DEFAULT_SESSION_TIMEOUT)
        sess_record = SessionRecord(
            session_token=session_token,
            user_id=user.id,
            ip_address=ip_address,
            is_active=True,
            expires_at=now + expiry_delta,
            last_active_at=now,
        )
        session.add(sess_record)
        session.commit()

        role_name = user.role.name if user.role else "Viewer"
        permissions = user.role.permissions if user.role and user.role.permissions else {}

        user_info = {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "role": role_name,
            "permissions": permissions,
            "session_token": session_token,
            "remember_me": remember_me,
            "last_login": user.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if user.last_login_at else "First Login",
        }

        record_audit_event(
            user=user.username,
            action="Login",
            module="Authentication",
            status="Success",
            details=f"Authenticated as {role_name} (Remember Me: {remember_me})",
        )
        return True, "Login successful", user_info


# ─────────────────────────────────────────────────────────────────────────────
# 3. SECURE REGISTRATION ID WORKFLOW
# ─────────────────────────────────────────────────────────────────────────────

def validate_registration_id(token: str) -> Tuple[bool, str, Optional[RegistrationId]]:
    """
    Validate that a Registration ID exists, is active, and has not expired.
    """
    token_clean = token.strip()
    if not token_clean:
        return False, "Registration ID cannot be blank.", None

    now = datetime.now()
    with get_db_session() as session:
        reg = session.execute(
            select(RegistrationId).where(RegistrationId.token == token_clean)
        ).scalar_one_or_none()

        if not reg:
            return False, "Invalid Registration ID. Please request a valid authorized key from company administration.", None

        if reg.status == "USED":
            return False, f"Registration ID was already used by '{reg.used_by}' on {reg.used_at.strftime('%Y-%m-%d %H:%M') if reg.used_at else 'prior date'}.", None

        if reg.status == "REVOKED":
            return False, "This Registration ID has been revoked by an administrator.", None

        if reg.expiry_date and reg.expiry_date < now:
            reg.status = "EXPIRED"
            session.commit()
            return False, "This Registration ID has expired. Please request a renewed key.", None

        return True, "Registration ID is valid.", reg


def register_admin_user(
    registration_token: str,
    full_name: str,
    username: str,
    email: str,
    password: str,
    target_role: str = "Administrator",
) -> Tuple[bool, str]:
    """
    Registers a new user strictly bounded to a verified Registration ID.
    Marks the Registration ID as USED and assigns the requested role.
    """
    from src.admin_manager import record_audit_event

    # 1. Validate Registration ID
    is_valid, err_msg, reg_obj = validate_registration_id(registration_token)
    if not is_valid or not reg_obj:
        record_audit_event(
            user=username or "Unregistered",
            action="Registration Rejected",
            module="Registration",
            status="Failure",
            details=f"Attempted with invalid key '{registration_token}': {err_msg}",
        )
        return False, err_msg

    # 2. Input validation
    clean_username = username.strip()
    clean_email = email.strip().lower()
    clean_name = full_name.strip()

    if not clean_username or len(clean_username) < 3:
        return False, "Username must be at least 3 characters."
    if "@" not in clean_email or "." not in clean_email:
        return False, "Please provide a valid email address."
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."

    now = datetime.now()

    with get_db_session() as session:
        # Check username uniqueness
        existing_user = session.execute(
            select(User).where(User.username == clean_username)
        ).scalar_one_or_none()
        if existing_user:
            return False, f"Username '{clean_username}' is already taken."

        # Check email uniqueness
        existing_email = session.execute(
            select(User).where(User.email == clean_email)
        ).scalar_one_or_none()
        if existing_email:
            return False, f"Email '{clean_email}' is already registered."

        # Fetch role
        role = session.execute(select(Role).where(Role.name == target_role)).scalar_one_or_none()
        if not role:
            role = session.execute(select(Role).where(Role.name == "Administrator")).scalar_one()

        # Hash password using bcrypt
        pwd_hash = hash_password_bcrypt(password)

        # Create user
        new_user = User(
            username=clean_username,
            email=clean_email,
            full_name=clean_name,
            password_hash=pwd_hash,
            role_id=role.id,
            is_active=True,
        )
        session.add(new_user)
        session.flush()

        # Mark registration ID as USED
        reg = session.execute(
            select(RegistrationId).where(RegistrationId.token == registration_token.strip())
        ).scalar_one()
        reg.status = "USED"
        reg.used_by = clean_username
        reg.used_at = now
        session.commit()

        record_audit_event(
            user=clean_username,
            action="Registration",
            module="Registration",
            status="Success",
            details=f"Account created via Registration ID {registration_token[:8]}... with role '{role.name}'",
        )
        logger.info("Created account %s via Registration ID %s", clean_username, registration_token)
        return True, f"Account '{clean_username}' successfully registered! You may now sign in."


# ─────────────────────────────────────────────────────────────────────────────
# 4. SESSION VALIDATION & AUTO-LOGOUT
# ─────────────────────────────────────────────────────────────────────────────

def validate_active_session(
    session_token: str,
    timeout_seconds: int = DEFAULT_SESSION_TIMEOUT,
) -> Tuple[bool, Optional[User]]:
    """Check session token validity against database and update last active time."""
    if not session_token:
        return False, None

    now = datetime.now()
    with get_db_session() as session:
        sess = session.execute(
            select(SessionRecord).where(
                SessionRecord.session_token == session_token,
                SessionRecord.is_active == True,
            )
        ).scalar_one_or_none()

        if not sess:
            return False, None

        # Check expiry
        if sess.expires_at < now:
            sess.is_active = False
            session.commit()
            return False, None

        # Check inactivity timeout
        if (now - sess.last_active_at).total_seconds() > timeout_seconds:
            sess.is_active = False
            session.commit()
            return False, None

        # Keep alive
        sess.last_active_at = now
        user = sess.user
        session.commit()
        return True, user


def terminate_session(session_token: str, username: str = "Unknown") -> None:
    """Revoke session token and mark inactive in database."""
    from src.admin_manager import record_audit_event

    if not session_token:
        return
    with get_db_session() as session:
        sess = session.execute(
            select(SessionRecord).where(SessionRecord.session_token == session_token)
        ).scalar_one_or_none()
        if sess:
            sess.is_active = False
            session.commit()

    record_audit_event(
        user=username,
        action="Logout",
        module="Authentication",
        status="Success",
        details="User securely terminated session",
    )


# Compatibility aliases for existing imports
def authenticate_user(username: str, password: str) -> Tuple[bool, str]:
    ok, msg, _ = authenticate_user_db(username, password)
    return ok, msg


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Enforces enterprise password complexity:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 numeric digit
    - At least 1 special character
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number."
    special_chars = set("!@#$%^&*()-_=+[]{}|;:,.<>?/~`")
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special symbol (e.g. !@#$%^&*)."
    return True, "Password meets complexity requirements."


def update_admin_password_db(
    username: str,
    current_password: str,
    new_password: str,
    confirm_password: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Verify current password, validate strength & confirmation, update bcrypt hash,
    and invalidate all active sessions for this user so re-login is required.
    """
    from src.admin_manager import record_audit_event

    clean_user = username.strip()
    if not clean_user or not current_password or not new_password:
        return False, "All password fields are required."

    if confirm_password is not None and new_password != confirm_password:
        return False, "New password and confirmation do not match."

    if current_password == new_password:
        return False, "New password must be different from current password."

    # Validate password strength
    is_strong, strength_msg = validate_password_strength(new_password)
    if not is_strong:
        return False, strength_msg

    try:
        with get_db_session() as session:
            user = session.execute(select(User).where(User.username == clean_user)).scalar_one_or_none()
            if not user:
                record_audit_event(
                    user=clean_user,
                    action="Password Change Failed",
                    module="Authentication",
                    status="Failure",
                    details="Target user account not found",
                )
                return False, "User account not found."

            # Verify current password
            if not verify_password_bcrypt(current_password, user.password_hash):
                record_audit_event(
                    user=clean_user,
                    action="Password Change Failed",
                    module="Authentication",
                    status="Failure",
                    details="Incorrect current password provided",
                )
                return False, "Incorrect current password."

            # Store only bcrypt hash
            user.password_hash = hash_password_bcrypt(new_password)
            user.updated_at = datetime.now()

            # Immediately invalidate all existing sessions for this user
            sessions = session.execute(
                select(SessionRecord).where(
                    SessionRecord.user_id == user.id,
                    SessionRecord.is_active == True,
                )
            ).scalars().all()
            for s in sessions:
                s.is_active = False

            session.commit()

        record_audit_event(
            user=clean_user,
            action="Password Changed",
            module="Authentication",
            status="Success",
            details="Administrator updated password; all active sessions revoked",
        )
        logger.info("Password updated and sessions revoked for user %s", clean_user)
        return True, "Security passphrase updated successfully! All active sessions have been terminated. Please log in with your new password."

    except Exception as e:
        logger.error("Failed to update password in database: %s", e)
        record_audit_event(
            user=clean_user,
            action="Password Change Error",
            module="Authentication",
            status="Failure",
            details=f"Database exception during password change: {str(e)}",
        )
        return False, f"Failed to update password due to a system error: {str(e)}"


def get_last_successful_login() -> Optional[Dict[str, Any]]:
    """
    Query the latest successful login audit record or user last_login_at.
    """
    try:
        from src.db.models import AuditLog
        with get_db_session() as session:
            log = session.execute(
                select(AuditLog)
                .where(AuditLog.action == "Login Success", AuditLog.status == "Success")
                .order_by(AuditLog.timestamp.desc())
            ).scalars().first()

            if log:
                return {
                    "username": log.user,
                    "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else "Recent",
                }

            # Fallback to User table last_login_at
            user = session.execute(
                select(User).where(User.last_login_at.is_not(None)).order_by(User.last_login_at.desc())
            ).scalars().first()

            if user and user.last_login_at:
                return {
                    "username": user.username,
                    "timestamp": user.last_login_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
    except Exception as e:
        logger.debug("Failed to fetch last login: %s", e)

    return None


