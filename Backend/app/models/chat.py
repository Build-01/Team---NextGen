from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SymptomInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    severity: int = Field(..., ge=0, le=10)
    symptom_started_at: datetime | None = None
    body_location: str | None = Field(default=None, max_length=120)
    character: str | None = Field(default=None, max_length=120)
    aggravating_factors: list[str] = Field(default_factory=list)
    radiation: str | None = Field(default=None, max_length=200)
    duration_pattern: str | None = Field(default=None, max_length=120)
    timing_pattern: str | None = Field(default=None, max_length=120)
    relieving_factors: list[str] = Field(default_factory=list)
    associated_symptoms: list[str] = Field(default_factory=list)
    progression: str | None = Field(default=None, max_length=120)
    is_constant: bool | None = None
    duration_hours: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=500)


class PatientContext(BaseModel):
    age: int | None = Field(default=None, ge=0, le=130)
    biological_sex: str | None = Field(default=None, max_length=20)
    chronic_conditions: list[str] = Field(default_factory=list)
    current_medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)


class UrgencyLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    emergency = "emergency"


class AssessmentData(BaseModel):
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
    message: str = Field(..., min_length=5, max_length=3000)
    symptoms: list[SymptomInput] = Field(default_factory=list)
    patient_context: PatientContext | None = None
    locale: str = Field(default="en-NG", max_length=15)
    session_id: str | None = None


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
