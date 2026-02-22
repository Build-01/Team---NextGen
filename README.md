# Team---NextGen (HealthBud)

HealthBud is a healthcare chatbot web app with a static frontend and a FastAPI backend.

## Stack
- Frontend: HTML, CSS, Vanilla JavaScript (`HealthBud_Frontend`)
- Backend: Python, FastAPI, SQLAlchemy, Pydantic Settings (`Backend`)
- AI providers: OpenRouter or Gemini (provider switch via env)
- Search: DuckDuckGo trusted-medical-domain filtering
- Database: SQLite (`chats`, `symptoms`, `chat_messages`)
- Deployment: Vercel (`api/index.py` + static routes)

## Core process
1. User sends message in chat.
2. Backend runs triage assessment (AI or safe fallback).
3. Backend stores chat + symptoms + turn-level messages.
4. Frontend shows urgency, red flags, remedies, and follow-up questions.
5. Optional endpoints:
	 - analyze stored chat with web evidence
	 - fetch session chat logs

## Main APIs
- `GET /health`
- `POST /api/v1/chat/assess`
- `GET /api/v1/chat/{chat_number}/analyze`
- `GET /api/v1/chat/session/{session_id}/logs`

## Run locally
1. Install deps: `pip install -r requirements.txt`
2. Create `Backend/.env` and set keys (OpenRouter or Gemini)
3. Start API: `uvicorn Backend.app.main:app --reload --port 8000`

## Deploy
- From project root: `vercel.cmd --prod --yes`

## Safety
HealthBud is for informational triage support only, not medical diagnosis.