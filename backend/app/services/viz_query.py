"""
시각화용 데이터 조회
데이터베이스에서 시각화에 필요한 데이터를 조회
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.models.env_data import EnvironmentalData
from app.models.location_mapping import LocationMapping


def get_site_coordinates(site_name: str, db: Session) -> Optional[Dict[str, float]]:
    """
    지점 좌표 조회
    
    Args:
        site_name: 지점명
        db: 데이터베이스 세션
    
    Returns:
        {"lat": float, "lng": float} 또는 None
    """
    print(f"🔍 좌표 조회 시작: site_name={site_name}")
    
    # location_mapping 테이블에서 조회 (정확한 매칭)
    mapping = db.query(LocationMapping).filter(
        LocationMapping.algae_location == site_name
    ).first()
    
    # 정확한 매칭이 실패하면 부분 매칭 시도 (예: "강정고령보" -> "강정고령보_다사")
    if not mapping:
        print(f"정확한 매칭 실패, 부분 매칭 시도...")
        # "강정고령보" -> "강정고령보_다사" 같은 경우를 찾기 위해 contains 사용
        mapping = db.query(LocationMapping).filter(
            LocationMapping.algae_location.contains(site_name)
        ).first()
        
        # 역방향 매칭도 시도 (site_name이 algae_location을 포함하는 경우)
        if not mapping:
            all_mappings = db.query(LocationMapping).all()
            for m in all_mappings:
                if site_name in m.algae_location or m.algae_location in site_name:
                    mapping = m
                    print(f"역방향 매칭 성공: {m.algae_location}")
                    break
    
    if mapping:
        print(f"location_mapping에서 찾음: {mapping.algae_location}")
        if mapping.latitude and mapping.longitude:
            result = {
                "lat": float(mapping.latitude),
                "lng": float(mapping.longitude)
            }
            print(f"✓ 좌표 반환: {result}")
            return result
        else:
            print(f"⚠ 좌표가 없음: latitude={mapping.latitude}, longitude={mapping.longitude}")
    else:
        print(f"location_mapping에서 찾지 못함, environmental_data에서 시도")
    
    # environmental_data에서 좌표 조회 시도
    coord_data = db.query(
        func.avg(EnvironmentalData.latitude).label('lat'),
        func.avg(EnvironmentalData.longitude).label('lng')
    ).filter(
        EnvironmentalData.location.contains(site_name)
    ).first()
    
    if coord_data and coord_data.lat and coord_data.lng:
        result = {
            "lat": float(coord_data.lat),
            "lng": float(coord_data.lng)
        }
        print(f"✓ environmental_data에서 좌표 반환: {result}")
        return result
    
    print(f"❌ 좌표를 찾을 수 없음: {site_name}")
    return None


def get_timeseries_data(
    site_name: str,
    variable: str,
    start_date: datetime,
    end_date: datetime,
    db: Session,
    limit: int = 52  # 최근 52주 (1년)
) -> Dict[str, List]:
    """
    시계열 데이터 조회 (최근 N개 제한)
    
    Args:
        site_name: 지점명
        variable: 변수명 (예: "유해남조류 세포수 (cells/㎖)")
        start_date: 시작 날짜
        end_date: 종료 날짜
        db: 데이터베이스 세션
        limit: 최대 데이터 포인트 수
    
    Returns:
        {
            "labels": [날짜 문자열 리스트],
            "observed": [관측값 리스트],
            "predicted": [예측값 리스트]  # 현재는 None
        }
    """
    try:
        # location_mapping을 통해 실제 DB의 location 확인
        mapping = db.query(LocationMapping).filter(
            LocationMapping.algae_location == site_name
        ).first()
        
        # 정확한 매칭 실패 시 부분 매칭 시도
        if not mapping:
            mapping = db.query(LocationMapping).filter(
                LocationMapping.algae_location.contains(site_name)
            ).first()
        
        # 역방향 매칭도 시도
        if not mapping:
            all_mappings = db.query(LocationMapping).all()
            for m in all_mappings:
                if site_name in m.algae_location or m.algae_location in site_name:
                    mapping = m
                    break
        
        # 실제 조회할 location 결정
        actual_location = site_name
        if mapping:
            # 녹조 데이터는 algae_location에서, 수질 데이터는 wq_location에서
            if "녹조" in variable or "조류" in variable or "세포수" in variable:
                actual_location = mapping.algae_location
            else:
                actual_location = mapping.wq_location
            print(f"✓ location_mapping 매칭: {site_name} -> {actual_location}")
        
        # 데이터 조회 (일 단위, 최근 limit개)
        # 주 단위 집계 대신 일 단위로 조회 (더 많은 데이터 포인트)
        data = db.query(EnvironmentalData).filter(
            EnvironmentalData.location == actual_location,
            EnvironmentalData.data_type == variable,
            EnvironmentalData.date >= start_date.date(),
            EnvironmentalData.date <= end_date.date(),
            EnvironmentalData.value.isnot(None)
        ).order_by(EnvironmentalData.date.desc()).limit(limit * 7).all()  # 주당 약 7일 데이터
        
        # 날짜 오름차순으로 정렬
        data = sorted(data, key=lambda x: x.date)
        
        labels = []
        observed = []
        
        for record in data:
            if record.date:
                labels.append(record.date.isoformat())
                observed.append(float(record.value) if record.value is not None else None)
        
        # 예측값은 현재 없음 (나중에 예측 결과와 병합)
        predicted = [None] * len(observed)
        
        return {
            "labels": labels,
            "observed": observed,
            "predicted": predicted
        }
    
    except Exception as e:
        # 오류 발생 시 빈 데이터 반환
        import logging
        logging.error(f"시계열 데이터 조회 실패: {e}")
        return {
            "labels": [],
            "observed": [],
            "predicted": []
        }


def get_multiple_sites_data(
    site_names: List[str],
    variable: str,
    start_date: datetime,
    end_date: datetime,
    aggregation: str = "mean",  # "mean" or "max"
    db: Session = None
) -> List[Dict[str, Any]]:
    """
    여러 지점의 데이터 조회 (지도용)
    
    Args:
        site_names: 지점명 리스트
        variable: 변수명
        start_date: 시작 날짜
        end_date: 종료 날짜
        aggregation: 집계 방식 ("mean" or "max")
        db: 데이터베이스 세션
    
    Returns:
        지점별 데이터 리스트
        [
            {
                "site_id": str,
                "name": str,
                "lat": float,
                "lng": float,
                "value": float
            },
            ...
        ]
    """
    result = []
    
    try:
        for site_name in site_names:
            # 좌표 조회
            coords = get_site_coordinates(site_name, db)
            if not coords:
                continue
            
            # location_mapping을 통해 실제 DB의 location 확인
            mapping = db.query(LocationMapping).filter(
                LocationMapping.algae_location == site_name
            ).first()
            
            # 실제 조회할 location 결정
            actual_location = site_name
            if mapping:
                if "녹조" in variable or "조류" in variable or "세포수" in variable:
                    actual_location = mapping.algae_location
                else:
                    actual_location = mapping.wq_location
            
            # 데이터 조회 및 집계
            query = db.query(EnvironmentalData).filter(
                EnvironmentalData.location == actual_location,
                EnvironmentalData.data_type == variable,
                EnvironmentalData.date >= start_date.date(),
                EnvironmentalData.date <= end_date.date(),
                EnvironmentalData.value.isnot(None)
            )
            
            if aggregation == "mean":
                agg_result = query.with_entities(func.avg(EnvironmentalData.value)).scalar()
            elif aggregation == "max":
                agg_result = query.with_entities(func.max(EnvironmentalData.value)).scalar()
            else:
                agg_result = query.with_entities(func.avg(EnvironmentalData.value)).scalar()
            
            if agg_result is None:
                continue
            
            result.append({
                "site_id": site_name,
                "name": site_name,
                "lat": coords["lat"],
                "lng": coords["lng"],
                "value": float(agg_result)
            })
    
    except Exception as e:
        import logging
        logging.error(f"여러 지점 데이터 조회 실패: {e}")
    
    return result

