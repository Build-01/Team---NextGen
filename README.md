# Team---NextGen

Minimal FastAPI backend for a health chatbot that stores symptom intake records per user in PostgreSQL.

## Run locally

```bash
pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg2://postgres:postgres@localhost:5432/health_chatbot'
uvicorn backend.main:app --reload
```

## API

- `POST /chatbot/intake` stores symptom details (`user_id`, `input_at`, `experienced_at`, `symptom`, severity, duration, notes).
- `GET /users/{user_id}/symptoms` retrieves previously stored symptom entries.
