"""
문서 모델 - RAG용 문서 저장
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import BYTEA
from app.database import Base


class Document(Base):
    """문서 테이블 모델"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False, index=True)
    content = Column(Text, nullable=False)
    source = Column(String(500))  # 출처 (예: "메뉴얼", "가이드라인")
    doc_type = Column(String(100))  # 문서 타입 (예: "manual", "guideline")
    
    # 벡터 임베딩 (pgvector 사용)
    # 주의: pgvector 확장 설치 후에만 사용 가능
    embedding = Column(BYTEA)  # 벡터는 BYTEA로 저장 (나중에 vector 타입으로 변경)
    
    # 메타데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Document(id={self.id}, title='{self.title[:30]}...')>"

