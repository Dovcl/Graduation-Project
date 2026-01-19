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
from app.database import SessionLocal


class ChatService:
    """채팅 오케스트레이터 서비스"""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.rag_service = RAGService()  # 기존 RAG (호환성 유지)
        self.rag_service_langchain = RAGServiceLangChain()  # LangChain RAG
        self.data_service = DataService()
        self.prediction_service = PredictionService()
    
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
                        # 가이드라인 관련 문서 추가 검색
                        guideline_query = "녹조 대응 방법 가이드라인 예방 조치"
                        guideline_docs = await self.rag_service_langchain.search(
                            guideline_query, top_k=2, db=db
                        )
                        # 기존 RAG 문서에 가이드라인 문서 추가 (중복 제거)
                        existing_sources = {doc.get("source") for doc in rag_docs}
                        for doc in guideline_docs:
                            if doc.get("source") not in existing_sources:
                                rag_docs.append(doc)
            
            # 5. 컨텍스트 구성
            context = self._build_context(rag_docs, env_data, prediction_result)
            
            # 6. LLM 호출 (컨텍스트 포함)
            answer = await self.llm_service.generate_answer(
                message=message,
                history=history,
                context=context
            )
            
            # 7. 응답 포맷팅
            suggestions = self._generate_suggestions(
                message, rag_docs, env_data, prediction_result
            )
            
            return ChatResponse(
                answer=answer,
                suggestions=suggestions,
                data=env_data if env_data.get("results") else None,
                metadata={
                    "rag_documents_count": len(rag_docs),
                    "data_results_count": env_data.get("statistics", {}).get("count", 0),
                    "prediction_performed": prediction_info["needs_prediction"]
                }
            )
        
        finally:
            db.close()
    
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
        
        # 긴 위치명부터 매칭 (예: "강정고령보"가 "강정"보다 우선)
        sorted_keywords = sorted(location_keywords, key=len, reverse=True)
        
        for keyword in sorted_keywords:
            if keyword in message:
                location = keyword
                break
        
        # 타겟 날짜 계산 (기준 날짜 + 주 단위)
        target_date = base_date + timedelta(weeks=weeks_ahead)
        
        return {
            "needs_prediction": True,
            "location": location,
            "target_date": target_date,
            "weeks_ahead": weeks_ahead
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
        prediction_result: Optional[Dict[str, Any]] = None
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
            for i, doc in enumerate(sorted_docs, 1):
                doc_type = "[가이드라인] " if doc in guideline_docs else ""
                context_parts.append(f"\n[문서 {i}] {doc_type}{doc.get('title', '제목 없음')}")
                context_parts.append(f"출처: {doc.get('source', '알 수 없음')}")
                context_parts.append(f"내용: {doc.get('content', '')[:300]}...")
        
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
                
                context_parts.append(f"위치: {prediction_result.get('location', '알 수 없음')}")
                context_parts.append(f"예측 날짜: {prediction_result.get('target_date', '알 수 없음')}")
                
                # 데이터베이스 정보 및 사용된 데이터 정보
                db_date_range = data_info.get("db_date_range", {})
                used_base_date = data_info.get("used_base_date")
                data_source = data_info.get("data_source")
                data_date_range = data_info.get("data_date_range", {})
                
                context_parts.append("\n[데이터베이스 정보]")
                if db_date_range.get("min") and db_date_range.get("max"):
                    context_parts.append(f"데이터베이스에 저장된 날짜 범위: {db_date_range['min']} ~ {db_date_range['max']}")
                
                if data_source == "latest_available" and used_base_date:
                    context_parts.append(f"⚠ 요청한 예측 날짜({prediction_result.get('target_date')}) 기준으로 과거 7주 데이터가 없어,")
                    context_parts.append(f"  데이터베이스의 최신 데이터 날짜({used_base_date}) 기준으로 예측을 수행했습니다.")
                
                if data_date_range.get("min") and data_date_range.get("max"):
                    context_parts.append(f"실제 예측에 사용된 데이터 날짜 범위: {data_date_range['min']} ~ {data_date_range['max']}")
                
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
                    context_parts.append("\n⚠ 예측 기반 경고:")
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
        
        # 예측 결과가 있을 때 제안
        if prediction_result and prediction_result.get("success"):
            # 예측 결과가 높을 때 가이드라인 제안 우선
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

