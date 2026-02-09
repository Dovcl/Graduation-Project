"""
게시판 테이블 마이그레이션 스크립트 (기존 테이블에 author_ip 컬럼 추가)
"""
import sys
from pathlib import Path

# backend 디렉토리를 Python 경로에 추가
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.database import engine

def main():
    """기존 테이블에 author_ip 컬럼 추가"""
    print("🔧 게시판 테이블 마이그레이션 시작...")
    
    try:
        with engine.connect() as conn:
            # 트랜잭션 시작
            trans = conn.begin()
            
            try:
                # posts 테이블에 author_ip 컬럼 추가 (없는 경우만)
                print("📝 posts 테이블 확인 중...")
                conn.execute(text("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='posts' AND column_name='author_ip'
                        ) THEN
                            ALTER TABLE posts ADD COLUMN author_ip VARCHAR(45) DEFAULT '127.0.0.1';
                            CREATE INDEX IF NOT EXISTS ix_posts_author_ip ON posts(author_ip);
                            UPDATE posts SET author_ip = '127.0.0.1' WHERE author_ip IS NULL;
                            ALTER TABLE posts ALTER COLUMN author_ip SET NOT NULL;
                            RAISE NOTICE 'author_ip 컬럼 추가 완료';
                        ELSE
                            RAISE NOTICE 'author_ip 컬럼이 이미 존재합니다';
                        END IF;
                    END $$;
                """))
                
                # comments 테이블에 author_ip 컬럼 추가 (없는 경우만)
                print("📝 comments 테이블 확인 중...")
                conn.execute(text("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='comments' AND column_name='author_ip'
                        ) THEN
                            ALTER TABLE comments ADD COLUMN author_ip VARCHAR(45) DEFAULT '127.0.0.1';
                            CREATE INDEX IF NOT EXISTS ix_comments_author_ip ON comments(author_ip);
                            UPDATE comments SET author_ip = '127.0.0.1' WHERE author_ip IS NULL;
                            ALTER TABLE comments ALTER COLUMN author_ip SET NOT NULL;
                            RAISE NOTICE 'author_ip 컬럼 추가 완료';
                        ELSE
                            RAISE NOTICE 'author_ip 컬럼이 이미 존재합니다';
                        END IF;
                    END $$;
                """))
                
                trans.commit()
                print("✅ 마이그레이션 완료!")
                
            except Exception as e:
                trans.rollback()
                raise e
                
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

