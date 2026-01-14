"""
채팅 API 요청/응답 스키마
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class Message(BaseModel):
    """메시지 모델"""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """채팅 요청 모델"""
    message: str
    history: List[Message] = []


class ChatResponse(BaseModel):
    """채팅 응답 모델"""
    answer: str
    suggestions: List[str] = []
    data: Optional[Dict[str, Any]] = None
    visualizations: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

