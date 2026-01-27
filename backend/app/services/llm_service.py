"""
LLM 서비스 - OpenAI API 호출
"""
from typing import List
from openai import AsyncOpenAI
from app.core.config import settings
from app.schemas.chat import Message


class LLMService:
    """LLM 서비스"""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = "gpt-5-mini"  # GPT-5 Mini 모델
        self.client = None
    
    def _get_client(self):
        """클라이언트 지연 초기화 (비동기)"""
        if self.client is None:
            if not self.api_key or self.api_key == "your_openai_api_key_here" or not self.api_key.startswith("sk-"):
                raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
            self.client = AsyncOpenAI(api_key=self.api_key)
        return self.client
    
    async def generate_answer(
        self, 
        message: str, 
        history: List[Message] = None,
        context: str = ""
    ) -> str:
        """
        LLM을 사용하여 답변 생성
        
        Args:
            message: 사용자 메시지
            history: 대화 히스토리
            context: 추가 컨텍스트 (RAG 문서, 환경 데이터 등)
        
        Returns:
            생성된 답변
        """
        # 대화 히스토리 구성
        messages = []
        
        # 시스템 프롬프트 (컨텍스트 포함)
        system_prompt = """당신은 환경 데이터 분석 전문가입니다. 수질, 녹조, 수문, 기상 데이터에 대해 정확하고 도움이 되는 답변을 제공하세요.

[답변 방식]
- 제공된 컨텍스트 정보(문서, 데이터, 예측 결과)가 있으면 이를 우선적으로 활용하여 답변하세요.
- 컨텍스트에 없는 내용이 필요하면, 당신의 일반 지식과 전문성을 활용하여 보완적으로 답변할 수 있습니다.
- 컨텍스트와 일반 지식이 충돌할 경우, 컨텍스트 정보를 우선하되 이를 명시하세요.
- 답변은 한국어로 작성하고, 구체적인 수치를 명시하세요.

[중요] 위치명 예시 제시 시 주의사항 (절대 규칙):
- 예측이나 데이터 조회를 위한 위치명 예시를 제시할 때는, 반드시 실제 데이터베이스에 존재하는 위치만 제시하세요.
- 컨텍스트에 "사용 가능한 위치 목록"이 제공되면, 그 목록에 있는 위치만 예시로 사용하세요.
- 일반적인 지식으로 알고 있는 위치명(예: "한강 팔당댐", "낙동강 달성" 등)이라도, 데이터베이스에 없다면 절대 예시로 제시하지 마세요.
- 데이터베이스에 등록되지 않은 위치를 제시하면 예측이나 데이터 조회가 불가능하므로, 반드시 제공된 목록 내의 위치만 사용하세요.
- 예시 위치명을 제시할 때는 "(예: 위치명)" 형식으로 명확히 표시하세요.
- 위치 추천을 요청받았을 때, 제공된 "사용 가능한 위치 목록"에서만 선택하여 추천하세요.

[중요] 출처 표현 방식:
- 답변에 직접 출처를 명시하지 마세요. 사용자가 "근거를 알려줘" 또는 "출처를 알려줘"라고 물어볼 때만 출처를 제공하세요.
- 사용자가 출처를 요청하지 않으면, 답변만 제공하고 출처는 언급하지 마세요.

[중요] 예측 모델의 한계:
- 예측 결과가 제공될 경우, 반드시 "이 모델은 과거 7주 실제 관측 데이터 기반입니다"라는 내용을 포함하세요.
- 예측값은 참고용이며, 실제 관측과 다를 수 있음을 명시하세요.
- 1주 이상 미래 예측은 신뢰도가 낮으며, 이 모델은 과거 7주 → 다음 1주 예측 전용임을 설명하세요.
- 예측값을 재귀적으로 사용해 장기 예측하는 것은 절대 하면 안 됨을 명시하세요.

[중요] 예측 결과가 높은 수준으로 나타날 경우:
- 예측 결과를 명확히 설명한 후
- "녹조가 높을 때 대응 방법을 알려드릴까요?" 또는 "가이드라인을 설명해드릴까요?"라고 자연스럽게 제안하세요.
- 사용자가 동의하면 제공된 가이드라인 문서를 바탕으로 구체적인 대응 방법을 설명하세요.

[중요] 출처 요청 처리:
- 사용자가 "근거를 알려줘", "출처를 알려줘", "어떤 근거로 말하는지 알려줘" 같은 요청을 하면:
  - 컨텍스트에 있는 문서 출처를 명시하세요 (예: "기후에너지환경부 녹조발생과 대응보고서", "환경데이터 통계" 등)
  - 사용된 데이터의 위치, 기간, 데이터 타입을 명시하세요
  - 예측 결과의 경우, 사용된 데이터 범위와 모델 정보를 명시하세요"""
        
        if context:
            system_prompt += f"\n\n=== 참고 정보 ===\n{context}"
        
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # 대화 히스토리 추가
        if history:
            for msg in history[-5:]:  # 최근 5개만 사용
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # 현재 메시지 추가
        messages.append({
            "role": "user",
            "content": message
        })
        
        try:
            # OpenAI API 비동기 호출
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_completion_tokens=4096  # 적절한 응답 길이 (gpt-5-mini는 max_completion_tokens 사용)
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"오류가 발생했습니다: {str(e)}"

