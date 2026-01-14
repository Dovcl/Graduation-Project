"""
RAG 검색 서비스 - 벡터 검색을 통한 관련 문서 찾기
"""
from typing import List, Dict, Any
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models.documents import Document
from app.core.config import settings

# 임베딩 생성 모델 (지연 로딩)
_embedding_model = None


def get_embedding_model():
    """임베딩 모델 지연 로딩"""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _embedding_model


class RAGService:
    """RAG 검색 서비스"""
    
    def __init__(self):
        self.embedding_model = None  # 필요할 때 로드
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        텍스트를 벡터 임베딩으로 변환
        
        Args:
            text: 임베딩할 텍스트
        
        Returns:
            벡터 임베딩 (리스트)
        """
        model = get_embedding_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    async def search(
        self, 
        query: str, 
        top_k: int = 5,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """
        쿼리와 관련된 문서 검색
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 수
            db: 데이터베이스 세션 (None이면 자동 생성)
        
        Returns:
            관련 문서 리스트
        """
        # 임베딩 생성
        query_embedding = self._generate_embedding(query)
        
        # DB 세션 관리
        if db is None:
            db_gen = get_db()
            db = next(db_gen)
            should_close = True
        else:
            should_close = False
        
        try:
            # pgvector를 사용한 벡터 검색
            # 주의: pgvector 확장이 설치되어 있어야 함
            # embedding 컬럼이 vector 타입이어야 함
            
            # 방법 1: pgvector 확장 사용 (설치 후)
            # query_vector_str = str(query_embedding).replace('[', '').replace(']', '')
            # results = db.execute(
            #     text("""
            #         SELECT id, title, content, source,
            #                1 - (embedding <=> :query_vector::vector) as similarity
            #         FROM documents
            #         ORDER BY embedding <=> :query_vector::vector
            #         LIMIT :top_k
            #     """),
            #     {
            #         "query_vector": query_vector_str,
            #         "top_k": top_k
            #     }
            # )
            
            # 방법 2: 임시로 키워드 검색 (pgvector 설치 전)
            # 나중에 pgvector 설치 후 위 방법으로 교체
            results = db.query(Document).filter(
                Document.content.contains(query) | 
                Document.title.contains(query)
            ).limit(top_k).all()
            
            # 결과 포맷팅
            documents = []
            for doc in results:
                documents.append({
                    "id": doc.id,
                    "title": doc.title,
                    "content": doc.content[:500],  # 처음 500자만
                    "source": doc.source,
                    "doc_type": doc.doc_type,
                    "similarity": 1.0  # 임시 (벡터 검색 시 실제 유사도)
                })
            
            return documents
        
        finally:
            if should_close:
                db.close()
    
    async def add_document(
        self,
        title: str,
        content: str,
        source: str = None,
        doc_type: str = None,
        db: Session = None
    ) -> Document:
        """
        문서를 데이터베이스에 추가 (임베딩 포함)
        
        Args:
            title: 문서 제목
            content: 문서 내용
            source: 출처
            doc_type: 문서 타입
            db: 데이터베이스 세션
        
        Returns:
            생성된 Document 객체
        """
        # 임베딩 생성
        embedding = self._generate_embedding(content)
        
        # DB 세션 관리
        if db is None:
            db_gen = get_db()
            db = next(db_gen)
            should_close = True
        else:
            should_close = False
        
        try:
            # 문서 생성
            doc = Document(
                title=title,
                content=content,
                source=source,
                doc_type=doc_type,
                embedding=bytes(embedding)  # BYTEA로 저장 (나중에 vector 타입으로 변경)
            )
            
            db.add(doc)
            db.commit()
            db.refresh(doc)
            
            return doc
        
        finally:
            if should_close:
                db.close()

