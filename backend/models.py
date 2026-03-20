"""
Database models (SQLAlchemy) and API schemas (Pydantic).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from backend.database import Base


# ── SQLAlchemy ORM Models ──────────────────────────────────────────

class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String(255), nullable=False, unique=True)
    platform = Column(String(50), default="general")
    created_at = Column(DateTime, default=datetime.utcnow)


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
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)


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


class SettingCreate(BaseModel):
    key: str
    value: str = ""

class SettingOut(BaseModel):
    id: int
    key: str
    value: str
    class Config:
        from_attributes = True
