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
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.time_series_transformer import TimeSeriesTransformer
from app.database import get_db
from app.models.env_data import EnvironmentalData
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
    
    def _prepare_input_sequence(
        self,
        location: str,
        target_date: datetime,
        db: Session
    ) -> Optional[Tuple[np.ndarray, str, str]]:
        """
        예측을 위한 입력 시퀀스 준비
        
        Args:
            location: 위치명
            target_date: 예측할 날짜
            db: 데이터베이스 세션
        
        Returns:
            (X_time_series, temporal_context, spatial_context) 또는 None
        """
        seq_len = self.config['model_hyperparameters']['seq_len']
        feature_order = self.config['features']['feature_order']
        cyano_vars = self.config['features']['cyano_vars']
        wq_vars = self.config['features']['wq_vars']
        
        # 과거 7주 데이터 조회 (t-6 ~ t)
        # 각 주의 데이터를 조회하여 시퀀스 구성
        X_time_series = []
        
        for week_offset in range(seq_len, 0, -1):  # t-6, t-5, ..., t-1, t
            week_start = target_date - timedelta(weeks=week_offset)
            week_end = target_date - timedelta(weeks=week_offset-1)
            
            # 해당 주의 데이터 조회
            query = db.query(EnvironmentalData).filter(
                EnvironmentalData.location.contains(location),
                EnvironmentalData.date >= week_start.date(),
                EnvironmentalData.date < week_end.date()
            )
            
            week_data = query.all()
            
            if not week_data:
                return None  # 해당 주의 데이터가 없음
            
            # 주간 평균 계산 (data_type별로)
            week_values = {}
            
            # cyano_vars와 wq_vars를 data_type으로 매핑
            # 실제 데이터베이스 구조에 맞게 조정 필요
            for var in feature_order:
                # data_type으로 필터링하여 값 추출
                # 실제 구현은 데이터베이스 스키마에 맞게 조정 필요
                values = []
                for d in week_data:
                    # data_type이 var와 일치하는 경우
                    if hasattr(d, 'data_type') and d.data_type == var:
                        if d.value is not None:
                            values.append(d.value)
                
                week_values[var] = np.mean(values) if values else 0.0
            
            # Feature 순서대로 값 추출
            feature_values = [week_values.get(var, 0.0) for var in feature_order]
            X_time_series.append(feature_values)
        
        X_time_series = np.array(X_time_series, dtype=np.float32)  # (seq_len, num_features)
        
        # log1p 적용 (전처리 설정에 따라)
        if self.config['preprocessing']['log1p_applied']:
            X_time_series = np.log1p(X_time_series)
        
        # Scaler 적용
        X_time_series_reshaped = X_time_series.reshape(-1, len(feature_order))
        X_time_series_scaled = self.scaler.transform(X_time_series_reshaped).reshape(seq_len, len(feature_order))
        
        # Temporal context (마지막 주차)
        last_week_date = target_date - timedelta(weeks=1)
        temporal_context = self._get_week_of_year(last_week_date)
        
        # Spatial context
        spatial_context = location
        
        return X_time_series_scaled, temporal_context, spatial_context
    
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
            # 입력 시퀀스 준비
            input_data = self._prepare_input_sequence(location, target_date, db)
            if input_data is None:
                return {
                    "success": False,
                    "error": "예측을 위한 충분한 과거 데이터가 없습니다.",
                    "location": location,
                    "target_date": target_date.isoformat()
                }
            
            X_time_series, temporal_context, spatial_context = input_data
            
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
                    "log1p_applied": self.config['preprocessing']['log1p_applied']
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

