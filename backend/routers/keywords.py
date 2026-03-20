"""
Keywords API router.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Keyword, KeywordCreate, KeywordOut

router = APIRouter(prefix="/keywords", tags=["keywords"])


@router.get("/", response_model=list[KeywordOut])
def list_keywords(db: Session = Depends(get_db)):
    return db.query(Keyword).order_by(Keyword.created_at.desc()).all()


@router.post("/", response_model=KeywordOut)
def create_keyword(data: KeywordCreate, db: Session = Depends(get_db)):
    existing = db.query(Keyword).filter(Keyword.text == data.text).first()
    if existing:
        raise HTTPException(status_code=400, detail="Keyword already exists")
    kw = Keyword(text=data.text, platform=data.platform)
    db.add(kw)
    db.commit()
    db.refresh(kw)
    return kw


@router.delete("/{keyword_id}")
def delete_keyword(keyword_id: int, db: Session = Depends(get_db)):
    kw = db.query(Keyword).get(keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    db.delete(kw)
    db.commit()
    return {"ok": True}
