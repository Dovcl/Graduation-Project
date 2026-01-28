"""
CSV 파일에서 관측 지점 좌표를 읽어서 DB에 저장하는 스크립트
"""

import os
import sys
from pathlib import Path
import pandas as pd

# 프로젝트 루트 설정
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

# .env 파일 로드
from dotenv import load_dotenv
env_path = project_root / "backend" / ".env"
load_dotenv(env_path)

from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db, Base, engine
from app.models.monitoring_station import MonitoringStation


def find_csv_file():
    """CSV 파일 경로 찾기"""
    # 여러 경로 시도
    csv_paths = [
        Path("/Users/gimdohyeon/Desktop/UOS/grad_proj/grad_proj1/졸논. 녹조예측 주단위/Data/visualization/조류지점_좌표_pro.csv"),
        project_root / "Data" / "visualization" / "조류지점_좌표_pro.csv",
        project_root.parent / "Data" / "visualization" / "조류지점_좌표_pro.csv",
        Path("/Users/gimdohyeon/Desktop/UOS/grad_proj/grad_proj1/Data/visualization/조류지점_좌표_pro.csv"),
        project_root / "backend" / "data" / "조류지점_좌표_pro.csv",
    ]
    
    for path in csv_paths:
        if path.exists():
            return path
    
    return None


def load_stations_from_csv(csv_path: Path) -> list:
    """CSV 파일에서 관측 지점 데이터 읽기"""
    print(f"📖 CSV 파일 읽기: {csv_path}")
    
    # CSV 파일 읽기
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    print(f"✓ CSV 파일 읽기 완료: {len(df)}개 행")
    print(f"  컬럼: {list(df.columns)}")
    
    # 컬럼명 매핑
    lat_col = None
    lon_col = None
    name_col = None
    region_col = None
    
    for col in df.columns:
        col_lower = col.lower()
        if '위도' in col or 'lat' in col_lower:
            lat_col = col
        elif '경도' in col or 'lon' in col_lower or 'long' in col_lower:
            lon_col = col
        elif '지점' in col or 'name' in col_lower or 'station' in col_lower or 'site' in col_lower:
            name_col = col
        elif '수계' in col or 'region' in col_lower:
            region_col = col
    
    if not lat_col or not lon_col:
        raise ValueError(f"필수 컬럼을 찾을 수 없습니다. 위도/경도 컬럼이 필요합니다.")
    
    stations = []
    for idx, row in df.iterrows():
        try:
            lat = float(row[lat_col]) if pd.notna(row[lat_col]) else None
            lon = float(row[lon_col]) if pd.notna(row[lon_col]) else None
            
            if lat is None or lon is None:
                continue
            
            # 지점명 추출
            station_name = ""
            if name_col and pd.notna(row.get(name_col)):
                station_name = str(row[name_col]).strip()
            elif '지점명' in df.columns:
                station_name = str(row.get('지점명', '')).strip()
            elif '지점명_pro' in df.columns:
                station_name = str(row.get('지점명_pro', '')).strip()
            
            if not station_name:
                station_name = f"지점_{idx+1}"
            
            # 수계 추출 (선택적)
            region = None
            if region_col and pd.notna(row.get(region_col)):
                region = str(row[region_col]).strip()
            
            stations.append({
                "station_name": station_name,
                "latitude": lat,
                "longitude": lon,
                "region": region
            })
        except Exception as e:
            print(f"⚠ 행 {idx+1} 처리 중 오류: {e}")
            continue
    
    print(f"✓ {len(stations)}개 관측 지점 데이터 추출 완료")
    return stations


def main():
    print("="*60)
    print("관측 지점 좌표 DB 저장")
    print("="*60)
    
    # CSV 파일 찾기
    csv_path = find_csv_file()
    if not csv_path:
        print("❌ CSV 파일을 찾을 수 없습니다.")
        print("다음 경로를 확인해주세요:")
        print("  - Data/visualization/조류지점_좌표_pro.csv")
        print("  - backend/data/조류지점_좌표_pro.csv")
        return
    
    # CSV 파일 읽기
    try:
        stations = load_stations_from_csv(csv_path)
    except Exception as e:
        print(f"❌ CSV 파일 읽기 실패: {e}")
        return
    
    if not stations:
        print("❌ 추출된 관측 지점이 없습니다.")
        return
    
    # 테이블 생성
    Base.metadata.create_all(bind=engine)
    print("✓ 테이블 생성 완료")
    
    db = SessionLocal()
    
    try:
        # 기존 데이터 삭제
        db.execute(text("DELETE FROM monitoring_stations"))
        db.commit()
        print("✓ 기존 데이터 삭제 완료")
        
        # 데이터 삽입
        for station_data in stations:
            station = MonitoringStation(**station_data)
            db.add(station)
        
        db.commit()
        print(f"✓ {len(stations)}개 관측 지점 데이터 저장 완료")
        
        # 결과 확인
        print("\n" + "="*60)
        print("[저장된 관측 지점 샘플 (최대 10개)]")
        print("="*60)
        
        result = db.execute(text("""
            SELECT station_name, latitude, longitude, region
            FROM monitoring_stations
            ORDER BY station_name
            LIMIT 10
        """))
        
        for row in result:
            region_str = f" ({row.region})" if row.region else ""
            print(f"  {row.station_name:<30} [{row.latitude:.6f}, {row.longitude:.6f}]{region_str}")
        
        total_count = db.execute(text("SELECT COUNT(*) FROM monitoring_stations")).scalar()
        print(f"\n총 {total_count}개 관측 지점이 저장되었습니다.")
        print(f"\n✅ 완료!")
        
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    
    finally:
        db.close()


if __name__ == "__main__":
    main()

