"""
Sync config API router.
"""

from datetime import datetime, timezone, timedelta


def _beijing_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import SyncConfig, SyncConfigCreate, SyncConfigOut, Content, SyncLog, SyncLogOut
from backend.sources.mock_source import MockContentSource

router = APIRouter(prefix="/sync-configs", tags=["sync-configs"])


@router.get("/", response_model=list[SyncConfigOut])
def list_sync_configs(db: Session = Depends(get_db)):
    return db.query(SyncConfig).order_by(SyncConfig.created_at.desc()).all()


@router.post("/", response_model=SyncConfigOut)
def create_sync_config(data: SyncConfigCreate, db: Session = Depends(get_db)):
    item = SyncConfig(
        **data.model_dump(),
        current_status="未执行",
        last_run_at="",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{config_id}", response_model=SyncConfigOut)
def update_sync_config(config_id: int, data: SyncConfigCreate, db: Session = Depends(get_db)):
    """Update user-editable fields only. current_status and last_run_at are system-maintained."""
    item = db.query(SyncConfig).get(config_id)
    if not item:
        raise HTTPException(status_code=404, detail="Sync config not found")
    item.name = data.name
    item.source = data.source
    item.keywords = data.keywords
    item.enabled = data.enabled
    item.sync_mode = data.sync_mode
    item.frequency_desc = data.frequency_desc
    item.source_params = data.source_params
    item.updated_at = _beijing_now()
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{config_id}/toggle", response_model=SyncConfigOut)
def toggle_sync_config(config_id: int, db: Session = Depends(get_db)):
    """Toggle the enabled flag for a sync config."""
    item = db.query(SyncConfig).get(config_id)
    if not item:
        raise HTTPException(status_code=404, detail="Sync config not found")
    item.enabled = not item.enabled
    item.updated_at = _beijing_now()
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{config_id}")
def delete_sync_config(config_id: int, db: Session = Depends(get_db)):
    item = db.query(SyncConfig).get(config_id)
    if not item:
        raise HTTPException(status_code=404, detail="Sync config not found")
    db.delete(item)
    db.commit()
    return {"ok": True}


# ── Supported sources ───────────────────────────────────────────────────────
_MOCK_SOURCE_NAMES = {"模拟数据", "mock", "模拟", "MockContentSource"}
_DOUYIN_SOURCE_NAMES = {"抖音关键词搜索"}


def _run_mock_import(db: Session, keywords_raw: str = "") -> dict:
    """Run the mock content import with optional keyword filtering, return result dict."""
    source = MockContentSource()
    records = source.fetch()

    # ── 记录原始抓取总数 ────────────────────────────────────────────
    original_total = len(records)

    # ── 解析关键词（逗号分隔，去除空格） ───────────────────────────
    keywords = [kw.strip() for kw in keywords_raw.split(",") if kw.strip()]

    # ── 关键词过滤 ──────────────────────────────────────────────────
    if keywords:
        filtered = []
        for r in records:
            haystack = " ".join([
                r.title or "",
                r.summary or "",
                r.raw_text or "",
            ]).lower()
            if any(kw.lower() in haystack for kw in keywords):
                filtered.append(r)
        records = filtered

    matched_count = len(records)
    imported = 0
    skipped = 0

    for record in records:
        existing = db.query(Content).filter(Content.url == record.url).first()
        if existing:
            skipped += 1
            continue

        content = Content(
            title=record.title,
            url=record.url,
            platform=record.platform,
            summary=record.summary,
            author=record.author,
            published_at=record.published_at,
            raw_text=record.raw_text,
            status="new",
            source_name="模拟数据",
            source_label="模拟数据",
        )
        db.add(content)
        imported += 1

    db.commit()

    # ── 组装中文结果消息 ────────────────────────────────────────────
    if keywords:
        kw_label = "、".join(keywords)
        if matched_count == 0:
            msg = (
                f"导入完成：共抓取 {original_total} 条，"
                f"按关键词「{kw_label}」过滤后无匹配记录，未导入任何内容。"
            )
        else:
            msg = (
                f"导入完成：共抓取 {original_total} 条，"
                f"按关键词「{kw_label}」过滤后剩余 {matched_count} 条，"
                f"成功导入 {imported} 条，跳过 {skipped} 条（重复 URL）。"
            )
    else:
        msg = (
            f"导入完成：共抓取 {original_total} 条，"
            f"成功导入 {imported} 条，跳过 {skipped} 条（重复 URL）。"
        )

    return {
        "total": original_total,
        "matched_count": matched_count,
        "imported": imported,
        "skipped": skipped,
        "message": msg,
    }


@router.post("/{config_id}/execute")
def execute_sync_config(config_id: int, db: Session = Depends(get_db)):
    """手动触发同步配置的导入流程，更新状态、执行时间，并写入执行日志。"""
    item = db.query(SyncConfig).get(config_id)
    if not item:
        raise HTTPException(status_code=404, detail="Sync config not found")

    executed_at = _beijing_now().strftime("%Y-%m-%d %H:%M")

    # Mark as running
    item.current_status = "执行中"
    item.updated_at = _beijing_now()
    db.commit()

    try:
        source_name = (item.source or "").strip()
        if source_name in _MOCK_SOURCE_NAMES:
            result = _run_mock_import(db, keywords_raw=item.keywords or "")
            log_result = "成功"
        elif source_name in _DOUYIN_SOURCE_NAMES:
            result = {
                "total": 0,
                "matched_count": 0,
                "imported": 0,
                "skipped": 0,
                "message": "当前来源「抖音关键词搜索」暂未接入真实执行逻辑，请后续配置抖音关键词搜索接口。",
            }
            log_result = "待接入"
        else:
            result = {
                "total": 0,
                "matched_count": 0,
                "imported": 0,
                "skipped": 0,
                "message": f"来源「{source_name}」暂不支持自动执行，请检查来源名称或等待后续接入。",
            }
            log_result = "失败"

        # Update config status
        item.current_status = "空闲"
        item.last_run_at = executed_at
        item.updated_at = _beijing_now()
        db.commit()

        # Write execution log
        log = SyncLog(
            sync_config_id=config_id,
            config_name=item.name,
            source=item.source or "",
            executed_at=executed_at,
            result=log_result,
            total=result["total"],
            matched_count=result.get("matched_count", result["total"]),
            imported=result["imported"],
            skipped=result["skipped"],
            message=result["message"],
        )
        db.add(log)
        db.commit()

        return {"ok": True, "status": "空闲", **result}

    except Exception as exc:
        item.current_status = "执行失败"
        item.updated_at = _beijing_now()
        db.commit()

        # Write failure log
        log = SyncLog(
            sync_config_id=config_id,
            config_name=item.name,
            source=item.source or "",
            executed_at=executed_at,
            result="失败",
            total=0,
            matched_count=0,
            imported=0,
            skipped=0,
            message=str(exc),
        )
        db.add(log)
        db.commit()

        raise HTTPException(status_code=500, detail=f"执行失败：{exc}") from exc


@router.get("/logs", response_model=list[SyncLogOut])
def list_sync_logs(db: Session = Depends(get_db)):
    """返回所有同步执行日志，最新的在前。"""
    return db.query(SyncLog).order_by(SyncLog.created_at.desc()).all()
