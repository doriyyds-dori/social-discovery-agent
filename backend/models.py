"""
Database models (SQLAlchemy) and API schemas (Pydantic).
"""

from datetime import datetime, timezone, timedelta
from typing import Optional


def _beijing_now() -> datetime:
    """Return the current time in Beijing (UTC+8), with no tzinfo, for DB storage."""
    return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)

from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from backend.database import Base


# ── SQLAlchemy ORM Models ──────────────────────────────────────────

class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String(255), nullable=False, unique=True)
    platform = Column(String(50), default="general")
    created_at = Column(DateTime, default=_beijing_now)


class Content(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    url = Column(String(2000), default="")
    platform = Column(String(50), default="")
    status = Column(String(50), default="new")  # new / reviewed / archived
    content_value = Column(String(10), default="")    # 高 / 中 / 低
    comment_value = Column(String(10), default="")    # 高 / 中 / 低
    recommended_action = Column(String(20), default="")  # 优先跟进 / 仅观察 / 暂不处理
    comment_signal = Column(String(20), default="")      # 评论关键信号
    source_name = Column(String(50), default="手工录入")   # 来源名称
    source_label = Column(String(50), default="手工导入")  # 来源类型
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=_beijing_now)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_number = Column(String(30), default="")
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=True)
    title = Column(String(500), nullable=False)
    assignee = Column(String(255), default="")
    due_date = Column(String(20), default="")
    description = Column(Text, default="")
    status = Column(String(50), default="待处理")  # 待处理 / 处理中 / 已完成 / 已跳过
    completed_at = Column(String(30), default="")
    created_at = Column(DateTime, default=_beijing_now)


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), nullable=False, unique=True)
    value = Column(Text, default="")


# ── Pydantic Schemas ───────────────────────────────────────────────

class KeywordCreate(BaseModel):
    text: str
    platform: str = "general"

class KeywordOut(BaseModel):
    id: int
    text: str
    platform: str
    created_at: datetime
    class Config:
        from_attributes = True


class ContentCreate(BaseModel):
    title: str
    url: str = ""
    platform: str = ""
    status: str = "new"
    content_value: str = ""
    comment_value: str = ""
    recommended_action: str = ""
    comment_signal: str = ""
    source_name: str = "手工录入"
    source_label: str = "手工导入"
    notes: str = ""

class ContentOut(BaseModel):
    id: int
    title: str
    url: str
    platform: str
    status: str
    content_value: str
    comment_value: str
    recommended_action: str
    comment_signal: str
    source_name: str
    source_label: str
    notes: str
    created_at: datetime
    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    content_id: Optional[int] = None
    title: str
    assignee: str = ""
    due_date: str = ""
    description: str = ""
    status: str = "待处理"

class TaskOut(BaseModel):
    id: int
    task_number: str = ""
    content_id: Optional[int] = None
    content_title: Optional[str] = None
    title: str
    assignee: str
    due_date: str
    description: str
    status: str
    completed_at: str = ""
    created_at: datetime
    class Config:
        from_attributes = True


class BatchTaskCreate(BaseModel):
    content_ids: list[int]
    assignee: str = ""
    due_date: str = ""
    description: str = ""

class BatchTaskResult(BaseModel):
    selected: int
    created: int
    skipped: int
    message: str
    task_numbers: list[str]


class SettingCreate(BaseModel):
    key: str
    value: str = ""

class SettingOut(BaseModel):
    id: int
    key: str
    value: str
    class Config:
        from_attributes = True


# ── Sync Config ────────────────────────────────────────────────────

class SyncConfig(Base):
    __tablename__ = "sync_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    source = Column(String(255), default="")
    keywords = Column(Text, default="")          # comma-separated plain text
    enabled = Column(Boolean, default=True)
    sync_mode = Column(String(20), default="手动")  # 手动 / 定时
    frequency_desc = Column(Text, default="")     # free text
    last_run_at = Column(String(30), default="")  # system-written
    current_status = Column(String(20), default="未执行")  # system-maintained enum
    created_at = Column(DateTime, default=_beijing_now)
    updated_at = Column(DateTime, default=_beijing_now)


class SyncConfigCreate(BaseModel):
    name: str
    source: str = ""
    keywords: str = ""
    enabled: bool = True
    sync_mode: str = "手动"
    frequency_desc: str = ""

class SyncConfigOut(BaseModel):
    id: int
    name: str
    source: str
    keywords: str
    enabled: bool
    sync_mode: str
    frequency_desc: str
    last_run_at: str
    current_status: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


# ── Sync Execution Log ────────────────────────────────────────────

class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    sync_config_id = Column(Integer, nullable=True)   # kept even if config deleted
    config_name = Column(String(255), default="")      # snapshot of 任务名称
    source = Column(String(255), default="")           # snapshot of 来源
    executed_at = Column(String(30), default="")       # Beijing time string
    result = Column(String(10), default="")            # 成功 / 失败
    total = Column(Integer, default=0)
    matched_count = Column(Integer, default=0)    # 关键词过滤后剩余数量
    imported = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    message = Column(Text, default="")
    created_at = Column(DateTime, default=_beijing_now)


class SyncLogOut(BaseModel):
    id: int
    sync_config_id: Optional[int]
    config_name: str
    source: str
    executed_at: str
    result: str
    total: int
    matched_count: int = 0
    imported: int
    skipped: int
    message: str
    created_at: datetime
    class Config:
        from_attributes = True
