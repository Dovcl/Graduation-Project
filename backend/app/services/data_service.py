"""
데이터 조회 서비스 - 환경 데이터 쿼리
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.database import get_db
from app.models.env_data import EnvironmentalData
import re
import json
from pathlib import Path


class DataService:
    """환경 데이터 조회 서비스"""
    
    def __init__(self):
        self.known_locations = self._load_known_locations()
        self.data_type_mapping = self._load_data_type_mapping()
        self.coords_cache = None  # 좌표 정보 캐시
    
    def _load_known_locations(self) -> List[str]:
        """model_config.json에서 알려진 위치 목록 로드"""
        models_dir = Path(__file__).parent.parent.parent / "models"
        config_path = models_dir / "model_config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # spatial_classes에서 "지점명_채수위치" 형태를 분리하여 개별 지점명도 포함
            locations = set()
            for full_name in config['encoders']['spatial_classes']:
                locations.add(full_name)
                if '_' in full_name:
                    # "강정고령보_다사" -> "강정고령보", "다사" 둘 다 추가
                    parts = full_name.split('_')
                    locations.add(parts[0])  # 예: "강정고령보"
                    if len(parts) > 1:
                        locations.add(parts[1])  # 예: "다사"
            return sorted(list(locations))
        return []
    
    def _load_data_type_mapping(self) -> Dict[str, str]:
        """model_config.json에서 데이터 타입 매핑 로드"""
        models_dir = Path(__file__).parent.parent.parent / "models"
        config_path = models_dir / "model_config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            mapping = {
                '수질': 'water_quality', # 일반적인 카테고리
                '녹조': 'algae',
                '조류': 'algae',
                '수문': 'hydrology',
                '기상': 'weather',
                '온도': '수온(℃)',
                '수온': '수온(℃)',
                'DO': 'DO(㎎/L)',
                '용존산소': 'DO(㎎/L)',
                'TN': 'TN',
                '총질소': 'TN',
                'TP': 'TP',
                '총인': 'TP',
                '유해남조류': '유해남조류 세포수 (cells/㎖)',
                'Microcystis': 'Microcystis',
                'Anabaena': 'Anabaena',
                'Oscillatoria': 'Oscillatoria',
                'Aphanizomenon': 'Aphanizomenon',
                'pH': 'pH',
                'ph': 'pH',
                # 클로로필-a 관련
                'chl-a': 'Chl-a (㎎/㎥)',  # 실제 DB 컬럼명
                'chl a': 'Chl-a (㎎/㎥)',
                '클로로필': 'Chl-a (㎎/㎥)',
                '클로로필-a': 'Chl-a (㎎/㎥)',
                '클로로필a': 'Chl-a (㎎/㎥)',
                'chlorophyll': 'Chl-a (㎎/㎥)',
                'chlorophyll-a': 'Chl-a (㎎/㎥)',
            }
            # 모델의 feature_order에 있는 모든 변수들을 매핑에 추가
            for feature in config['features']['feature_order']:
                mapping[feature.lower()] = feature
                # '유해남조류 세포수 (cells/㎖)' -> '유해남조류'로도 매핑
                if ' ' in feature:
                    mapping[feature.split(' ')[0]] = feature
            return mapping
        return {}
    
    def _parse_date_range(self, query: str) -> Optional[tuple]:
        """
        질문에서 날짜 범위 추출
        
        예시:
        - "2022년 1월" -> (2022-01-01, 2022-01-31)
        - "2022년 1월부터 3월까지" -> (2022-01-01, 2022-03-31)
        - "과거 3년" -> (3년 전, 오늘)
        """
        # 간단한 패턴 매칭 (나중에 더 정교하게 개선 가능)
        patterns = [
            (r'(\d{4})년\s*(\d{1,2})월', self._parse_year_month),
            (r'과거\s*(\d+)\s*년', self._parse_past_years),
            (r'(\d{4})-(\d{2})-(\d{2})', self._parse_iso_date),
        ]
        
        for pattern, parser in patterns:
            match = re.search(pattern, query)
            if match:
                return parser(match, query)
        
        return None
    
    def _parse_year_month(self, match, query: str) -> tuple:
        """YYYY년 MM월 파싱"""
        year = int(match.group(1))
        month = int(match.group(2))
        start_date = date(year, month, 1)
        
        # 다음 달 1일에서 1일 빼기 = 이번 달 마지막 날
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        from datetime import timedelta
        end_date = end_date - timedelta(days=1)
        
        return (start_date, end_date)
    
    def _parse_past_years(self, match, query: str) -> tuple:
        """과거 N년 파싱"""
        years = int(match.group(1))
        end_date = date.today()
        start_date = date(end_date.year - years, end_date.month, end_date.day)
        return (start_date, end_date)
    
    def _parse_iso_date(self, match, query: str) -> tuple:
        """ISO 날짜 형식 파싱"""
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        parsed_date = date(year, month, day)
        return (parsed_date, parsed_date)
    
    def _parse_coordinates(self, query: str) -> Optional[Tuple[float, float]]:
        """질문에서 좌표 정보 추출 (위도, 경도)"""
        # 좌표 패턴: (37.038583, 128.405833) 또는 37.038583, 128.405833
        coord_patterns = [
            r'\(?\s*([+-]?\d+\.?\d*)\s*,\s*([+-]?\d+\.?\d*)\s*\)?',  # (lat, lon) 또는 lat, lon
            r'위도\s*[:=]?\s*([+-]?\d+\.?\d*).*?경도\s*[:=]?\s*([+-]?\d+\.?\d*)',  # 위도: 37.038583, 경도: 128.405833
        ]
        
        for pattern in coord_patterns:
            match = re.search(pattern, query)
            if match:
                try:
                    lat = float(match.group(1))
                    lon = float(match.group(2))
                    # 유효한 좌표 범위 확인 (한국: 위도 33-43, 경도 124-132)
                    if 30 <= lat <= 45 and 120 <= lon <= 135:
                        return (lat, lon)
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _find_location_by_coordinates(
        self, 
        lat: float, 
        lon: float, 
        db: Session,
        tolerance: float = 0.001
    ) -> Optional[str]:
        """좌표로 위치 찾기"""
        # 데이터베이스에서 좌표로 위치 찾기
        matches = db.query(EnvironmentalData.location).filter(
            func.abs(EnvironmentalData.latitude - lat) < tolerance,
            func.abs(EnvironmentalData.longitude - lon) < tolerance,
            EnvironmentalData.latitude.isnot(None),
            EnvironmentalData.longitude.isnot(None)
        ).distinct().all()
        
        if matches:
            # 가장 많은 데이터가 있는 위치 반환
            location_counts = {}
            for match in matches:
                location = match[0]
                count = db.query(EnvironmentalData).filter(
                    EnvironmentalData.location == location
                ).count()
                location_counts[location] = count
            
            # 데이터가 가장 많은 위치 반환
            if location_counts:
                return max(location_counts.items(), key=lambda x: x[1])[0]
        
        return None
    
    def _parse_location(self, query: str, db: Session = None) -> Optional[str]:
        """질문에서 위치 정보 추출"""
        query_lower = query.lower()
        
        # 0. 좌표가 있으면 좌표로 먼저 찾기
        coords = self._parse_coordinates(query)
        if coords and db:
            lat, lon = coords
            location_by_coords = self._find_location_by_coordinates(lat, lon, db)
            if location_by_coords:
                return location_by_coords
        
        # 1. 알려진 위치명과 정확히 일치하거나 포함되는지 확인
        # 더 긴 위치명을 우선적으로 매칭 (예: "강천보"가 "강천"보다 우선)
        # 길이순으로 정렬하여 긴 것부터 확인
        sorted_locations = sorted(self.known_locations, key=len, reverse=True)
        
        for known_loc in sorted_locations:
            if known_loc in query or known_loc.lower() in query_lower:
                return known_loc
        
        # 2. 일반적인 패턴 매칭 (보, 호, 댐, 강 등 포함)
        location_patterns = [
            r'([가-힣]+(?:보|호|댐|강|하천|천|시|도|구|동|리))',
            r'([가-힣]{2,}(?:보|호|댐))',  # 2글자 이상 + 보/호/댐
            r'([A-Za-z]+(?:Lake|River|Station))',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, query)
            if match:
                matched_location = match.group(1)
                # 매칭된 위치가 알려진 위치 목록에 있는지 확인 (긴 것부터)
                for known_loc in sorted_locations:
                    if matched_location in known_loc or known_loc in matched_location:
                        return matched_location
                return matched_location
        
        return None
    
    def _parse_data_type(self, query: str) -> Optional[str]:
        """질문에서 데이터 타입 추출"""
        query_lower = query.lower()
        
        # model_config.json에서 로드한 매핑 사용
        for keyword, db_type in self.data_type_mapping.items():
            if keyword.lower() in query_lower or keyword in query:
                if db_type:  # None이 아닌 경우에만 반환
                    return db_type
        
        return None
    
    async def query(
        self,
        question: str,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        자연어 질문을 파싱하여 환경 데이터 조회
        
        Args:
            question: 자연어 질문
            db: 데이터베이스 세션
        
        Returns:
            조회된 데이터 및 메타데이터
        """
        # DB 세션 관리
        if db is None:
            db_gen = get_db()
            db = next(db_gen)
            should_close = True
        else:
            should_close = False
        
        try:
            # 질문 파싱
            date_range = self._parse_date_range(question)
            
            # 좌표 파싱 및 위치 찾기
            coords = self._parse_coordinates(question)
            location = None
            found_by_coordinates = False
            
            if coords and db:
                lat, lon = coords
                location = self._find_location_by_coordinates(lat, lon, db)
                if location:
                    found_by_coordinates = True
                    coords_info = {'lat': lat, 'lon': lon}
                else:
                    coords_info = None
            else:
                location = self._parse_location(question, db=db)
                coords_info = None
            
            data_type = self._parse_data_type(question)
            
            # 쿼리 구성
            query = db.query(EnvironmentalData)
            
            # 필터 적용
            filters = []
            
            if date_range:
                start_date, end_date = date_range
                filters.append(EnvironmentalData.date >= start_date)
                filters.append(EnvironmentalData.date <= end_date)
            
            if location:
                # 위치 매칭: 유연한 매칭
                # "강천보"를 검색할 때 "강천보_강천"과 "강천보" 둘 다 찾을 수 있도록
                location_filters = [
                    EnvironmentalData.location == location,  # 정확한 일치
                    EnvironmentalData.location.contains(location)  # 포함 관계
                ]
                
                # 알려진 위치 목록에서 관련된 모든 위치 검색
                # 예: "강천보" -> "강천보_강천", "강천보" 둘 다 찾기
                for known_loc in self.known_locations:
                    # location이 known_loc에 포함되거나, known_loc이 location에 포함되면 검색
                    if location in known_loc or known_loc in location:
                        location_filters.append(EnvironmentalData.location == known_loc)
                
                filters.append(or_(*location_filters))
            
            if data_type:
                # 데이터 타입 정확한 매칭
                filters.append(EnvironmentalData.data_type == data_type)
            
            if filters:
                query = query.filter(and_(*filters))
            
            # 전체 개수 조회
            total_count = query.count()
            
            # 데이터 타입별 통계 계산
            stats_by_type = {}
            if total_count > 0:
                type_stats = query.with_entities(
                    EnvironmentalData.data_type,
                    func.count(EnvironmentalData.id).label('count'),
                    func.min(EnvironmentalData.value).label('min'),
                    func.max(EnvironmentalData.value).label('max'),
                    func.avg(EnvironmentalData.value).label('avg')
                ).filter(
                    EnvironmentalData.value.isnot(None)
                ).group_by(EnvironmentalData.data_type).all()
                
                for data_type, count, min_val, max_val, avg_val in type_stats:
                    stats_by_type[data_type] = {
                        "count": count,
                        "min": float(min_val) if min_val is not None else None,
                        "max": float(max_val) if max_val is not None else None,
                        "avg": float(avg_val) if avg_val is not None else None,
                    }
            
            # 전체 통계 (모든 데이터 타입 합산 - 참고용)
            if total_count > 0:
                overall_stats_query = query.with_entities(
                    func.min(EnvironmentalData.value).label('min'),
                    func.max(EnvironmentalData.value).label('max'),
                    func.avg(EnvironmentalData.value).label('avg')
                ).filter(EnvironmentalData.value.isnot(None)).first()
                
                if overall_stats_query:
                    overall_stats = {
                        "count": total_count,
                        "min": float(overall_stats_query.min) if overall_stats_query.min is not None else None,
                        "max": float(overall_stats_query.max) if overall_stats_query.max is not None else None,
                        "avg": float(overall_stats_query.avg) if overall_stats_query.avg is not None else None,
                    }
                else:
                    overall_stats = {
                        "count": total_count,
                        "min": None,
                        "max": None,
                        "avg": None
                    }
            else:
                overall_stats = {
                    "count": 0,
                    "min": None,
                    "max": None,
                    "avg": None
                }
            
            # 통계에 데이터 타입별 통계 포함
            stats = {
                "overall": overall_stats,
                "by_type": stats_by_type
            }
            
            # 샘플 데이터 조회 (표시용, 최대 20개)
            sample_results = query.order_by(EnvironmentalData.date.desc()).limit(20).all()
            
            # 결과 포맷팅 (샘플 데이터는 최대 20개만 반환)
            data = {
                "results": [
                    {
                        "id": r.id,
                        "location": r.location,
                        "date": r.date.isoformat() if r.date else None,
                        "datetime": r.datetime.isoformat() if r.datetime else None,
                        "data_type": r.data_type,
                        "value": r.value,
                        "value2": r.value2,
                        "value3": r.value3,
                        "unit": r.unit,
                    }
                    for r in sample_results  # 최대 20개만 반환
                ],
                "statistics": stats,
                    "metadata": {
                        "date_range": {
                            "start": date_range[0].isoformat() if date_range else None,
                            "end": date_range[1].isoformat() if date_range else None,
                        } if date_range else None,
                        "location": location,
                        "data_type": data_type,
                        "total_found": total_count,  # 전체 개수
                        "found_by_coordinates": found_by_coordinates,
                        "coordinates": coords_info,
                    }
            }
            
            return data
        
        finally:
            if should_close:
                db.close()

