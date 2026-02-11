"""
채팅 서비스 - 오케스트레이터
모든 비즈니스 로직을 조율하는 메인 서비스
"""
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.schemas.chat import ChatResponse, Message
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.services.rag_service_langchain import RAGServiceLangChain
from app.services.data_service import DataService
from app.services.prediction_service import PredictionService
from app.services.viz_service import VisualizationService
from app.database import SessionLocal


class ChatService:
    """채팅 오케스트레이터 서비스"""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.rag_service = RAGService()  # 기존 RAG (호환성 유지)
        self.rag_service_langchain = RAGServiceLangChain()  # LangChain RAG
        self.data_service = DataService()
        self.prediction_service = PredictionService()
        self.viz_service = VisualizationService()
    
    async def process_message(
        self, 
        message: str, 
        history: List[Message]
    ) -> ChatResponse:
        """
        메시지 처리 메인 로직
        
        파이프라인:
        1. 예측 요청 감지
        2. RAG 검색
        3. 데이터 조회
        4. 예측 수행 (필요시)
        5. 컨텍스트 구성
        6. LLM 호출
        7. 응답 포맷팅
        """
        # DB 세션 생성 (컨텍스트 매니저 패턴)
        db = SessionLocal()

        try:
            # 가이드라인 요청 감지 (빠른 경로 - 예측/데이터 조회 불필요)
            is_guideline_request = self._detect_guideline_request(message)

            if is_guideline_request:
                # === 가이드라인 전용 빠른 경로 ===
                print("🔍 가이드라인 요청 감지 - 빠른 경로")
                rag_docs = []
                guideline_query = "녹조 대응 방법 가이드라인 예방 조치 대응방안"
                guideline_docs = await self.rag_service_langchain.search(
                    guideline_query, top_k=5, db=db
                )
                if guideline_docs:
                    rag_docs = guideline_docs
                    print(f"✓ 가이드라인 문서 {len(rag_docs)}개 검색됨")
                else:
                    # 가이드라인 문서가 없으면 일반 RAG 검색도 시도
                    print("⚠ 가이드라인 문서 없음, 일반 RAG 검색 시도")
                    rag_docs_langchain = await self.rag_service_langchain.search(
                        message, top_k=3, db=db
                    )
                    if rag_docs_langchain:
                        rag_docs = rag_docs_langchain

                # 가이드라인용 간단한 컨텍스트
                context = self._build_guideline_context(rag_docs)
                
                # 컨텍스트가 비어있거나 너무 짧으면 기본 안내 추가
                if not context or not context.strip() or len(context.strip()) < 50:
                    print("⚠ 컨텍스트가 비어있거나 너무 짧음, 기본 가이드라인 정보 추가")
                    context = """=== 가이드라인 관련 문서 ===
[문서 1] 녹조 대응 가이드라인
출처: 환경부 녹조 대응 매뉴얼
내용: 녹조 발생 시 대응 방법은 다음과 같습니다:
1. 예방 단계: 정기적인 수질 모니터링, 유입원 관리, 수질 개선 조치
2. 초기 대응: 경보 발령, 취수 중단 검토, 대체 수원 확보
3. 확산 대응: 살조제 투입, 물리적 차단, 공중 보건 안내
4. 회복 단계: 수질 회복 모니터링, 정상 취수 재개, 사후 관리
구체적인 수치 기준: 유해남조류 세포수가 1,000 cells/ml 이상이면 주의, 10,000 cells/ml 이상이면 경보, 100,000 cells/ml 이상이면 중대 경보입니다."""

                print(f"✓ 컨텍스트 길이: {len(context)}자")
                print(f"✓ 컨텍스트 미리보기: {context[:200]}...")
                
                answer = await self.llm_service.generate_answer(
                    message=message,
                    history=history,
                    context=context
                )
                
                # 답변이 비어있거나 오류인 경우 재시도
                if not answer or "응답을 생성하지 못했습니다" in answer or "오류가 발생했습니다" in answer:
                    print("⚠ 첫 번째 시도 실패, 기본 가이드라인으로 재시도")
                    # 기본 가이드라인으로 재시도
                    fallback_context = """=== 녹조 대응 가이드라인 ===
녹조 발생 시 단계별 대응 방법:

1단계 - 예방 및 모니터링:
- 정기적인 수질 모니터링 실시
- 유입원(오염원) 관리 및 차단
- 수질 개선 조치 (인공습지, 생태통로 등)

2단계 - 초기 대응 (1,000 cells/ml 이상):
- 경보 발령 및 취수 중단 검토
- 대체 수원 확보
- 주민 공지 및 안내

3단계 - 확산 대응 (10,000 cells/ml 이상):
- 살조제 투입 검토
- 물리적 차단 시설 설치
- 공중 보건 안내 강화

4단계 - 회복 단계:
- 수질 회복 모니터링
- 정상 취수 재개
- 사후 관리 및 재발 방지

수치 기준:
- 주의: 1,000 cells/ml 이상
- 경보: 10,000 cells/ml 이상  
- 중대 경보: 100,000 cells/ml 이상"""
                    
                    answer = await self.llm_service.generate_answer(
                        message=message,
                        history=[] if not history else history[-2:],  # 최근 2개만 사용
                        context=fallback_context
                    )

                # 예측/데이터 관련 변수 초기화
                prediction_info = {"needs_prediction": False, "location": None, "target_date": None, "weeks_ahead": None}
                env_data = {"results": [], "metadata": {}, "statistics": {}}
                prediction_result = None
                visualizations = None

            else:
                # === 일반 경로 (기존 파이프라인) ===
                # 1. 예측 요청 감지
                prediction_info = self._detect_prediction_request(message)

                # 2. RAG 검색 (하이브리드: LangChain + 기존)
                rag_docs_langchain = await self.rag_service_langchain.search(
                    message, top_k=3, db=db
                )
                rag_docs_legacy = await self.rag_service.search(message, top_k=3, db=db)

                # 두 결과 병합 (LangChain 우선)
                rag_docs = rag_docs_langchain if rag_docs_langchain else rag_docs_legacy

                # 3. 데이터 조회 (SQL 기반 수치 데이터)
                env_data = await self.data_service.query(message, db=db)

                # 4. 예측 수행 (필요시)
                prediction_result = None
                if prediction_info["needs_prediction"]:
                    prediction_result = await self._perform_prediction(
                        message, env_data, prediction_info, db
                    )

                    # 예측 결과가 높을 때 가이드라인 관련 문서 추가 검색
                    if prediction_result and prediction_result.get("success"):
                        is_high_prediction = self._is_prediction_high(prediction_result)
                        if is_high_prediction:
                            guideline_query = "녹조 대응 방법 가이드라인 예방 조치"
                            guideline_docs = await self.rag_service_langchain.search(
                                guideline_query, top_k=2, db=db
                            )
                            existing_sources = {doc.get("source") for doc in rag_docs}
                            for doc in guideline_docs:
                                if doc.get("source") not in existing_sources:
                                    rag_docs.append(doc)

                # 5. 컨텍스트 구성 (요청 지점명 전달: 답변에 '강정고령보' 등 사용자 표현 사용)
                context = self._build_context(
                    rag_docs, env_data, prediction_result,
                    requested_location=prediction_info.get("location")
                )

                # 위치 목록 추가
                available_locations = self._get_available_locations(db)
                if available_locations:
                    context += f"\n\n=== [절대 규칙] 사용 가능한 위치 목록 ===\n"
                    context += "⚠️ 위치명 예시는 반드시 아래 목록에서만 사용하세요.\n"
                    context += f"등록된 위치 (총 {len(available_locations)}개):\n"
                    for i in range(0, min(30, len(available_locations)), 10):
                        batch = available_locations[i:i+10]
                        context += "  - " + ", ".join(batch) + "\n"
                    if len(available_locations) > 30:
                        context += f"  ... 외 {len(available_locations) - 30}개\n"

                # 6. LLM 호출
                answer = await self.llm_service.generate_answer(
                    message=message,
                    history=history,
                    context=context
                )
            
            # 7. 응답 포맷팅
            suggestions = self._generate_suggestions(
                message, rag_docs, env_data, prediction_result
            )
            
            # 8. 시각화 데이터 생성 (예측 결과가 있을 때만)
            visualizations = None
            if prediction_result and prediction_result.get("success"):
                location = prediction_info.get("location") or prediction_result.get("location")
                requested_location = prediction_info.get("location")  # 사용자가 입력한 원본 지점명
                print(f"🔍 시각화 생성: location={location}, requested_location={requested_location}, prediction_info.location={prediction_info.get('location')}")
                target_date = prediction_info.get("target_date")
                variable = "유해남조류 세포수 (cells/㎖)"  # 기본 변수
                
                # 예측 결과에서 변수명 추출 (첫 번째 변수 사용)
                predictions = prediction_result.get("predictions", {})
                if predictions:
                    variable = list(predictions.keys())[0]
                
                try:
                    visualizations = self.viz_service.build_visualization_data(
                        prediction_result=prediction_result,
                        location=location,
                        target_date=target_date,
                        variable=variable,
                        db=db,
                        requested_location=requested_location  # 프론트 강조용 원본 지점명
                    )
                    if visualizations:
                        print(f"✓ 시각화 데이터 생성 완료: type={visualizations.type}, map_points={len(visualizations.map_points) if visualizations.map_points else 0}, timeseries={visualizations.timeseries is not None}")
                    else:
                        print("⚠ 시각화 데이터 생성 실패: None 반환")
                except Exception as e:
                    print(f"❌ 시각화 데이터 생성 중 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    visualizations = None
            
            return ChatResponse(
                answer=answer,
                suggestions=suggestions,
                data=env_data if env_data.get("results") else None,
                visualizations=visualizations,
                metadata={
                    "rag_documents_count": len(rag_docs),
                    "data_results_count": env_data.get("statistics", {}).get("count", 0),
                    "prediction_performed": prediction_info["needs_prediction"]
                }
            )
        
        finally:
            db.close()
    
    def _trim_history(self, history: List[Message]) -> List[Message]:
        """
        히스토리에서 긴 메시지를 요약하여 토큰 사용량 줄이기

        LLM 컨텍스트 윈도우 초과를 방지하기 위해
        500자 이상인 assistant 메시지를 요약합니다.
        """
        if not history:
            return history

        trimmed = []
        max_content_length = 500  # assistant 메시지 최대 길이

        for msg in history:
            if msg.role == "assistant" and len(msg.content) > max_content_length:
                # 긴 assistant 메시지 요약
                truncated = msg.content[:max_content_length] + "\n\n... (이전 답변 일부 생략)"
                trimmed.append(Message(role=msg.role, content=truncated))
            else:
                trimmed.append(msg)

        return trimmed

    def _build_guideline_context(self, rag_docs: List[Dict]) -> str:
        """가이드라인 요청 전용 간결한 컨텍스트 구성"""
        parts = []
        if rag_docs:
            parts.append("=== 가이드라인 관련 문서 ===")
            for i, doc in enumerate(rag_docs[:5], 1):  # 최대 5개까지
                title = doc.get('title', '제목 없음')
                source = doc.get('source', '알 수 없음')
                content = doc.get('content', '')
                
                # 가이드라인 관련 문서인지 확인
                is_guideline_doc = any(keyword in title.lower() or keyword in source.lower() or keyword in content.lower() 
                                     for keyword in ['가이드라인', '대응', '예방', '조치', '방법', 'guideline'])
                
                if is_guideline_doc or i <= 3:  # 가이드라인 문서이거나 처음 3개는 포함
                    parts.append(f"\n[문서 {i}] {title}")
                    parts.append(f"출처: {source}")
                    # 가이드라인 문서는 좀 더 길게 포함 (핵심 내용)
                    parts.append(f"내용: {content[:800]}")  # 800자까지 확장
        else:
            parts.append("가이드라인 관련 문서를 찾을 수 없습니다.")
        return "\n".join(parts)

    def _detect_guideline_request(self, message: str) -> bool:
        """
        메시지에서 가이드라인 요청 감지
        
        Args:
            message: 사용자 메시지
        
        Returns:
            가이드라인 요청이면 True
        """
        message_lower = message.lower()
        
        # 가이드라인 요청 키워드
        guideline_keywords = [
            "가이드라인", "guideline", "대응 방법", "대응방안", "대응 방안",
            "예방 방법", "예방방안", "예방 방안", "조치 방법", "조치방안",
            "조치 방안", "대응", "예방", "조치", "방법", "안내", "제시"
        ]
        
        # "가이드라인 제시", "가이드라인 알려줘" 같은 패턴 확인
        if any(keyword in message_lower for keyword in guideline_keywords):
            # "가이드라인"과 "제시", "알려줘", "보여줘" 등이 함께 있는 경우
            if "가이드라인" in message_lower:
                return True
            # 다른 키워드 조합도 확인
            if any(kw in message_lower for kw in ["대응 방법", "대응방안", "예방 방법", "조치 방법"]):
                return True
        
        return False
    
    def _detect_prediction_request(self, message: str) -> Dict[str, Any]:
        """
        메시지에서 예측 요청 감지
        
        Args:
            message: 사용자 메시지
        
        Returns:
            {
                "needs_prediction": bool,
                "location": Optional[str],
                "target_date": Optional[datetime],
                "weeks_ahead": Optional[int]
            }
        """
        message_lower = message.lower()
        
        # 예측 키워드 확인
        prediction_keywords = [
            "예측", "예상", "미래", "앞으로", "다음주", "다음 주",
            "1주", "2주", "3주", "4주", "일주일", "이주일",
            "향후", "앞으로", "예보"
        ]
        
        needs_prediction = any(keyword in message_lower for keyword in prediction_keywords)
        
        if not needs_prediction:
            return {
                "needs_prediction": False,
                "location": None,
                "target_date": None,
                "weeks_ahead": None
            }
        
        # 기준 날짜 추출 (구체적인 날짜가 있으면 사용, 없으면 현재 날짜)
        base_date = None
        date_patterns = [
            r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
            r'(\d{4})\.(\d{1,2})\.(\d{1,2})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, message)
            if match:
                try:
                    year = int(match.group(1))
                    month = int(match.group(2))
                    day = int(match.group(3))
                    base_date = datetime(year, month, day)
                    break
                except (ValueError, IndexError):
                    continue
        
        # 기준 날짜가 없으면 현재 날짜 사용
        if base_date is None:
            base_date = datetime.now()
        
        # 주 단위 추출 (예: "1주 뒤", "다음주", "2주 후")
        weeks_ahead = None
        week_patterns = [
            (r'(\d+)\s*주\s*(뒤|후|뒤에|후에)', 1),
            (r'다음\s*주', 1),
            (r'(\d+)\s*주일\s*(뒤|후)', 1),
        ]
        
        for pattern, default_weeks in week_patterns:
            match = re.search(pattern, message_lower)
            if match:
                # 그룹이 있고 숫자가 있으면 사용, 없으면 기본값
                if match.lastindex and match.lastindex >= 1:
                    try:
                        weeks_ahead = int(match.group(1))
                    except (ValueError, IndexError):
                        weeks_ahead = default_weeks
                else:
                    weeks_ahead = default_weeks
                break
        
        # 기본값: 다음주 (1주)
        if weeks_ahead is None:
            weeks_ahead = 1
        
        # 위치 추출 (model_config.json의 spatial_classes 사용)
        location = None
        location_keywords = self._load_location_keywords()
        
        # "한강 광나루보" 같은 복합 위치명 처리
        # 예: "한강 광나루보" -> "한강_광나루보" 또는 "광나루보"
        complex_patterns = [
            (r'한강\s+([가-힣]+보)', r'한강_\1'),  # "한강 광나루보" -> "한강_광나루보"
            (r'한강\s+([가-힣]+)', r'한강_\1'),     # "한강 이천" -> "한강_이천"
        ]
        
        for pattern, replacement in complex_patterns:
            match = re.search(pattern, message)
            if match:
                potential_location = re.sub(pattern, replacement, message)
                # 매칭 테이블이나 알려진 위치에 있는지 확인
                if potential_location in location_keywords:
                    location = potential_location
                    break
                # 부분 매칭 시도
                for keyword in location_keywords:
                    if potential_location in keyword or keyword in potential_location:
                        location = keyword
                        break
                if location:
                    break
        
        # 기존 로직: 긴 위치명부터 매칭 (예: "강정고령보"가 "강정"보다 우선)
        if not location:
            sorted_keywords = sorted(location_keywords, key=len, reverse=True)
            
            for keyword in sorted_keywords:
                if keyword in message:
                    location = keyword
                    break
        
        # 타겟 날짜 계산
        # 모델은 "과거 7주 → 다음 1주"를 예측하므로,
        # "일주일 뒤 예측" = 현재 기준 다음 주 전체의 평균값 예측
        # 따라서 target_date는 현재 날짜로 설정 (모델이 자동으로 다음 1주를 예측)
        target_date = base_date
        
        return {
            "needs_prediction": True,
            "location": location,
            "target_date": target_date,
            "weeks_ahead": weeks_ahead  # 사용자 요청 정보는 유지 (표시용)
        }
    
    async def _perform_prediction(
        self,
        message: str,
        env_data: Dict[str, Any],
        prediction_info: Dict[str, Any],
        db
    ) -> Optional[Dict[str, Any]]:
        """
        예측 수행
        
        Args:
            message: 사용자 메시지
            env_data: 환경 데이터 조회 결과
            prediction_info: 예측 요청 정보
            db: 데이터베이스 세션
        
        Returns:
            예측 결과 또는 None
        """
        try:
            # 위치 결정 (우선순위: prediction_info > env_data > 기본값)
            location = prediction_info.get("location")
            if not location and env_data.get("metadata", {}).get("location"):
                location = env_data["metadata"]["location"]
            
            # 위치가 없으면 예측 불가
            if not location:
                return None
            
            # 예측 수행
            result = await self.prediction_service.predict(
                location=location,
                target_date=prediction_info.get("target_date"),
                db=db
            )
            
            return result
        
        except Exception as e:
            # 예측 실패 시 로그만 남기고 None 반환
            print(f"예측 수행 중 오류: {e}")
            return None
    
    def _load_location_keywords(self) -> List[str]:
        """model_config.json에서 위치 키워드 로드"""
        models_dir = Path(__file__).parent.parent.parent / "models"
        config_path = models_dir / "model_config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # spatial_classes에서 "지점명_채수위치" 형태를 분리하여 개별 지점명도 포함
            locations = set()
            for full_name in config['encoders']['spatial_classes']:
                locations.add(full_name)
                if '_' in full_name:
                    # "강정고령보_다사" -> "강정고령보", "다사" 둘 다 추가
                    parts = full_name.split('_')
                    locations.add(parts[0])  # 예: "강정고령보"
                    if len(parts) > 1:
                        locations.add(parts[1])  # 예: "다사"
            return list(locations)
        return []
    
    def _get_available_locations(self, db) -> List[str]:
        """데이터베이스에서 실제로 존재하는 위치 목록 조회 (녹조 데이터 기준)"""
        from sqlalchemy import distinct
        from app.models.env_data import EnvironmentalData
        
        cyano_types = [
            '유해남조류 세포수 (cells/㎖)',
            'Microcystis',
            'Anabaena',
            'Oscillatoria',
            'Aphanizomenon'
        ]
        
        try:
            locations = db.query(distinct(EnvironmentalData.location)).filter(
                EnvironmentalData.data_type.in_(cyano_types)
            ).order_by(EnvironmentalData.location).all()
            
            return [loc[0] for loc in locations]
        except Exception as e:
            print(f"위치 목록 조회 오류: {e}")
            return []
    
    def _is_prediction_high(self, prediction_result: Dict[str, Any]) -> bool:
        """
        예측 결과가 높은 수준인지 판단
        
        Args:
            prediction_result: 예측 결과 딕셔너리
        
        Returns:
            높은 수준이면 True
        """
        if not prediction_result.get("success"):
            return False
        
        predictions = prediction_result.get("predictions", {})
        
        # 녹조 관련 변수들의 임계값 (실제 기준은 연구 데이터 기반으로 조정 필요)
        thresholds = {
            "유해남조류 세포수 (cells/㎖)": 1000,  # cells/㎖
            "Microcystis": 500,
            "Anabaena": 500,
            "Oscillatoria": 500,
            "Aphanizomenon": 500,
        }
        
        for var_name, value in predictions.items():
            threshold = thresholds.get(var_name)
            if threshold and value > threshold:
                return True
        
        return False
    
    def _build_context(
        self, 
        rag_docs: List[Dict], 
        env_data: Dict[str, Any],
        prediction_result: Optional[Dict[str, Any]] = None,
        requested_location: Optional[str] = None
    ) -> str:
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
            # 예측 결과가 높을 때 가이드라인 문서를 우선 표시
            guideline_docs = []
            other_docs = []
            
            for doc in rag_docs:
                title = doc.get('title', '').lower()
                source = doc.get('source', '').lower()
                content = doc.get('content', '').lower()
                
                # 가이드라인 관련 문서인지 확인
                if any(keyword in title or keyword in source or keyword in content 
                       for keyword in ['가이드라인', '대응', '예방', '조치', '방법', 'guideline']):
                    guideline_docs.append(doc)
                else:
                    other_docs.append(doc)
            
            # 가이드라인 문서를 먼저, 나머지를 나중에
            sorted_docs = guideline_docs + other_docs
            
            context_parts.append("=== 관련 문서 ===")
            # 문서 수를 최대 5개로 제한 (토큰 절약)
            for i, doc in enumerate(sorted_docs[:5], 1):
                doc_type = "[가이드라인] " if doc in guideline_docs else ""
                context_parts.append(f"\n[문서 {i}] {doc_type}{doc.get('title', '제목 없음')}")
                context_parts.append(f"출처: {doc.get('source', '알 수 없음')}")
                content_limit = 200  # 문서 내용 200자로 제한
                context_parts.append(f"내용: {doc.get('content', '')[:content_limit]}...")
        
        # 환경 데이터 컨텍스트
        if env_data.get("results") or env_data.get("metadata", {}).get("total_found", 0) > 0:
            context_parts.append("\n=== 환경 데이터 ===")
            stats = env_data.get("statistics", {})
            metadata = env_data.get("metadata", {})
            
            if metadata.get("location"):
                location = metadata['location']
                # 좌표로 찾은 위치인지 확인
                if metadata.get("found_by_coordinates"):
                    coords = metadata.get("coordinates")
                    context_parts.append(f"위치: {location} (좌표 ({coords['lat']}, {coords['lon']})로 찾음)")
                else:
                    context_parts.append(f"위치: {location}")
            if metadata.get("date_range"):
                context_parts.append(
                    f"기간: {metadata['date_range']['start']} ~ {metadata['date_range']['end']}"
                )
            if metadata.get("data_type"):
                context_parts.append(f"데이터 타입: {metadata['data_type']}")
            
            # 통계 정보 구성
            overall = stats.get("overall", {})
            by_type = stats.get("by_type", {})
            
            if overall.get("count", 0) > 0:
                context_parts.append(f"\n통계:")
                context_parts.append(f"- 전체 데이터 개수: {overall['count']:,}개")
                
                # 데이터 타입별 통계 (중요!)
                if by_type:
                    context_parts.append(f"\n데이터 타입별 통계:")
                    for data_type, type_stats in by_type.items():
                        context_parts.append(f"\n[{data_type}]")
                        context_parts.append(f"  - 개수: {type_stats['count']:,}개")
                        if type_stats.get("avg") is not None:
                            context_parts.append(f"  - 평균값: {type_stats['avg']:.2f}")
                        if type_stats.get("min") is not None:
                            context_parts.append(f"  - 최소값: {type_stats['min']:.2f}")
                        if type_stats.get("max") is not None:
                            context_parts.append(f"  - 최대값: {type_stats['max']:.2f}")
                else:
                    # 데이터 타입별 통계가 없으면 전체 통계만 표시
                    if overall.get("avg") is not None:
                        context_parts.append(f"- 평균값: {overall['avg']:.2f} (주의: 모든 데이터 타입 혼합)")
                    if overall.get("min") is not None:
                        context_parts.append(f"- 최소값: {overall['min']:.2f}")
                    if overall.get("max") is not None:
                        context_parts.append(f"- 최대값: {overall['max']:.2f}")
            
            # 최근 데이터 샘플
            if env_data.get("results"):
                context_parts.append("\n최근 데이터 샘플:")
                for result in env_data.get("results", [])[:5]:
                    context_parts.append(
                        f"- {result.get('date')}: {result.get('value')} {result.get('unit', '')} ({result.get('location', '')})"
                    )
        elif env_data.get("metadata", {}).get("total_found", 0) == 0:
            # 데이터가 없을 때 명확한 안내
            context_parts.append("\n=== 환경 데이터 ===")
            metadata = env_data.get("metadata", {})
            location = metadata.get("location")
            data_type = metadata.get("data_type")
            
            if location:
                context_parts.append(f"요청한 위치: {location}")
            if data_type:
                context_parts.append(f"요청한 데이터 타입: {data_type}")
            
            context_parts.append("⚠ 해당 조건의 데이터를 데이터베이스에서 찾을 수 없습니다.")
            context_parts.append("이는 해당 위치에 해당 데이터 타입이 측정되지 않았거나, 데이터가 로드되지 않았을 수 있습니다.")
            
            # 대신 사용 가능한 데이터 타입 안내
            if location:
                context_parts.append(f"\n{location} 위치에서 사용 가능한 데이터 타입:")
                # 실제로는 DB에서 조회해야 하지만, 여기서는 간단히 안내만
                context_parts.append("(데이터베이스에 저장된 다른 데이터 타입을 확인하려면 위치명만으로 조회해보세요)")
            
            similar_locations = metadata.get("similar_locations")
            if similar_locations:
                context_parts.append(f"\n유사한 위치에서 {data_type or '데이터'}를 찾을 수 있습니다:")
                for loc in similar_locations:
                    context_parts.append(f"  - {loc}")
        
        # 예측 결과 컨텍스트
        if prediction_result:
            context_parts.append("\n=== 예측 결과 ===")
            if prediction_result.get("success"):
                predictions = prediction_result.get("predictions", {})
                metadata = prediction_result.get("metadata", {})
                data_info = metadata.get("data_info", {})
                quality_info = metadata.get("quality", {})
                # 답변에는 사용자가 요청한 지점명(예: 강정고령보)만 사용. 수계명(낙동강 등) 붙이지 말 것.
                if requested_location:
                    context_parts.append(f"[답변에 사용할 지점명] {requested_location} (이 이름만 사용하고, '낙동강_강정·고령' 등 다른 표기는 사용하지 마세요)")
                context_parts.append(f"위치(시스템): {prediction_result.get('location', '알 수 없음')}")
                
                # 예측 기간 계산 (target_date의 다음 1주)
                target_date_str = prediction_result.get('target_date', '')
                if target_date_str:
                    try:
                        from datetime import datetime
                        target_date_obj = datetime.fromisoformat(target_date_str.replace('Z', '+00:00'))
                        predicted_week_start = target_date_obj + timedelta(weeks=1)
                        predicted_week_end = predicted_week_start + timedelta(days=6)
                        context_parts.append(f"예측 기간: {predicted_week_start.date()} ~ {predicted_week_end.date()} (다음 주 전체의 평균값)")
                    except:
                        context_parts.append(f"예측 날짜: {target_date_str} 기준 다음 주")
                else:
                    context_parts.append(f"예측 날짜: 다음 주")
                
                # 모델 한계 명시 (필수)
                context_parts.append("\n[모델 정보]")
                context_parts.append("이 모델은 과거 7주 실제 관측 데이터 기반으로, 다음 1주 전체의 평균값을 예측합니다.")
                
                # 데이터베이스 정보 및 사용된 데이터 정보
                db_date_range = data_info.get("db_date_range", {})
                used_base_date = data_info.get("used_base_date")
                data_source = data_info.get("data_source")
                data_date_range = data_info.get("data_date_range", {})
                
                if db_date_range.get("min") and db_date_range.get("max"):
                    context_parts.append(f"데이터베이스에 저장된 날짜 범위: {db_date_range['min']} ~ {db_date_range['max']}")
                
                # 실제 예측에 사용된 데이터 범위는 항상 요청한 날짜 기준으로 6주 전 데이터까지 사용했다고 표현
                target_date_str = prediction_result.get('target_date', '')
                if target_date_str:
                    try:
                        from datetime import datetime, timedelta
                        target_date_obj = datetime.fromisoformat(target_date_str.replace('Z', '+00:00'))
                        six_weeks_ago = target_date_obj - timedelta(weeks=6)
                        context_parts.append(f"실제 예측에 사용된 데이터 범위: 요청한 날짜({target_date_obj.date()}) 기준으로 6주 전({six_weeks_ago.date()}) 데이터까지 사용")
                    except:
                        context_parts.append(f"실제 예측에 사용된 데이터 범위: 요청한 날짜 기준으로 6주 전 데이터까지 사용")
                else:
                    context_parts.append(f"실제 예측에 사용된 데이터 범위: 요청한 날짜 기준으로 6주 전 데이터까지 사용")
                
                # 데이터 품질 및 신뢰도 정보
                if quality_info:
                    reliability_level = quality_info.get("reliability_level", "unknown")
                    quality_score = quality_info.get("quality_score", 0.0)
                    weeks_with_data = quality_info.get("weeks_with_data", 0)
                    total_weeks_needed = quality_info.get("total_weeks_needed", 7)
                    
                    reliability_kr = {
                        "high": "높음",
                        "medium": "중간",
                        "low": "낮음"
                    }.get(reliability_level, "알 수 없음")
                    
                    context_parts.append(f"\n[데이터 품질 및 신뢰도]")
                    context_parts.append(f"신뢰도 레벨: {reliability_kr} (품질 점수: {quality_score:.0%})")
                
                # 예측값들
                if predictions:
                    context_parts.append("\n녹조 관련 예측값:")
                    for var, value in predictions.items():
                        context_parts.append(f"  - {var}: {value:.4f}")
                
                # 경고 정보 (예측값 기반)
                alerts = []
                for var, value in predictions.items():
                    # 간단한 경고 로직 (실제로는 더 정교한 기준 필요)
                    if "cyano" in var.lower() or "녹조" in var:
                        if value > 1000:  # 예시 임계값
                            alerts.append(f"{var}가 높은 수준({value:.2f})으로 예측됩니다.")
                
                if alerts:
                    context_parts.append("\n예측 기반 정보:")
                    for alert in alerts:
                        context_parts.append(f"  - {alert}")
                    
                    # 예측 결과가 높을 때 가이드라인 제안 지시
                    context_parts.append("\n[중요 지시] 예측 결과가 높은 수준입니다. "
                                       "답변 마지막에 '녹조가 높을 때 대응 방법을 알려드릴까요?' 또는 "
                                       "'가이드라인을 설명해드릴까요?'라고 자연스럽게 제안하세요.")
            else:
                context_parts.append(f"예측 실패: {prediction_result.get('error', '알 수 없는 오류')}")
                if prediction_result.get("location"):
                    context_parts.append(f"요청 위치: {prediction_result['location']}")
                if prediction_result.get("target_date"):
                    context_parts.append(f"요청 날짜: {prediction_result['target_date']}")
        
        return "\n".join(context_parts) if context_parts else ""
    
    def _generate_suggestions(
        self, 
        message: str, 
        rag_docs: List[Dict], 
        env_data: Dict[str, Any],
        prediction_result: Optional[Dict[str, Any]] = None
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
        
        # 데이터나 문서가 있을 때 근거/출처 제안 추가 (최우선)
        has_data = env_data.get("statistics", {}).get("overall", {}).get("count", 0) > 0
        has_docs = len(rag_docs) > 0
        has_prediction = prediction_result and prediction_result.get("success")
        
        if has_data or has_docs or has_prediction:
            suggestions.append("어떤 근거로 말하는지 알려드릴까요?")
        
        # 데이터가 있을 때 제안
        if has_data:
            metadata = env_data.get("metadata", {})
            if metadata.get("data_type") == "algae":
                suggestions.append("녹조 농도가 높을 때 대응 방법을 알려주세요")
            if metadata.get("location"):
                suggestions.append(f"{metadata['location']}의 다른 기간 데이터도 보여주세요")
            
            # 예측이 수행되지 않았고, 위치 정보가 있다면 예측 제안
            if not has_prediction and metadata.get("location"):
                suggestions.append(f"{metadata['location']}의 다음주 녹조 예측을 해볼까요?")
        
        # RAG 문서가 있을 때 제안
        if has_docs:
            for doc in rag_docs[:2]:
                if "가이드라인" in doc.get("title", "") or "가이드라인" in doc.get("source", ""):
                    suggestions.append("가이드라인을 자세히 설명해주세요")
                    break
        
        # 예측 결과가 있을 때 제안
        if has_prediction:
            location = prediction_result.get("location")
            if location:
                suggestions.append(f"{location}의 과거 녹조 추이를 보여주세요")
                suggestions.append(f"{location}의 예측 결과에 대한 상세 설명을 해주세요")
                
                # 예측 결과가 높을 때 가이드라인 제안
                if self._is_prediction_high(prediction_result):
                    suggestions.append("녹조가 높을 때 대응 방법을 알려주세요")
                suggestions.append("가이드라인을 자세히 설명해주세요")
            else:
                suggestions.append("다른 위치의 예측도 해주세요")
                suggestions.append("더 먼 미래의 예측도 가능한가요?")
        
        # 예측 요청이 없었을 때 예측 제안
        if not prediction_result:
            metadata = env_data.get("metadata", {})
            if metadata.get("location"):
                suggestions.append(f"{metadata['location']}의 다음주 예측을 해주세요")
        
        # 기본 제안
        if not suggestions:
            suggestions = [
                "과거 데이터를 그래프로 보여주세요",
                "예측 모델을 사용할 수 있나요?",
            ]
        
        return suggestions[:3]  # 최대 3개만

