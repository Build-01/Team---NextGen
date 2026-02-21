from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.chat import router as chat_router
from app.core.config import get_settings
from app.db.session import init_db



import os
from dotenv import load_dotenv

load_dotenv()  # This loads the variables from .env into os.environ
api_key = os.getenv("GEMINI_API_KEY")

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(chat_router, prefix="/api/v1")
