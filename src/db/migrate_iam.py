from src.db.session import engine, Base
from sqlalchemy import text
import src.db.models

with engine.connect() as conn:
    # 1. Update developers table columns
    cols_dev = [r[1] for r in conn.execute(text("PRAGMA table_info(developers)")).fetchall()]
    print("Developers cols:", cols_dev)
    if "role_id" not in cols_dev:
        conn.execute(text("ALTER TABLE developers ADD COLUMN role_id INTEGER"))
        print("Added role_id")
    if "status" not in cols_dev:
        conn.execute(text("ALTER TABLE developers ADD COLUMN status VARCHAR(20) DEFAULT 'ACTIVE'"))
        print("Added status")
    if "must_change_password" not in cols_dev:
        conn.execute(text("ALTER TABLE developers ADD COLUMN must_change_password BOOLEAN DEFAULT 0"))
        print("Added must_change_password")

    # 2. Check developer_keys table columns
    if "developer_keys" in [r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]:
        cols_keys = [r[1] for r in conn.execute(text("PRAGMA table_info(developer_keys)")).fetchall()]
        print("Developer_keys cols:", cols_keys)
        if "key_version" not in cols_keys:
            conn.execute(text("ALTER TABLE developer_keys ADD COLUMN key_version INTEGER DEFAULT 1"))
        if "description" not in cols_keys:
            conn.execute(text("ALTER TABLE developer_keys ADD COLUMN description VARCHAR(255) DEFAULT ''"))
        if "created_by" not in cols_keys:
            conn.execute(text("ALTER TABLE developer_keys ADD COLUMN created_by VARCHAR(60) DEFAULT 'Owner'"))
        if "last_used_ip" not in cols_keys:
            conn.execute(text("ALTER TABLE developer_keys ADD COLUMN last_used_ip VARCHAR(45)"))
        if "last_used_device" not in cols_keys:
            conn.execute(text("ALTER TABLE developer_keys ADD COLUMN last_used_device VARCHAR(120)"))

    conn.commit()

# Create any tables not yet existing
Base.metadata.create_all(bind=engine)
print("Database schema migration successful!")
