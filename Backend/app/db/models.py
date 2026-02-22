from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base


class ChatRecord(Base):
    __tablename__ = "chats"

    chat_number: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(String(15), default="en-NG")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    biological_sex: Mapped[str | None] = mapped_column(String(20), nullable=True)
    chronic_conditions: Mapped[list[str]] = mapped_column(JSON, default=list)
    current_medications: Mapped[list[str]] = mapped_column(JSON, default=list)
    allergies: Mapped[list[str]] = mapped_column(JSON, default=list)

    assessment: Mapped[dict[str, Any]] = mapped_column(JSON)

    symptoms: Mapped[list["SymptomRecord"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["ChatMessageRecord"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
    )


class SymptomRecord(Base):
    __tablename__ = "symptoms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_number: Mapped[int] = mapped_column(ForeignKey("chats.chat_number", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[int] = mapped_column(Integer)
    symptom_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    body_location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    character: Mapped[str | None] = mapped_column(String(120), nullable=True)
    aggravating_factors: Mapped[list[str]] = mapped_column(JSON, default=list)
    radiation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    duration_pattern: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timing_pattern: Mapped[str | None] = mapped_column(String(120), nullable=True)
    relieving_factors: Mapped[list[str]] = mapped_column(JSON, default=list)
    associated_symptoms: Mapped[list[str]] = mapped_column(JSON, default=list)
    progression: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_constant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    duration_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    chat: Mapped[ChatRecord] = relationship(back_populates="symptoms")


class ChatMessageRecord(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_number: Mapped[int] = mapped_column(ForeignKey("chats.chat_number", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    chat: Mapped[ChatRecord] = relationship(back_populates="messages")
