"""
FastAPI 애플리케이션 엔트리 포인트
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.core.config import settings
from app.api import chat, visualization, board
from app.database import init_db

# FastAPI 앱 생성
app = FastAPI(
    title="환경 데이터 RAG 챗봇 API",
    description="환경 데이터 분석 및 예측을 위한 RAG 챗봇 API",
    version="1.0.0"
)

# 서버 시작 시 데이터베이스 테이블 자동 생성
@app.on_event("startup")
async def startup_event():
    """서버 시작 시 실행"""
    try:
        print("🔧 데이터베이스 테이블 초기화 중...")
        init_db()
        print("✅ 데이터베이스 테이블 초기화 완료")
    except Exception as e:
        print(f"⚠️ 데이터베이스 초기화 경고: {e}")
        # 테이블이 이미 존재하거나 다른 오류일 수 있으므로 계속 진행

# CORS 설정 (프론트엔드에서 접근 가능하도록)
# ngrok URL은 동적으로 변경되므로 개발 환경에서는 모든 origin 허용
# 프로덕션에서는 특정 origin만 허용하도록 설정
cors_origins = settings.CORS_ORIGINS
if settings.DEBUG:
    # 개발 환경: 모든 origin 허용 (ngrok URL 포함)
    cors_origins = ["*"]
else:
    # 프로덕션: 설정된 origin만 허용
    cors_origins = settings.CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(visualization.router, prefix="/api", tags=["visualization"])
app.include_router(board.router, prefix="/api", tags=["board"])

# 정적 파일 서빙 (프론트엔드)
frontend_path = Path(__file__).parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="static")


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "환경 데이터 RAG 챗봇 API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

