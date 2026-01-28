"""
관측 지점 모델 - 모든 관측 지점의 좌표 정보
"""
from sqlalchemy import Column, Integer, String, Float
from app.database import Base


class MonitoringStation(Base):
    """관측 지점 좌표 테이블"""
    __tablename__ = "monitoring_stations"

    id = Column(Integer, primary_key=True, index=True)
    station_name = Column(String(200), nullable=False, unique=True, index=True)  # 지점명
    latitude = Column(Float, nullable=False)  # 위도
    longitude = Column(Float, nullable=False)  # 경도
    region = Column(String(50))  # 수계 (한강, 금강, 낙동강, 영산강) - 선택적

    def __repr__(self):
        return f"<MonitoringStation(name='{self.station_name}', lat={self.latitude}, lon={self.longitude})>"

