"""
Assignments (任务分配) API router.

Handles batch assignment of comment tasks to personnel,
listing, filtering, deleting, and exporting assignment records.
"""

import csv
import io
import random
from collections import Counter
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import (
    Assignment, AssignmentOut,
    BatchAssignmentRequest, BatchAssignmentResult, ContentAssignmentDetail,
    Content, Personnel, CommentDraft,
    _beijing_now,
)

router = APIRouter(prefix="/assignments", tags=["assignments"])


# ── Helpers ────────────────────────────────────────────────────────

def _next_assignment_id(db: Session) -> str:
    """Generate next ASN-XXXXXX."""
    last = db.query(Assignment).order_by(Assignment.id.desc()).first()
    seq = 0
    if last and last.assignment_id:
        try:
            seq = int(last.assignment_id.split("-")[1])
        except (IndexError, ValueError):
            pass
    return f"ASN-{seq + 1:06d}"


def _next_batch_number(db: Session) -> str:
    """Generate BATCH-YYYYMMDD-NNN."""
    today = date.today().strftime("%Y%m%d")
    prefix = f"BATCH-{today}-"
    existing = db.query(Assignment).filter(
        Assignment.batch_number.like(f"{prefix}%")
    ).with_entities(Assignment.batch_number).distinct().count()
    return f"{prefix}{existing + 1:03d}"


def _pick_balanced_random(pool_pks: list[int], count: int,
                          batch_counter: Counter) -> list[int]:
    """Pick `count` distinct personnel PKs from `pool_pks`.

    Prefer those with the lowest assignment count in `batch_counter`,
    break ties randomly.
    """
    # Sort by current batch count, then shuffle within same count
    decorated = [(batch_counter.get(pk, 0), random.random(), pk) for pk in pool_pks]
    decorated.sort()  # (count ASC, random)
    return [pk for _, _, pk in decorated[:count]]


# ── List / Filter ─────────────────────────────────────────────────

@router.get("/", response_model=list[AssignmentOut])
def list_assignments(db: Session = Depends(get_db)):
    """列出所有分配记录，按创建时间倒序。"""
    return db.query(Assignment).order_by(Assignment.created_at.desc()).all()


@router.get("/batches", response_model=list[str])
def list_batches(db: Session = Depends(get_db)):
    """返回所有不重复的批次号（用于前端筛选）。"""
    rows = (
        db.query(Assignment.batch_number)
        .distinct()
        .order_by(Assignment.batch_number.desc())
        .all()
    )
    return [r[0] for r in rows]


@router.get("/departments", response_model=list[str])
def list_departments(db: Session = Depends(get_db)):
    """返回分配记录中的不重复部门。"""
    rows = db.query(Assignment.department).distinct().all()
    return sorted([r[0] for r in rows if r[0]])


# ── Batch Assignment ──────────────────────────────────────────────

@router.post("/batch", response_model=BatchAssignmentResult)
def batch_assign(data: BatchAssignmentRequest, db: Session = Depends(get_db)):
    """批量分配评论任务给人员。

    支持两种评论内容来源方式：
    - manual：手动填写统一评论内容（原有逻辑）
    - draft：从评论生成草稿中分配（每人分配不同草稿）
    """
    # ── Input validation ──────────────────────────────────────────
    if not data.targets:
        raise HTTPException(status_code=400, detail="请至少选择一条内容进行分配")
    if data.comment_source_mode == "manual" and not data.comment_text.strip():
        raise HTTPException(status_code=400, detail="手动模式下评论内容不能为空")
    for t in data.targets:
        if t.target_count < 1:
            raise HTTPException(
                status_code=400,
                detail=f"内容 ID {t.content_id} 的目标评论数必须为正整数",
            )

    # Load all personnel
    all_personnel = db.query(Personnel).all()
    if not all_personnel:
        raise HTTPException(status_code=400, detail="人员名单为空，请先添加人员")
    personnel_map = {p.id: p for p in all_personnel}
    all_pks = set(personnel_map.keys())

    batch_number = _next_batch_number(db)
    batch_counter: Counter = Counter()  # pk → count in this batch

    details: list[ContentAssignmentDetail] = []
    total_records = 0

    for t in data.targets:
        content = db.query(Content).get(t.content_id)
        if not content:
            details.append(ContentAssignmentDetail(
                content_id=t.content_id,
                content_title="（未找到）",
                content_url="",
                target_count=t.target_count,
                assigned_count=0,
                result="失败",
                reason=f"未找到内容 ID {t.content_id}",
            ))
            continue

        # Global exclusion: personnel already assigned to this content
        already_assigned_pks = {
            r[0] for r in
            db.query(Assignment.personnel_pk)
            .filter(Assignment.content_id == t.content_id)
            .all()
        }
        available_pks = list(all_pks - already_assigned_pks)

        if t.target_count > len(available_pks):
            details.append(ContentAssignmentDetail(
                content_id=t.content_id,
                content_title=content.title,
                content_url=content.url or "",
                target_count=t.target_count,
                assigned_count=0,
                result="失败",
                reason=(
                    f"当前可用人员数不足（可用 {len(available_pks)} 人，"
                    f"需要 {t.target_count} 人），"
                    f"无法满足「同一内容下人员不重复」的分配规则"
                ),
            ))
            continue

        # ── Draft mode: check draft sufficiency ──────────────
        available_drafts: list | None = None
        if data.comment_source_mode == "draft":
            available_drafts = (
                db.query(CommentDraft)
                .filter(
                    CommentDraft.content_id == t.content_id,
                    CommentDraft.usage_status == "未使用",
                    CommentDraft.status == "生成成功",
                )
                .all()
            )
            if len(available_drafts) < t.target_count:
                details.append(ContentAssignmentDetail(
                    content_id=t.content_id,
                    content_title=content.title,
                    content_url=content.url or "",
                    target_count=t.target_count,
                    assigned_count=0,
                    result="失败",
                    reason=(
                        f"当前内容可用评论草稿不足"
                        f"（可用 {len(available_drafts)} 条，"
                        f"需要 {t.target_count} 条），"
                        f"无法满足本次分配数量"
                    ),
                ))
                continue
            # Shuffle for randomness
            random.shuffle(available_drafts)

        # Pick balanced-random personnel
        chosen_pks = _pick_balanced_random(available_pks, t.target_count, batch_counter)

        assigned_count = 0
        for idx, pk in enumerate(chosen_pks):
            p = personnel_map[pk]
            asn_id = _next_assignment_id(db)

            # Determine comment text and draft reference
            if data.comment_source_mode == "draft" and available_drafts:
                draft = available_drafts[idx]
                comment_text = draft.comment_text
                draft_pk_val = draft.id
                draft_id_snap = draft.draft_id
                # Mark draft as used
                draft.usage_status = "已分配"
                draft.updated_at = _beijing_now()
            else:
                comment_text = data.comment_text.strip()
                draft_pk_val = None
                draft_id_snap = ""

            record = Assignment(
                assignment_id=asn_id,
                batch_number=batch_number,
                content_id=content.id,
                content_title=content.title,
                content_platform=content.platform or "",
                content_source=content.source_name or "",
                personnel_pk=p.id,
                personnel_eid=p.personnel_id,
                department=p.department,
                name=p.name,
                comment_url=content.url or "",
                comment_text=comment_text,
                draft_pk=draft_pk_val,
                draft_id_snapshot=draft_id_snap,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            batch_counter[pk] += 1
            assigned_count += 1
            total_records += 1

        details.append(ContentAssignmentDetail(
            content_id=content.id,
            content_title=content.title,
            content_url=content.url or "",
            target_count=t.target_count,
            assigned_count=assigned_count,
            result="成功",
        ))

    success_count = sum(1 for d in details if d.result == "成功")
    failed_count = sum(1 for d in details if d.result == "失败")

    mode_label = "手动评论" if data.comment_source_mode == "manual" else "草稿分配"
    parts = [
        f"选中 {len(data.targets)} 条内容",
        f"成功 {success_count} 条",
    ]
    if failed_count:
        parts.append(f"失败 {failed_count} 条")
    parts.append(f"生成分配记录 {total_records} 条")
    parts.append(f"批次号 {batch_number}")
    parts.append(f"来源方式：{mode_label}")
    message = "，".join(parts) + "。"

    return BatchAssignmentResult(
        selected_count=len(data.targets),
        success_count=success_count,
        failed_count=failed_count,
        total_records=total_records,
        batch_number=batch_number,
        details=details,
        message=message,
    )


# ── Delete ────────────────────────────────────────────────────────

@router.delete("/{assignment_pk}")
def delete_assignment(assignment_pk: int, db: Session = Depends(get_db)):
    """删除单条分配记录。

    TODO（后续扩展）：
    - 可增加软删除、批量删除、按批次号整批删除等功能。
    """
    item = db.query(Assignment).get(assignment_pk)
    if not item:
        raise HTTPException(status_code=404, detail="未找到该分配记录")
    db.delete(item)
    db.commit()
    return {"ok": True}


# ── Export CSV ────────────────────────────────────────────────────

@router.get("/export-csv")
def export_csv(
    batch_number: str | None = None,
    db: Session = Depends(get_db),
):
    """导出任务分配表为 CSV（UTF-8-SIG 以兼容 Excel 中文显示）。"""
    query = db.query(Assignment).order_by(Assignment.created_at.desc())
    if batch_number:
        query = query.filter(Assignment.batch_number == batch_number)
    records = query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["人员ID", "部门", "姓名", "评论链接", "评论内容"])
    for r in records:
        writer.writerow([
            r.personnel_eid,
            r.department,
            r.name,
            r.comment_url,
            r.comment_text,
        ])

    content = output.getvalue()
    # Use UTF-8-SIG BOM so Excel opens Chinese correctly
    encoded = content.encode("utf-8-sig")

    filename = f"任务分配表_{batch_number or '全部'}.csv"
    encoded_filename = quote(filename)
    return StreamingResponse(
        io.BytesIO(encoded),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": (
                f"attachment; filename=export.csv; "
                f"filename*=UTF-8''{encoded_filename}"
            )
        },
    )
