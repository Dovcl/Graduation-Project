"""
환경 데이터 테이블 초기화 스크립트
기존 데이터를 모두 삭제합니다.

주의: 이 스크립트는 모든 환경 데이터를 삭제합니다!
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.env_data import EnvironmentalData


def clear_all_data():
    """모든 환경 데이터 삭제"""
    db = SessionLocal()
    
    try:
        # 현재 데이터 개수 확인
        count = db.query(EnvironmentalData).count()
        print(f"현재 데이터 개수: {count:,}개")
        
        if count == 0:
            print("삭제할 데이터가 없습니다.")
            return
        
        # 확인
        response = input(f"\n⚠️  정말로 {count:,}개의 데이터를 모두 삭제하시겠습니까? (yes/no): ")
        if response.lower() != 'yes':
            print("취소되었습니다.")
            return
        
        # 모든 데이터 삭제
        print("\n데이터 삭제 중...")
        deleted = db.query(EnvironmentalData).delete()
        db.commit()
        
        print(f"✅ {deleted:,}개의 데이터가 삭제되었습니다.")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    print("="*80)
    print("환경 데이터 초기화 스크립트")
    print("="*80)
    print("\n⚠️  주의: 이 스크립트는 모든 환경 데이터를 삭제합니다!")
    print("="*80)
    
    clear_all_data()

