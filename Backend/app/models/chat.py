from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class SymptomInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    severity: int = Field(..., ge=0, le=10)
    symptom_started_at: datetime | None = None
    body_location: str | None = Field(default=None, max_length=120)
    character: str | None = Field(default=None, max_length=120)
    aggravating_factors: list[str] = Field(default_factory=list, max_length=12)
    radiation: str | None = Field(default=None, max_length=200)
    duration_pattern: str | None = Field(default=None, max_length=120)
    timing_pattern: str | None = Field(default=None, max_length=120)
    relieving_factors: list[str] = Field(default_factory=list, max_length=12)
    associated_symptoms: list[str] = Field(default_factory=list, max_length=20)
    progression: str | None = Field(default=None, max_length=120)
    is_constant: bool | None = None
    duration_hours: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=500)


class PatientContext(BaseModel):
    age: int | None = Field(default=None, ge=0, le=130)
    biological_sex: str | None = Field(default=None, max_length=20)
    chronic_conditions: list[str] = Field(default_factory=list, max_length=25)
    current_medications: list[str] = Field(default_factory=list, max_length=25)
    allergies: list[str] = Field(default_factory=list, max_length=25)


class UrgencyLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    emergency = "emergency"


class AssessmentData(BaseModel):
    assistant_message: str
    show_structured_output: bool = True
    summary: str
    follow_up_questions: list[str] = Field(default_factory=list)
    possible_conditions: list[str] = Field(default_factory=list)
    possible_remedies: list[str] = Field(default_factory=list)
    urgency_level: UrgencyLevel
    urgency_reason: str
    seek_care_within: str
    red_flags: list[str] = Field(default_factory=list)
    specialist_types: list[str] = Field(default_factory=list)
    safety_disclaimer: str


class ChatAssessmentRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    symptoms: list[SymptomInput] = Field(default_factory=list, max_length=20)
    patient_context: PatientContext | None = None
    locale: str = Field(default="en-NG", max_length=15, pattern=r"^[a-zA-Z]{2,3}(?:-[a-zA-Z]{2,4})?$")
    session_id: str | None = Field(default=None, max_length=64, pattern=r"^[a-zA-Z0-9-]+$")

    @field_validator("message")
    @classmethod
    def validate_message_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message cannot be blank")
        return cleaned


class ChatAssessmentResponse(BaseModel):
    chat_number: int
    session_id: str
    timestamp: datetime
    assessment: AssessmentData


class EvidenceSource(BaseModel):
    title: str
    url: str
    snippet: str


class ConditionAnalysis(BaseModel):
    condition: str
    confidence: float = Field(..., ge=0, le=1)
    rationale: str
    related_symptoms: list[str] = Field(default_factory=list)
    recommended_remedies: list[str] = Field(default_factory=list)
    doctor_specialties: list[str] = Field(default_factory=list)
    evidence: list[EvidenceSource] = Field(default_factory=list)


class StoredChatAnalysisResponse(BaseModel):
    chat_number: int
    session_id: str
    analyzed_at: datetime
    urgency_level: UrgencyLevel
    urgency_reason: str
    seek_care_within: str
    conditions: list[ConditionAnalysis] = Field(default_factory=list)
    recommended_remedies: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    disclaimer: str


class ChatLogEntry(BaseModel):
    id: int
    role: str
    content: str
    timestamp: datetime


class ChatSessionLogsResponse(BaseModel):
    session_id: str
    total_messages: int
    logs: list[ChatLogEntry] = Field(default_factory=list)
