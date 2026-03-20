"""
Settings API router.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Setting, SettingCreate, SettingOut

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", response_model=list[SettingOut])
def list_settings(db: Session = Depends(get_db)):
    return db.query(Setting).all()


@router.post("/", response_model=SettingOut)
def upsert_setting(data: SettingCreate, db: Session = Depends(get_db)):
    """Create or update a setting by key."""
    existing = db.query(Setting).filter(Setting.key == data.key).first()
    if existing:
        existing.value = data.value
        db.commit()
        db.refresh(existing)
        return existing
    item = Setting(key=data.key, value=data.value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{setting_id}")
def delete_setting(setting_id: int, db: Session = Depends(get_db)):
    item = db.query(Setting).get(setting_id)
    if not item:
        raise HTTPException(status_code=404, detail="Setting not found")
    db.delete(item)
    db.commit()
    return {"ok": True}
