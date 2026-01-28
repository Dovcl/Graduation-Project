"""
시각화 관련 API 엔드포인트
PNG 이미지 다운로드 기능
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import Response
from typing import Optional
from datetime import datetime, timedelta
import io
import matplotlib
matplotlib.use('Agg')  # 백엔드에서 사용 (GUI 없음)
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import platform

# 한글 폰트 설정 (경고 무시하고 진행)
import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')

if platform.system() == 'Darwin':  # macOS
    plt.rcParams['font.family'] = 'AppleGothic'
elif platform.system() == 'Windows':
    plt.rcParams['font.family'] = 'Malgun Gothic'
else:  # Linux
    plt.rcParams['font.family'] = 'DejaVu Sans'
    
plt.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.viz_query import get_timeseries_data
from app.services.prediction_service import PredictionService

router = APIRouter()


@router.get("/visualizations/export-png")
async def export_visualization_png(
    location: str = Query(..., description="지점명"),
    target_date: Optional[str] = Query(None, description="예측 대상 날짜 (YYYY-MM-DD)"),
    variable: str = Query("유해남조류 세포수 (cells/㎖)", description="변수명"),
    db: Session = Depends(get_db)
):
    """
    시각화를 PNG 이미지로 다운로드
    
    노트북과 동일한 스타일의 시계열 플롯 생성
    """
    try:
        print(f"PNG 생성 요청: location={location}, target_date={target_date}, variable={variable}")
        
        # 날짜 파싱
        if target_date:
            try:
                pred_date = datetime.fromisoformat(target_date)
            except ValueError:
                # YYYY-MM-DD 형식으로 파싱 시도
                pred_date = datetime.strptime(target_date, "%Y-%m-%d")
        else:
            pred_date = datetime.now()
        
        print(f"예측 날짜: {pred_date}")
        
        # 예측 수행
        prediction_service = PredictionService()
        prediction_result = await prediction_service.predict(
            location=location,
            target_date=pred_date,
            db=db
        )
        
        print(f"예측 결과: success={prediction_result.get('success') if prediction_result else False}")
        
        if not prediction_result or not prediction_result.get("success"):
            raise HTTPException(status_code=400, detail="예측 실패")
        
        # 시계열 데이터 조회
        start_date = pred_date - timedelta(weeks=52)
        end_date = pred_date
        
        timeseries_data = get_timeseries_data(
            location, variable, start_date, end_date, db, limit=52
        )
        
        print(f"시계열 데이터: labels={len(timeseries_data.get('labels', []))}, observed={len(timeseries_data.get('observed', []))}")
        
        # 예측값 추가
        predictions = prediction_result.get("predictions", {})
        pred_value = predictions.get(variable)
        
        if pred_value is not None:
            # 예측 날짜 추가
            days_until_monday = (7 - pred_date.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            prediction_date = pred_date + timedelta(days=days_until_monday)
            prediction_date_str = prediction_date.isoformat()
            
            if prediction_date_str not in timeseries_data["labels"]:
                timeseries_data["labels"].append(prediction_date_str)
                timeseries_data["observed"].append(None)
                timeseries_data["predicted"].append(float(pred_value))
            else:
                idx = timeseries_data["labels"].index(prediction_date_str)
                timeseries_data["predicted"][idx] = float(pred_value)
        
        # matplotlib로 플롯 생성
        fig, ax = plt.subplots(figsize=(14, 6))
        
        # 날짜 인덱스
        time_index = np.arange(len(timeseries_data["labels"]))
        
        # 관측값 플롯 (파란색) - None 값 제외
        observed = timeseries_data["observed"]
        observed_valid = [(i, v) for i, v in enumerate(observed) if v is not None]
        if observed_valid:
            obs_indices = [x[0] for x in observed_valid]
            obs_values = [x[1] for x in observed_valid]
            try:
                ax.plot(obs_indices, obs_values, 'o-', color='#4A90E2', 
                        label='관측값', linewidth=2, markersize=4, alpha=0.7)
            except:
                ax.plot(obs_indices, obs_values, 'o-', color='#4A90E2', 
                        label='Observed', linewidth=2, markersize=4, alpha=0.7)
        
        # 예측값 플롯 (빨간색, 점선) - None 값 제외
        predicted = timeseries_data["predicted"]
        predicted_valid = [(i, v) for i, v in enumerate(predicted) if v is not None]
        if predicted_valid:
            pred_indices = [x[0] for x in predicted_valid]
            pred_values = [x[1] for x in predicted_valid]
            try:
                ax.plot(pred_indices, pred_values, 's--', color='#E74C3C', 
                        label='예측값', linewidth=2, markersize=4, alpha=0.7)
            except:
                ax.plot(pred_indices, pred_values, 's--', color='#E74C3C', 
                        label='Predicted', linewidth=2, markersize=4, alpha=0.7)
        
        # 축 레이블 및 제목
        ax.set_xlabel('날짜', fontsize=12)
        ax.set_ylabel(f'{variable}', fontsize=12)
        ax.set_title(f'{location} - {variable} (시계열 예측)', 
                    fontsize=14, fontweight='bold')
        
        # 그리드 및 범례
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=10, loc='best')
        
        # X축 라벨 (날짜)
        if len(timeseries_data["labels"]) <= 20:
            ax.set_xticks(time_index)
            ax.set_xticklabels(
                [d.split('T')[0][5:] for d in timeseries_data["labels"]], 
                rotation=45, ha='right'
            )
        else:
            step = max(1, len(timeseries_data["labels"]) // 10)
            ax.set_xticks(time_index[::step])
            ax.set_xticklabels(
                [timeseries_data["labels"][i].split('T')[0][5:] 
                 for i in range(0, len(timeseries_data["labels"]), step)], 
                rotation=45, ha='right'
            )
        
        plt.tight_layout()
        
        # PNG로 변환
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        # 응답 반환 (한글 파일명 인코딩 문제 해결)
        from urllib.parse import quote
        safe_filename = f"prediction_{pred_date.strftime('%Y%m%d')}.png"
        encoded_filename = quote(safe_filename)
        
        return Response(
            content=buffer.getvalue(),
            media_type="image/png",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{encoded_filename}'
            }
        )
    
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"PNG 생성 오류: {error_detail}")
        raise HTTPException(status_code=500, detail=f"이미지 생성 실패: {str(e)}")

