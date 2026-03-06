#!/usr/bin/env python3
"""
RAG 평가용 청크 레퍼런스 추출
- 인덱싱과 동일한 방식으로 문서를 로드·청킹한 뒤 JSON으로 저장
- 사용: python scripts/export_chunks_for_eval.py --manual
        python scripts/export_chunks_for_eval.py --pdf path/to/doc.pdf
        python scripts/export_chunks_for_eval.py --text path/to/doc.txt
"""
import sys
import os
import json
import argparse
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

from app.services.rag_service_langchain import RAGServiceLangChain
from langchain_core.documents import Document as LangChainDocument

# index_documents_langchain.py --manual 과 동일한 문서
MANUAL_DOCS = [
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


def main():
    parser = argparse.ArgumentParser(description="RAG 평가용 청크 추출")
    parser.add_argument("--manual", action="store_true", help="index_manual_documents와 동일한 3개 문서 사용")
    parser.add_argument("--pdf", type=str, help="PDF 파일 경로")
    parser.add_argument("--text", type=str, help="텍스트 파일 경로")
    parser.add_argument("--out", type=str, default=None, help="출력 JSON 경로 (기본: eval/chunk_reference.json)")
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else Path(__file__).resolve().parent.parent / "eval" / "chunk_reference.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rag = RAGServiceLangChain()
    documents = []

    if args.manual:
        for doc_info in MANUAL_DOCS:
            documents.append(LangChainDocument(
                page_content=doc_info["content"].strip(),
                metadata={
                    "title": doc_info["title"],
                    "source": doc_info["source"],
                    "doc_type": doc_info["doc_type"]
                }
            ))
        print(f"--manual: 문서 {len(documents)}개 로드")
    elif args.pdf:
        if not Path(args.pdf).exists():
            print(f"파일 없음: {args.pdf}")
            return 1
        documents = rag.load_pdf_file(args.pdf, extract_tables=True)
    elif args.text:
        if not Path(args.text).exists():
            print(f"파일 없음: {args.text}")
            return 1
        documents = rag.load_text_file(args.text)
    else:
        print("--manual, --pdf, 또는 --text 중 하나를 지정하세요.")
        return 1

    if not documents:
        print("로드된 문서가 없습니다.")
        return 1

    chunks = rag.chunk_documents(documents)
    refs = []
    default_source = "manual" if args.manual else (args.pdf or args.text or "")
    for i, c in enumerate(chunks):
        refs.append({
            "chunk_index": i,
            "content": c.page_content,
            "source": c.metadata.get("source", default_source),
            "metadata": {k: v for k, v in c.metadata.items() if k != "source"}
        })

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(refs, f, ensure_ascii=False, indent=2)
    print(f"저장 완료: {out_path} (청크 {len(refs)}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
