"""
session.py
==========
Database engine configuration and session provider for the Nassau Candy
Logistics Administration System.

Designed for modularity:
- Defaults to SQLite for local application metadata.
- Can seamlessly switch to PostgreSQL by setting DATABASE_URL in environment.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, scoped_session, sessionmaker

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_DIR = ROOT / "data" / "admin"
DEFAULT_DB_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_SQLITE_PATH = DEFAULT_DB_DIR / "logistics_platform.db"

# Resolve database URL
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")

# Set appropriate engine arguments based on DB dialect
engine_kwargs = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL connection pool tuning
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **engine_kwargs)

# Thread-safe scoped session factory
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ScopedSession = scoped_session(session_factory)


class Base(DeclarativeBase):
    """Declarative base class for all metadata models."""
    pass


_DB_BOOTSTRAPPED = False
_DB_BOOTSTRAPPING = False


def ensure_db_ready() -> None:
    """
    Ensure database schema tables and core metadata seed records exist.
    Called automatically on first database access or dashboard startup to support
    zero-config cloud hosting (Streamlit Community Cloud, Render, Docker, etc.).
    """
    global _DB_BOOTSTRAPPED, _DB_BOOTSTRAPPING
    if _DB_BOOTSTRAPPED or _DB_BOOTSTRAPPING:
        return

    _DB_BOOTSTRAPPING = True
    try:
        from src.db.init_db import init_database
        from src.developer.dev_security import ensure_root_owner_and_system_security

        init_database()
        ensure_root_owner_and_system_security()
        _DB_BOOTSTRAPPED = True
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Automatic database bootstrap check: %s", e)
    finally:
        _DB_BOOTSTRAPPING = False


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    if not _DB_BOOTSTRAPPED and not _DB_BOOTSTRAPPING:
        ensure_db_ready()
    session = ScopedSession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

