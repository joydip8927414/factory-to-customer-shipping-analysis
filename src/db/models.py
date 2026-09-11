"""
models.py
=========
Normalized database models for the Nassau Candy Logistics Administration System.

Categories:
1. Authentication (Users, Roles, Sessions)
2. Administration (Registration IDs, Audit Logs, Dataset Versions, Uploaded Files)
3. Business (Factory Mapping, Factory Coordinates, Product Mapping, Delay Threshold,
             Business Rules, Dashboard Settings, ML Settings)
4. Application (Saved Filters, User Preferences, Reports, ML Metadata)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base


# ─────────────────────────────────────────────────────────────────────────────
# 1. AUTHENTICATION & ACCESS CONTROL
# ─────────────────────────────────────────────────────────────────────────────

class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    permissions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[List["User"]] = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    role: Mapped["Role"] = relationship("Role", back_populates="users")
    sessions: Mapped[List["SessionRecord"]] = relationship("SessionRecord", back_populates="user", cascade="all, delete-orphan")


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), default="127.0.0.1")
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="sessions")


# ─────────────────────────────────────────────────────────────────────────────
# 1. DEVELOPER AUTHENTICATION & PORTAL CONTROL
# ─────────────────────────────────────────────────────────────────────────────

class DeveloperRole(Base):
    """Enterprise IAM role definitions for developers and platform maintainers."""
    __tablename__ = "developer_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)  # Owner, Developer
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    permissions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    developers: Mapped[List["Developer"]] = relationship("Developer", back_populates="role_rel")


class Developer(Base):
    """
    Independent Developer account model for enterprise IAM platform governance.
    Every developer has an isolated identity, password hash, status, personal keys,
    trusted devices, and audit history.
    """
    __tablename__ = "developers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="Developer")  # Owner, Developer
    role_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("developer_roles.id"), nullable=True)
    totp_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE, SUSPENDED, DEACTIVATED
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    role_rel: Mapped[Optional["DeveloperRole"]] = relationship("DeveloperRole", back_populates="developers")
    sessions: Mapped[List["DeveloperSession"]] = relationship("DeveloperSession", back_populates="developer", cascade="all, delete-orphan")
    keys: Mapped[List["DeveloperKey"]] = relationship("DeveloperKey", back_populates="developer", cascade="all, delete-orphan")
    devices: Mapped[List["DeveloperDevice"]] = relationship("DeveloperDevice", back_populates="developer", cascade="all, delete-orphan")

    # Backwards-compatible aliases
    @property
    def access_keys(self) -> List["DeveloperKey"]:
        return self.keys

    @property
    def trusted_devices(self) -> List["DeveloperDevice"]:
        return self.devices


class DeveloperSession(Base):
    __tablename__ = "developer_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    developer_id: Mapped[int] = mapped_column(Integer, ForeignKey("developers.id"), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), default="127.0.0.1")
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    developer: Mapped["Developer"] = relationship("Developer", back_populates="sessions")


class DeveloperKey(Base):
    """
    Enterprise Developer Access Key.
    Individual credential owned strictly by each developer. Never shared.
    Managed, rotated, and revoked exclusively by the Owner/Team Lead.
    """
    __tablename__ = "developer_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    developer_id: Mapped[int] = mapped_column(Integer, ForeignKey("developers.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), default="Primary Access Key")
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)  # ACTIVE, EXPIRED, REVOKED, SUSPENDED, COMPROMISED, REPLACED
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str] = mapped_column(String(255), default="")
    created_by: Mapped[str] = mapped_column(String(60), default="Owner")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_used_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    last_used_device: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    developer: Mapped["Developer"] = relationship("Developer", back_populates="keys")


# Backwards compatibility alias for DeveloperAccessKey
DeveloperAccessKey = DeveloperKey


class DeveloperDevice(Base):
    """
    Developer Trusted Device Registry.
    Restricts access to pre-authorized workstations with browser/OS tracking.
    """
    __tablename__ = "developer_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    developer_id: Mapped[int] = mapped_column(Integer, ForeignKey("developers.id"), nullable=False, index=True)
    device_fingerprint: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    device_name: Mapped[str] = mapped_column(String(120), default="Workstation Browser")
    browser: Mapped[str] = mapped_column(String(60), default="Unknown Browser")
    os: Mapped[str] = mapped_column(String(60), default="Unknown OS")
    ip_address: Mapped[str] = mapped_column(String(45), default="127.0.0.1")
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="TRUSTED")  # TRUSTED, BLOCKED, PENDING
    first_login_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Legacy field compatibility
    @property
    def last_used_at(self) -> datetime:
        return self.last_login_at

    @last_used_at.setter
    def last_used_at(self, val: datetime) -> None:
        self.last_login_at = val

    developer: Mapped["Developer"] = relationship("Developer", back_populates="devices")


# Backwards compatibility alias for TrustedDevice
TrustedDevice = DeveloperDevice


class DeveloperAuditLog(Base):
    """
    Dedicated Enterprise Audit Log for Developer IAM activities.
    """
    __tablename__ = "developer_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    developer: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    performed_by: Mapped[str] = mapped_column(String(60), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="Success")  # Success, Failure, Warning
    device: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), default="127.0.0.1")
    details: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)


class SystemSecurity(Base):
    """
    Cryptographic System Security Configuration.
    Stores salted bcrypt hash of Master Management Key, security version,
    and platform IAM policy governance metadata.
    """
    __tablename__ = "system_security"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    master_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    security_version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by: Mapped[str] = mapped_column(String(60), default="Owner")


# ─────────────────────────────────────────────────────────────────────────────
# 2. ADMINISTRATION & REGISTRATION KEYS
# ─────────────────────────────────────────────────────────────────────────────

class RegistrationId(Base):
    """
    Authorized company registration keys required for administrative account creation.
    Created, revoked, and extended EXCLUSIVELY by the Developer Portal.
    The Logistics Dashboard has read-only access to validate and redeem keys.
    """
    __tablename__ = "registration_ids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE, USED, REVOKED, EXPIRED
    expiry_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[str] = mapped_column(String(60), default="Developer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    used_by: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(255), default="")


class ApiKey(Base):
    """Developer managed API credentials for external ERP/WMS integrations."""
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE, REVOKED
    created_by: Mapped[str] = mapped_column(String(60), default="Developer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class LicenseInfo(Base):
    """Platform deployment license and customer metadata."""
    __tablename__ = "license_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    licensee: Mapped[str] = mapped_column(String(120), nullable=False)
    license_tier: Mapped[str] = mapped_column(String(50), default="Enterprise Tier 1")
    license_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    max_nodes: Mapped[int] = mapped_column(Integer, default=25)
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class AuditLog(Base):
    """
    Comprehensive audit log capturing every administrative activity.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    administrator: Mapped[str] = mapped_column(String(60), nullable=False)
    module: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="Success")  # Success, Failure, Warning, Info
    description: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)


class DatasetVersion(Base):
    """
    Maintains historical snapshots of datasets with rollback and restore paths.
    """
    __tablename__ = "dataset_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    author: Mapped[str] = mapped_column(String(60), default="Administrator")
    description: Mapped[str] = mapped_column(String(255), default="")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    col_count: Mapped[int] = mapped_column(Integer, default=0)
    backup_path: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)


class UploadedFile(Base):
    """
    Catalog of all ingested dataset files.
    """
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), default="CSV")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[str] = mapped_column(String(60), default="Administrator")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(30), default="STAGED")  # STAGED, COMMITTED, REJECTED
    storage_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# 3. BUSINESS CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

class FactoryCoordinate(Base):
    __tablename__ = "factory_coordinates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    division: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProductMapping(Base):
    __tablename__ = "product_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    factory_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class DelayThreshold(Base):
    __tablename__ = "delay_thresholds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ship_mode: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    threshold_days: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class BusinessRule(Base):
    __tablename__ = "business_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    rule_value: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="GENERAL")
    updated_by: Mapped[str] = mapped_column(String(60), default="System")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DashboardSetting(Base):
    __tablename__ = "dashboard_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    setting_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    setting_value: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MLSetting(Base):
    __tablename__ = "ml_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    setting_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    setting_value: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# 4. APPLICATION & USER PREFERENCES
# ─────────────────────────────────────────────────────────────────────────────

class SavedFilter(Base):
    __tablename__ = "saved_filters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_by: Mapped[str] = mapped_column(String(60), nullable=False)
    filter_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    preferences: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), default="EXECUTIVE_SUMMARY")
    created_by: Mapped[str] = mapped_column(String(60), nullable=False)
    content_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MLMetadata(Base):
    __tablename__ = "ml_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    metrics: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    feature_importance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    artifact_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    trained_by: Mapped[str] = mapped_column(String(60), default="System")
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
