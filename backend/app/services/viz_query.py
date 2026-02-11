"""
시각화용 데이터 조회
데이터베이스에서 시각화에 필요한 데이터를 조회
"""
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.models.env_data import EnvironmentalData
from app.models.location_mapping import LocationMapping
from app.models.monitoring_station import MonitoringStation


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


def _resolve_actual_location(site_name: str, variable: str, db: Session) -> str:
    """지점명 + 변수에 따라 DB 조회용 actual_location 반환."""
    mapping = db.query(LocationMapping).filter(
        LocationMapping.algae_location == site_name
    ).first()
    if not mapping:
        mapping = db.query(LocationMapping).filter(
            LocationMapping.algae_location.contains(site_name)
        ).first()
    if not mapping:
        for m in db.query(LocationMapping).all():
            if site_name in (m.algae_location or "") or (m.algae_location or "") in site_name:
                mapping = m
                break
    actual_location = site_name
    if mapping:
        if "녹조" in variable or "조류" in variable or "세포수" in variable:
            actual_location = mapping.algae_location
        else:
            actual_location = mapping.wq_location
    return actual_location


def get_max_date_for_timeseries(site_name: str, variable: str, db: Session) -> Optional[datetime]:
    """
    해당 지점·변수에 대해 DB에 있는 최신 관측일 반환.
    시계열 관측값 조회 시 end_date를 DB 범위 안으로 제한할 때 사용.
    """
    try:
        actual_location = _resolve_actual_location(site_name, variable, db)
        q = db.query(func.max(EnvironmentalData.date)).filter(
            EnvironmentalData.location == actual_location,
            EnvironmentalData.data_type == variable,
            EnvironmentalData.value.isnot(None),
        )
        max_date = q.scalar()
        if max_date:
            return datetime.combine(max_date, datetime.min.time())
        return None
    except Exception:
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
    end_date가 DB 최신일보다 미래면, DB에 있는 최신일까지로 제한해 관측값이 나오도록 함.
    
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
        actual_location = _resolve_actual_location(site_name, variable, db)
        if site_name != actual_location:
            print(f"✓ location_mapping 매칭: {site_name} -> {actual_location}")

        # end_date가 미래면 DB에 있는 최신일로 제한 → 관측값이 항상 나오도록
        db_max = get_max_date_for_timeseries(site_name, variable, db)
        query_end = end_date
        if db_max and end_date.date() > db_max.date():
            query_end = db_max
            print(f"✓ 관측 기간 제한: 요청 end_date가 DB 이후라 DB 최신일까지 사용: {query_end.date()}")

        # 데이터 조회 (일 단위, 최근 limit개)
        data = db.query(EnvironmentalData).filter(
            EnvironmentalData.location == actual_location,
            EnvironmentalData.data_type == variable,
            EnvironmentalData.date >= start_date.date(),
            EnvironmentalData.date <= query_end.date(),
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


def get_all_monitoring_stations(db: Session) -> List[Dict[str, Any]]:
    """
    모든 관측 지점의 좌표 조회 (지도용)
    
    노트북의 "Algal Monitoring Stations over Watershed and River Network" 방식
    데이터베이스의 monitoring_stations 테이블에서 조회
    
    Args:
        db: 데이터베이스 세션
    
    Returns:
        모든 관측 지점 리스트
        [
            {
                "site_id": str,
                "name": str,
                "lat": float,
                "lng": float
            },
            ...
        ]
    """
    result = []
    
    try:
        # monitoring_stations 테이블에서 모든 지점 조회
        stations = db.query(MonitoringStation).filter(
            MonitoringStation.latitude.isnot(None),
            MonitoringStation.longitude.isnot(None)
        ).all()
        
        if stations:
            for station in stations:
                result.append({
                    "site_id": station.station_name,
                    "name": station.station_name,
                    "lat": float(station.latitude),
                    "lng": float(station.longitude)
                })
            print(f"✓ DB에서 {len(result)}개 관측 지점 조회 완료")
            return result
        
        # monitoring_stations 테이블이 비어있으면 폴백: location_mapping 테이블 사용
        print(f"⚠ monitoring_stations 테이블이 비어있습니다. location_mapping 폴백 사용")
        return _get_stations_from_db(db)
    
    except Exception as e:
        import logging
        logging.error(f"DB에서 관측 지점 조회 실패: {e}")
        print(f"❌ DB 조회 실패: {e}")
        # 폴백: location_mapping 테이블 사용
        return _get_stations_from_db(db)


def _get_stations_from_db(db: Session) -> List[Dict[str, Any]]:
    """location_mapping 테이블에서 관측 지점 조회 (폴백)"""
    result = []
    
    try:
        mappings = db.query(LocationMapping).filter(
            LocationMapping.latitude.isnot(None),
            LocationMapping.longitude.isnot(None)
        ).all()
        
        for mapping in mappings:
            if mapping.latitude and mapping.longitude:
                site_name = mapping.algae_location or mapping.wq_location or ""
                if site_name:
                    result.append({
                        "site_id": site_name,
                        "name": site_name,
                        "lat": float(mapping.latitude),
                        "lng": float(mapping.longitude)
                    })
        
        print(f"✓ DB에서 {len(result)}개 관측 지점 조회 완료 (폴백)")
        return result
    
    except Exception as e:
        import logging
        logging.error(f"DB에서 관측 지점 조회 실패: {e}")
        return []


def get_predictable_stations(db: Session) -> List[Dict[str, Any]]:
    """
    녹조 예측 가능 31개 지점만 조회 (model_config spatial_classes 기준).
    location_mapping에서 해당 algae_location의 좌표를 가져옴.
    """
    result = []
    try:
        models_dir = Path(__file__).resolve().parent.parent.parent / "models"
        config_path = models_dir / "model_config.json"
        if not config_path.exists():
            print(f"⚠ model_config.json 없음: {config_path}, get_all_monitoring_stations 폴백")
            return get_all_monitoring_stations(db)
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        spatial_classes = config.get("encoders", {}).get("spatial_classes") or []
        if not spatial_classes:
            return get_all_monitoring_stations(db)
        # location_mapping에서 algae_location이 spatial_classes에 있는 행만 조회
        mappings = db.query(LocationMapping).filter(
            LocationMapping.algae_location.in_(spatial_classes),
            LocationMapping.latitude.isnot(None),
            LocationMapping.longitude.isnot(None),
        ).all()
        for m in mappings:
            if m.algae_location and m.latitude is not None and m.longitude is not None:
                result.append({
                    "site_id": m.algae_location,
                    "name": m.algae_location,
                    "lat": float(m.latitude),
                    "lng": float(m.longitude),
                })
        print(f"✓ 예측 가능 지점 {len(result)}개 조회 완료 (spatial_classes 기준)")
        return result
    except Exception as e:
        import logging
        logging.error(f"예측 가능 지점 조회 실패: {e}")
        return get_all_monitoring_stations(db)

