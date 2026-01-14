"""
환경 데이터 모델 - 수질, 녹조, 수문, 기상 데이터
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, func, Index
from app.database import Base


class EnvironmentalData(Base):
    """환경 데이터 테이블 모델"""
    __tablename__ = "environmental_data"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 위치 정보
    location = Column(String(200), nullable=False, index=True)  # 위치명
    latitude = Column(Float)  # 위도
    longitude = Column(Float)  # 경도
    
    # 날짜 정보
    date = Column(Date, nullable=False, index=True)
    datetime = Column(DateTime(timezone=True), index=True)  # 정확한 시간
    
    # 데이터 타입
    data_type = Column(String(50), nullable=False, index=True)  # "water_quality", "algae", "hydrology", "weather"
    
    # 측정값들 (데이터 타입에 따라 사용)
    value = Column(Float)  # 주요 값
    value2 = Column(Float)  # 보조 값
    value3 = Column(Float)  # 추가 값
    
    # 단위 및 메타데이터
    unit = Column(String(50))  # 단위 (예: "mg/L", "℃")
    quality_flag = Column(String(50))  # 품질 플래그
    notes = Column(Text)  # 메모
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 복합 인덱스 (검색 성능 향상)
    __table_args__ = (
        Index('idx_location_date_type', 'location', 'date', 'data_type'),
    )
    
    def __repr__(self):
        return f"<EnvironmentalData(id={self.id}, location='{self.location}', date={self.date}, type='{self.data_type}')>"

