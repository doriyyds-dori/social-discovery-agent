"""
Contents API router.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Content, ContentCreate, ContentOut

router = APIRouter(prefix="/contents", tags=["contents"])


@router.get("/", response_model=list[ContentOut])
def list_contents(db: Session = Depends(get_db)):
    return db.query(Content).order_by(Content.created_at.desc()).all()


@router.post("/", response_model=ContentOut)
def create_content(data: ContentCreate, db: Session = Depends(get_db)):
    item = Content(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{content_id}", response_model=ContentOut)
def update_content(content_id: int, data: ContentCreate, db: Session = Depends(get_db)):
    item = db.query(Content).get(content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{content_id}")
def delete_content(content_id: int, db: Session = Depends(get_db)):
    item = db.query(Content).get(content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    db.delete(item)
    db.commit()
    return {"ok": True}
