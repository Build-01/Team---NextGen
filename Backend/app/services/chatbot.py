import json
from functools import lru_cache

from openai import OpenAI

from app.core.config import get_settings
from app.models.chat import AssessmentData, ChatAssessmentRequest, UrgencyLevel


SYSTEM_PROMPT = """
You are HealthBud, a healthcare intake and triage assistant for web users.
- You are not a doctor and must not provide final diagnosis.
- Use the user's message and symptom details to produce a structured triage summary.
- Be careful and conservative with safety; escalate if emergency red flags are present.
- Keep remedies general and low-risk, and always include clear safety disclaimer.
Return only valid JSON with the following keys exactly:
summary, follow_up_questions, possible_conditions, possible_remedies,
urgency_level, urgency_reason, seek_care_within, red_flags, specialist_types, safety_disclaimer.
urgency_level must be one of: low, medium, high, emergency.
""".strip()


class ChatbotService:
    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.openai_model
        self._client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def assess_health_input(self, payload: ChatAssessmentRequest) -> AssessmentData:
        if self._client is None:
            return self._fallback_assessment(payload)

        user_input = {
            "message": payload.message,
            "symptoms": [symptom.model_dump() for symptom in payload.symptoms],
            "patient_context": payload.patient_context.model_dump() if payload.patient_context else {},
            "locale": payload.locale,
        }

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(user_input)},
                ],
            )
            content = response.choices[0].message.content or "{}"
            parsed = json.loads(content)
            return AssessmentData.model_validate(parsed)
        except Exception:
            return self._fallback_assessment(payload)

    def _fallback_assessment(self, payload: ChatAssessmentRequest) -> AssessmentData:
        text = payload.message.lower()
        symptom_names = [symptom.name.lower() for symptom in payload.symptoms]
        combined = " ".join([text, *symptom_names])

        emergency_terms = [
            "chest pain",
            "difficulty breathing",
            "can't breathe",
            "stroke",
            "seizure",
            "fainted",
            "passed out",
            "bleeding heavily",
        ]

        high_terms = ["high fever", "persistent vomiting", "severe headache", "blood pressure"]

        if any(term in combined for term in emergency_terms):
            urgency = UrgencyLevel.emergency
            seek_care = "Immediately (call emergency services now)."
            reason = "Possible emergency warning signs were detected in your symptoms."
            conditions = ["Cardiovascular emergency", "Respiratory emergency", "Neurological emergency"]
            specialists = ["Emergency Medicine", "Cardiology", "Neurology"]
        elif any(term in combined for term in high_terms):
            urgency = UrgencyLevel.high
            seek_care = "Within 4-12 hours, preferably urgent care or ER if worsening."
            reason = "Potentially serious symptoms may need rapid in-person evaluation."
            conditions = ["Acute infection", "Migraine or neurological issue", "Metabolic issue"]
            specialists = ["Internal Medicine", "Emergency Medicine", "Neurology"]
        else:
            urgency = UrgencyLevel.medium
            seek_care = "Within 24-48 hours if symptoms persist or worsen."
            reason = "Symptoms appear non-emergency but should still be reviewed clinically."
            conditions = ["Viral illness", "Mild gastrointestinal issue", "Stress-related symptoms"]
            specialists = ["General Practitioner", "Internal Medicine"]

        return AssessmentData(
            summary="Preliminary triage generated from your message and symptom details.",
            follow_up_questions=[
                "When did each symptom start, and has it changed over time?",
                "Do you have fever, chest pain, shortness of breath, or fainting?",
                "What medications have you taken for this and did they help?",
            ],
            possible_conditions=conditions,
            possible_remedies=[
                "Rest, hydration, and symptom monitoring.",
                "Use only previously prescribed or pharmacist-recommended over-the-counter medicine.",
                "Avoid strenuous activity until assessed if symptoms are worsening.",
            ],
            urgency_level=urgency,
            urgency_reason=reason,
            seek_care_within=seek_care,
            red_flags=[
                "Severe chest pain",
                "Difficulty breathing",
                "Confusion, fainting, or seizures",
                "Uncontrolled bleeding",
            ],
            specialist_types=specialists,
            safety_disclaimer="This is not a medical diagnosis. If symptoms are severe, worsening, or you feel unsafe, seek urgent in-person medical care immediately.",
        )


@lru_cache
def get_chatbot_service() -> ChatbotService:
    return ChatbotService()
