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
    PORT: int = 8000  # Render.com 등에서는 $PORT 환경 변수 사용 (uvicorn --port $PORT로 직접 사용)
    DEBUG: bool = True
    
    # CORS 설정 (쉼표로 구분된 문자열도 지원)
    # ngrok URL은 동적으로 허용되므로 여기에 명시하지 않아도 됨
    # 하지만 개발 편의를 위해 ngrok 도메인 패턴 허용
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
    
    # 데이터 파일 경로 설정
    STATIONS_CSV_PATH: str = ""  # 빈 문자열이면 기본 경로 사용
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# 전역 설정 인스턴스
settings = Settings()

