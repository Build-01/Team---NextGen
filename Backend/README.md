# HealthBud Backend (FastAPI)

Backend API for a health-focused AI chatbot intake flow.

## What this version includes
- FastAPI server with CORS enabled for frontend integration
- `POST /api/v1/chat/assess` endpoint for health concern triage
- OpenAI-backed response generation when `OPENAI_API_KEY` is set
- Safe fallback triage logic when no API key is configured

## Quick start
1. Create and activate a virtual environment
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy environment file:
   ```bash
   copy .env.example .env
   ```
4. Add your OpenAI key in `.env` (optional but recommended):
   ```env
   OPENAI_API_KEY=your_key_here
   ```
5. Run the server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

## API sample
`POST /api/v1/chat/assess`

Request body:
```json
{
  "message": "I have had chest discomfort and shortness of breath since this morning.",
  "symptoms": [
    {"name": "chest pain", "severity": 8, "duration_hours": 10},
    {"name": "shortness of breath", "severity": 7, "duration_hours": 6}
  ],
  "patient_context": {
    "age": 41,
    "biological_sex": "female",
    "chronic_conditions": ["hypertension"],
    "current_medications": ["amlodipine"],
    "allergies": []
  },
  "locale": "en-NG"
}
```

The response returns a structured triage payload your frontend can render directly.

## Note
This service provides AI-assisted intake guidance only and is not a medical diagnosis engine.
