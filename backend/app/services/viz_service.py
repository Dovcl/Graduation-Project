"""
시각화 서비스 (오케스트레이션)
예측 결과와 환경 데이터를 시각화용 데이터로 변환
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.viz_transform import build_timeseries, build_map_points, calculate_metrics
from app.services.viz_query import (
    get_site_coordinates,
    get_timeseries_data,
    get_max_date_for_timeseries,
    get_multiple_sites_data,
    get_all_monitoring_stations,
    get_predictable_stations,
)
from app.schemas.chat import VisualizationData, QueryContext, TimeseriesData, MapPoint
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class VisualizationService:
    """시각화 데이터 생성 서비스"""
    
    def __init__(self):
        pass
    
    def build_visualization_data(
        self,
        prediction_result: Optional[Dict[str, Any]],
        location: Optional[str],
        target_date: Optional[datetime],
        variable: str = "유해남조류 세포수 (cells/㎖)",
        db: Session = None,
        requested_location: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        시각화 데이터 생성
        
        Args:
            prediction_result: 예측 결과 딕셔너리
            location: 지점명 (예측에 사용된 해석된 지점명, 예: 강정고령보_다사)
            target_date: 예측 대상 날짜
            variable: 변수명
            db: 데이터베이스 세션
            requested_location: 사용자가 입력한 원본 지점명 (예: 강정고령보) - 프론트 강조용
        
        Returns:
            시각화 데이터 딕셔너리 또는 None
        """
        try:
            # 예측 결과가 없으면 시각화 데이터 생성 불가
            if not prediction_result or not prediction_result.get("success"):
                return None
            
            if not location or not db:
                return None
            
            # 쿼리 컨텍스트 구성 (site_name에는 사용자가 입력한 원본 지점명 사용)
            display_location = requested_location or location
            print(f"🔍 시각화 query_context.site_name 설정: requested_location={requested_location}, location={location}, display_location={display_location}")
            query_context = self._build_query_context(
                display_location, variable, target_date, prediction_result
            )
            print(f"✓ query_context.site_name = {query_context.get('site_name')}")
            
            # 시계열 데이터 준비 (최근 52주)
            timeseries = self._build_timeseries_data(
                location, variable, target_date, prediction_result, db
            )
            if timeseries:
                print(f"✓ 시계열 데이터 생성 완료: labels={len(timeseries.get('labels', []))}, observed={len(timeseries.get('observed', []))}, predicted={len(timeseries.get('predicted', []))}")
            else:
                print(f"⚠ 시계열 데이터 생성 실패: location={location}, variable={variable}")
            
            # 지도 포인트 데이터 준비: 예측 가능 31개 지점만 표시, 요청 지점은 프론트에서 빨간색 강조
            # 상세 플롯용: 예측값이 있는 지점만 (기존 방식 유지)
            plot_map_points = self._build_map_points_data(
                location, variable, target_date, prediction_result, db
            )
            # 지도용: 예측 가능 31개 지점만 (model_config spatial_classes 기준)
            predictable_map_points = self._build_predictable_stations_map_data(db)
            map_points = predictable_map_points if predictable_map_points else plot_map_points
            
            if map_points:
                print(f"✓ 지도 포인트 데이터 생성 완료: {len(map_points)}개 (예측 가능 지점만), 강조 지점: {location}")
            else:
                print(f"⚠ 지도 포인트 데이터 생성 실패")
            
            # 상세 플롯용 데이터는 별도로 저장 (예측값이 있는 지점만)
            if plot_map_points:
                print(f"✓ 상세 플롯 포인트 데이터: {len(plot_map_points)}개")
            
            # 메트릭 계산
            metrics = None
            if timeseries and timeseries.get("observed") and timeseries.get("predicted"):
                metrics = calculate_metrics(
                    timeseries["observed"],
                    timeseries["predicted"]
                )
            
            # Pydantic 모델로 변환
            return VisualizationData(
                schema_version="1.0",
                type="algae_forecast",
                generated_at=datetime.now().isoformat(),
                query_context=QueryContext(**query_context),
                timeseries=TimeseriesData(**timeseries) if timeseries else None,
                map_points=[MapPoint(**mp) for mp in map_points] if map_points else None,
                plot_points=[MapPoint(**mp) for mp in plot_map_points] if plot_map_points else None,  # 상세 플롯용
                metrics=metrics,
                visualizations_error=None
            )
        
        except Exception as e:
            logger.error(f"시각화 데이터 생성 실패: {e}", exc_info=True)
            if settings.DEBUG:
                # 에러 발생 시에도 Pydantic 모델 반환
                return VisualizationData(
                    schema_version="1.0",
                    type="algae_forecast",
                    generated_at=datetime.now().isoformat(),
                    query_context=QueryContext(
                        site_id=location or "",
                        site_name=location or "",
                        variable=variable,
                        unit="cells/㎖",
                        period={"start": "", "end": ""}
                    ),
                    timeseries=None,
                    map_points=None,
                    plot_points=None,
                    metrics=None,
                    visualizations_error=str(e)
                )
            return None
    
    def _build_query_context(
        self,
        location: str,
        variable: str,
        target_date: Optional[datetime],
        prediction_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """쿼리 컨텍스트 구성"""
        # 예측 결과에서 기간 정보 추출
        metadata = prediction_result.get("metadata", {})
        data_info = metadata.get("data_info", {})
        data_date_range = data_info.get("data_date_range", {})
        
        period_start = data_date_range.get("min")
        period_end = data_date_range.get("max")
        
        # 단위 추출
        unit = "cells/㎖"  # 기본값
        if "cells" in variable or "세포수" in variable:
            unit = "cells/㎖"
        elif "℃" in variable or "수온" in variable:
            unit = "℃"
        elif "mg/L" in variable or "㎎/L" in variable:
            unit = "mg/L"
        
        return {
            "site_id": location,
            "site_name": location,
            "variable": variable,
            "unit": unit,
            "period": {
                "start": period_start or (target_date - timedelta(weeks=52)).isoformat() if target_date else "",
                "end": period_end or target_date.isoformat() if target_date else ""
            },
            "aggregation": "mean"
        }
    
    def _build_timeseries_data(
        self,
        location: str,
        variable: str,
        target_date: Optional[datetime],
        prediction_result: Dict[str, Any],
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """시계열 데이터 구성"""
        try:
            print(f"🔍 시계열 데이터 생성 시작: location={location}, variable={variable}")

            # 관측값은 DB에 있는 기간 안에서만 조회 (target_date가 미래면 DB 최신일까지 사용)
            db_max_date = get_max_date_for_timeseries(location, variable, db)
            if target_date:
                end_date = target_date
                start_date = target_date - timedelta(weeks=52)
                if db_max_date and end_date.date() > db_max_date.date():
                    end_date = db_max_date
                    start_date = end_date - timedelta(weeks=52)
            else:
                end_date = datetime.now()
                start_date = end_date - timedelta(weeks=52)
                if db_max_date and end_date.date() > db_max_date.date():
                    end_date = db_max_date
                    start_date = end_date - timedelta(weeks=52)

            print(f"조회 기간: {start_date.date()} ~ {end_date.date()}")

            # 관측 데이터 조회
            timeseries_data = get_timeseries_data(
                location, variable, start_date, end_date, db, limit=52
            )
            
            print(f"시계열 데이터 조회 결과: labels={len(timeseries_data.get('labels', []))}, observed={len(timeseries_data.get('observed', []))}")
            
            # 예측 결과를 시계열에 병합
            predictions = prediction_result.get("predictions", {})
            pred_value = predictions.get(variable)
            
            if pred_value is not None and target_date:
                # 예측값을 predicted 리스트에 추가
                # target_date의 다음 주 시작일(월요일)을 예측 날짜로 사용
                # 주 단위 예측이므로 다음 주의 시작일을 예측 날짜로 설정
                days_until_monday = (7 - target_date.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 7  # 오늘이 월요일이면 다음 주 월요일
                prediction_date = target_date + timedelta(days=days_until_monday)
                prediction_date_str = prediction_date.isoformat().split('T')[0]  # 날짜만
                
                # predicted 리스트 초기화 (모두 None으로)
                if not timeseries_data["predicted"]:
                    timeseries_data["predicted"] = [None] * len(timeseries_data["labels"])
                
                # 예측 날짜가 labels에 있는지 확인
                prediction_date_iso = prediction_date.isoformat()
                if prediction_date_iso not in timeseries_data["labels"]:
                    # 없으면 추가
                    timeseries_data["labels"].append(prediction_date_iso)
                    timeseries_data["observed"].append(None)
                    timeseries_data["predicted"].append(float(pred_value))
                else:
                    # 있으면 해당 인덱스의 predicted 업데이트
                    idx = timeseries_data["labels"].index(prediction_date_iso)
                    timeseries_data["predicted"][idx] = float(pred_value)
            
            return build_timeseries(
                timeseries_data["labels"],
                timeseries_data["observed"],
                timeseries_data["predicted"]
            )
        
        except Exception as e:
            logger.error(f"시계열 데이터 구성 실패: {e}")
            return None
    
    def _build_map_points_data(
        self,
        location: str,
        variable: str,
        target_date: Optional[datetime],
        prediction_result: Dict[str, Any],
        db: Session
    ) -> Optional[List[Dict[str, Any]]]:
        """지도 포인트 데이터 구성"""
        try:
            print(f"🔍 지도 포인트 데이터 생성 시작: location={location}")
            
            # 좌표 조회
            coords = get_site_coordinates(location, db)
            if not coords:
                print(f"❌ 좌표 조회 실패: location={location}")
                return None
            
            print(f"✓ 좌표 조회 성공: {coords}")
            
            # 예측값 추출
            predictions = prediction_result.get("predictions", {})
            pred_value = predictions.get(variable)
            print(f"예측값: {pred_value}, 변수: {variable}")
            
            # 지도 포인트 생성
            sites = [{
                "site_id": location,
                "name": location,
                "lat": coords["lat"],
                "lng": coords["lng"],
                "value": float(pred_value) if pred_value is not None else None
            }]
            
            result = build_map_points(sites)
            print(f"✓ 지도 포인트 생성 완료: {result}")
            return result
        
        except Exception as e:
            logger.error(f"지도 포인트 데이터 구성 실패: {e}", exc_info=True)
            print(f"❌ 지도 포인트 데이터 구성 중 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _build_all_stations_map_data(
        self,
        db: Session
    ) -> Optional[List[Dict[str, Any]]]:
        """
        모든 관측 지점 지도 데이터 구성 (폴백용)
        """
        try:
            all_stations = get_all_monitoring_stations(db)
            if not all_stations:
                return None
            return build_map_points(all_stations)
        except Exception as e:
            logger.error(f"모든 관측 지점 지도 데이터 구성 실패: {e}", exc_info=True)
            return None

    def _build_predictable_stations_map_data(
        self,
        db: Session
    ) -> Optional[List[Dict[str, Any]]]:
        """
        예측 가능 31개 지점만 지도 데이터 구성 (값 없이 위치만).
        강조할 지점은 query_context.site_name으로 프론트에서 빨간색 표시.
        """
        try:
            print(f"🔍 예측 가능 지점(31개) 지도 데이터 생성 시작")
            stations = get_predictable_stations(db)
            if not stations:
                print(f"❌ 예측 가능 지점 조회 실패")
                return None
            print(f"✓ 예측 가능 지점 {len(stations)}개 조회 성공")
            return build_map_points(stations)
        except Exception as e:
            logger.error(f"예측 가능 지점 지도 데이터 구성 실패: {e}", exc_info=True)
            return None

