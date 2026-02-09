"""
게시판 테이블 초기화 스크립트
"""
import sys
from pathlib import Path

# backend 디렉토리를 Python 경로에 추가
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database import init_db, engine
from app.models.board import Post, Comment, Base

def main():
    """게시판 테이블 생성"""
    print("🔧 게시판 테이블 초기화 시작...")
    
    try:
        # 테이블 생성
        Base.metadata.create_all(bind=engine, tables=[Post.__table__, Comment.__table__])
        print("✅ 게시판 테이블 생성 완료!")
        print("   - posts 테이블")
        print("   - comments 테이블")
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

