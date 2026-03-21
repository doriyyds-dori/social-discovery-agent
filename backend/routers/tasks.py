"""
Tasks API router.
"""

from datetime import date, datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Task, TaskCreate, TaskOut, Content, BatchTaskCreate, BatchTaskResult

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Platform name → code mapping (Chinese platform names used in Content.platform)
PLATFORM_CODE = {
    "小红书": "XHS",
    "抖音": "DY",
    "视频号": "SPH",
    "微博": "WB",
    "其他": "OT",
}


def _generate_task_number(db: Session, content_id: int | None) -> str:
    """Generate a task number in format RW-平台码-YYYYMMDD-序号."""
    platform_code = "OT"
    if content_id:
        content = db.query(Content).get(content_id)
        if content and content.platform:
            platform_code = PLATFORM_CODE.get(content.platform, "OT")

    today = date.today().strftime("%Y%m%d")
    prefix = f"RW-{platform_code}-{today}-"

    existing = db.query(Task).filter(Task.task_number.like(f"{prefix}%")).count()
    seq = existing + 1

    return f"{prefix}{seq:03d}"


def _task_to_out(task: Task, db: Session) -> dict:
    """Convert a Task ORM instance to a dict compatible with TaskOut."""
    data = {
        "id": task.id,
        "task_number": task.task_number or "",
        "content_id": task.content_id,
        "title": task.title,
        "assignee": task.assignee,
        "due_date": task.due_date,
        "description": task.description,
        "status": task.status,
        "completed_at": task.completed_at or "",
        "created_at": task.created_at,
        "content_title": None,
    }
    if task.content_id:
        content = db.query(Content).get(task.content_id)
        if content:
            data["content_title"] = content.title
    return data


@router.get("/", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
    return [_task_to_out(t, db) for t in tasks]


@router.post("/", response_model=TaskOut)
def create_task(data: TaskCreate, db: Session = Depends(get_db)):
    task_number = _generate_task_number(db, data.content_id)
    item = Task(**data.model_dump(), task_number=task_number)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _task_to_out(item, db)


@router.put("/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskCreate, db: Session = Depends(get_db)):
    item = db.query(Task).get(task_id)
    if not item:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    # Auto-set completed_at when status changes to 已完成
    if data.status == "已完成" and not item.completed_at:
        item.completed_at = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    db.commit()
    db.refresh(item)
    return _task_to_out(item, db)


@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    item = db.query(Task).get(task_id)
    if not item:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/batch", response_model=BatchTaskResult)
def batch_create_tasks(data: BatchTaskCreate, db: Session = Depends(get_db)):
    """Batch-create one task per content ID; skip content IDs that already have a task."""
    selected = len(data.content_ids)
    created_nums: list[str] = []
    skipped = 0

    # Build a set of content_ids that already have at least one task
    existing_content_ids = {
        row.content_id
        for row in db.query(Task.content_id).filter(
            Task.content_id.in_(data.content_ids)
        ).all()
        if row.content_id is not None
    }

    for cid in data.content_ids:
        if cid in existing_content_ids:
            skipped += 1
            continue

        content = db.query(Content).get(cid)
        if not content:
            skipped += 1
            continue

        task_title = f"[{content.title}] {data.description[:30]}" if data.description else f"[{content.title}] 新任务"
        task_number = _generate_task_number(db, cid)
        task = Task(
            content_id=cid,
            title=task_title,
            assignee=data.assignee,
            due_date=data.due_date,
            description=data.description,
            status="待处理",
            task_number=task_number,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        created_nums.append(task_number)

    created = len(created_nums)
    parts = [f"选中 {selected} 条", f"成功创建 {created} 条"]
    if skipped:
        parts.append(f"跳过 {skipped} 条（已有任务）")
    message = "，".join(parts) + "。"

    return BatchTaskResult(
        selected=selected,
        created=created,
        skipped=skipped,
        message=message,
        task_numbers=created_nums,
    )
