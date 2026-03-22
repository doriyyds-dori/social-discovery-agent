"""
Database models (SQLAlchemy) and API schemas (Pydantic).
"""

from datetime import datetime, timezone, timedelta
from typing import Optional


def _beijing_now() -> datetime:
    """Return the current time in Beijing (UTC+8), with no tzinfo, for DB storage."""
    return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)

from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, UniqueConstraint
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
    summary = Column(Text, default="")                    # 摘要
    author = Column(String(255), default="")              # 作者
    published_at = Column(String(50), default="")         # 发布时间（字符串）
    raw_text = Column(Text, default="")                   # 原始文本
    status = Column(String(50), default="new")            # new / reviewed / archived
    content_value = Column(String(10), default="")        # 高 / 中 / 低
    comment_value = Column(String(10), default="")        # 高 / 中 / 低
    recommended_action = Column(String(20), default="")   # 优先跟进 / 仅观察 / 暂不处理
    comment_signal = Column(String(20), default="")       # 评论关键信号
    source_name = Column(String(50), default="手工录入")    # 来源名称
    source_label = Column(String(50), default="手工导入")   # 来源类型
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
    summary: str = ""
    author: str = ""
    published_at: str = ""
    raw_text: str = ""
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
    summary: str = ""
    author: str = ""
    published_at: str = ""
    raw_text: str = ""
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
    source_params = Column(Text, default="{}")          # JSON: source-specific params
    created_at = Column(DateTime, default=_beijing_now)
    updated_at = Column(DateTime, default=_beijing_now)


class SyncConfigCreate(BaseModel):
    name: str
    source: str = ""
    keywords: str = ""
    enabled: bool = True
    sync_mode: str = "手动"
    frequency_desc: str = ""
    source_params: str = "{}"

class SyncConfigOut(BaseModel):
    id: int
    name: str
    source: str
    keywords: str
    enabled: bool
    sync_mode: str
    frequency_desc: str
    source_params: str = "{}"
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


# ── Personnel (人员名单) ──────────────────────────────────────────

class Personnel(Base):
    __tablename__ = "personnel"
    __table_args__ = (
        UniqueConstraint("department", "name", name="uq_personnel_dept_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    personnel_id = Column(String(20), unique=True, nullable=False)  # EMP-0001
    department = Column(String(255), nullable=False)                 # 部门
    name = Column(String(255), nullable=False)                       # 姓名
    created_at = Column(DateTime, default=_beijing_now)
    updated_at = Column(DateTime, default=_beijing_now, onupdate=_beijing_now)


class PersonnelCreate(BaseModel):
    department: str
    name: str


class PersonnelUpdate(BaseModel):
    department: str
    name: str


class PersonnelOut(BaseModel):
    id: int
    personnel_id: str
    department: str
    name: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


# ── Assignment (任务分配) ─────────────────────────────────────────

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(String(30), unique=True, nullable=False)   # ASN-000001
    batch_number = Column(String(30), nullable=False, index=True)     # BATCH-YYYYMMDD-001
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False)
    content_title = Column(String(500), default="")                   # 内容标题快照
    content_platform = Column(String(50), default="")                 # 平台快照
    content_source = Column(String(50), default="")                   # 来源快照
    personnel_pk = Column(Integer, ForeignKey("personnel.id"), nullable=False)
    personnel_eid = Column(String(20), default="")                    # EMP-XXXX 快照
    department = Column(String(255), default="")                      # 部门快照
    name = Column(String(255), default="")                            # 姓名快照
    comment_url = Column(String(2000), default="")                    # 评论链接
    comment_text = Column(Text, default="")                           # 评论内容
    draft_pk = Column(Integer, nullable=True)                         # 关联草稿PK（可空）
    draft_id_snapshot = Column(String(20), default="")                # 草稿ID快照 CMT-XXXXXX
    created_at = Column(DateTime, default=_beijing_now)
    updated_at = Column(DateTime, default=_beijing_now, onupdate=_beijing_now)


# ── Assignment Pydantic Schemas ───────────────────────────────────

class ContentTarget(BaseModel):
    """Per-content target in a batch request."""
    content_id: int
    target_count: int


class BatchAssignmentRequest(BaseModel):
    targets: list[ContentTarget]
    comment_source_mode: str = "manual"  # manual / draft
    comment_text: str = ""


class ContentAssignmentDetail(BaseModel):
    """Per-content result detail."""
    content_id: int
    content_title: str
    content_url: str
    target_count: int
    assigned_count: int
    result: str          # 成功 / 失败
    reason: str = ""


class BatchAssignmentResult(BaseModel):
    selected_count: int
    success_count: int
    failed_count: int
    total_records: int
    batch_number: str
    details: list[ContentAssignmentDetail]
    message: str


class AssignmentOut(BaseModel):
    id: int
    assignment_id: str
    batch_number: str
    content_id: int
    content_title: str
    content_platform: str
    content_source: str
    personnel_pk: int
    personnel_eid: str
    department: str
    name: str
    comment_url: str
    comment_text: str
    draft_pk: int | None = None
    draft_id_snapshot: str = ""
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


# ── LLM Configuration (大模型配置) ────────────────────────────────

# Supported providers
LLM_PROVIDERS = ["OpenAI", "Gemini", "Claude", "千问", "DeepSeek", "豆包", "自定义兼容接口"]
# Protocol / 接入方式
LLM_PROTOCOLS = ["openai_compatible", "native"]
# Default protocol per provider
PROVIDER_DEFAULT_PROTOCOL = {
    "OpenAI": "openai_compatible",
    "Gemini": "openai_compatible",
    "Claude": "native",
    "千问": "openai_compatible",
    "DeepSeek": "openai_compatible",
    "豆包": "openai_compatible",
    "自定义兼容接口": "openai_compatible",
}
# Default base_url per provider (empty = user must fill)
PROVIDER_DEFAULT_BASE_URL = {
    "OpenAI": "",
    "Gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "Claude": "https://api.anthropic.com",
    "千问": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "DeepSeek": "https://api.deepseek.com",
    "豆包": "",
    "自定义兼容接口": "",
}
LLM_PURPOSES = ["评论生成", "备用", "测试"]


class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False)           # 服务商
    model_name = Column(String(100), nullable=False)        # 模型名称
    api_key = Column(String(500), nullable=False)           # API Key（完整存储）
    base_url = Column(String(500), default="")              # Base URL
    protocol = Column(String(30), default="openai_compatible")  # 接入方式
    enabled = Column(Boolean, default=True)                 # 是否启用
    is_default = Column(Boolean, default=False)             # 是否默认用于评论生成
    purpose = Column(String(20), default="评论生成")         # 用途
    notes = Column(Text, default="")                        # 备注
    created_at = Column(DateTime, default=_beijing_now)
    updated_at = Column(DateTime, default=_beijing_now, onupdate=_beijing_now)


def _mask_api_key(key: str) -> str:
    """Mask API key: show first 3 + last 4, mask middle."""
    if not key:
        return ""
    if len(key) <= 7:
        return key[:1] + "****" + key[-1:]
    return key[:3] + "****" + key[-4:]


class LLMConfigCreate(BaseModel):
    provider: str
    model_name: str
    api_key: str
    base_url: str = ""
    protocol: str = "openai_compatible"
    enabled: bool = True
    is_default: bool = False
    purpose: str = "评论生成"
    notes: str = ""


class LLMConfigUpdate(BaseModel):
    provider: str
    model_name: str
    api_key: str = ""        # empty = keep existing
    base_url: str = ""
    protocol: str = "openai_compatible"
    enabled: bool = True
    is_default: bool = False
    purpose: str = "评论生成"
    notes: str = ""


class LLMConfigOut(BaseModel):
    id: int
    provider: str
    model_name: str
    api_key_masked: str      # masked version
    base_url: str
    protocol: str
    enabled: bool
    is_default: bool
    purpose: str
    notes: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


# ── Comment Draft (评论草稿) ──────────────────────────────────────

COMMENT_STYLES = ["真实用户口吻", "理性分析", "轻松交流", "简洁直接"]
COMMENT_TONES = ["中性", "正向", "轻微种草", "提问式"]
COMMENT_LENGTHS = ["简短", "适中", "较长"]
DRAFT_STATUSES = ["生成成功", "生成失败", "待处理"]
USAGE_STATUSES = ["未使用", "已分配", "已废弃"]


class CommentDraft(Base):
    __tablename__ = "comment_drafts"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(String(20), unique=True, index=True)      # CMT-000001
    batch_number = Column(String(30), index=True)                # GEN-YYYYMMDD-001
    content_id = Column(Integer, nullable=False)
    content_title = Column(String(500), default="")              # snapshot
    comment_url = Column(String(1000), default="")               # snapshot
    topic = Column(String(200), default="")                      # 评论主题
    requirements = Column(Text, default="")                      # 生成要求
    comment_text = Column(Text, default="")                      # 评论内容
    style = Column(String(30), default="")                       # 风格
    tone = Column(String(30), default="")                        # 语气
    length_req = Column(String(20), default="")                  # 字数要求
    diversified = Column(Boolean, default=True)                  # 差异化表达
    llm_provider = Column(String(50), default="")                # snapshot
    llm_model = Column(String(100), default="")                  # snapshot
    llm_config_id = Column(Integer, nullable=True)               # FK to llm_configs
    generation_mode = Column(String(20), default="real_llm")     # real_llm / mock
    status = Column(String(20), default="待处理")                # 生成状态
    error_message = Column(Text, default="")                     # 错误信息
    is_edited = Column(Boolean, default=False)                   # 是否已编辑
    edited_at = Column(DateTime, nullable=True)                  # 编辑时间
    usage_status = Column(String(20), default="未使用")          # 未使用/已分配/已废弃
    created_at = Column(DateTime, default=_beijing_now)
    updated_at = Column(DateTime, default=_beijing_now, onupdate=_beijing_now)


# ── Comment Draft Schemas ─────────────────────────────────────────

class CommentGenContentTarget(BaseModel):
    content_id: int
    target_count: int = 3


class CommentGenRequest(BaseModel):
    targets: list[CommentGenContentTarget]
    topic: str = ""
    requirements: str = ""
    style: str = "真实用户口吻"
    tone: str = "中性"
    length_req: str = "适中"
    diversified: bool = True
    use_mock: bool = False          # explicit mock switch


class ContentGenDetail(BaseModel):
    content_id: int
    content_title: str
    content_url: str = ""
    target_count: int
    actual_count: int
    result: str                     # 成功 / 部分成功 / 失败
    reason: str = ""


class CommentGenResult(BaseModel):
    selected_count: int
    success_count: int
    partial_count: int = 0
    failed_count: int
    total_drafts: int
    batch_number: str
    generation_mode: str            # real_llm / mock
    llm_info: str = ""              # e.g. "DeepSeek / deepseek-chat"
    details: list[ContentGenDetail]
    message: str


class CommentDraftOut(BaseModel):
    id: int
    draft_id: str
    batch_number: str
    content_id: int
    content_title: str
    comment_url: str
    topic: str
    requirements: str
    comment_text: str
    style: str
    tone: str
    length_req: str
    diversified: bool
    llm_provider: str
    llm_model: str
    llm_config_id: int | None
    generation_mode: str
    status: str
    error_message: str
    is_edited: bool
    edited_at: datetime | None
    usage_status: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


class CommentDraftUpdate(BaseModel):
    comment_text: str
