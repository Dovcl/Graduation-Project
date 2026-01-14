"""
LLM 서비스 - OpenAI API 호출
"""
from typing import List
from openai import OpenAI
from app.core.config import settings
from app.schemas.chat import Message


class LLMService:
    """LLM 서비스"""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = "gpt-5-mini"  # GPT-5 Mini 모델
        self.client = None
    
    def _get_client(self):
        """클라이언트 지연 초기화"""
        if self.client is None:
            if not self.api_key or self.api_key == "your_openai_api_key_here" or not self.api_key.startswith("sk-"):
                raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
            self.client = OpenAI(api_key=self.api_key)
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

제공된 컨텍스트 정보를 활용하여 답변하되, 컨텍스트에 없는 내용은 추측하지 마세요.
답변은 한국어로 작성하고, 구체적인 수치와 출처를 명시하세요."""
        
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
            # OpenAI API 호출
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_completion_tokens=128000  # 모델 최대 출력 토큰 (128000)
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            return f"오류가 발생했습니다: {str(e)}"

