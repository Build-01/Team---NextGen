from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.security import rate_limit_chat_analyze, rate_limit_chat_assess
from app.db.models import ChatMessageRecord, ChatRecord, SymptomRecord
from app.db.session import get_db_session
from app.models.chat import (
    ChatAssessmentRequest,
    ChatAssessmentResponse,
    ChatLogEntry,
    ChatSessionLogsResponse,
    StoredChatAnalysisResponse,
)
from app.services.chat_analysis import ChatAnalysisService, get_chat_analysis_service
from app.services.chatbot import ChatbotService, get_chatbot_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/assess", response_model=ChatAssessmentResponse)
async def assess_health_concern(
    payload: ChatAssessmentRequest,
    chatbot_service: ChatbotService = Depends(get_chatbot_service),
    db: Session = Depends(get_db_session),
    _: None = Depends(rate_limit_chat_assess),
) -> ChatAssessmentResponse:
    session_id = payload.session_id or str(uuid4())
    turn_id = str(uuid4())
    recorded_at = datetime.now(UTC)

    settings = get_settings()
    history_limit = max(0, settings.memory_turn_window)
    conversation_history: list[dict] = []
    if history_limit > 0:
        history_statement = (
            select(ChatRecord)
            .where(ChatRecord.session_id == session_id)
            .order_by(ChatRecord.chat_number.desc())
            .limit(history_limit)
        )
        recent_turns = list(db.execute(history_statement).scalars().all())
        recent_turns.reverse()
        for turn in recent_turns:
            turn_assessment = turn.assessment if isinstance(turn.assessment, dict) else {}
            conversation_history.append(
                {
                    "chat_number": turn.chat_number,
                    "recorded_at": turn.recorded_at.isoformat() if turn.recorded_at else None,
                    "user_message": turn.message,
                    "assistant_message": str(turn_assessment.get("assistant_message") or ""),
                    "summary": str(turn_assessment.get("summary") or ""),
                    "urgency_level": str(turn_assessment.get("urgency_level") or ""),
                }
            )

    assessment = chatbot_service.assess_health_input(payload, conversation_history=conversation_history)

    patient_context = payload.patient_context
    chat_record = ChatRecord(
        chat_id=turn_id,
        session_id=session_id,
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

    db.add_all(
        [
            ChatMessageRecord(
                chat_number=chat_record.chat_number,
                session_id=session_id,
                role="user",
                content=payload.message,
                created_at=recorded_at,
            ),
            ChatMessageRecord(
                chat_number=chat_record.chat_number,
                session_id=session_id,
                role="assistant",
                content=assessment.assistant_message,
                created_at=recorded_at,
            ),
        ]
    )
    db.commit()

    return ChatAssessmentResponse(
        chat_number=chat_record.chat_number,
        session_id=session_id,
        timestamp=recorded_at,
        assessment=assessment,
    )


@router.get("/{chat_number}/analyze", response_model=StoredChatAnalysisResponse)
async def analyze_stored_chat(
    chat_number: int,
    db: Session = Depends(get_db_session),
    analysis_service: ChatAnalysisService = Depends(get_chat_analysis_service),
    _: None = Depends(rate_limit_chat_analyze),
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


@router.get("/session/{session_id}/logs", response_model=ChatSessionLogsResponse)
async def get_session_logs(
    session_id: str,
    db: Session = Depends(get_db_session),
    _: None = Depends(rate_limit_chat_assess),
) -> ChatSessionLogsResponse:
    statement = (
        select(ChatMessageRecord)
        .where(ChatMessageRecord.session_id == session_id)
        .order_by(ChatMessageRecord.created_at.asc(), ChatMessageRecord.id.asc())
    )
    rows = list(db.execute(statement).scalars().all())

    return ChatSessionLogsResponse(
        session_id=session_id,
        total_messages=len(rows),
        logs=[
            ChatLogEntry(
                id=item.id,
                role=item.role,
                content=item.content,
                timestamp=item.created_at,
            )
            for item in rows
        ],
    )
