"""
채팅 서비스 - 오케스트레이터
모든 비즈니스 로직을 조율하는 메인 서비스
"""
from typing import List, Dict, Any
from app.schemas.chat import ChatResponse, Message
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.services.data_service import DataService
from app.database import get_db


class ChatService:
    """채팅 오케스트레이터 서비스"""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.rag_service = RAGService()
        self.data_service = DataService()
    
    async def process_message(
        self, 
        message: str, 
        history: List[Message]
    ) -> ChatResponse:
        """
        메시지 처리 메인 로직
        
        파이프라인:
        1. RAG 검색
        2. 데이터 조회
        3. 컨텍스트 구성
        4. LLM 호출
        5. 응답 포맷팅
        """
        # DB 세션 생성
        db = next(get_db())
        
        try:
            # 1. RAG 검색
            rag_docs = await self.rag_service.search(message, top_k=3, db=db)
            
            # 2. 데이터 조회
            env_data = await self.data_service.query(message, db=db)
            
            # 3. 컨텍스트 구성
            context = self._build_context(rag_docs, env_data)
            
            # 4. LLM 호출 (컨텍스트 포함)
            answer = await self.llm_service.generate_answer(
                message=message,
                history=history,
                context=context
            )
            
            # 5. 응답 포맷팅
            suggestions = self._generate_suggestions(message, rag_docs, env_data)
            
            return ChatResponse(
                answer=answer,
                suggestions=suggestions,
                data=env_data if env_data.get("results") else None,
                metadata={
                    "rag_documents_count": len(rag_docs),
                    "data_results_count": env_data.get("statistics", {}).get("count", 0)
                }
            )
        
        finally:
            db.close()
    
    def _build_context(self, rag_docs: List[Dict], env_data: Dict[str, Any]) -> str:
        """
        컨텍스트 구성 - RAG 문서와 환경 데이터를 통합
        
        Args:
            rag_docs: RAG 검색 결과 문서 리스트
            env_data: 환경 데이터 조회 결과
        
        Returns:
            LLM에 전달할 컨텍스트 문자열
        """
        context_parts = []
        
        # RAG 문서 컨텍스트
        if rag_docs:
            context_parts.append("=== 관련 문서 ===")
            for i, doc in enumerate(rag_docs, 1):
                context_parts.append(f"\n[문서 {i}] {doc.get('title', '제목 없음')}")
                context_parts.append(f"출처: {doc.get('source', '알 수 없음')}")
                context_parts.append(f"내용: {doc.get('content', '')[:300]}...")
        
        # 환경 데이터 컨텍스트
        if env_data.get("results"):
            context_parts.append("\n=== 환경 데이터 ===")
            stats = env_data.get("statistics", {})
            metadata = env_data.get("metadata", {})
            
            if metadata.get("location"):
                context_parts.append(f"위치: {metadata['location']}")
            if metadata.get("date_range"):
                context_parts.append(
                    f"기간: {metadata['date_range']['start']} ~ {metadata['date_range']['end']}"
                )
            if metadata.get("data_type"):
                context_parts.append(f"데이터 타입: {metadata['data_type']}")
            
            if stats.get("count", 0) > 0:
                context_parts.append(f"\n통계:")
                context_parts.append(f"- 데이터 개수: {stats['count']}개")
                if stats.get("avg") is not None:
                    context_parts.append(f"- 평균값: {stats['avg']:.2f}")
                if stats.get("min") is not None:
                    context_parts.append(f"- 최소값: {stats['min']:.2f}")
                if stats.get("max") is not None:
                    context_parts.append(f"- 최대값: {stats['max']:.2f}")
            
            # 최근 데이터 샘플
            context_parts.append("\n최근 데이터 샘플:")
            for result in env_data.get("results", [])[:5]:
                context_parts.append(
                    f"- {result.get('date')}: {result.get('value')} {result.get('unit', '')}"
                )
        
        return "\n".join(context_parts) if context_parts else ""
    
    def _generate_suggestions(
        self, 
        message: str, 
        rag_docs: List[Dict], 
        env_data: Dict[str, Any]
    ) -> List[str]:
        """
        제안 질문 생성
        
        Args:
            message: 사용자 메시지
            rag_docs: RAG 검색 결과
            env_data: 환경 데이터 결과
        
        Returns:
            제안 질문 리스트
        """
        suggestions = []
        
        # 데이터가 있을 때 제안
        if env_data.get("statistics", {}).get("count", 0) > 0:
            metadata = env_data.get("metadata", {})
            if metadata.get("data_type") == "algae":
                suggestions.append("녹조 농도가 높을 때 대응 방법을 알려주세요")
            if metadata.get("location"):
                suggestions.append(f"{metadata['location']}의 다른 기간 데이터도 보여주세요")
        
        # RAG 문서가 있을 때 제안
        if rag_docs:
            for doc in rag_docs[:2]:
                if "가이드라인" in doc.get("title", "") or "가이드라인" in doc.get("source", ""):
                    suggestions.append("가이드라인을 자세히 설명해주세요")
        
        # 기본 제안
        if not suggestions:
            suggestions = [
                "과거 데이터를 그래프로 보여주세요",
                "예측 모델을 사용할 수 있나요?",
            ]
        
        return suggestions[:3]  # 최대 3개만

