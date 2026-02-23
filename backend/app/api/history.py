"""
대화 기록 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.database import get_db
from app.models.chat_history import ChatHistory

router = APIRouter()


class HistoryItemCreate(BaseModel):
    id: str
    title: str
    timestamp: str
    messages: str
    visualization_data: Optional[str] = None


class HistoryItemUpdate(BaseModel):
    messages: str
    visualization_data: Optional[str] = None


class HistoryItemResponse(BaseModel):
    id: str
    title: str
    timestamp: str
    messages: str
    visualization_data: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/history", response_model=List[HistoryItemResponse])
def get_history(db: Session = Depends(get_db)):
    return db.query(ChatHistory).order_by(ChatHistory.created_at.desc()).all()


@router.post("/history", response_model=HistoryItemResponse)
def create_history(item: HistoryItemCreate, db: Session = Depends(get_db)):
    db_item = ChatHistory(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.put("/history/{item_id}", response_model=HistoryItemResponse)
def update_history(item_id: str, item: HistoryItemUpdate, db: Session = Depends(get_db)):
    db_item = db.query(ChatHistory).filter(ChatHistory.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Not found")
    db_item.messages = item.messages
    db_item.visualization_data = item.visualization_data
    db.commit()
    db.refresh(db_item)
    return db_item


@router.delete("/history/{item_id}")
def delete_history(item_id: str, db: Session = Depends(get_db)):
    db_item = db.query(ChatHistory).filter(ChatHistory.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(db_item)
    db.commit()
    return {"ok": True}
