"""
PostgreSQL 데이터베이스 연결 설정
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# SQLAlchemy 엔진 생성
# pool_pre_ping: 연결이 끊어졌을 때 자동으로 재연결
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # 연결 상태 확인 후 사용
    echo=settings.DEBUG  # 디버그 모드에서 SQL 쿼리 출력
)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스 (모델들이 상속받을 클래스)
Base = declarative_base()


def get_db():
    """
    데이터베이스 세션 의존성 함수
    FastAPI의 Depends()와 함께 사용
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    데이터베이스 초기화 (테이블 생성)
    """
    Base.metadata.create_all(bind=engine)

