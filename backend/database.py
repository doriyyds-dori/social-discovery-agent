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
    from backend.models import Keyword, Content, Task, Setting, SyncConfig, SyncLog, Personnel, Assignment, LLMConfig, CommentDraft  # noqa: F401
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
    for col in ("content_value", "comment_value", "recommended_action", "comment_signal", "source_name", "source_label"):
        if col not in content_cols:
            default = "手工录入" if col == "source_name" else ("手工导入" if col == "source_label" else "")
            cursor.execute(f"ALTER TABLE contents ADD COLUMN {col} TEXT DEFAULT '{default}'")
    for col in ("summary", "author", "published_at", "raw_text"):
        if col not in content_cols:
            cursor.execute(f"ALTER TABLE contents ADD COLUMN {col} TEXT DEFAULT ''")

    # ── Fix source label for existing mock records ─────────────────
    cursor.execute(
        "UPDATE contents SET source_name = '模拟数据', source_label = '模拟数据' "
        "WHERE url LIKE '%example.com/mock/%' AND (source_name = '手工录入' OR source_name = '' OR source_name IS NULL)"
    )

    # ── sync_logs table ───────────────────────────────────────────
    cursor.execute("PRAGMA table_info(sync_logs)")
    log_cols = {row[1] for row in cursor.fetchall()}
    if "matched_count" not in log_cols:
        cursor.execute("ALTER TABLE sync_logs ADD COLUMN matched_count INTEGER DEFAULT 0")

    # ── sync_configs table ─────────────────────────────────────────
    cursor.execute("PRAGMA table_info(sync_configs)")
    sc_cols = {row[1] for row in cursor.fetchall()}
    if "source_params" not in sc_cols:
        cursor.execute("ALTER TABLE sync_configs ADD COLUMN source_params TEXT DEFAULT '{}'")

    # ── assignments table ─────────────────────────────────────────
    cursor.execute("PRAGMA table_info(assignments)")
    asn_cols = {row[1] for row in cursor.fetchall()}
    if "draft_pk" not in asn_cols:
        cursor.execute("ALTER TABLE assignments ADD COLUMN draft_pk INTEGER DEFAULT NULL")
    if "draft_id_snapshot" not in asn_cols:
        cursor.execute("ALTER TABLE assignments ADD COLUMN draft_id_snapshot TEXT DEFAULT ''")

    conn.commit()
    conn.close()
