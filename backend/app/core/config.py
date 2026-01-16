"""
환경 변수 설정 관리
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Union


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # 데이터베이스 (실제 비밀번호는 .env 파일에서 설정)
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5433/rag_chatbot_db"
    
    # LLM API 키
    GROQ_API_KEY: str = ""  # 선택적 (사용 안 함)
    OPENAI_API_KEY: str = ""  # 필수 (GPT-5 Mini 사용)
    
    # 서버 설정
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    # CORS 설정 (쉼표로 구분된 문자열도 지원)
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000,http://localhost:8080,http://127.0.0.1:8080"
    
    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """CORS_ORIGINS를 리스트로 변환"""
        if isinstance(v, str):
            # 쉼표로 구분된 문자열을 리스트로 변환
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    # 임베딩 모델 설정
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# 전역 설정 인스턴스
settings = Settings()

