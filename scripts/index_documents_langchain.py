#!/usr/bin/env python3
"""
LangChain 기반 문서 인덱싱 스크립트
엑셀, 텍스트 파일 등을 벡터화하여 PGVector에 저장
"""
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.database import SessionLocal, init_db
from app.services.rag_service_langchain import RAGServiceLangChain


def index_excel_file(file_path: str, collection_name: str = "documents"):
    """엑셀 파일 인덱싱"""
    print(f"\n[엑셀 파일 인덱싱]")
    print(f"파일: {file_path}")
    
    if not Path(file_path).exists():
        print(f"✗ 파일을 찾을 수 없습니다: {file_path}")
        return False
    
    rag_service = RAGServiceLangChain()
    
    try:
        # 엑셀 파일 로드
        documents = rag_service.load_excel_file(file_path)
        print(f"✓ 로드된 문서: {len(documents)}개")
        
        if not documents:
            print("⚠ 문서가 없습니다.")
            return False
        
        # 인덱싱
        print(f"청킹 및 벡터화 중...")
        vectorstore = rag_service.index_documents(
            documents, 
            collection_name=collection_name
        )
        
        print(f"✓ 인덱싱 완료: {collection_name}")
        return True
    
    except Exception as e:
        print(f"✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


def index_text_file(file_path: str, collection_name: str = "documents"):
    """텍스트 파일 인덱싱"""
    print(f"\n[텍스트 파일 인덱싱]")
    print(f"파일: {file_path}")
    
    if not Path(file_path).exists():
        print(f"✗ 파일을 찾을 수 없습니다: {file_path}")
        return False
    
    rag_service = RAGServiceLangChain()
    
    try:
        # 텍스트 파일 로드
        documents = rag_service.load_text_file(file_path)
        print(f"✓ 로드된 문서: {len(documents)}개")
        
        if not documents:
            print("⚠ 문서가 없습니다.")
            return False
        
        # 인덱싱
        print(f"청킹 및 벡터화 중...")
        vectorstore = rag_service.index_documents(
            documents, 
            collection_name=collection_name
        )
        
        print(f"✓ 인덱싱 완료: {collection_name}")
        return True
    
    except Exception as e:
        print(f"✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


def index_manual_documents(collection_name: str = "documents"):
    """예시 매뉴얼 문서 인덱싱"""
    print(f"\n[예시 매뉴얼 문서 인덱싱]")
    
    rag_service = RAGServiceLangChain()
    
    example_docs = [
        {
            "title": "녹조 가이드라인",
            "content": """
            녹조 현상은 수온이 높고 영양염류가 풍부한 환경에서 발생합니다.
            녹조 농도가 높을 때는 다음과 같은 조치를 취해야 합니다:
            1. 취수 중단
            2. 정수 처리 강화
            3. 주민 안내
            4. 모니터링 강화
            
            경보 단계별 대응:
            - 관심: 주의 관찰
            - 주의: 취수량 조절
            - 경보: 취수 중단 검토
            - 심각: 취수 중단
            """,
            "source": "환경부 가이드라인",
            "doc_type": "guideline"
        },
        {
            "title": "수질 측정 방법",
            "content": """
            수질 측정은 매일 정해진 시간에 실시합니다.
            측정 항목: pH, DO, BOD, COD, T-N, T-P 등
            측정 위치: 취수구, 정수장 입구, 정수장 출구
            측정 결과는 즉시 기록하고 이상 시 보고합니다.
            
            수질 등급 기준:
            - I등급: pH 6.5~8.5, BOD ≤1.0, T-N ≤0.2, T-P ≤0.02
            - II등급: pH 6.0~9.0, BOD ≤2.0, T-N ≤0.3, T-P ≤0.04
            - III등급: pH 5.5~9.5, BOD ≤3.0, T-N ≤0.5, T-P ≤0.1
            """,
            "source": "운영 매뉴얼",
            "doc_type": "manual"
        },
        {
            "title": "녹조 예측 모델 사용법",
            "content": """
            시계열 예측 모델을 사용하여 다음주 녹조 농도를 예측할 수 있습니다.
            
            사용 방법:
            1. 위치를 지정하세요 (예: 강정고령보)
            2. "다음주 예측" 또는 "1주 뒤 예측"이라고 질문하세요
            3. 모델이 과거 7주 데이터를 기반으로 예측합니다
            
            필요한 데이터:
            - 최근 7주 이상의 과거 데이터
            - 9개 변수: 유해남조류, Microcystis, Anabaena, Oscillatoria, 
              Aphanizomenon, 수온, DO, TN, TP
            """,
            "source": "모델 가이드",
            "doc_type": "guide"
        }
    ]
    
    try:
        success_count = 0
        for doc_info in example_docs:
            result = rag_service.add_document(
                title=doc_info["title"],
                content=doc_info["content"],
                source=doc_info["source"],
                doc_type=doc_info["doc_type"],
                collection_name=collection_name
            )
            if result:
                print(f"✓ 인덱싱 완료: {doc_info['title']}")
                success_count += 1
            else:
                print(f"✗ 인덱싱 실패: {doc_info['title']}")
        
        print(f"\n✓ 총 {success_count}/{len(example_docs)}개 문서 인덱싱 완료")
        return success_count > 0
    
    except Exception as e:
        print(f"✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LangChain 기반 문서 인덱싱")
    parser.add_argument(
        "--excel",
        type=str,
        help="인덱싱할 엑셀 파일 경로"
    )
    parser.add_argument(
        "--text",
        type=str,
        help="인덱싱할 텍스트 파일 경로"
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="예시 매뉴얼 문서 인덱싱"
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="documents",
        help="컬렉션 이름 (기본값: documents)"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("LangChain 기반 문서 인덱싱 스크립트")
    print("=" * 80)
    
    # 데이터베이스 초기화
    print("\n1. 데이터베이스 초기화 중...")
    init_db()
    print("✓ 데이터베이스 초기화 완료")
    
    success = False
    
    # 엑셀 파일 인덱싱
    if args.excel:
        success = index_excel_file(args.excel, args.collection) or success
    
    # 텍스트 파일 인덱싱
    if args.text:
        success = index_text_file(args.text, args.collection) or success
    
    # 예시 매뉴얼 인덱싱
    if args.manual:
        success = index_manual_documents(args.collection) or success
    
    # 아무것도 지정하지 않으면 예시 매뉴얼 인덱싱
    if not args.excel and not args.text and not args.manual:
        print("\n⚠ 인덱싱할 파일이 지정되지 않았습니다.")
        print("예시 매뉴얼 문서를 인덱싱합니다...")
        success = index_manual_documents(args.collection)
    
    print("\n" + "=" * 80)
    if success:
        print("✅ 문서 인덱싱 완료!")
    else:
        print("❌ 문서 인덱싱 실패")
    print("=" * 80)


if __name__ == "__main__":
    main()

