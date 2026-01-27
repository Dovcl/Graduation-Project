"""
위치 매칭 모델 - 녹조 지점과 수질 지점 매칭
"""
from sqlalchemy import Column, Integer, String, Float
from app.database import Base


class LocationMapping(Base):
    """녹조-수질 지점 매칭 테이블"""
    __tablename__ = "location_mapping"

    id = Column(Integer, primary_key=True, index=True)
    algae_location = Column(String(100), nullable=False, unique=True, index=True)  # 녹조 지점 (cyanohab)
    wq_location = Column(String(100), nullable=False, index=True)  # 수질 지점 (WQ_TOTAL)
    region = Column(String(50))  # 수계 (한강, 금강, 낙동강, 영산강)
    latitude = Column(Float)  # 수질 지점 위도
    longitude = Column(Float)  # 수질 지점 경도

    def __repr__(self):
        return f"<LocationMapping(algae='{self.algae_location}', wq='{self.wq_location}')>"

