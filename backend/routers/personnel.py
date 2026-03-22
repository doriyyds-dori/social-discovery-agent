"""
Personnel (人员名单) API router.
"""

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.database import get_db
from backend.models import (
    Personnel, PersonnelCreate, PersonnelUpdate, PersonnelOut,
    _beijing_now,
)

router = APIRouter(prefix="/personnel", tags=["personnel"])


# ── Helpers ────────────────────────────────────────────────────────

def _next_personnel_id(db: Session) -> str:
    """Generate the next unique personnel ID in EMP-XXXX format."""
    last = (
        db.query(Personnel)
        .order_by(Personnel.id.desc())
        .first()
    )
    if last and last.personnel_id:
        try:
            seq = int(last.personnel_id.split("-")[1])
        except (IndexError, ValueError):
            seq = 0
    else:
        seq = 0
    return f"EMP-{seq + 1:04d}"


SUPPORTED_ENCODINGS = ["utf-8-sig", "utf-8", "gbk", "gb18030"]


def _decode_csv_bytes(raw: bytes, forced_encoding: Optional[str] = None) -> str:
    """Try to decode CSV bytes with auto-detection or a forced encoding.

    Returns the decoded string.
    Raises ValueError with a Chinese message on failure.
    """
    if forced_encoding:
        try:
            return raw.decode(forced_encoding)
        except (UnicodeDecodeError, LookupError):
            raise ValueError(f"使用编码 {forced_encoding} 解码失败，请检查文件编码")

    # Auto-detect: try each encoding in order
    for enc in SUPPORTED_ENCODINGS:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue

    raise ValueError(
        "无法自动识别文件编码，请手动选择编码重试（支持：UTF-8、GBK、GB18030）"
    )


# ── Pydantic model for CSV import result ──────────────────────────

class CsvImportResult(BaseModel):
    total: int
    imported: int
    skipped: int
    failed: int
    message: str


# ── Routes ─────────────────────────────────────────────────────────

@router.get("/", response_model=list[PersonnelOut])
def list_personnel(db: Session = Depends(get_db)):
    """列出所有人员，按 updated_at 倒序排列。"""
    return (
        db.query(Personnel)
        .order_by(Personnel.updated_at.desc())
        .all()
    )


@router.get("/departments", response_model=list[str])
def list_departments(db: Session = Depends(get_db)):
    """返回所有不重复的部门名称（用于前端筛选下拉框）。"""
    rows = db.query(Personnel.department).distinct().all()
    return sorted([r[0] for r in rows])


@router.post("/", response_model=PersonnelOut)
def create_personnel(data: PersonnelCreate, db: Session = Depends(get_db)):
    """新增人员，自动生成人员ID。"""
    if not data.department.strip():
        raise HTTPException(status_code=400, detail="部门不能为空")
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="姓名不能为空")

    # Check for duplicate (department + name)
    existing = (
        db.query(Personnel)
        .filter(Personnel.department == data.department.strip(),
                Personnel.name == data.name.strip())
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"该部门下已存在同名人员：{data.department} - {data.name}",
        )

    personnel_id = _next_personnel_id(db)

    # Extra safety: check personnel_id uniqueness (should not normally conflict)
    if db.query(Personnel).filter(Personnel.personnel_id == personnel_id).first():
        raise HTTPException(
            status_code=409,
            detail=f"人员ID冲突（{personnel_id}），请重试或联系管理员",
        )

    item = Personnel(
        personnel_id=personnel_id,
        department=data.department.strip(),
        name=data.name.strip(),
    )
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="数据冲突，可能存在重复的人员ID或部门+姓名组合",
        )
    return item


@router.put("/{person_id}", response_model=PersonnelOut)
def update_personnel(person_id: int, data: PersonnelUpdate, db: Session = Depends(get_db)):
    """编辑人员信息。"""
    item = db.query(Personnel).get(person_id)
    if not item:
        raise HTTPException(status_code=404, detail="未找到该人员记录")

    if not data.department.strip():
        raise HTTPException(status_code=400, detail="部门不能为空")
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="姓名不能为空")

    # Check uniqueness if values changed
    if data.department.strip() != item.department or data.name.strip() != item.name:
        dup = (
            db.query(Personnel)
            .filter(Personnel.department == data.department.strip(),
                    Personnel.name == data.name.strip(),
                    Personnel.id != person_id)
            .first()
        )
        if dup:
            raise HTTPException(
                status_code=409,
                detail=f"该部门下已存在同名人员：{data.department} - {data.name}",
            )

    item.department = data.department.strip()
    item.name = data.name.strip()
    item.updated_at = _beijing_now()

    try:
        db.commit()
        db.refresh(item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="数据冲突，可能存在重复的部门+姓名组合",
        )
    return item


@router.delete("/{person_id}")
def delete_personnel(person_id: int, db: Session = Depends(get_db)):
    """删除人员记录。

    TODO（后续扩展）：
    - 当接入任务分配表后，删除前应检查该人员是否已被任务引用。
    - 若已被引用，可改为软删除（增加 is_deleted / deleted_at 字段），
      或返回提示"该人员已关联任务，无法删除"。
    - 当前版本为简单物理删除，便于早期开发使用。
    """
    item = db.query(Personnel).get(person_id)
    if not item:
        raise HTTPException(status_code=404, detail="未找到该人员记录")
    db.delete(item)
    db.commit()
    return {"ok": True}


# ── CSV Batch Import ──────────────────────────────────────────────

@router.post("/import-csv", response_model=CsvImportResult)
async def import_csv(
    file: UploadFile = File(...),
    encoding: Optional[str] = Query(None, description="手动指定编码，如 utf-8、gbk、gb18030"),
    db: Session = Depends(get_db),
):
    """CSV 批量导入人员名单。

    CSV 必须包含中文表头：部门, 姓名。
    人员ID 由系统自动生成，不从 CSV 读取。
    按 部门+姓名 去重，已存在则跳过。
    """
    raw = await file.read()
    if not raw.strip():
        raise HTTPException(status_code=400, detail="上传的文件为空")

    # Decode
    try:
        text = _decode_csv_bytes(raw, forced_encoding=encoding)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Parse CSV
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    # Strip BOM/whitespace from headers
    headers = [h.strip().strip("\ufeff") for h in headers]

    if "部门" not in headers or "姓名" not in headers:
        raise HTTPException(
            status_code=400,
            detail=f"CSV 缺少必要列。需要：部门, 姓名。当前列头：{', '.join(headers) if headers else '（无）'}",
        )

    # Build existing set for fast lookup
    existing_pairs = {
        (r.department, r.name)
        for r in db.query(Personnel.department, Personnel.name).all()
    }

    total = 0
    imported = 0
    skipped = 0
    failed = 0

    for row in reader:
        dept = (row.get("部门") or "").strip()
        name = (row.get("姓名") or "").strip()

        # Skip empty rows
        if not dept and not name:
            continue

        total += 1

        if not dept or not name:
            failed += 1
            continue

        # Duplicate check
        if (dept, name) in existing_pairs:
            skipped += 1
            continue

        personnel_id = _next_personnel_id(db)
        item = Personnel(
            personnel_id=personnel_id,
            department=dept,
            name=name,
        )
        try:
            db.add(item)
            db.commit()
            db.refresh(item)
            existing_pairs.add((dept, name))
            imported += 1
        except IntegrityError:
            db.rollback()
            skipped += 1

    parts = [f"共 {total} 条记录"]
    if imported:
        parts.append(f"成功导入 {imported} 条")
    if skipped:
        parts.append(f"跳过 {skipped} 条（已存在）")
    if failed:
        parts.append(f"失败 {failed} 条（缺少部门或姓名）")
    if total == 0:
        parts = ["文件中无有效数据行"]
    message = "，".join(parts) + "。"

    return CsvImportResult(
        total=total,
        imported=imported,
        skipped=skipped,
        failed=failed,
        message=message,
    )
