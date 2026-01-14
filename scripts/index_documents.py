#!/usr/bin/env python3
"""
문서 인덱싱 스크립트
기존 문서를 벡터로 변환하여 데이터베이스에 저장
"""
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.database import SessionLocal, init_db
from app.services.rag_service import RAGService
from app.models.documents import Document


def index_document(title: str, content: str, source: str = None, doc_type: str = None):
    """단일 문서 인덱싱"""
    db = SessionLocal()
    rag_service = RAGService()
    
    try:
        # 문서 추가
        doc = rag_service.add_document(
            title=title,
            content=content,
            source=source,
            doc_type=doc_type,
            db=db
        )
        print(f"✓ 인덱싱 완료: {title}")
        return doc
    except Exception as e:
        print(f"✗ 오류 발생 ({title}): {e}")
        db.rollback()
        return None
    finally:
        db.close()


def index_from_file(file_path: str, source: str = None, doc_type: str = None):
    """파일에서 문서 읽어서 인덱싱"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        title = os.path.basename(file_path)
        return index_document(title, content, source, doc_type)
    except Exception as e:
        print(f"✗ 파일 읽기 오류 ({file_path}): {e}")
        return None


def main():
    """메인 함수"""
    print("=" * 50)
    print("문서 인덱싱 스크립트")
    print("=" * 50)
    
    # 데이터베이스 초기화 (테이블 생성)
    print("\n1. 데이터베이스 초기화 중...")
    init_db()
    print("✓ 데이터베이스 초기화 완료")
    
    # 예시 문서 인덱싱
    print("\n2. 예시 문서 인덱싱 중...")
    
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
            """,
            "source": "운영 매뉴얼",
            "doc_type": "manual"
        }
    ]
    
    for doc_info in example_docs:
        index_document(**doc_info)
    
    print("\n" + "=" * 50)
    print("✓ 문서 인덱싱 완료!")
    print("=" * 50)


if __name__ == "__main__":
    main()

