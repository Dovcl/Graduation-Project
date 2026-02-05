"""
LLM 서비스 - OpenAI API 호출
"""
from typing import List
from openai import AsyncOpenAI
from app.core.config import settings
from app.schemas.chat import Message


# 컨텍스트 최대 글자 수 (시스템 프롬프트 + 컨텍스트 + 히스토리 합산)
MAX_CONTEXT_CHARS = 6000
MAX_HISTORY_MSG_CHARS = 400


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
        """
        # 시스템 프롬프트
        system_prompt = """환경 데이터 분석 전문가로서 수질·녹조 데이터에 대해 한국어로 답변하세요.

[규칙]
- 컨텍스트 정보를 우선 활용. 없으면 일반 지식으로 보완.
- 위치명 예시는 컨텍스트의 "사용 가능한 위치 목록"에서만 사용. 목록에 없는 위치는 절대 제시 금지.
- 출처는 사용자가 명시적으로 요청할 때만 표시.
- 예측 결과 제공 시: "과거 7주 관측 데이터 기반 다음 1주 예측"임을 명시. 참고용임을 안내.
- 예측값이 높으면 "가이드라인을 설명해드릴까요?"라고 제안.

[중요] 가이드라인 요청 처리:
- 사용자가 "가이드라인 제시해줘", "가이드라인 알려줘", "대응 방법 알려줘" 같은 요청을 하면:
  1. 컨텍스트에 가이드라인 문서가 있으면 그 내용을 바탕으로 단계별로 정리하여 제시하세요.
  2. 가이드라인 문서가 없거나 부족하면, 일반적인 녹조 대응 방법을 단계별로 설명하세요.
  3. 반드시 구체적인 수치나 기준을 포함하세요 (예: 1,000 cells/ml 이상이면 주의, 10,000 cells/ml 이상이면 경보 등).
  4. 단계별로 명확하게 정리하여 제시하세요 (1단계, 2단계 등).
  5. 절대 빈 답변을 반환하지 마세요. 최소한 일반적인 대응 방법이라도 설명하세요."""

        # 컨텍스트 크기 제한
        if context:
            max_ctx = MAX_CONTEXT_CHARS
            if len(context) > max_ctx:
                context = context[:max_ctx] + "\n...(일부 생략)"
            system_prompt += f"\n\n=== 참고 정보 ===\n{context}"

        messages = [{"role": "system", "content": system_prompt}]

        # 히스토리 추가 (최근 5개, 각 메시지 길이 제한)
        if history:
            for msg in history[-5:]:
                content = msg.content
                if len(content) > MAX_HISTORY_MSG_CHARS:
                    content = content[:MAX_HISTORY_MSG_CHARS] + "...(이하 생략)"
                messages.append({"role": msg.role, "content": content})

        # 현재 메시지 추가
        messages.append({"role": "user", "content": message})

        # 전체 메시지 크기 로깅
        total_chars = sum(len(m["content"]) for m in messages)
        print(f"ℹ LLM 호출: messages={len(messages)}개, total_chars={total_chars}")

        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_completion_tokens=4096
            )

            content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason

            if not content or not content.strip():
                print(f"⚠ LLM 빈 응답: finish_reason={finish_reason}, total_chars={total_chars}")
                return "죄송합니다. 응답을 생성하지 못했습니다. 질문을 다시 시도해주세요."

            if finish_reason == "length":
                print(f"⚠ LLM 응답 잘림 (finish_reason=length), 하지만 부분 응답 반환")

            return content

        except Exception as e:
            print(f"❌ LLM 오류: {e}")
            return f"오류가 발생했습니다: {str(e)}"
