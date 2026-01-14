"""
채팅 API 엔드포인트
"""
from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter()

# 서비스 인스턴스는 함수 내에서 생성 (지연 초기화)
def get_chat_service():
    return ChatService()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    채팅 메시지 처리
    
    - **message**: 사용자 메시지
    - **history**: 대화 히스토리 (선택적)
    
    응답:
    - **answer**: 챗봇 답변
    - **suggestions**: 제안 질문 목록
    - **data**: 관련 데이터 (선택적)
    - **visualizations**: 시각화 정보 (선택적)
    """
    try:
        chat_service = get_chat_service()
        response = await chat_service.process_message(
            message=request.message,
            history=request.history
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

