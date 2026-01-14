# 환경 데이터 RAG 챗봇 v3

환경 데이터(수질, 녹조, 수문, 기상)를 분석하고 예측하는 능동적 RAG 챗봇 시스템

---

## 1. Before / After (한 장 요약)

### Before: 현재 상태
- ❌ 프론트엔드가 로직/DB/LLM 직접 처리 → 보안 이슈, API 키 노출 위험
- ❌ Supabase 클라이언트에서 직접 접근
- ❌ RAG가 키워드 기반 검색만 지원 (벡터 검색 없음)
- ❌ 모든 비즈니스 로직이 프론트엔드에 분산

### After: 목표 아키텍처
- ✅ **프론트엔드**: UI + 시각화만 담당 (Thin Client)
- ✅ **백엔드**: `/api/chat` 하나에서 모든 처리
  - RAG 검색 (메뉴얼, 기준 문서)
  - 데이터 조회 (환경 데이터)
  - LLM 호출 (Groq API)
  - 응답 포맷팅 (답변 + 제안 + 데이터 + 시각화)
- ✅ **보안**: API 키는 백엔드에서만 접근
- ✅ **확장 가능**: 나중에 서비스 분리 가능

---

## 2. 파이프라인

```
Frontend (Thin Client)
  │
  └─ POST /api/chat { message, history }
        │
        ▼
ChatService (Orchestrator)
  │
  ├─ RAG 검색 (내부 함수 / 추후 rag_service.py로 분리 가능)
  │   └─ 임베딩 생성 → 벡터 검색 → 관련 문서 반환
  │
  ├─ Data Query (내부 함수 / 추후 data_service.py로 분리 가능)
  │   └─ 질문 파싱 → DB 조회 → 환경 데이터 반환
  │
  ├─ Context Build
  │   └─ RAG 문서 + 조회된 데이터 + 기준 정보 통합
  │
  ├─ LLM Call (llm_service.py)
  │   └─ Groq API 호출 → 답변 생성
  │
  └─ Response Format
      └─ 답변 + 제안 + 데이터 + 시각화 정보 구성
        │
        ▼
{ 
  answer: "...",
  suggestions: [...],
  data: {...},
  visualizations: {...},
  metadata: {...}
}
```

---

## 3. MVP 폴더 구조 (최소 확장형)

```
project-root/
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── script.js            # API 호출 + 렌더링만
│   ├── config.js            # 백엔드 URL 설정
│   ├── api/
│   │   └── client.js        # POST /api/chat
│   └── modules/
│       └── visualization.js # 시각화만
│
└── backend/
    └── app/
        ├── main.py          # FastAPI 엔트리
        ├── database.py      # PostgreSQL 연결
        ├── core/
        │   └── config.py    # 환경 변수 로드
        ├── api/
        │   └── chat.py      # POST /api/chat
        ├── schemas/
        │   └── chat.py      # ChatRequest, ChatResponse
        └── services/
            ├── chat_service.py   # Orchestrator (처음엔 내부 함수로 다)
            └── llm_service.py    # LLM 호출만
```

### chat_service.py 구조 (처음엔 통합, 나중에 분리 가능)

```python
class ChatService:
    async def process_message(self, message: str, history: List):
        # 1. RAG 검색 (내부 함수)
        rag_docs = await self._search_rag_documents(message)
        
        # 2. 데이터 조회 (내부 함수)
        env_data = await self._query_environmental_data(message)
        
        # 3. 컨텍스트 구성
        context = self._build_context(rag_docs, env_data)
        
        # 4. LLM 호출
        answer = await self.llm_service.generate_answer(message, context)
        
        # 5. 응답 포맷팅
        return self._format_response(answer, rag_docs, env_data)
    
    # 나중에 분리 가능:
    # _search_rag_documents → rag_service.py
    # _query_environmental_data → data_service.py
```

---

**버전**: v3.0  
**최종 업데이트**: 2024년 12월

