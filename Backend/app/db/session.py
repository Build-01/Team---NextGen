from collections.abc import Generator
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()
database_url = settings.database_url
if os.getenv("VERCEL") == "1" and database_url.startswith("sqlite:///./"):
    sqlite_filename = database_url.removeprefix("sqlite:///./")
    database_url = f"sqlite:////tmp/{sqlite_filename}"

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}

engine = create_engine(database_url, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def init_db() -> None:
    import app.db.models

    Base.metadata.create_all(bind=engine)
    _ensure_schema_evolution()


def _ensure_schema_evolution() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(chats)"))
        }
        if "session_id" not in columns:
            connection.execute(text("ALTER TABLE chats ADD COLUMN session_id VARCHAR(64)"))

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chats_session_id ON chats (session_id)"
            )
        )

        connection.execute(
            text(
                "UPDATE chats SET session_id = chat_id WHERE session_id IS NULL OR session_id = ''"
            )
        )


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
