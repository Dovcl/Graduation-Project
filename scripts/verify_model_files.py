"""
모델 파일 검증 스크립트
추출된 파일들이 올바른지 확인합니다.
"""

import os
import json
import pickle
import torch
import numpy as np
from pathlib import Path
from sklearn.preprocessing import StandardScaler, LabelEncoder


def verify_model_files(models_dir=None):
    """
    모델 파일들을 검증합니다.
    
    Args:
        models_dir: 모델 파일이 있는 디렉토리 (None이면 자동 탐색)
    """
    print("="*80)
    print("모델 파일 검증 시작")
    print("="*80)
    
    # 디렉토리 찾기
    if models_dir is None:
        # 가능한 경로들
        possible_dirs = [
            Path(__file__).parent.parent / "backend" / "models",
            Path(os.getcwd()) / "rag-chatbot" / "backend" / "models",
            Path(os.getcwd()) / "backend" / "models",
            Path(os.getcwd()) / "models",
            Path("rag-chatbot/backend/models"),
            Path("backend/models"),
            Path("models"),
        ]
        
        # 현재 디렉토리에서 재귀적으로 찾기
        current_dir = Path(os.getcwd())
        for pattern in ["**/model_config.json", "**/scaler.pkl"]:
            for found_file in current_dir.glob(pattern):
                found_dir = found_file.parent
                if found_dir not in possible_dirs:
                    possible_dirs.append(found_dir)
        
        for dir_path in possible_dirs:
            if dir_path.exists() and (dir_path / "model_config.json").exists():
                models_dir = dir_path
                break
        
        if models_dir is None:
            print("❌ 모델 디렉토리를 찾을 수 없습니다.")
            print("\n다음 위치들을 확인했습니다:")
            for dir_path in possible_dirs:
                exists = dir_path.exists()
                has_config = (dir_path / "model_config.json").exists() if exists else False
                status = "✓" if has_config else ("존재" if exists else "없음")
                print(f"  {status} {dir_path.absolute()}")
            
            print("\n💡 해결 방법:")
            print("  1. 파일이 있는 디렉토리 경로를 직접 지정:")
            print("     python verify_model_files.py /path/to/models")
            print("  2. 또는 파일들을 다음 위치에 복사:")
            print(f"     {Path(__file__).parent.parent / 'backend' / 'models'}")
            return False
    else:
        models_dir = Path(models_dir)
    
    print(f"\n✓ 모델 디렉토리: {models_dir.absolute()}")
    
    # 필수 파일 목록
    required_files = {
        "model_config.json": "모델 설정",
        "scaler.pkl": "StandardScaler",
        "temporal_encoder.pkl": "Temporal Encoder",
        "spatial_encoder.pkl": "Spatial Encoder",
        "TimeSeriesTransformer_best.pth": "모델 가중치"
    }
    
    print("\n" + "="*80)
    print("파일 존재 확인")
    print("="*80)
    
    missing_files = []
    existing_files = {}
    
    for filename, description in required_files.items():
        filepath = models_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            existing_files[filename] = filepath
            print(f"✓ {filename:40s} ({size:>10,} bytes) - {description}")
        else:
            missing_files.append(filename)
            print(f"✗ {filename:40s} {'없음':>10} - {description}")
    
    if missing_files:
        print(f"\n❌ 누락된 파일 {len(missing_files)}개: {missing_files}")
        return False
    
    print("\n✓ 모든 필수 파일이 존재합니다!")
    
    # 파일 내용 검증
    print("\n" + "="*80)
    print("파일 내용 검증")
    print("="*80)
    
    try:
        # 1. Config 파일 검증
        print("\n[1] model_config.json 검증 중...")
        with open(existing_files["model_config.json"], 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 필수 키 확인
        required_keys = [
            "model_hyperparameters",
            "features",
            "preprocessing",
            "encoders"
        ]
        
        for key in required_keys:
            if key not in config:
                print(f"  ✗ 필수 키 없음: {key}")
                return False
        
        print("  ✓ JSON 구조 올바름")
        print(f"  ✓ d_model: {config['model_hyperparameters']['d_model']}")
        print(f"  ✓ seq_len: {config['model_hyperparameters']['seq_len']}")
        print(f"  ✓ cyano_vars 개수: {len(config['features']['cyano_vars'])}")
        print(f"  ✓ wq_vars 개수: {len(config['features']['wq_vars'])}")
        print(f"  ✓ feature_order 개수: {len(config['features']['feature_order'])}")
        print(f"  ✓ log1p_applied: {config['preprocessing']['log1p_applied']}")
        
        # 2. Scaler 검증
        print("\n[2] scaler.pkl 검증 중...")
        with open(existing_files["scaler.pkl"], 'rb') as f:
            scaler = pickle.load(f)
        
        if not isinstance(scaler, StandardScaler):
            print(f"  ✗ 타입 오류: StandardScaler가 아님 (실제: {type(scaler)})")
            return False
        
        print("  ✓ StandardScaler 타입 올바름")
        if hasattr(scaler, 'mean_') and scaler.mean_ is not None:
            print(f"  ✓ mean_ shape: {scaler.mean_.shape}")
        if hasattr(scaler, 'scale_') and scaler.scale_ is not None:
            print(f"  ✓ scale_ shape: {scaler.scale_.shape}")
        
        # 3. Temporal Encoder 검증
        print("\n[3] temporal_encoder.pkl 검증 중...")
        with open(existing_files["temporal_encoder.pkl"], 'rb') as f:
            temporal_encoder = pickle.load(f)
        
        if not isinstance(temporal_encoder, LabelEncoder):
            print(f"  ✗ 타입 오류: LabelEncoder가 아님 (실제: {type(temporal_encoder)})")
            return False
        
        print("  ✓ LabelEncoder 타입 올바름")
        print(f"  ✓ 클래스 수: {len(temporal_encoder.classes_)}")
        print(f"  ✓ 클래스 샘플: {temporal_encoder.classes_[:5].tolist()}...")
        
        # 4. Spatial Encoder 검증
        print("\n[4] spatial_encoder.pkl 검증 중...")
        with open(existing_files["spatial_encoder.pkl"], 'rb') as f:
            spatial_encoder = pickle.load(f)
        
        if not isinstance(spatial_encoder, LabelEncoder):
            print(f"  ✗ 타입 오류: LabelEncoder가 아님 (실제: {type(spatial_encoder)})")
            return False
        
        print("  ✓ LabelEncoder 타입 올바름")
        print(f"  ✓ 클래스 수: {len(spatial_encoder.classes_)}")
        print(f"  ✓ 클래스 샘플: {spatial_encoder.classes_[:5].tolist()}...")
        
        # 5. 모델 가중치 검증
        print("\n[5] TimeSeriesTransformer_best.pth 검증 중...")
        try:
            state_dict = torch.load(existing_files["TimeSeriesTransformer_best.pth"], 
                                  map_location='cpu', 
                                  weights_only=False)
            
            if not isinstance(state_dict, dict):
                print(f"  ✗ 타입 오류: dict가 아님 (실제: {type(state_dict)})")
                return False
            
            print("  ✓ PyTorch state_dict 타입 올바름")
            print(f"  ✓ 가중치 키 개수: {len(state_dict)}")
            
            # 주요 레이어 확인
            expected_keys = [
                "input_projection.weight",
                "temporal_embedding.weight",
                "spatial_embedding.weight",
                "transformer.layers.0.self_attn.in_proj_weight",
                "output_head.1.weight"
            ]
            
            found_keys = []
            for key in expected_keys:
                if any(key in k for k in state_dict.keys()):
                    found_keys.append(key)
            
            print(f"  ✓ 예상 레이어 {len(found_keys)}/{len(expected_keys)}개 발견")
            
            # 가중치 shape 확인
            sample_key = list(state_dict.keys())[0]
            print(f"  ✓ 샘플 키: {sample_key}, shape: {state_dict[sample_key].shape}")
            
        except Exception as e:
            print(f"  ✗ 모델 로드 실패: {e}")
            return False
        
        # 6. Config와 Encoder 일치 확인
        print("\n[6] Config와 Encoder 일치 확인 중...")
        config_temporal_count = config['encoders']['num_temporal_categories']
        config_spatial_count = config['encoders']['num_spatial_categories']
        actual_temporal_count = len(temporal_encoder.classes_)
        actual_spatial_count = len(spatial_encoder.classes_)
        
        if config_temporal_count != actual_temporal_count:
            print(f"  ✗ Temporal 카테고리 수 불일치: config={config_temporal_count}, encoder={actual_temporal_count}")
            return False
        
        if config_spatial_count != actual_spatial_count:
            print(f"  ✗ Spatial 카테고리 수 불일치: config={config_spatial_count}, encoder={actual_spatial_count}")
            return False
        
        print(f"  ✓ Temporal 카테고리 수 일치: {actual_temporal_count}")
        print(f"  ✓ Spatial 카테고리 수 일치: {actual_spatial_count}")
        
        # 7. Feature 순서 확인
        print("\n[7] Feature 순서 확인 중...")
        feature_order = config['features']['feature_order']
        cyano_vars = config['features']['cyano_vars']
        wq_vars = config['features']['wq_vars']
        
        expected_order = cyano_vars + wq_vars
        
        if feature_order != expected_order:
            print(f"  ⚠ Feature 순서가 예상과 다릅니다.")
            print(f"    Config: {feature_order[:3]}...")
            print(f"    예상: {expected_order[:3]}...")
        else:
            print(f"  ✓ Feature 순서 올바름: {len(feature_order)}개")
            print(f"    - cyano_vars: {len(cyano_vars)}개")
            print(f"    - wq_vars: {len(wq_vars)}개")
        
        print("\n" + "="*80)
        print("✅ 모든 파일 검증 완료!")
        print("="*80)
        print("\n요약:")
        print(f"  - 모델 디렉토리: {models_dir.absolute()}")
        print(f"  - 파일 개수: {len(existing_files)}개")
        print(f"  - 모델 하이퍼파라미터: d_model={config['model_hyperparameters']['d_model']}, seq_len={config['model_hyperparameters']['seq_len']}")
        print(f"  - Feature 개수: {len(feature_order)}개")
        print(f"  - Temporal 카테고리: {actual_temporal_count}개")
        print(f"  - Spatial 카테고리: {actual_spatial_count}개")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 검증 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    
    # 명령줄 인자로 디렉토리 지정 가능
    if len(sys.argv) > 1:
        models_dir = Path(sys.argv[1])
    else:
        models_dir = None
    
    success = verify_model_files(models_dir)
    sys.exit(0 if success else 1)

