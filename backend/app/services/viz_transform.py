"""
시각화 데이터 변환 함수 (순수 함수)
의존성 없이 데이터 변환만 담당
"""
from typing import List, Optional, Dict, Any


def build_timeseries(
    labels: List[str],
    observed: List[Optional[float]],
    predicted: List[Optional[float]]
) -> Dict[str, Any]:
    """
    시계열 데이터 빌드
    
    Args:
        labels: 날짜 문자열 리스트
        observed: 관측값 리스트 (null 가능)
        predicted: 예측값 리스트 (null 가능)
    
    Returns:
        시계열 데이터 딕셔너리
    """
    return {
        "labels": labels,
        "observed": observed,
        "predicted": predicted
    }


def build_map_points(
    sites: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    지도 포인트 데이터 빌드
    
    Args:
        sites: 지점 정보 리스트
            - site_id: str
            - name: str
            - lat: float
            - lng: float
            - value: Optional[float]
    
    Returns:
        지도 포인트 리스트
    """
    return [
        {
            "site_id": s["site_id"],
            "name": s["name"],
            "lat": s["lat"],
            "lng": s["lng"],
            "value": s.get("value")
        }
        for s in sites
    ]


def calculate_metrics(
    observed: List[Optional[float]],
    predicted: List[Optional[float]]
) -> Dict[str, float]:
    """
    예측 성능 메트릭 계산
    
    Args:
        observed: 관측값 리스트
        predicted: 예측값 리스트
    
    Returns:
        메트릭 딕셔너리 (RMSE, R², NSE 등)
    """
    import numpy as np
    
    # null 값 제거하고 유효한 쌍만 추출
    valid_pairs = [
        (obs, pred) 
        for obs, pred in zip(observed, predicted) 
        if obs is not None and pred is not None
    ]
    
    if len(valid_pairs) == 0:
        return {
            "rmse": 0.0,
            "r2": 0.0,
            "nse": 0.0
        }
    
    obs_values = np.array([pair[0] for pair in valid_pairs])
    pred_values = np.array([pair[1] for pair in valid_pairs])
    
    # RMSE
    rmse = np.sqrt(np.mean((obs_values - pred_values) ** 2))
    
    # R²
    ss_res = np.sum((obs_values - pred_values) ** 2)
    ss_tot = np.sum((obs_values - np.mean(obs_values)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    
    # NSE (Nash-Sutcliffe Efficiency)
    nse = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    
    return {
        "rmse": float(rmse),
        "r2": float(r2),
        "nse": float(nse)
    }

