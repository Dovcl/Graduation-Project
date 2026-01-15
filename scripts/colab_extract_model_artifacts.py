"""
Google Colab용 모델 아티팩트 추출 스크립트
Colab에서 실행하여 필요한 파일들을 추출하고 다운로드합니다.
"""

import os
import json
import pickle
import numpy as np
from pathlib import Path
from google.colab import files

def get_save_dir_colab():
    """Colab에서 저장 디렉토리 경로를 반환합니다."""
    save_dir = Path("/content/model_artifacts")
    save_dir.mkdir(parents=True, exist_ok=True)
    return save_dir


def save_model_artifacts_colab(
    scaler,
    temporal_encoder,
    spatial_encoder,
    train_dataset,
    cyano_vars,
    wq_vars,
    model_hyperparams,
    save_dir=None
):
    """
    모델 아티팩트를 저장합니다 (Colab용).
    
    Args:
        scaler: StandardScaler 객체
        temporal_encoder: LabelEncoder 객체 (temporal context)
        spatial_encoder: LabelEncoder 객체 (spatial context)
        train_dataset: TimeSeriesDataset 객체 (encoder 접근용)
        cyano_vars: list, 녹조 변수 리스트
        wq_vars: list, 수질 변수 리스트
        model_hyperparams: dict, 모델 하이퍼파라미터
        save_dir: 저장 디렉토리
    """
    if save_dir is None:
        save_dir = get_save_dir_colab()
    
    print("="*80)
    print("모델 아티팩트 저장 시작 (Google Colab)")
    print(f"저장 디렉토리: {save_dir}")
    print("="*80)
    
    saved_files = []
    
    # 1. Scaler 저장
    scaler_path = save_dir / "scaler.pkl"
    try:
        with open(scaler_path, 'wb') as f:
            pickle.dump(scaler, f)
        print(f"✓ Scaler 저장 완료: {scaler_path}")
        print(f"  파일 크기: {scaler_path.stat().st_size:,} bytes")
        saved_files.append(scaler_path)
    except Exception as e:
        print(f"✗ Scaler 저장 실패: {e}")
        raise
    
    # 2. Temporal Encoder 저장
    temporal_encoder_path = save_dir / "temporal_encoder.pkl"
    if temporal_encoder is None and train_dataset is not None:
        temporal_encoder = train_dataset.temporal_encoder
    if temporal_encoder is None:
        raise ValueError("temporal_encoder를 찾을 수 없습니다.")
    try:
        with open(temporal_encoder_path, 'wb') as f:
            pickle.dump(temporal_encoder, f)
        print(f"✓ Temporal Encoder 저장 완료: {temporal_encoder_path}")
        print(f"  - 클래스 수: {len(temporal_encoder.classes_)}")
        print(f"  - 파일 크기: {temporal_encoder_path.stat().st_size:,} bytes")
        saved_files.append(temporal_encoder_path)
    except Exception as e:
        print(f"✗ Temporal Encoder 저장 실패: {e}")
        raise
    
    # 3. Spatial Encoder 저장
    spatial_encoder_path = save_dir / "spatial_encoder.pkl"
    if spatial_encoder is None and train_dataset is not None:
        spatial_encoder = train_dataset.spatial_encoder
    if spatial_encoder is None:
        raise ValueError("spatial_encoder를 찾을 수 없습니다.")
    try:
        with open(spatial_encoder_path, 'wb') as f:
            pickle.dump(spatial_encoder, f)
        print(f"✓ Spatial Encoder 저장 완료: {spatial_encoder_path}")
        print(f"  - 클래스 수: {len(spatial_encoder.classes_)}")
        print(f"  - 파일 크기: {spatial_encoder_path.stat().st_size:,} bytes")
        saved_files.append(spatial_encoder_path)
    except Exception as e:
        print(f"✗ Spatial Encoder 저장 실패: {e}")
        raise
    
    # 4. Feature 순서 확인
    all_features = cyano_vars + wq_vars
    print(f"\n✓ Feature 순서:")
    for i, feat in enumerate(all_features):
        print(f"  {i}: {feat}")
    
    # 5. 모델 설정 저장
    config = {
        "model_hyperparameters": {
            "d_model": model_hyperparams.get("d_model", 128),
            "nhead": model_hyperparams.get("nhead", 8),
            "num_layers": model_hyperparams.get("num_layers", 4),
            "max_seq_len": model_hyperparams.get("max_seq_len", 7),
            "seq_len": model_hyperparams.get("seq_len", 7),
            "dim_feedforward": model_hyperparams.get("dim_feedforward", 512),
            "dropout": model_hyperparams.get("dropout", 0.1)
        },
        "features": {
            "cyano_vars": cyano_vars,
            "wq_vars": wq_vars,
            "feature_order": all_features,
            "num_features": len(all_features),
            "num_cyano_vars": len(cyano_vars)
        },
        "preprocessing": {
            "log1p_applied": True,
            "target_offset": 1,
            "spatial_col": "지점명_pro",
            "temporal_col": "WoY_dat",
            "scaler_type": "StandardScaler"
        },
        "encoders": {
            "num_spatial_categories": len(spatial_encoder.classes_),
            "num_temporal_categories": len(temporal_encoder.classes_),
            "spatial_classes": spatial_encoder.classes_.tolist(),
            "temporal_classes": temporal_encoder.classes_.tolist()
        },
        "model_path": "models/TimeSeriesTransformer_best.pth"
    }
    
    config_path = save_dir / "model_config.json"
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"\n✓ 모델 설정 저장 완료: {config_path}")
        print(f"  파일 크기: {config_path.stat().st_size:,} bytes")
        saved_files.append(config_path)
    except Exception as e:
        print(f"✗ 모델 설정 저장 실패: {e}")
        raise
    
    print("\n" + "="*80)
    print("모든 아티팩트 저장 완료!")
    print("="*80)
    print(f"\n저장된 파일:")
    for f in saved_files:
        print(f"  - {f.name}")
    
    return config, saved_files


def extract_from_notebook_context_colab():
    """
    Colab 노트북의 전역 변수에서 필요한 객체들을 추출하여 저장합니다.
    """
    try:
        import __main__ as main_module
        
        print("\n" + "="*80)
        print("변수 확인 중...")
        print("="*80)
        
        # 필수 변수 확인
        required_vars = ['scaler', 'train_dataset', 'cyano_vars', 'wq_vars']
        missing_vars = [var for var in required_vars if not hasattr(main_module, var)]
        if missing_vars:
            raise ValueError(f"필수 변수가 없습니다: {missing_vars}")
        
        print("✓ 모든 필수 변수 확인 완료")
        
        # 변수 가져오기
        scaler = main_module.scaler
        train_dataset = main_module.train_dataset
        cyano_vars = main_module.cyano_vars
        wq_vars = main_module.wq_vars
        
        print(f"✓ scaler 타입: {type(scaler)}")
        print(f"✓ train_dataset 타입: {type(train_dataset)}")
        print(f"✓ cyano_vars 개수: {len(cyano_vars)}")
        print(f"✓ wq_vars 개수: {len(wq_vars)}")
        
        # 하이퍼파라미터 가져오기
        model_hyperparams = {
            "d_model": getattr(main_module, 'TST_d_model', 128),
            "nhead": getattr(main_module, 'TST_nhead', 8),
            "num_layers": getattr(main_module, 'TST_num_layers', 4),
            "max_seq_len": getattr(main_module, 'TST_seq_len', 7),
            "seq_len": getattr(main_module, 'TST_seq_len', 7),
            "dim_feedforward": getattr(main_module, 'TST_dim_feedforward', 512),
            "dropout": getattr(main_module, 'TST_dropout', 0.1)
        }
        
        print(f"✓ 하이퍼파라미터: {model_hyperparams}")
        
        # 저장 실행
        print("\n" + "="*80)
        config, saved_files = save_model_artifacts_colab(
            scaler=scaler,
            temporal_encoder=None,
            spatial_encoder=None,
            train_dataset=train_dataset,
            cyano_vars=cyano_vars,
            wq_vars=wq_vars,
            model_hyperparams=model_hyperparams
        )
        
        # 저장 확인
        print("\n" + "="*80)
        print("저장 확인 중...")
        print("="*80)
        for filepath in saved_files:
            if filepath.exists():
                size = filepath.stat().st_size
                print(f"✓ {filepath.name} 저장됨 ({size:,} bytes)")
            else:
                print(f"✗ {filepath.name} 저장 실패!")
        
        return config, saved_files
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def download_files_colab(file_paths):
    """
    Colab에서 파일들을 다운로드합니다.
    
    Args:
        file_paths: 다운로드할 파일 경로 리스트
    """
    print("\n" + "="*80)
    print("파일 다운로드 시작")
    print("="*80)
    
    for filepath in file_paths:
        if filepath.exists():
            print(f"다운로드 중: {filepath.name}")
            files.download(str(filepath))
        else:
            print(f"⚠ 파일 없음: {filepath}")


def create_zip_colab(save_dir=None):
    """
    저장된 파일들을 zip으로 압축합니다.
    
    Args:
        save_dir: 저장 디렉토리
    """
    import zipfile
    
    if save_dir is None:
        save_dir = get_save_dir_colab()
    
    zip_path = save_dir.parent / "model_artifacts.zip"
    
    print(f"\n압축 파일 생성 중: {zip_path}")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in save_dir.glob("*"):
            if file_path.is_file():
                zipf.write(file_path, file_path.name)
                print(f"  - {file_path.name} 추가됨")
    
    print(f"✓ 압축 완료: {zip_path}")
    return zip_path

