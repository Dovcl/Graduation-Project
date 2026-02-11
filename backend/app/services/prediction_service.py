"""
예측 서비스 - 학습된 모델을 사용하여 녹조 예측
"""

import os
import pickle
import json
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.time_series_transformer import TimeSeriesTransformer
from app.database import get_db
from app.models.env_data import EnvironmentalData
from app.models.location_mapping import LocationMapping
from app.core.config import settings


class PredictionService:
    """녹조 예측 서비스"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.temporal_encoder = None
        self.spatial_encoder = None
        self.config = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._load_model()
    
    def _load_model(self):
        """모델 및 전처리 객체 로드"""
        models_dir = Path(__file__).parent.parent.parent / "models"
        
        # Config 로드
        config_path = models_dir / "model_config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"모델 설정 파일을 찾을 수 없습니다: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        # Scaler 로드
        scaler_path = models_dir / "scaler.pkl"
        if not scaler_path.exists():
            raise FileNotFoundError(f"Scaler 파일을 찾을 수 없습니다: {scaler_path}")
        
        with open(scaler_path, 'rb') as f:
            self.scaler = pickle.load(f)
        
        # Encoders 로드
        temporal_encoder_path = models_dir / "temporal_encoder.pkl"
        spatial_encoder_path = models_dir / "spatial_encoder.pkl"
        
        if not temporal_encoder_path.exists():
            raise FileNotFoundError(f"Temporal encoder 파일을 찾을 수 없습니다: {temporal_encoder_path}")
        if not spatial_encoder_path.exists():
            raise FileNotFoundError(f"Spatial encoder 파일을 찾을 수 없습니다: {spatial_encoder_path}")
        
        with open(temporal_encoder_path, 'rb') as f:
            self.temporal_encoder = pickle.load(f)
        
        with open(spatial_encoder_path, 'rb') as f:
            self.spatial_encoder = pickle.load(f)
        
        # 모델 아키텍처 생성
        hyperparams = self.config['model_hyperparameters']
        features = self.config['features']
        
        self.model = TimeSeriesTransformer(
            num_features=features['num_features'],
            num_cyano_vars=features['num_cyano_vars'],
            num_temporal_categories=self.config['encoders']['num_temporal_categories'],
            num_spatial_categories=self.config['encoders']['num_spatial_categories'],
            d_model=hyperparams['d_model'],
            nhead=hyperparams['nhead'],
            num_layers=hyperparams['num_layers'],
            dim_feedforward=hyperparams['dim_feedforward'],
            dropout=hyperparams.get('dropout', 0.1),
            max_seq_len=hyperparams['max_seq_len']
        )
        
        # 모델 가중치 로드
        model_path = models_dir / "TimeSeriesTransformer_best.pth"
        if not model_path.exists():
            raise FileNotFoundError(f"모델 가중치 파일을 찾을 수 없습니다: {model_path}")
        
        self.model.load_state_dict(torch.load(model_path, map_location=self.device, weights_only=False))
        self.model.to(self.device)
        self.model.eval()
        
        print("✓ 모델 및 전처리 객체 로드 완료")
    
    def _get_week_of_year(self, date: datetime) -> str:
        """날짜에서 주차(WoY) 계산"""
        # ISO 주차 계산
        iso_calendar = date.isocalendar()
        year = iso_calendar[0]
        week = iso_calendar[1]
        return f"{year}_{week:02d}"
    
    def _resolve_location_to_spatial_class(self, location: str) -> Optional[str]:
        """
        사용자 입력(예: '강정고령보')을 model_config의 spatial_classes 한 개로 확정.
        '강정고령보' -> '강정고령보_다사' 우선, '낙동강_강정·고령'이 선택되지 않도록 함.
        """
        if not location or not self.config:
            return location
        spatial_classes = self.config.get("encoders", {}).get("spatial_classes") or []
        if not spatial_classes:
            return location
        loc = (location or "").strip()
        # 1) 정확 일치
        if loc in spatial_classes:
            return loc
        # 2) spatial_class가 loc으로 시작 (예: '강정고령보' -> '강정고령보_다사')
        for sc in spatial_classes:
            if sc.startswith(loc):
                return sc
        # 3) loc이 spatial_class로 시작
        for sc in spatial_classes:
            if loc.startswith(sc):
                return sc
        # 4) loc이 spatial_class에 포함
        for sc in spatial_classes:
            if loc in sc:
                return sc
        return location
    
    def _get_wq_location(self, algae_location: str, db: Session) -> Optional[str]:
        """
        녹조 지점으로부터 매칭된 수질 지점 찾기
        
        Args:
            algae_location: 녹조 지점명
            db: 데이터베이스 세션
        
        Returns:
            매칭된 수질 지점명 또는 None
        """
        # 정확한 매칭 시도
        mapping = db.query(LocationMapping).filter(
            LocationMapping.algae_location == algae_location
        ).first()
        
        if mapping:
            return mapping.wq_location
        
        # 부분 매칭 시도 (contains)
        mapping = db.query(LocationMapping).filter(
            LocationMapping.algae_location.contains(algae_location)
        ).first()
        
        if mapping:
            return mapping.wq_location
        
        # 역방향 매칭 시도 (Python에서 처리: 변수 ↔ DB 값 포함 관계)
        for m in db.query(LocationMapping).all():
            if not m.algae_location:
                continue
            if algae_location in m.algae_location or m.algae_location in algae_location:
                return m.wq_location

        # 매칭되지 않으면 None 반환 (기존 동작 유지)
        return None
    
    def _prepare_input_sequence(
        self,
        location: str,
        target_date: datetime,
        db: Session
    ) -> Optional[Tuple[np.ndarray, str, str, Dict[str, Any]]]:
        """
        예측을 위한 입력 시퀀스 준비

        Args:
            location: 위치명
            target_date: 예측할 날짜
            db: 데이터베이스 세션

        Returns:
            (X_time_series, temporal_context, spatial_context, metadata) 또는 None
            metadata: 사용된 데이터 범위 정보
        """
        seq_len = self.config['model_hyperparameters']['seq_len']
        feature_order = self.config['features']['feature_order']
        cyano_vars = self.config['features']['cyano_vars']
        wq_vars = self.config['features']['wq_vars']
        
        # 데이터베이스의 날짜 범위 조회
        from sqlalchemy import func
        date_range = db.query(
            func.min(EnvironmentalData.date).label('min_date'),
            func.max(EnvironmentalData.date).label('max_date')
        ).filter(
            EnvironmentalData.location.contains(location)
        ).first()
        
        db_min_date = date_range.min_date if date_range else None
        db_max_date = date_range.max_date if date_range else None

        # 먼저 target_date 기준으로 과거 7주 데이터 시도
        result = self._try_get_sequence_data(
            location, target_date, seq_len, feature_order, db
        )
        
        used_base_date = target_date
        data_source = "target_date"

        # 데이터가 없으면 해당 위치의 가장 최근 7주 데이터 사용
        if result is None:
            print(f"⚠ {target_date.date()} 기준 과거 7주 데이터 없음. 최근 데이터로 대체합니다.")
            result = self._get_latest_sequence_data(
                location, seq_len, feature_order, db
            )
            
            if result is None:
                return None  # 해당 위치의 데이터가 전혀 없음
            
            # 최근 데이터 날짜 찾기
            latest_date_query = db.query(func.max(EnvironmentalData.date)).filter(
                EnvironmentalData.location.contains(location)
            ).scalar()
            
            if latest_date_query:
                if isinstance(latest_date_query, datetime):
                    used_base_date = latest_date_query
                else:
                    used_base_date = datetime.combine(latest_date_query, datetime.min.time())
                data_source = "latest_available"
        
        X_time_series, data_date_range = result

        # numpy 배열로 변환
        X_time_series = np.array(X_time_series, dtype=np.float32)  # (seq_len, num_features)

        # log1p 적용 (전처리 설정에 따라)
        if self.config['preprocessing']['log1p_applied']:
            X_time_series = np.log1p(X_time_series)

        # Scaler 적용
        X_time_series_reshaped = X_time_series.reshape(-1, len(feature_order))
        X_time_series_scaled = self.scaler.transform(X_time_series_reshaped).reshape(seq_len, len(feature_order))

        # Temporal context (target_date의 주차 사용)
        temporal_context = self._get_week_of_year(target_date)

        # Spatial context
        spatial_context = location
        
        # 메타데이터 구성
        metadata = {
            "db_date_range": {
                "min": db_min_date.isoformat() if db_min_date else None,
                "max": db_max_date.isoformat() if db_max_date else None
            },
            "used_base_date": used_base_date.isoformat(),
            "data_source": data_source,  # "target_date" or "latest_available"
            "data_date_range": data_date_range  # 실제 사용된 데이터의 날짜 범위
        }

        return X_time_series_scaled, temporal_context, spatial_context, metadata

    def _try_get_sequence_data(
        self,
        location: str,
        target_date: datetime,
        seq_len: int,
        feature_order: List[str],
        db: Session
    ) -> Optional[Tuple[List[List[float]], Dict[str, str]]]:
        """
        target_date 기준 과거 7주 데이터 조회 시도
        녹조 변수는 원래 지점에서, 수질 변수는 매칭된 수질 지점에서 조회
        """
        # 매칭된 수질 지점 찾기
        wq_location = self._get_wq_location(location, db)
        cyano_vars = self.config['features']['cyano_vars']
        wq_vars = self.config['features']['wq_vars']
        
        if wq_location:
            print(f"ℹ 매칭 테이블 사용: {location} → {wq_location} (수질 지점)")
        
        X_time_series = []
        min_date = None
        max_date = None

        for week_offset in range(seq_len, 0, -1):
            week_start = target_date - timedelta(weeks=week_offset)
            week_end = target_date - timedelta(weeks=week_offset-1)

            # 녹조 변수: 원래 지점에서 조회
            cyano_query = db.query(EnvironmentalData).filter(
                EnvironmentalData.location.contains(location),
                EnvironmentalData.date >= week_start.date(),
                EnvironmentalData.date <= (week_end - timedelta(days=1)).date(),
                EnvironmentalData.data_type.in_(cyano_vars)
            )
            cyano_data = cyano_query.all()

            # 수질 변수: 매칭된 수질 지점에서 조회 (매칭이 있는 경우)
            wq_data = []
            if wq_location:
                wq_query = db.query(EnvironmentalData).filter(
                    EnvironmentalData.location.contains(wq_location),
                    EnvironmentalData.date >= week_start.date(),
                    EnvironmentalData.date <= (week_end - timedelta(days=1)).date(),
                    EnvironmentalData.data_type.in_(wq_vars)
                )
                wq_data = wq_query.all()
            else:
                # 매칭이 없으면 원래 지점에서 수질 변수도 조회
                wq_query = db.query(EnvironmentalData).filter(
                    EnvironmentalData.location.contains(location),
                    EnvironmentalData.date >= week_start.date(),
                    EnvironmentalData.date <= (week_end - timedelta(days=1)).date(),
                    EnvironmentalData.data_type.in_(wq_vars)
                )
                wq_data = wq_query.all()

            # 두 데이터 합치기
            week_data = cyano_data + wq_data

            if not week_data:
                return None  # 해당 기간 데이터 없음
            
            # 날짜 범위 업데이트
            for d in week_data:
                if d.date:
                    if min_date is None or d.date < min_date:
                        min_date = d.date
                    if max_date is None or d.date > max_date:
                        max_date = d.date

            # 주간 평균 계산
            week_values = self._calculate_week_values(week_data, feature_order, cyano_vars, wq_vars)
            feature_values = [week_values.get(var, 0.0) for var in feature_order]
            X_time_series.append(feature_values)

        data_date_range = {
            "min": min_date.isoformat() if min_date else None,
            "max": max_date.isoformat() if max_date else None
        }
        
        return X_time_series, data_date_range

    def _get_latest_sequence_data(
        self,
        location: str,
        seq_len: int,
        feature_order: List[str],
        db: Session
    ) -> Optional[Tuple[List[List[float]], Dict[str, str]]]:
        """
        해당 위치의 가장 최근 7주 데이터 조회
        녹조 변수는 원래 지점에서, 수질 변수는 매칭된 수질 지점에서 조회
        """
        from sqlalchemy import func

        # 매칭된 수질 지점 찾기
        wq_location = self._get_wq_location(location, db)
        cyano_vars = self.config['features']['cyano_vars']
        wq_vars = self.config['features']['wq_vars']
        
        if wq_location:
            print(f"ℹ 매칭 테이블 사용: {location} → {wq_location} (수질 지점)")

        # 해당 위치의 가장 최근 날짜 찾기 (녹조 데이터 기준)
        latest_date_query = db.query(func.max(EnvironmentalData.date)).filter(
            EnvironmentalData.location.contains(location),
            EnvironmentalData.data_type.in_(cyano_vars)
        ).scalar()

        # 수질 지점의 최근 날짜도 확인
        if wq_location:
            wq_latest_date_query = db.query(func.max(EnvironmentalData.date)).filter(
                EnvironmentalData.location.contains(wq_location),
                EnvironmentalData.data_type.in_(wq_vars)
            ).scalar()
            
            # 더 최근 날짜 사용
            if wq_latest_date_query:
                if latest_date_query is None or wq_latest_date_query > latest_date_query:
                    latest_date_query = wq_latest_date_query

        if not latest_date_query:
            return None  # 해당 위치 데이터 없음

        # datetime으로 변환
        if isinstance(latest_date_query, datetime):
            latest_date = latest_date_query
        else:
            latest_date = datetime.combine(latest_date_query, datetime.min.time())

        print(f"ℹ {location} 위치의 최근 데이터 날짜: {latest_date.date()}")

        X_time_series = []
        min_date = None
        max_date = None

        # 최근 날짜 기준으로 과거 7주 데이터 조회
        for week_offset in range(seq_len, 0, -1):
            week_start = latest_date - timedelta(weeks=week_offset)
            week_end = latest_date - timedelta(weeks=week_offset-1)

            # 녹조 변수: 원래 지점에서 조회
            cyano_query = db.query(EnvironmentalData).filter(
                EnvironmentalData.location.contains(location),
                EnvironmentalData.date >= week_start.date(),
                EnvironmentalData.date <= (week_end - timedelta(days=1)).date(),
                EnvironmentalData.data_type.in_(cyano_vars)
            )
            cyano_data = cyano_query.all()

            # 수질 변수: 매칭된 수질 지점에서 조회 (매칭이 있는 경우)
            wq_data = []
            if wq_location:
                wq_query = db.query(EnvironmentalData).filter(
                    EnvironmentalData.location.contains(wq_location),
                    EnvironmentalData.date >= week_start.date(),
                    EnvironmentalData.date <= (week_end - timedelta(days=1)).date(),
                    EnvironmentalData.data_type.in_(wq_vars)
                )
                wq_data = wq_query.all()
            else:
                # 매칭이 없으면 원래 지점에서 수질 변수도 조회
                wq_query = db.query(EnvironmentalData).filter(
                    EnvironmentalData.location.contains(location),
                    EnvironmentalData.date >= week_start.date(),
                    EnvironmentalData.date <= (week_end - timedelta(days=1)).date(),
                    EnvironmentalData.data_type.in_(wq_vars)
                )
                wq_data = wq_query.all()

            # 두 데이터 합치기
            week_data = cyano_data + wq_data

            # 데이터가 없으면 주 범위 확장
            if not week_data:
                extended_start = week_start - timedelta(weeks=2)
                
                # 녹조 데이터 확장 조회
                extended_cyano_query = db.query(EnvironmentalData).filter(
                    EnvironmentalData.location.contains(location),
                    EnvironmentalData.date >= extended_start.date(),
                    EnvironmentalData.date < week_end.date(),
                    EnvironmentalData.data_type.in_(cyano_vars)
                ).order_by(EnvironmentalData.date.desc()).limit(50)
                cyano_data = extended_cyano_query.all()
                
                # 수질 데이터 확장 조회
                if wq_location:
                    extended_wq_query = db.query(EnvironmentalData).filter(
                        EnvironmentalData.location.contains(wq_location),
                        EnvironmentalData.date >= extended_start.date(),
                        EnvironmentalData.date < week_end.date(),
                        EnvironmentalData.data_type.in_(wq_vars)
                    ).order_by(EnvironmentalData.date.desc()).limit(50)
                    wq_data = extended_wq_query.all()
                else:
                    extended_wq_query = db.query(EnvironmentalData).filter(
                        EnvironmentalData.location.contains(location),
                        EnvironmentalData.date >= extended_start.date(),
                        EnvironmentalData.date < week_end.date(),
                        EnvironmentalData.data_type.in_(wq_vars)
                    ).order_by(EnvironmentalData.date.desc()).limit(50)
                    wq_data = extended_wq_query.all()
                
                week_data = cyano_data + wq_data

                if not week_data:
                    # 해당 주 데이터 없으면 0으로 채움 (최소한의 fallback)
                    feature_values = [0.0] * len(feature_order)
                    X_time_series.append(feature_values)
                    continue
            
            # 날짜 범위 업데이트
            for d in week_data:
                if d.date:
                    if min_date is None or d.date < min_date:
                        min_date = d.date
                    if max_date is None or d.date > max_date:
                        max_date = d.date

            # 주간 평균 계산
            week_values = self._calculate_week_values(week_data, feature_order, cyano_vars, wq_vars)
            feature_values = [week_values.get(var, 0.0) for var in feature_order]
            X_time_series.append(feature_values)

        if not X_time_series:
            return None
        
        data_date_range = {
            "min": min_date.isoformat() if min_date else None,
            "max": max_date.isoformat() if max_date else None
        }
        
        return X_time_series, data_date_range

    def _calculate_week_values(
        self,
        week_data: List,
        feature_order: List[str],
        cyano_vars: List[str],
        wq_vars: List[str]
    ) -> Dict[str, float]:
        """
        주간 데이터에서 각 변수의 평균값 계산
        녹조 변수는 원래 지점에서, 수질 변수는 매칭된 수질 지점에서 조회
        
        Args:
            week_data: 주간 데이터 리스트 (녹조 데이터와 수질 데이터가 혼합되어 있을 수 있음)
            feature_order: 변수 순서
            cyano_vars: 녹조 변수 리스트
            wq_vars: 수질 변수 리스트
        """
        week_values = {}

        for var in feature_order:
            values = []
            for d in week_data:
                if hasattr(d, 'data_type') and d.data_type == var:
                    if d.value is not None:
                        values.append(d.value)

            week_values[var] = np.mean(values) if values else 0.0

        return week_values
    
    def _calculate_data_quality_score(
        self,
        location: str,
        base_date: datetime,  # 실제 사용된 기준 날짜 (target_date 또는 latest_date)
        seq_len: int,
        feature_order: List[str],
        db: Session
    ) -> Dict[str, Any]:
        """
        데이터 품질 점수 및 신뢰도 레벨 계산
        실제 예측에 사용된 데이터 기준으로 계산
        
        Args:
            location: 위치명
            base_date: 실제 사용된 기준 날짜 (target_date 또는 latest_date)
            seq_len: 필요한 주 수
            feature_order: 변수 순서
            db: 데이터베이스 세션
        
        Returns:
            {
                "quality_score": float (0.0 ~ 1.0),
                "reliability_level": str ("high" | "medium" | "low"),
                "weeks_with_data": int,
                "total_weeks_needed": int,
                "missing_weeks": List[int],
                "data_completeness": float (0.0 ~ 1.0)
            }
        """
        from sqlalchemy import func
        
        # 매칭된 수질 지점 찾기
        wq_location = self._get_wq_location(location, db)
        cyano_vars = self.config['features']['cyano_vars']
        wq_vars = self.config['features']['wq_vars']
        
        weeks_with_data = 0
        missing_weeks = []
        total_features_found = 0
        total_features_needed = seq_len * len(feature_order)
        
        for week_offset in range(seq_len, 0, -1):
            week_start = base_date - timedelta(weeks=week_offset)
            week_end = base_date - timedelta(weeks=week_offset-1)
            
            # 녹조 변수: 원래 지점에서 조회
            cyano_query = db.query(EnvironmentalData).filter(
                EnvironmentalData.location.contains(location),
                EnvironmentalData.date >= week_start.date(),
                EnvironmentalData.date <= (week_end - timedelta(days=1)).date(),
                EnvironmentalData.data_type.in_(cyano_vars)
            )
            cyano_data = cyano_query.all()
            
            # 수질 변수: 매칭된 수질 지점에서 조회 (매칭이 있는 경우)
            wq_data = []
            if wq_location:
                wq_query = db.query(EnvironmentalData).filter(
                    EnvironmentalData.location.contains(wq_location),
                    EnvironmentalData.date >= week_start.date(),
                    EnvironmentalData.date <= (week_end - timedelta(days=1)).date(),
                    EnvironmentalData.data_type.in_(wq_vars)
                )
                wq_data = wq_query.all()
            else:
                # 매칭이 없으면 원래 지점에서 수질 변수도 조회
                wq_query = db.query(EnvironmentalData).filter(
                    EnvironmentalData.location.contains(location),
                    EnvironmentalData.date >= week_start.date(),
                    EnvironmentalData.date <= (week_end - timedelta(days=1)).date(),
                    EnvironmentalData.data_type.in_(wq_vars)
                )
                wq_data = wq_query.all()
            
            # 두 데이터 합치기
            week_data = cyano_data + wq_data
            
            if week_data:
                # 해당 주에 필요한 변수들이 얼마나 있는지 확인
                week_features_found = 0
                for var in feature_order:
                    for d in week_data:
                        if hasattr(d, 'data_type') and d.data_type == var and d.value is not None:
                            week_features_found += 1
                            break
                
                total_features_found += week_features_found
                weeks_with_data += 1
            else:
                missing_weeks.append(week_offset)
        
        # 데이터 완전도 계산
        data_completeness = total_features_found / total_features_needed if total_features_needed > 0 else 0.0
        
        # 주 단위 완전도
        weeks_completeness = weeks_with_data / seq_len
        
        # 종합 품질 점수 (가중 평균)
        quality_score = (weeks_completeness * 0.6 + data_completeness * 0.4)
        
        # 신뢰도 레벨 결정
        if quality_score >= 0.8 and weeks_with_data == seq_len:
            reliability_level = "high"
        elif quality_score >= 0.5:
            reliability_level = "medium"
        else:
            reliability_level = "low"
        
        return {
            "quality_score": round(quality_score, 2),
            "reliability_level": reliability_level,
            "weeks_with_data": weeks_with_data,
            "total_weeks_needed": seq_len,
            "missing_weeks": missing_weeks,
            "data_completeness": round(data_completeness, 2),
            "weeks_completeness": round(weeks_completeness, 2)
        }

    async def predict(
        self,
        location: str,
        target_date: Optional[datetime] = None,
        db: Session = None
    ) -> Dict:
        """
        녹조 예측 수행
        
        Args:
            location: 위치명
            target_date: 예측할 날짜 (None이면 다음 주)
            db: 데이터베이스 세션
        
        Returns:
            예측 결과 딕셔너리
        """
        if target_date is None:
            target_date = datetime.now() + timedelta(weeks=1)
        
        if db is None:
            db_gen = get_db()
            db = next(db_gen)
            should_close = True
        else:
            should_close = False
        
        try:
            # 사용자 입력을 spatial_classes 한 개로 확정 (예: 강정고령보 -> 강정고령보_다사)
            resolved = self._resolve_location_to_spatial_class(location)
            if resolved:
                if resolved != location:
                    print(f"ℹ 지점 매칭: '{location}' -> '{resolved}'")
                location = resolved
            # 입력 시퀀스 준비
            input_data = self._prepare_input_sequence(location, target_date, db)
            if input_data is None:
                return {
                    "success": False,
                    "error": "예측을 위한 충분한 과거 데이터가 없습니다.",
                    "location": location,
                    "target_date": target_date.isoformat()
                }
            
            X_time_series, temporal_context, spatial_context, data_metadata = input_data
            
            # 데이터 품질 점수 및 신뢰도 레벨 계산
            # 실제 사용된 기준 날짜로 계산 (target_date 또는 latest_date)
            seq_len = self.config['model_hyperparameters']['seq_len']
            feature_order = self.config['features']['feature_order']
            
            # 실제 사용된 기준 날짜 결정
            data_source = data_metadata.get("data_source", "target_date")
            if data_source == "latest_available":
                # 최신 날짜 기준으로 계산
                used_base_date_str = data_metadata.get("used_base_date")
                if used_base_date_str:
                    # ISO 형식 문자열을 datetime으로 변환
                    if isinstance(used_base_date_str, str):
                        if 'T' in used_base_date_str:
                            used_base_date = datetime.fromisoformat(used_base_date_str.replace('Z', '+00:00'))
                        else:
                            used_base_date = datetime.fromisoformat(used_base_date_str)
                    else:
                        used_base_date = used_base_date_str
                else:
                    used_base_date = target_date
            else:
                # target_date 기준으로 계산
                used_base_date = target_date
            
            quality_info = self._calculate_data_quality_score(
                location, used_base_date, seq_len, feature_order, db
            )
            
            # Encoder로 변환
            try:
                temporal_encoded = self.temporal_encoder.transform([temporal_context])[0]
            except ValueError:
                # 새로운 temporal context인 경우 기본값 사용
                temporal_encoded = 0
            
            try:
                spatial_encoded = self.spatial_encoder.transform([spatial_context])[0]
            except ValueError:
                # 새로운 location인 경우 기본값 사용
                spatial_encoded = 0
            
            # 텐서 변환
            X_ts_tensor = torch.tensor(X_time_series, dtype=torch.float32).unsqueeze(0).to(self.device)  # (1, seq_len, num_features)
            temporal_tensor = torch.tensor([temporal_encoded], dtype=torch.long).to(self.device)  # (1,)
            spatial_tensor = torch.tensor([spatial_encoded], dtype=torch.long).to(self.device)  # (1,)
            
            # 예측
            with torch.no_grad():
                predictions = self.model(X_ts_tensor, temporal_tensor, spatial_tensor)
                predictions = predictions.cpu().numpy()[0]  # (num_cyano_vars,)
            
            # log1p 역변환 (전처리 설정에 따라)
            if self.config['preprocessing']['log1p_applied']:
                predictions = np.expm1(predictions)
            
            # 결과 포맷팅
            cyano_vars = self.config['features']['cyano_vars']
            results = {
                "success": True,
                "location": location,
                "target_date": target_date.isoformat(),
                "predictions": {
                    var_name: float(pred_value)
                    for var_name, pred_value in zip(cyano_vars, predictions)
                },
                "metadata": {
                    "model": "TimeSeriesTransformer",
                    "seq_len": self.config['model_hyperparameters']['seq_len'],
                    "log1p_applied": self.config['preprocessing']['log1p_applied'],
                    "data_info": {
                        "db_date_range": data_metadata.get("db_date_range"),
                        "used_base_date": data_metadata.get("used_base_date"),
                        "data_source": data_metadata.get("data_source"),
                        "data_date_range": data_metadata.get("data_date_range")
                    },
                    "quality": quality_info
                }
            }
            
            return results
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "location": location,
                "target_date": target_date.isoformat() if target_date else None
            }
        
        finally:
            if should_close:
                db.close()

