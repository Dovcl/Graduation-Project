"""
졸논 폴더의 학습 데이터를 데이터베이스에 로드하는 스크립트

사용법:
    python scripts/load_training_data.py --data-dir "졸논. 녹조예측 주단위/Data"
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models.env_data import EnvironmentalData


def load_csv_with_encoding(file_path: Path) -> Optional[pd.DataFrame]:
    """다양한 인코딩으로 CSV 파일 로드 시도"""
    encodings = ['utf-8', 'cp949', 'euc-kr', 'latin-1']
    
    for encoding in encodings:
        try:
            df = pd.read_csv(file_path, encoding=encoding, low_memory=False)
            print(f"✓ {file_path.name} 로드 성공 (인코딩: {encoding})")
            return df
        except (UnicodeDecodeError, LookupError):
            continue
    
    print(f"✗ {file_path.name} 로드 실패 (모든 인코딩 시도 실패)")
    return None


def process_cyanohab_data(df: pd.DataFrame) -> pd.DataFrame:
    """녹조 데이터 처리"""
    print("\n[녹조 데이터 처리]")
    
    # 컬럼명 확인 및 정리
    print(f"컬럼 수: {len(df.columns)}")
    print(f"행 수: {len(df)}")
    
    # 필요한 컬럼 확인
    required_cols = {
        '지점명': ['지점명', '지점', 'Station', '측정소명'],
        '조사일': ['조사일', 'Date', '날짜', 'date'],
        '유해남조류 세포수 (cells/㎖)': ['유해남조류 세포수 (cells/㎖)', '유해남조류', 'Cyanobacteria'],
        'Microcystis': ['Microcystis'],
        'Anabaena': ['Anabaena'],
        'Oscillatoria': ['Oscillatoria'],
        'Aphanizomenon': ['Aphanizomenon'],
    }
    
    # 컬럼 매핑 찾기
    col_mapping = {}
    for target_col, possible_names in required_cols.items():
        for col in df.columns:
            if any(name in str(col) for name in possible_names):
                col_mapping[target_col] = col
                break
    
    print(f"매핑된 컬럼: {col_mapping}")
    
    # 데이터 정리
    result = []
    for idx, row in df.iterrows():
        location = row.get(col_mapping.get('지점명', ''), '')
        date_str = row.get(col_mapping.get('조사일', ''), '')
        
        if pd.isna(location) or pd.isna(date_str):
            continue
        
        # 날짜 파싱
        try:
            date = pd.to_datetime(date_str).date()
        except:
            continue
        
        # 위치명 처리: 지점명 + 채수위치 조합
        # 모델이 학습한 형식: "강정고령보_다사"
        sampling_location_col = None
        for col in df.columns:
            if '채수위치' in str(col) or '위치' in str(col):
                sampling_location_col = col
                break
        
        sampling_location = row.get(sampling_location_col, '') if sampling_location_col else ''
        if pd.notna(sampling_location) and str(sampling_location).strip():
            # 채수위치가 있으면 "지점명_채수위치" 형식으로 저장
            full_location = f"{str(location).strip()}_{str(sampling_location).strip()}"
        else:
            full_location = str(location).strip()
        
        # 녹조 변수들 추출
        cyano_vars = {
            '유해남조류 세포수 (cells/㎖)': row.get(col_mapping.get('유해남조류 세포수 (cells/㎖)', ''), None),
            'Microcystis': row.get(col_mapping.get('Microcystis', ''), None),
            'Anabaena': row.get(col_mapping.get('Anabaena', ''), None),
            'Oscillatoria': row.get(col_mapping.get('Oscillatoria', ''), None),
            'Aphanizomenon': row.get(col_mapping.get('Aphanizomenon', ''), None),
        }
        
        # 수질 변수들도 추출 (cyanohab_final.csv에 포함되어 있음)
        # 모델이 학습한 wq_vars: 수온(℃), DO(㎎/L), TN, TP
        # cyanohab_final.csv에는 수온, DO, pH, Chl-a가 있지만 TN, TP는 없을 수 있음
        wq_vars = {}
        
        # 수온 추출
        for col in df.columns:
            if '수온' in str(col) or ('온도' in str(col) and '℃' in str(col)):
                value = row.get(col, None)
                if pd.notna(value) and value != '':
                    try:
                        value_float = float(value)
                        if value_float >= 0:
                            wq_vars['수온(℃)'] = value_float
                    except:
                        pass
                break
        
        # DO 추출
        for col in df.columns:
            if 'DO' in str(col) and '㎎/L' in str(col):
                value = row.get(col, None)
                if pd.notna(value) and value != '':
                    try:
                        value_float = float(value)
                        if value_float >= 0:
                            wq_vars['DO(㎎/L)'] = value_float
                    except:
                        pass
                break
        
        # pH 추출
        for col in df.columns:
            if str(col).strip() == 'pH' or str(col).strip().lower() == 'ph':
                value = row.get(col, None)
                if pd.notna(value) and value != '':
                    try:
                        value_float = float(value)
                        if 0 <= value_float <= 14:  # pH는 0-14 범위
                            wq_vars['pH'] = value_float
                    except:
                        pass
                break
        
        # Chl-a 추출
        for col in df.columns:
            if 'Chl-a' in str(col) or 'chl-a' in str(col).lower() or '클로로필' in str(col):
                value = row.get(col, None)
                if pd.notna(value) and value != '':
                    try:
                        value_float = float(value)
                        if value_float >= 0:
                            # 컬럼명에 단위가 포함되어 있으면 그대로 사용
                            col_name = str(col).strip()
                            if '㎎/㎥' in col_name or 'mg/m3' in col_name.lower():
                                wq_vars['Chl-a (㎎/㎥)'] = value_float
                            else:
                                wq_vars['Chl-a'] = value_float
                    except:
                        pass
                break
        
        # 모든 변수를 하나의 딕셔너리로 합치기
        all_vars = {**cyano_vars, **wq_vars}
        
        # 각 변수를 별도 행으로 저장
        for var_name, value in all_vars.items():
            if pd.isna(value) or value == '':
                continue
            
            try:
                value_float = float(value)
                if value_float < 0:
                    continue
            except:
                continue
            
            # 단위 결정 (모델이 학습한 변수 기준)
            unit_map = {
                '유해남조류 세포수 (cells/㎖)': 'cells/㎖',
                'Microcystis': 'count',
                'Anabaena': 'count',
                'Oscillatoria': 'count',
                'Aphanizomenon': 'count',
                '수온(℃)': '℃',
                'DO(㎎/L)': '㎎/L',
                'TN': '㎎/L',
                'TP': '㎎/L',
                'pH': '',  # pH는 단위 없음
                'Chl-a': '㎎/㎥',
                'Chl-a (㎎/㎥)': '㎎/㎥',
            }
            unit = unit_map.get(var_name, '')
            
            result.append({
                'location': full_location,  # 지점명_채수위치 형식
                'date': date,
                'data_type': var_name,
                'value': value_float,
                'unit': unit,
            })
    
    result_df = pd.DataFrame(result)
    print(f"처리된 데이터: {len(result_df)}행")
    return result_df


def process_wq_data(df: pd.DataFrame) -> pd.DataFrame:
    """수질 데이터 처리"""
    print("\n[수질 데이터 처리]")
    
    # 컬럼명 확인
    print(f"컬럼 수: {len(df.columns)}")
    print(f"행 수: {len(df)}")
    
    # 필요한 컬럼 확인
    required_cols = {
        'Station': ['Station', '측정소명', '지점명', 'Station'],
        'Date': ['Date', '조사일', '날짜', 'date'],
        '수온(℃)': ['Temp', '수온', 'Temperature', 'temp'],
        'DO(㎎/L)': ['DO', '용존산소', 'Dissolved Oxygen'],
        'TN': ['TN', '총질소', 'Total Nitrogen', 'DTN'],
        'TP': ['TP', '총인', 'Total Phosphorus', 'DTP'],
    }
    
    # 컬럼 매핑 찾기
    col_mapping = {}
    for target_col, possible_names in required_cols.items():
        for col in df.columns:
            col_str = str(col).strip()
            if any(name.lower() in col_str.lower() for name in possible_names):
                col_mapping[target_col] = col
                break
    
    print(f"매핑된 컬럼: {col_mapping}")
    
    # 위치명 매핑: 수질좌표_2025.csv를 기반으로 model_config.json 형식으로 매핑
    # model_config.json의 spatial_classes에 있는 위치는 해당 형식으로 매핑
    # 그 외는 수질좌표_2025.csv의 측정소명을 그대로 사용 (1대1 매칭)
    location_mapping = {}
    
    # model_config.json에서 spatial_classes 로드
    models_dir = Path(__file__).parent.parent / "backend" / "models"
    config_path = models_dir / "model_config.json"
    if config_path.exists():
        import json
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        spatial_classes = config.get('encoders', {}).get('spatial_classes', [])
        
        # spatial_classes의 각 위치에서 "지점명_채수위치" 형식을 분리하여 매핑
        # 예: "강정고령보_다사" -> "강정", "고령", "다사" 모두 "강정고령보_다사"로 매핑
        for full_location in spatial_classes:
            if '_' in full_location:
                parts = full_location.split('_')
                # 각 부분을 전체 위치명으로 매핑
                for part in parts:
                    location_mapping[part] = full_location
                # 전체 이름도 자기 자신으로 매핑
                location_mapping[full_location] = full_location
    
    print(f"위치명 매핑: {len(location_mapping)}개 (예: {list(location_mapping.items())[:5]})")
    
    # 데이터 정리
    result = []
    for idx, row in df.iterrows():
        location = row.get(col_mapping.get('Station', ''), '')
        date_str = row.get(col_mapping.get('Date', ''), '')
        
        if pd.isna(location) or pd.isna(date_str):
            continue
        
        # 날짜 파싱
        try:
            date = pd.to_datetime(date_str).date()
        except:
            continue
        
        # 위치명 매핑: WQ_TOTAL.csv의 위치명을 model_config.json 형식으로 변환
        location_str = str(location).strip()
        mapped_location = location_mapping.get(location_str, location_str)
        
        # 수질 변수들 추출
        wq_vars = {
            '수온(℃)': row.get(col_mapping.get('수온(℃)', ''), None),
            'DO(㎎/L)': row.get(col_mapping.get('DO(㎎/L)', ''), None),
            'TN': row.get(col_mapping.get('TN', ''), None),
            'TP': row.get(col_mapping.get('TP', ''), None),
        }
        
        # 각 변수를 별도 행으로 저장
        for var_name, value in wq_vars.items():
            if pd.isna(value) or value == '' or value == '분석중' or value == '정량한계미만':
                continue
            
            try:
                value_float = float(value)
                if value_float < 0:
                    continue
            except:
                continue
            
            unit_map = {
                '수온(℃)': '℃',
                'DO(㎎/L)': '㎎/L',
                'TN': '㎎/L',
                'TP': '㎎/L',
            }
            
            result.append({
                'location': mapped_location,  # 매핑된 위치명 사용
                'date': date,
                'data_type': var_name,
                'value': value_float,
                'unit': unit_map.get(var_name, ''),
            })
    
    result_df = pd.DataFrame(result)
    print(f"처리된 데이터: {len(result_df)}행")
    return result_df


def load_location_coordinates(coords_file: Path) -> Dict[str, Dict[str, float]]:
    """위치 좌표 정보 로드"""
    if not coords_file.exists():
        print(f"⚠ 좌표 파일 없음: {coords_file}")
        return {}
    
    df = load_csv_with_encoding(coords_file)
    if df is None:
        return {}
    
    coords = {}
    for idx, row in df.iterrows():
        location = str(row.get('측정소명', '')).strip()
        lat = row.get('latitude', None)
        lon = row.get('longitude', None)
        
        if location and not pd.isna(lat) and not pd.isna(lon):
            coords[location] = {
                'latitude': float(lat),
                'longitude': float(lon)
            }
    
    print(f"✓ 좌표 정보 로드: {len(coords)}개 위치")
    return coords


def save_to_database(data_df: pd.DataFrame, coords: Dict[str, Dict[str, float]], db: Session):
    """데이터를 데이터베이스에 저장"""
    print(f"\n[데이터베이스 저장]")
    print(f"저장할 데이터: {len(data_df)}행")
    
    saved_count = 0
    skipped_count = 0
    
    for idx, row in data_df.iterrows():
        # 좌표 정보 추가
        location = row['location']
        coord_info = coords.get(location, {})
        
        # 중복 체크
        existing = db.query(EnvironmentalData).filter(
            EnvironmentalData.location == location,
            EnvironmentalData.date == row['date'],
            EnvironmentalData.data_type == row['data_type']
        ).first()
        
        if existing:
            skipped_count += 1
            continue
        
        # 새 레코드 생성
        env_data = EnvironmentalData(
            location=location,
            latitude=coord_info.get('latitude'),
            longitude=coord_info.get('longitude'),
            date=row['date'],
            datetime=datetime.combine(row['date'], datetime.min.time()),
            data_type=row['data_type'],
            value=row['value'],
            unit=row.get('unit', ''),
        )
        
        db.add(env_data)
        saved_count += 1
        
        # 배치 커밋 (1000개마다)
        if saved_count % 1000 == 0:
            db.commit()
            print(f"  저장 중... {saved_count}개")
    
    db.commit()
    print(f"\n✓ 저장 완료: {saved_count}개")
    print(f"  건너뜀 (중복): {skipped_count}개")


def main():
    parser = argparse.ArgumentParser(description='학습 데이터를 데이터베이스에 로드')
    parser.add_argument(
        '--data-dir',
        type=str,
        default='졸논. 녹조예측 주단위/Data',
        help='데이터 폴더 경로'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제 저장하지 않고 데이터만 확인'
    )
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"❌ 데이터 폴더를 찾을 수 없습니다: {data_dir}")
        return
    
    print("="*80)
    print("학습 데이터 로드 스크립트")
    print("="*80)
    
    # 데이터베이스 초기화
    if not args.dry_run:
        init_db()
        db = SessionLocal()
    else:
        db = None
        print("\n[DRY RUN 모드 - 실제 저장하지 않습니다]")
    
    try:
        # 파일 경로
        cyanohab_file = data_dir / "cyanohab_final.csv"
        wq_file = data_dir / "WQ_TOTAL.csv"
        coords_file = data_dir / "수질좌표_2025.csv"
        
        # 좌표 정보 로드
        coords = load_location_coordinates(coords_file)
        
        # 녹조 데이터 로드 및 처리
        if cyanohab_file.exists():
            cyanohab_df = load_csv_with_encoding(cyanohab_file)
            if cyanohab_df is not None:
                cyanohab_processed = process_cyanohab_data(cyanohab_df)
                
                if not args.dry_run and db:
                    save_to_database(cyanohab_processed, coords, db)
        else:
            print(f"⚠ 녹조 데이터 파일 없음: {cyanohab_file}")
        
        # 수질 데이터 로드 및 처리
        if wq_file.exists():
            wq_df = load_csv_with_encoding(wq_file)
            if wq_df is not None:
                wq_processed = process_wq_data(wq_df)
                
                if not args.dry_run and db:
                    save_to_database(wq_processed, coords, db)
        else:
            print(f"⚠ 수질 데이터 파일 없음: {wq_file}")
        
        print("\n" + "="*80)
        print("✅ 완료!")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        if db:
            db.rollback()
    
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    main()

