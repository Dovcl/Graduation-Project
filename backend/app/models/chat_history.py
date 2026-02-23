"""
대화 기록 모델
"""
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(String(50), primary_key=True)
    title = Column(String(200), nullable=False)
    timestamp = Column(String(50), nullable=False)
    messages = Column(Text, nullable=False)       # JSON 문자열
    visualization_data = Column(Text, nullable=True)  # JSON 문자열
    created_at = Column(DateTime(timezone=True), server_default=func.now())
