"""
시연용 데이터 복제 스크립트 (SQL 기반 - 빠른 버전)

녹조 변수: 2021~2023년 → 2024~2026년으로 복제
수질 변수: 2023년6월~2024년12월 → 2025년6월~2026년12월로 복제
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트 설정
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

# .env 파일 로드
from dotenv import load_dotenv
env_path = project_root / "backend" / ".env"
load_dotenv(env_path)

from sqlalchemy import text
from app.database import SessionLocal, init_db


def main():
    print("="*60)
    print("시연용 데이터 복제 스크립트")
    print("="*60)

    init_db()
    db = SessionLocal()

    try:
        # 현재 상태 확인
        print("\n[현재 데이터 상태]")
        result = db.execute(text("""
            SELECT
                CASE
                    WHEN data_type IN ('유해남조류 세포수 (cells/㎖)', 'Microcystis', 'Anabaena', 'Oscillatoria', 'Aphanizomenon')
                    THEN '녹조변수'
                    ELSE '수질변수'
                END as category,
                MIN(date) as min_date,
                MAX(date) as max_date,
                COUNT(*) as count
            FROM environmental_data
            GROUP BY category
        """))
        for row in result:
            print(f"  {row.category}: {row.min_date} ~ {row.max_date} ({row.count}개)")

        # ==========================================
        # 녹조 변수 복제: 2021~2023 → 2024~2026
        # ==========================================
        print("\n" + "="*60)
        print("[녹조 변수 복제]")
        print("원본: 2021-01-01 ~ 2023-12-31 → 대상: 2024-01-01 ~ 2026-12-31")
        print("="*60)

        # 기존 복제 데이터 삭제
        print("\n기존 2024년 이후 녹조 데이터 삭제 중...")
        result = db.execute(text("""
            DELETE FROM environmental_data
            WHERE data_type IN ('유해남조류 세포수 (cells/㎖)', 'Microcystis', 'Anabaena', 'Oscillatoria', 'Aphanizomenon')
            AND date >= '2024-01-01'
        """))
        print(f"  삭제: {result.rowcount}개")
        db.commit()

        # SQL로 직접 복제 (3년 추가)
        print("\n녹조 데이터 복제 중 (SQL INSERT SELECT)...")
        result = db.execute(text("""
            INSERT INTO environmental_data
            (location, latitude, longitude, date, datetime, data_type, value, value2, value3, unit, quality_flag, notes)
            SELECT
                location, latitude, longitude,
                date + INTERVAL '3 years',
                datetime + INTERVAL '3 years',
                data_type, value, value2, value3, unit, quality_flag, notes
            FROM environmental_data
            WHERE data_type IN ('유해남조류 세포수 (cells/㎖)', 'Microcystis', 'Anabaena', 'Oscillatoria', 'Aphanizomenon')
            AND date >= '2021-01-01'
            AND date <= '2023-12-31'
        """))
        algae_count = result.rowcount
        print(f"✓ 녹조 변수 복제 완료: {algae_count}개")
        db.commit()

        # ==========================================
        # 수질 변수 복제: 2023.6~2024.12 → 2025.6~2026.12
        # ==========================================
        print("\n" + "="*60)
        print("[수질 변수 복제]")
        print("원본: 2023-06-01 ~ 2024-12-31 → 대상: 2025-06-01 ~ 2026-12-31")
        print("="*60)

        # 기존 복제 데이터 삭제
        print("\n기존 2025년 6월 이후 수질 데이터 삭제 중...")
        result = db.execute(text("""
            DELETE FROM environmental_data
            WHERE data_type NOT IN ('유해남조류 세포수 (cells/㎖)', 'Microcystis', 'Anabaena', 'Oscillatoria', 'Aphanizomenon')
            AND date >= '2025-06-01'
        """))
        print(f"  삭제: {result.rowcount}개")
        db.commit()

        # SQL로 직접 복제 (2년 추가)
        print("\n수질 데이터 복제 중 (SQL INSERT SELECT)...")
        result = db.execute(text("""
            INSERT INTO environmental_data
            (location, latitude, longitude, date, datetime, data_type, value, value2, value3, unit, quality_flag, notes)
            SELECT
                location, latitude, longitude,
                date + INTERVAL '2 years',
                datetime + INTERVAL '2 years',
                data_type, value, value2, value3, unit, quality_flag, notes
            FROM environmental_data
            WHERE data_type NOT IN ('유해남조류 세포수 (cells/㎖)', 'Microcystis', 'Anabaena', 'Oscillatoria', 'Aphanizomenon')
            AND date >= '2023-06-01'
            AND date <= '2024-12-31'
        """))
        wq_count = result.rowcount
        print(f"✓ 수질 변수 복제 완료: {wq_count}개")
        db.commit()

        # ==========================================
        # 최종 상태 확인
        # ==========================================
        print("\n" + "="*60)
        print("[최종 데이터 상태]")
        print("="*60)

        result = db.execute(text("""
            SELECT
                CASE
                    WHEN data_type IN ('유해남조류 세포수 (cells/㎖)', 'Microcystis', 'Anabaena', 'Oscillatoria', 'Aphanizomenon')
                    THEN '녹조변수'
                    ELSE '수질변수'
                END as category,
                MIN(date) as min_date,
                MAX(date) as max_date,
                COUNT(*) as count
            FROM environmental_data
            GROUP BY category
        """))
        for row in result:
            print(f"  {row.category}: {row.min_date} ~ {row.max_date} ({row.count}개)")

        print(f"\n✅ 완료! 총 {algae_count + wq_count}개 레코드 추가")

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()

    finally:
        db.close()


if __name__ == "__main__":
    main()
