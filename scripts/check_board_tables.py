"""
게시판 테이블 상태 확인 스크립트
"""
import sys
from pathlib import Path

# backend 디렉토리를 Python 경로에 추가
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text, inspect
from app.database import engine

def main():
    """게시판 테이블 상태 확인"""
    print("🔍 게시판 테이블 상태 확인 중...\n")
    
    try:
        inspector = inspect(engine)
        
        # posts 테이블 확인
        if inspector.has_table("posts"):
            print("✅ posts 테이블 존재")
            columns = inspector.get_columns("posts")
            print("   컬럼 목록:")
            for col in columns:
                nullable = "NULL 가능" if col['nullable'] else "NOT NULL"
                print(f"   - {col['name']}: {col['type']} ({nullable})")
            
            # author_ip 컬럼 확인
            has_author_ip = any(col['name'] == 'author_ip' for col in columns)
            if has_author_ip:
                print("   ✅ author_ip 컬럼 존재")
            else:
                print("   ❌ author_ip 컬럼 없음 - 마이그레이션 필요!")
        else:
            print("❌ posts 테이블 없음 - 테이블 생성 필요!")
        
        print()
        
        # comments 테이블 확인
        if inspector.has_table("comments"):
            print("✅ comments 테이블 존재")
            columns = inspector.get_columns("comments")
            print("   컬럼 목록:")
            for col in columns:
                nullable = "NULL 가능" if col['nullable'] else "NOT NULL"
                print(f"   - {col['name']}: {col['type']} ({nullable})")
            
            # author_ip 컬럼 확인
            has_author_ip = any(col['name'] == 'author_ip' for col in columns)
            if has_author_ip:
                print("   ✅ author_ip 컬럼 존재")
            else:
                print("   ❌ author_ip 컬럼 없음 - 마이그레이션 필요!")
        else:
            print("❌ comments 테이블 없음 - 테이블 생성 필요!")
        
        print("\n💡 해결 방법:")
        print("   1. 테이블이 없으면: python scripts/init_board_tables.py")
        print("   2. 컬럼이 없으면: python scripts/migrate_board_tables.py")
        print("   3. 서버 재시작 후 자동 생성됨")
        
    except Exception as e:
        print(f"❌ 확인 실패: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

