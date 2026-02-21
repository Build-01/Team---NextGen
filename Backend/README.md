# HealthBud Backend (FastAPI)

Backend API for a health-focused AI chatbot intake flow.

## What this version includes
- FastAPI server with CORS enabled for frontend integration
- `POST /api/v1/chat/assess` endpoint for health concern triage
- SQLite-backed database tables for chats and symptoms
- `GET /api/v1/chat/{chat_number}/analyze` endpoint to analyze stored chat records
- Gemini-backed response generation when `GEMINI_API_KEY` is set
- Internet evidence search from trusted medical domains for grounded condition suggestions
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
4. Add your Gemini key in `.env` (optional but recommended):
   ```env
   GEMINI_API_KEY=your_key_here
   GEMINI_MODEL=gemini-2.0-flash
   DATABASE_URL=sqlite:///./healthbud.db
   ENABLE_WEB_SEARCH=true
   WEB_SEARCH_MAX_RESULTS=8
   TRUSTED_MEDICAL_DOMAINS=mayoclinic.org,medlineplus.gov,nhs.uk,who.int,cdc.gov,clevelandclinic.org,webmd.com
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
      {
         "name": "chest pain",
         "severity": 8,
         "symptom_started_at": "2026-02-21T09:30:00Z",
         "body_location": "left chest",
         "character": "sharp",
         "aggravating_factors": ["walking", "deep breathing"],
         "radiation": "to left arm",
         "duration_pattern": "intermittent",
         "timing_pattern": "worse at night",
         "relieving_factors": ["rest"],
         "associated_symptoms": ["nausea"],
         "progression": "worsening",
         "is_constant": false,
         "duration_hours": 10,
         "notes": "Started after climbing stairs"
      },
      {
         "name": "shortness of breath",
         "severity": 7,
         "duration_hours": 6
      }
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

The response returns a structured triage payload plus a stored `chat_number`.

## Analyze stored chat records
Use the persisted `chat_number` to trigger grounded analysis from DB data:

- `GET /api/v1/chat/{chat_number}/analyze`

Response includes:
- condition candidates tied to stored symptom characteristics
- confidence per condition
- evidence links from trusted medical sources
- recommended low-risk remedies
- urgency assessment and how soon to seek care

## Database structure
- `chats`
   - `chat_number` (primary key)
   - `chat_id` (external session/chat id)
   - `message`, `locale`, `recorded_at`
   - patient context: `age`, `biological_sex`, `chronic_conditions`, `current_medications`, `allergies`
   - `assessment` (JSON output from chatbot)
- `symptoms`
   - `id` (primary key), `chat_number` (foreign key to chats)
   - `name`, `severity` (0-10)
   - `symptom_started_at`, `recorded_at`
   - `body_location`, `character`, `aggravating_factors`, `radiation`
   - `duration_pattern`, `timing_pattern`, `relieving_factors`
   - `associated_symptoms`, `progression`, `is_constant`, `duration_hours`, `notes`

## Note
This service provides AI-assisted intake guidance only and is not a medical diagnosis engine.
