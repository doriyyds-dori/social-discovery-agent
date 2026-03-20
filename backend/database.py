"""
Database setup - SQLite with SQLAlchemy.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Store the database file in the project root
DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATABASE_DIR, exist_ok=True)
DATABASE_URL = f"sqlite:///{os.path.join(DATABASE_DIR, 'discovery.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Yield a database session, auto-close when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables defined by models, then run lightweight migrations."""
    from backend.models import Keyword, Content, Task, Setting  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Add columns that may be missing from earlier schema versions."""
    import sqlite3
    db_path = os.path.join(DATABASE_DIR, "discovery.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # ── tasks table ───────────────────────────────────────────────
    cursor.execute("PRAGMA table_info(tasks)")
    task_cols = {row[1] for row in cursor.fetchall()}
    if "task_number" not in task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN task_number TEXT DEFAULT ''")
    if "completed_at" not in task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN completed_at TEXT DEFAULT ''")

    # ── contents table ────────────────────────────────────────────
    cursor.execute("PRAGMA table_info(contents)")
    content_cols = {row[1] for row in cursor.fetchall()}
    for col in ("content_value", "comment_value", "recommended_action", "comment_signal"):
        if col not in content_cols:
            cursor.execute(f"ALTER TABLE contents ADD COLUMN {col} TEXT DEFAULT ''")

    conn.commit()
    conn.close()
