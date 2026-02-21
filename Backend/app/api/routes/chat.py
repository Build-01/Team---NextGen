from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends

from app.models.chat import ChatAssessmentRequest, ChatAssessmentResponse
from app.services.chatbot import ChatbotService, get_chatbot_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/assess", response_model=ChatAssessmentResponse)
async def assess_health_concern(
    payload: ChatAssessmentRequest,
    chatbot_service: ChatbotService = Depends(get_chatbot_service),
) -> ChatAssessmentResponse:
    assessment = chatbot_service.assess_health_input(payload)

    return ChatAssessmentResponse(
        session_id=payload.session_id or str(uuid4()),
        timestamp=datetime.now(UTC),
        assessment=assessment,
    )
