"""
Sources API router — endpoints for content source operations.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Content
from backend.sources.mock_source import MockContentSource

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceRecordOut(BaseModel):
    """API response schema for a single source record."""
    platform: str
    title: str
    url: str
    summary: str
    author: str
    published_at: str
    raw_text: str
    source_type: str


class ImportResultOut(BaseModel):
    """API response schema for an import operation."""
    total: int
    imported: int
    skipped: int
    message: str


@router.get("/mock", response_model=list[SourceRecordOut], summary="获取模拟数据来源的示例记录")
def get_mock_records():
    """
    返回模拟内容来源的示例记录（3 条），用于测试内容来源接入架构。
    """
    source = MockContentSource()
    records = source.fetch()
    return [record.__dict__ for record in records]


@router.post("/mock/import", response_model=ImportResultOut, summary="将模拟来源记录导入内容库")
def import_mock_records(db: Session = Depends(get_db)):
    """
    将模拟内容来源的记录导入现有内容库（contents 表）。
    - 按 URL 去重：相同 URL 已存在则跳过
    - 返回导入汇总：成功导入数量、跳过数量、总数量
    """
    source = MockContentSource()
    records = source.fetch()

    imported = 0
    skipped = 0

    for record in records:
        # De-duplicate by URL
        existing = db.query(Content).filter(Content.url == record.url).first()
        if existing:
            skipped += 1
            continue

        # Map SourceRecord → Content
        # summary + author + published_at + raw_text go into notes for now
        notes_parts = []
        if record.summary:
            notes_parts.append(f"摘要：{record.summary}")
        if record.author:
            notes_parts.append(f"作者：{record.author}")
        if record.published_at:
            notes_parts.append(f"发布时间：{record.published_at}")
        if record.raw_text:
            notes_parts.append(f"原文：{record.raw_text[:200]}")

        content = Content(
            title=record.title,
            url=record.url,
            platform=record.platform,
            status="new",
            source_name="模拟数据",
            source_label="模拟数据",
            notes="\n".join(notes_parts),
        )
        db.add(content)
        imported += 1

    db.commit()

    return ImportResultOut(
        total=len(records),
        imported=imported,
        skipped=skipped,
        message=f"导入完成：成功 {imported} 条，跳过 {skipped} 条（重复 URL），共 {len(records)} 条。",
    )


@router.get("/", summary="列出所有已注册的内容来源")
def list_sources():
    """
    返回当前已注册的内容来源列表及其元信息。
    """
    return [
        {"name": "模拟数据", "source_type": "mock", "status": "active", "endpoint": "/sources/mock"},
        {"name": "抖音关键词搜索", "source_type": "douyin_keyword", "status": "planned", "endpoint": None},
        {"name": "手工导入", "source_type": "manual", "status": "planned", "endpoint": None},
        {"name": "授权来源", "source_type": "authorized", "status": "planned", "endpoint": None},
        {"name": "第三方监测", "source_type": "third_party", "status": "planned", "endpoint": None},
    ]
