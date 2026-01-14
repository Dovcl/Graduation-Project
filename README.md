# Graduation-Project
All i want is to graduate successfully.

### 26_01_09
사용할 스택 정리 + 파이프라인 구축 설계

### 26_01_12
프론트 디자인 재구성(학교 상징색으로 구성 + 좀 더 깔끔한 UI)
fast api 환경 설정 + postgresql 다운 및 설정

### 26_01_14

### 아키텍처 패턴

#### 1. Service Layer Pattern (서비스 레이어 패턴)
- **역할**: 비즈니스 로직을 서비스 단위로 분리
- **구성**:
  - `ChatService`: 전체 대화 흐름 관리
  - `RAGService`: 문서 검색 담당
  - `DataService`: 환경 데이터 조회 담당
  - `LLMService`: AI 답변 생성 담당

#### 2. Orchestrator Pattern (오케스트레이터 패턴)
- **역할**: 여러 서비스를 조율하는 중앙 관리자
- **구성**: `ChatService`가 RAG 검색 → 데이터 조회 → LLM 호출 순서로 조율

#### 3. Repository Pattern (레포지토리 패턴)
- **역할**: 데이터베이스 접근을 추상화
- **구성**: SQLAlchemy ORM으로 `Document`, `EnvironmentalData` 모델 사용


## 🛠️ 기술 스택

### Backend
- **Python** 3.10.19
- **FastAPI** 0.104.1 - 비동기 웹 프레임워크
- **Uvicorn** 0.24.0 - ASGI 서버
- **SQLAlchemy** 2.0.23 - ORM
- **Alembic** 1.12.1 - 데이터베이스 마이그레이션
- **Pydantic** 2.5.0 - 데이터 검증 및 설정 관리

### Frontend
- **HTML5** - 마크업
- **CSS3** - 스타일링 (UOS 컬러 팔레트 적용)
- **JavaScript (ES6+)** - 클라이언트 로직
- **Vanilla JS** - 프레임워크 없이 순수 JavaScript 사용

### Database
- **PostgreSQL** 15 (Docker) - 관계형 데이터베이스
- **pgvector** 0.2.4 - 벡터 검색 확장
- **psycopg2-binary** 2.9.9 - PostgreSQL 어댑터

### AI/ML
- **OpenAI API** (GPT-5 Mini) - 대규모 언어 모델
- **sentence-transformers** 2.2.2 - 다국어 임베딩 모델
  - `paraphrase-multilingual-MiniLM-L12-v2` 사용
- **numpy** 1.24.3 - 수치 연산
- **pandas** 2.1.3 - 데이터 분석

### DevOps & Infrastructure
- **Docker** - 컨테이너화
- **Docker Compose** - 다중 컨테이너 관리
- **pgvector/pgvector:pg15** - PostgreSQL 15 + pgvector 이미지

---

## 💾 데이터베이스 설계

### 주요 테이블

#### 1. documents (RAG 문서)
- `id`: 문서 ID
- `title`: 문서 제목
- `content`: 문서 내용
- `source`: 출처
- `doc_type`: 문서 타입 (manual, guideline 등)
- `embedding`: 벡터 임베딩 (BYTEA, 추후 vector 타입으로 변경)
- `created_at`, `updated_at`: 타임스탬프

#### 2. environmental_data (환경 데이터)
- `id`: 데이터 ID
- `location`: 위치 정보
- `latitude`, `longitude`: 좌표
- `date`, `datetime`: 날짜/시간
- `data_type`: 데이터 타입 (water_quality, algae, hydrology, weather)
- `value`, `value2`, `value3`: 측정값
- `unit`: 단위
- `quality_flag`: 품질 플래그
- `notes`: 메모
- `created_at`, `updated_at`: 타임스탬프



