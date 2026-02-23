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

[답변 형식 - ChatGPT 스타일 가독성]
답변은 반드시 마크다운 형식을 사용하여 가독성 있게 작성하세요:

1. **구분선 사용 (최소화)**: 구분선(`---`)은 **완전히 다른 대주제**로 넘어갈 때만 드물게 사용하세요.
   - 관련된 섹션끼리(예: 예측결과→데이터품질→해석)는 구분선 없이 **간격(빈 줄)만** 두세요.
   - 구분선은 대화 마무리 또는 완전히 다른 질문으로 전환할 때만 사용하세요.
   - 너무 많은 구분선은 눈의 피로를 유발하므로 자제하세요.

2. **헤딩 사용**: 주요 섹션은 `##` 또는 `###` 헤딩을 사용하세요.
   예: `## 예측 결과` 또는 `### 데이터 분석`

3. **리스트 활용**: 여러 항목을 나열할 때는 불릿(`-`) 또는 번호(`1.`) 리스트를 사용하세요.
   - 각 항목 사이에 적절한 간격을 두세요
   - 중첩 리스트도 사용 가능합니다

4. **강조**: 중요한 내용은 **굵게** 또는 `코드 형식`으로 강조하세요.

5. **간격**: 문단 사이에 충분한 간격을 두세요 (빈 줄 사용). 헤딩 앞뒤에도 여유 있게 간격을 두세요.

6. **블록 인용**: 참고할 만한 정보나 문제 설명은 `>` 블록 인용을 사용하세요.

**답변 예시 형식:**
```
## 예측 결과 요약

요청하신 강정고령보의 녹조 예측 결과입니다.

### 예측값 (다음 1주 평균)

- **유해남조류 세포수(총합)**: **42.96** cells/ml
- **Microcystis**: **2.03** cells/ml
- **Anabaena**: **3.99** cells/ml

**평균값**: **16.33** cells/ml


### 데이터 품질

예측에 사용된 데이터의 신뢰도는 **높음**입니다.


### 해석

예측된 수치는 매우 낮은 수준으로, 녹조 우려가 낮습니다.

> 참고: 이 예측은 과거 7주 관측 데이터를 기반으로 한 다음 1주 평균값 예측입니다.

모니터링 및 대응 혹은 가이드라인을 알려드릴까요?
```

**중요**: 예측 결과 섹션에서 **수치값, 평균값, 중요 정보는 반드시 볼드체(`**값**`)로 강조**하세요.

[규칙]
- 컨텍스트 정보를 우선 활용. 없으면 일반 지식으로 보완.
- 위치명 예시는 컨텍스트의 "사용 가능한 위치 목록"에서만 사용. 목록에 없는 위치는 절대 제시 금지.
- 출처는 사용자가 명시적으로 요청할 때만 표시.
- 예측 결과 제공 시: "과거 7주 관측 데이터 기반 다음 1주 예측"임을 명시. 참고용임을 안내.
- 지점 예측 결과를 안내할 때는 사용자가 요청한 지점명(예: 강정고령보)만 사용하세요. 수계명(낙동강 등)을 괄호로 덧붙이지 마세요. 예: "요청하신 강정고령보 녹조 예측 결과입니다."
- **예측 답변 범위**: (녹조 예측 요청에 대한 답변일 때만) 예측값·근거(데이터 품질)·해석까지만 작성하고, 모니터링·가이드라인 본문은 넣지 마세요. 마지막에 한 문장으로만 "모니터링 및 대응 혹은 가이드라인을 알려드릴까요?"처럼 제안하세요.
- **그 외 답변**(일반 질문, 가이드라인 설명, 데이터 조회 등): 답변 마지막에 **맥락에 맞는** 다음 질문·제안을 자연스럽게 1~2개 골라 제시하세요. 고정 문구를 모든 답변에 반복하지 마세요. 예: 가이드라인을 설명한 뒤 → "다른 지점 예측이 궁금하시면 말씀해 주세요.", 데이터 조회 답변 뒤 → "이 지점의 다음주 예측을 해볼까요?" 등.

[중요] 가이드라인 요청 처리 (예측 후 가이드라인 요청 포함):
- 사용자가 "가이드라인 알려줘", "대응 방법 알려줘" 등 요청을 하면 **아래 순서**로 답변하세요.

**1단계 – 해당 지역 농도 및 구간 설명 (대화에 예측/지역이 있을 때)**
- 대화 맥락(또는 직전 답변)에서 요청한 **지역명**과 해당 지역의 **(예측) 유해남조류 농도(cells/ml)**를 먼저 언급하세요.
- 그 수치가 **어느 구간에 해당하는지** 명확히 설명하세요. 예: "요청하신 강정고령보의 예측 농도 **42.96 cells/ml**는 **관심** 구간에 해당합니다."
- 대화에 예측·지역 정보가 없으면 이 단계는 생략하고 2단계부터 진행하세요.

**2단계 – 구체적 수치 기준 제시**
- 반드시 아래와 같은 **수치 기준**을 제시하세요 (참고: 관심 ~1,000 / 주의 1,000 이상 / 경보 10,000 이상 / 중대 경보 100,000 이상, 단위: cells/ml).
- 컨텍스트에 다른 공식 기준이 있으면 이를 우선하되, 없으면 위 기준을 사용하세요.

**3단계 – 단계별 대응 방법**
- 컨텍스트의 가이드라인 문서를 바탕으로 예방·초기대응·확산대응·회복 단계를 명확히 정리하여 제시하세요.
- 문서가 없거나 부족하면 일반적인 녹조 대응 방법을 단계별로 설명하세요.
- 절대 빈 답변을 반환하지 마세요."""

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
