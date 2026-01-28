"""
채팅 API 요청/응답 스키마
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class Message(BaseModel):
    """메시지 모델"""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """채팅 요청 모델"""
    message: str
    history: List[Message] = []


class QueryContext(BaseModel):
    """쿼리 컨텍스트"""
    site_id: str
    site_name: str
    variable: str
    unit: str
    period: Dict[str, str]  # {"start": "...", "end": "..."}
    aggregation: Optional[str] = "mean"  # "mean" or "max"


class TimeseriesData(BaseModel):
    """시계열 데이터"""
    labels: List[str]  # 날짜 문자열
    observed: List[Optional[float]]  # 관측값 (null 가능)
    predicted: List[Optional[float]]  # 예측값 (null 가능)


class MapPoint(BaseModel):
    """지도 포인트"""
    site_id: str
    name: str
    lat: float
    lng: float
    value: Optional[float] = None


class VisualizationData(BaseModel):
    """시각화 데이터 모델"""
    schema_version: str = "1.0"
    type: str  # "algae_forecast", "data_query"
    generated_at: str  # ISO format
    query_context: QueryContext
    timeseries: Optional[TimeseriesData] = None
    map_points: Optional[List[MapPoint]] = None  # 지도용: 모든 관측 지점
    plot_points: Optional[List[MapPoint]] = None  # 상세 플롯용: 예측값이 있는 지점만
    metrics: Optional[Dict[str, float]] = None
    visualizations_error: Optional[str] = None  # 개발 모드용


class ChatResponse(BaseModel):
    """채팅 응답 모델"""
    answer: str
    suggestions: List[str] = []
    data: Optional[Dict[str, Any]] = None
    visualizations: Optional[VisualizationData] = None
    metadata: Optional[Dict[str, Any]] = None

