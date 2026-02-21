from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.db.models import ChatRecord, SymptomRecord
from app.db.session import get_db_session
from app.models.chat import ChatAssessmentRequest, ChatAssessmentResponse, StoredChatAnalysisResponse
from app.services.chat_analysis import ChatAnalysisService, get_chat_analysis_service
from app.services.chatbot import ChatbotService, get_chatbot_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/assess", response_model=ChatAssessmentResponse)
async def assess_health_concern(
    payload: ChatAssessmentRequest,
    chatbot_service: ChatbotService = Depends(get_chatbot_service),
    db: Session = Depends(get_db_session),
) -> ChatAssessmentResponse:
    chat_id = payload.session_id or str(uuid4())
    recorded_at = datetime.now(UTC)
    assessment = chatbot_service.assess_health_input(payload)

    patient_context = payload.patient_context
    chat_record = ChatRecord(
        chat_id=chat_id,
        message=payload.message,
        locale=payload.locale,
        recorded_at=recorded_at,
        age=patient_context.age if patient_context else None,
        biological_sex=patient_context.biological_sex if patient_context else None,
        chronic_conditions=patient_context.chronic_conditions if patient_context else [],
        current_medications=patient_context.current_medications if patient_context else [],
        allergies=patient_context.allergies if patient_context else [],
        assessment=assessment.model_dump(mode="json"),
    )

    for symptom in payload.symptoms:
        chat_record.symptoms.append(
            SymptomRecord(
                name=symptom.name,
                severity=symptom.severity,
                symptom_started_at=symptom.symptom_started_at,
                recorded_at=recorded_at,
                body_location=symptom.body_location,
                character=symptom.character,
                aggravating_factors=symptom.aggravating_factors,
                radiation=symptom.radiation,
                duration_pattern=symptom.duration_pattern,
                timing_pattern=symptom.timing_pattern,
                relieving_factors=symptom.relieving_factors,
                associated_symptoms=symptom.associated_symptoms,
                progression=symptom.progression,
                is_constant=symptom.is_constant,
                duration_hours=symptom.duration_hours,
                notes=symptom.notes,
            )
        )

    db.add(chat_record)
    db.commit()
    db.refresh(chat_record)

    return ChatAssessmentResponse(
        chat_number=chat_record.chat_number,
        session_id=chat_id,
        timestamp=recorded_at,
        assessment=assessment,
    )


@router.get("/{chat_number}/analyze", response_model=StoredChatAnalysisResponse)
async def analyze_stored_chat(
    chat_number: int,
    db: Session = Depends(get_db_session),
    analysis_service: ChatAnalysisService = Depends(get_chat_analysis_service),
) -> StoredChatAnalysisResponse:
    statement = (
        select(ChatRecord)
        .options(selectinload(ChatRecord.symptoms))
        .where(ChatRecord.chat_number == chat_number)
    )
    chat_record = db.execute(statement).scalars().first()
    if chat_record is None:
        raise HTTPException(status_code=404, detail="Chat record not found")

    return analysis_service.analyze_stored_chat(chat_record)
