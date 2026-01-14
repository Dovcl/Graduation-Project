"""
데이터 조회 서비스 - 환경 데이터 쿼리
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.database import get_db
from app.models.env_data import EnvironmentalData
import re


class DataService:
    """환경 데이터 조회 서비스"""
    
    def __init__(self):
        pass
    
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
    
    def _parse_location(self, query: str) -> Optional[str]:
        """질문에서 위치 정보 추출"""
        # 간단한 패턴 (나중에 개선 가능)
        location_patterns = [
            r'([가-힣]+(?:시|도|구|동|리|호수|강|하천))',
            r'([A-Za-z]+(?:Lake|River|Station))',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, query)
            if match:
                return match.group(1)
        
        return None
    
    def _parse_data_type(self, query: str) -> Optional[str]:
        """질문에서 데이터 타입 추출"""
        type_mapping = {
            '수질': 'water_quality',
            '녹조': 'algae',
            '조류': 'algae',
            '수문': 'hydrology',
            '기상': 'weather',
            '온도': 'weather',
            '강수': 'weather',
            '습도': 'weather',
        }
        
        query_lower = query.lower()
        for korean, english in type_mapping.items():
            if korean in query:
                return english
        
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
            location = self._parse_location(question)
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
                filters.append(EnvironmentalData.location.contains(location))
            
            if data_type:
                filters.append(EnvironmentalData.data_type == data_type)
            
            if filters:
                query = query.filter(and_(*filters))
            
            # 결과 조회
            results = query.order_by(EnvironmentalData.date.desc()).limit(100).all()
            
            # 통계 계산
            if results:
                values = [r.value for r in results if r.value is not None]
                stats = {
                    "count": len(results),
                    "min": min(values) if values else None,
                    "max": max(values) if values else None,
                    "avg": sum(values) / len(values) if values else None,
                }
            else:
                stats = {"count": 0, "min": None, "max": None, "avg": None}
            
            # 결과 포맷팅
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
                    for r in results[:20]  # 최대 20개만 반환
                ],
                "statistics": stats,
                "metadata": {
                    "date_range": {
                        "start": date_range[0].isoformat() if date_range else None,
                        "end": date_range[1].isoformat() if date_range else None,
                    } if date_range else None,
                    "location": location,
                    "data_type": data_type,
                    "total_found": len(results),
                }
            }
            
            return data
        
        finally:
            if should_close:
                db.close()

