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


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = ScopedSession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
