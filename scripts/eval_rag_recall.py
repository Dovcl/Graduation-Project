#!/usr/bin/env python3
"""
RAG Recall@k 평가 스크립트
- eval/rag_eval_questions.json, eval/chunk_reference.json 사용
- asyncio로 search 호출 후 Recall@3, Recall@5 계산
"""
import sys
import os
import json
import asyncio
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

from app.services.rag_service_langchain import RAGServiceLangChain


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_hit(retrieved_content: str, ref_content: str, min_overlap: int = 150) -> bool:
    """검색 결과가 정답 청크와 같은지 여부 (내용 겹침으로 판단)"""
    if not retrieved_content or not ref_content:
        return False
    # 정답 청크 앞부분이 검색 결과에 포함되면 같은 청크로 간주
    fingerprint = ref_content[:min_overlap].strip()
    if len(fingerprint) < 50:
        fingerprint = ref_content[:300].strip()
    return fingerprint in retrieved_content or retrieved_content[:min_overlap].strip() in ref_content


async def main():
    base = Path(__file__).resolve().parent.parent
    questions_path = base / "eval" / "rag_eval_questions.json"
    chunks_path = base / "eval" / "chunk_reference.json"

    if not questions_path.exists():
        print(f"질문 파일 없음: {questions_path}")
        return 1
    if not chunks_path.exists():
        print(f"청크 레퍼런스 없음: {chunks_path} (먼저 export_chunks_for_eval.py 실행)")
        return 1

    questions = load_json(questions_path)
    chunk_refs = load_json(chunks_path)
    rag = RAGServiceLangChain()

    hit_at_3 = 0
    hit_at_5 = 0
    n = len(questions)

    for item in questions:
        q = item["question"]
        gt_indices = set(item.get("ground_truth_chunk_indices", []))
        if not gt_indices:
            continue

        docs = await rag.search(q, top_k=5)
        gt_contents = [chunk_refs[i]["content"] for i in gt_indices if i < len(chunk_refs)]

        found_in_3 = False
        found_in_5 = False
        for i, doc in enumerate(docs):
            content = doc.get("content", "")
            for gt in gt_contents:
                if is_hit(content, gt):
                    if i < 5:
                        found_in_5 = True
                    if i < 3:
                        found_in_3 = True
                    break

        if found_in_3:
            hit_at_3 += 1
        if found_in_5:
            hit_at_5 += 1

    recall_3 = hit_at_3 / n if n else 0
    recall_5 = hit_at_5 / n if n else 0
    print(f"Recall@3: {recall_3:.2f} ({hit_at_3}/{n})")
    print(f"Recall@5: {recall_5:.2f} ({hit_at_5}/{n})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
