"""
모든 수질/녹조 데이터를 데이터베이스에 로드하는 스크립트
- WQ_TOTAL.csv의 모든 지점 데이터 로드
- cyanohab_final.csv의 녹조 데이터 로드
- 수질좌표_2025.csv의 좌표 정보 매칭
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import argparse

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

# .env 파일 로드
from dotenv import load_dotenv
env_path = project_root / "backend" / ".env"
load_dotenv(env_path)

from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import SessionLocal, init_db
from app.models.env_data import EnvironmentalData


def load_csv_with_encoding(file_path: Path) -> Optional[pd.DataFrame]:
    """다양한 인코딩으로 CSV 파일 로드"""
    encodings = ['utf-8', 'cp949', 'euc-kr', 'latin-1']

    for encoding in encodings:
        try:
            df = pd.read_csv(file_path, encoding=encoding, low_memory=False)
            print(f"✓ {file_path.name} 로드 성공 (인코딩: {encoding}, {len(df)}행)")
            return df
        except (UnicodeDecodeError, LookupError):
            continue

    print(f"✗ {file_path.name} 로드 실패")
    return None


def load_coordinates(coords_file: Path) -> Dict[str, Dict[str, float]]:
    """좌표 정보 로드"""
    if not coords_file.exists():
        return {}

    df = load_csv_with_encoding(coords_file)
    if df is None:
        return {}

    coords = {}
    for _, row in df.iterrows():
        location = str(row.get('측정소명', '')).strip()
        lat = row.get('latitude', None)
        lon = row.get('longitude', None)

        if location and pd.notna(lat) and pd.notna(lon):
            coords[location] = {
                'latitude': float(lat),
                'longitude': float(lon)
            }

    print(f"✓ 좌표 정보: {len(coords)}개 위치")
    return coords


def get_existing_records(db: Session) -> set:
    """기존 레코드의 (location, date, data_type) 조합 조회"""
    print("기존 레코드 조회 중...")

    result = db.execute(text("""
        SELECT location || '|' || date || '|' || data_type as key
        FROM environmental_data
    """))

    existing = set(row[0] for row in result)
    print(f"✓ 기존 레코드: {len(existing)}개")
    return existing


def process_wq_total(wq_file: Path, coords: Dict, db: Session, existing: set) -> int:
    """WQ_TOTAL.csv 처리 - 모든 지점 데이터 로드"""
    print("\n" + "="*60)
    print("[WQ_TOTAL.csv 처리]")
    print("="*60)

    df = load_csv_with_encoding(wq_file)
    if df is None:
        return 0

    # 컬럼 매핑
    col_mapping = {
        'Station': 'Station',
        'Date': 'Date',
        'Temp': '수온(℃)',
        'DO': 'DO(㎎/L)',
        'TN': 'TN',
        'TP': 'TP',
    }

    # 실제 컬럼 찾기
    actual_cols = {}
    for target, default in col_mapping.items():
        if target in df.columns:
            actual_cols[target] = target
        elif default in df.columns:
            actual_cols[target] = default

    print(f"매핑된 컬럼: {actual_cols}")

    # 데이터 타입별 단위
    unit_map = {
        '수온(℃)': '℃',
        'DO(㎎/L)': '㎎/L',
        'TN': '㎎/L',
        'TP': '㎎/L',
    }

    # 처리할 수질 변수들
    wq_vars = ['Temp', 'DO', 'TN', 'TP']

    saved_count = 0
    skipped_count = 0
    error_count = 0
    batch = []
    batch_size = 5000

    total_rows = len(df)
    print(f"처리할 행: {total_rows}")

    for idx, row in df.iterrows():
        if idx % 50000 == 0 and idx > 0:
            print(f"  진행: {idx}/{total_rows} ({idx*100/total_rows:.1f}%)")

        # 위치, 날짜 추출
        location = str(row.get(actual_cols.get('Station', 'Station'), '')).strip()
        date_str = row.get(actual_cols.get('Date', 'Date'), '')

        if not location or pd.isna(date_str):
            continue

        # 날짜 파싱
        try:
            date = pd.to_datetime(date_str).date()
        except:
            error_count += 1
            continue

        # 좌표 정보
        coord_info = coords.get(location, {})

        # 각 수질 변수 처리
        for var in wq_vars:
            col_name = actual_cols.get(var)
            if not col_name:
                continue

            value = row.get(col_name)

            # 유효하지 않은 값 스킵
            if pd.isna(value) or value == '' or value == '분석중' or value == '정량한계미만':
                continue

            try:
                value_float = float(value)
                if value_float < 0:
                    continue
            except:
                continue

            # 데이터 타입 결정
            data_type = col_mapping.get(var, var)

            # 중복 체크
            key = f"{location}|{date}|{data_type}"
            if key in existing:
                skipped_count += 1
                continue

            # 새 레코드 추가
            existing.add(key)

            env_data = EnvironmentalData(
                location=location,
                latitude=coord_info.get('latitude'),
                longitude=coord_info.get('longitude'),
                date=date,
                datetime=datetime.combine(date, datetime.min.time()),
                data_type=data_type,
                value=value_float,
                unit=unit_map.get(data_type, ''),
            )

            batch.append(env_data)
            saved_count += 1

            # 배치 저장
            if len(batch) >= batch_size:
                db.bulk_save_objects(batch)
                db.commit()
                batch = []

    # 남은 배치 저장
    if batch:
        db.bulk_save_objects(batch)
        db.commit()

    print(f"\n✓ WQ_TOTAL 저장 완료: {saved_count}개")
    print(f"  건너뜀 (중복): {skipped_count}개")
    print(f"  오류: {error_count}개")

    return saved_count


def process_cyanohab(cyano_file: Path, coords: Dict, db: Session, existing: set) -> int:
    """cyanohab_final.csv 처리 - 녹조 데이터 로드"""
    print("\n" + "="*60)
    print("[cyanohab_final.csv 처리]")
    print("="*60)

    df = load_csv_with_encoding(cyano_file)
    if df is None:
        return 0

    print(f"컬럼: {list(df.columns)}")

    # 녹조 관련 컬럼
    cyano_vars = [
        '유해남조류 세포수 (cells/㎖)',
        'Microcystis',
        'Anabaena',
        'Oscillatoria',
        'Aphanizomenon',
    ]

    # 추가 수질 변수 (cyanohab에만 있는 것들)
    wq_vars = ['수온(℃)', 'DO(㎎/L)', 'pH', 'Chl-a (㎎/㎥)']

    # 단위 매핑
    unit_map = {
        '유해남조류 세포수 (cells/㎖)': 'cells/㎖',
        'Microcystis': 'cells/㎖',
        'Anabaena': 'cells/㎖',
        'Oscillatoria': 'cells/㎖',
        'Aphanizomenon': 'cells/㎖',
        '수온(℃)': '℃',
        'DO(㎎/L)': '㎎/L',
        'pH': '',
        'Chl-a (㎎/㎥)': '㎎/㎥',
    }

    all_vars = cyano_vars + wq_vars

    saved_count = 0
    skipped_count = 0
    batch = []
    batch_size = 5000

    total_rows = len(df)
    print(f"처리할 행: {total_rows}")

    for idx, row in df.iterrows():
        if idx % 5000 == 0 and idx > 0:
            print(f"  진행: {idx}/{total_rows} ({idx*100/total_rows:.1f}%)")

        # 지점명, 채수위치, 조사일 추출
        station = str(row.get('지점명', '')).strip()
        sampling_loc = row.get('채수위치', '')
        date_str = row.get('조사일', '')

        if not station or pd.isna(date_str):
            continue

        # 위치명 생성: "지점명_채수위치" 형식
        if pd.notna(sampling_loc) and str(sampling_loc).strip():
            location = f"{station}_{str(sampling_loc).strip()}"
        else:
            location = station

        # 날짜 파싱
        try:
            date = pd.to_datetime(date_str).date()
        except:
            continue

        # 좌표 정보 (지점명 또는 채수위치로 매칭 시도)
        coord_info = coords.get(station, {})
        if not coord_info and pd.notna(sampling_loc):
            coord_info = coords.get(str(sampling_loc).strip(), {})

        # 각 변수 처리
        for var in all_vars:
            if var not in df.columns:
                continue

            value = row.get(var)

            if pd.isna(value) or value == '':
                continue

            try:
                value_float = float(value)
                if value_float < 0:
                    continue
            except:
                continue

            # 중복 체크
            key = f"{location}|{date}|{var}"
            if key in existing:
                skipped_count += 1
                continue

            existing.add(key)

            env_data = EnvironmentalData(
                location=location,
                latitude=coord_info.get('latitude'),
                longitude=coord_info.get('longitude'),
                date=date,
                datetime=datetime.combine(date, datetime.min.time()),
                data_type=var,
                value=value_float,
                unit=unit_map.get(var, ''),
            )

            batch.append(env_data)
            saved_count += 1

            if len(batch) >= batch_size:
                db.bulk_save_objects(batch)
                db.commit()
                batch = []

    if batch:
        db.bulk_save_objects(batch)
        db.commit()

    print(f"\n✓ cyanohab 저장 완료: {saved_count}개")
    print(f"  건너뜀 (중복): {skipped_count}개")

    return saved_count


def main():
    parser = argparse.ArgumentParser(description='모든 수질/녹조 데이터 로드')
    parser.add_argument(
        '--data-dir',
        type=str,
        default='../졸논. 녹조예측 주단위/Data',
        help='데이터 폴더 경로'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제 저장하지 않고 확인만'
    )

    args = parser.parse_args()

    # 경로 설정
    script_dir = Path(__file__).parent
    data_dir = (script_dir / args.data_dir).resolve()

    if not data_dir.exists():
        print(f"❌ 데이터 폴더 없음: {data_dir}")
        return

    print("="*60)
    print("전체 데이터 로드 스크립트")
    print("="*60)
    print(f"데이터 폴더: {data_dir}")

    # 파일 경로
    wq_file = data_dir / "WQ_TOTAL.csv"
    cyano_file = data_dir / "cyanohab_final.csv"
    coords_file = data_dir / "수질좌표_2025.csv"

    # 파일 존재 확인
    print("\n[파일 확인]")
    for f in [wq_file, cyano_file, coords_file]:
        status = "✓" if f.exists() else "✗"
        print(f"  {status} {f.name}")

    if args.dry_run:
        print("\n[DRY RUN 모드]")
        return

    # DB 초기화
    init_db()
    db = SessionLocal()

    try:
        # 좌표 정보 로드
        coords = load_coordinates(coords_file)

        # 기존 레코드 조회
        existing = get_existing_records(db)

        total_saved = 0

        # WQ_TOTAL.csv 처리
        if wq_file.exists():
            total_saved += process_wq_total(wq_file, coords, db, existing)

        # cyanohab_final.csv 처리
        if cyano_file.exists():
            total_saved += process_cyanohab(cyano_file, coords, db, existing)

        print("\n" + "="*60)
        print(f"✅ 완료! 총 {total_saved}개 레코드 추가")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()

    finally:
        db.close()


if __name__ == "__main__":
    main()
