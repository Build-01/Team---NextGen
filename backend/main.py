import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import DateTime, Integer, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/health_chatbot"
)


class Base(DeclarativeBase):
    pass


class SymptomEntry(Base):
    __tablename__ = "symptom_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    symptom: Mapped[str] = mapped_column(String(255), index=True)
    raw_input: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    input_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    experienced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    severity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


KNOWN_SYMPTOMS = [
    "fever",
    "cough",
    "headache",
    "nausea",
    "vomiting",
    "sore throat",
    "fatigue",
    "dizziness",
    "chest pain",
    "shortness of breath",
    "diarrhea",
    "body ache",
    "congestion",
]
MAX_EXTRACTED_SYMPTOMS = 5


class SymptomIntakeRequest(BaseModel):
    user_id: Optional[str] = Field(default=None, min_length=1)
    message: Optional[str] = Field(default=None, min_length=1)
    symptoms: list[str] = Field(default_factory=list)
    experienced_at: Optional[datetime] = None
    severity: Optional[int] = Field(default=None, ge=1, le=10)
    duration_days: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def ensure_message_or_symptoms(self) -> "SymptomIntakeRequest":
        if not self.message and not self.symptoms:
            raise ValueError("Either message or symptoms must be provided")
        return self


class SymptomEntryResponse(BaseModel):
    id: int
    user_id: str
    symptom: str
    input_at: datetime
    experienced_at: Optional[datetime]
    severity: Optional[int]
    duration_days: Optional[int]
    notes: Optional[str]


class IntakeResponse(BaseModel):
    stored_entries: list[SymptomEntryResponse]


def extract_symptoms(message: str) -> list[str]:
    lower_message = message.lower()
    extracted = [symptom for symptom in KNOWN_SYMPTOMS if symptom in lower_message]
    if extracted:
        return extracted
    chunks = [chunk.strip() for chunk in message.split(",") if chunk.strip()]
    return chunks[:MAX_EXTRACTED_SYMPTOMS]


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Health Chatbot Backend", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chatbot/intake", response_model=IntakeResponse)
def intake_symptoms(payload: SymptomIntakeRequest, x_user_id: Optional[str] = Header(default=None)) -> IntakeResponse:
    user_id = x_user_id or payload.user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing user_id (header X-User-Id or body user_id)")

    symptoms = payload.symptoms or extract_symptoms(payload.message or "")
    if not symptoms:
        raise HTTPException(status_code=400, detail="Could not identify any symptoms")

    with SessionLocal() as db:  # type: Session
        saved_entries: list[SymptomEntry] = []
        for symptom in symptoms:
            entry = SymptomEntry(
                user_id=user_id,
                symptom=symptom,
                raw_input=payload.message,
                experienced_at=payload.experienced_at,
                severity=payload.severity,
                duration_days=payload.duration_days,
                notes=payload.notes,
            )
            db.add(entry)
            saved_entries.append(entry)

        db.commit()
        for entry in saved_entries:
            db.refresh(entry)

    return IntakeResponse(
        stored_entries=[
            SymptomEntryResponse(
                id=entry.id,
                user_id=entry.user_id,
                symptom=entry.symptom,
                input_at=entry.input_at,
                experienced_at=entry.experienced_at,
                severity=entry.severity,
                duration_days=entry.duration_days,
                notes=entry.notes,
            )
            for entry in saved_entries
        ]
    )


@app.get("/users/{user_id}/symptoms", response_model=list[SymptomEntryResponse])
def get_user_symptoms(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[SymptomEntryResponse]:
    with SessionLocal() as db:  # type: Session
        rows = (
            db.query(SymptomEntry)
            .filter(SymptomEntry.user_id == user_id)
            .order_by(SymptomEntry.input_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    return [
        SymptomEntryResponse(
            id=row.id,
            user_id=row.user_id,
            symptom=row.symptom,
            input_at=row.input_at,
            experienced_at=row.experienced_at,
            severity=row.severity,
            duration_days=row.duration_days,
            notes=row.notes,
        )
        for row in rows
    ]
