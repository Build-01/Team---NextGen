from functools import lru_cache
import logging

from app.core.config import get_settings
from app.models.chat import AssessmentData, ChatAssessmentRequest, UrgencyLevel
from app.services.gemini_client import LLMClient


SYSTEM_PROMPT = """
You are HealthBud, a healthcare intake and triage assistant for web users.
- Reply naturally and conversationally in assistant_message.
- Start with empathy and reassurance in a warm, friendly tone.
- Address the person directly as "you"; never refer to them as "the user", "this user", "the patient", or in third person.
- You can reply to ANY user message (health or non-health).
- If message is not health-related, respond conversationally and gently steer to health check-in.
- For health-related messages, provide practical triage guidance with calm tone.
- Use conversation_history to keep continuity with prior user and assistant turns.
- For health-related messages, include 3 to 6 concise diagnostic follow-up questions in follow_up_questions.
- Prefer targeted questions that clarify onset, duration, severity, associated symptoms, red flags, and relevant medical history.
- You are not a doctor and must not provide final diagnosis.
Return only valid JSON with the following keys exactly:
assistant_message, summary, follow_up_questions, possible_conditions, possible_remedies,
urgency_level, urgency_reason, seek_care_within, red_flags, specialist_types, safety_disclaimer.
urgency_level must be one of: low, medium, high, emergency.
""".strip()

logger = logging.getLogger(__name__)


class ChatbotService:
    def __init__(self) -> None:
        settings = get_settings()
        provider = settings.llm_provider.strip().lower()
        api_key = settings.openrouter_api_key if provider == "openrouter" else settings.gemini_api_key
        model = settings.openrouter_model if provider == "openrouter" else settings.gemini_model
        self._client = LLMClient(
            provider=provider,
            api_key=api_key,
            model=model,
            app_name=settings.openrouter_app_name,
            site_url=settings.openrouter_site_url,
        )

    def assess_health_input(
        self,
        payload: ChatAssessmentRequest,
        conversation_history: list[dict] | None = None,
    ) -> AssessmentData:
        if not self._client.enabled:
            return self._fallback_for_any_message(payload)

        conversation_history = conversation_history or []
        health_related = self._looks_like_health_message(payload, conversation_history)

        user_input = {
            "message": payload.message,
            "symptoms": [symptom.model_dump() for symptom in payload.symptoms],
            "patient_context": payload.patient_context.model_dump() if payload.patient_context else {},
            "locale": payload.locale,
            "conversation_history": conversation_history,
        }

        try:
            parsed = self._client.generate_json(
                system_prompt=SYSTEM_PROMPT,
                user_payload=user_input,
                temperature=0.2,
            )
            normalized = self._normalize_assessment_payload(
                parsed=parsed,
                health_related=health_related,
            )
            return AssessmentData.model_validate(normalized)
        except Exception as exc:
            logger.warning("LLM request failed (%s); using fallback assessment: %s", self._client.provider, exc)
            return self._fallback_for_any_message(payload)

    def _normalize_assessment_payload(self, parsed: dict, health_related: bool) -> dict:
        if not isinstance(parsed, dict):
            raise ValueError("LLM response must be a JSON object")

        urgency_value = parsed.get("urgency_level", "medium")
        urgency = self._normalize_urgency(urgency_value)

        follow_up_questions = parsed.get("follow_up_questions", [])
        if isinstance(follow_up_questions, str):
            follow_up_questions = [follow_up_questions]

        possible_conditions = parsed.get("possible_conditions", [])
        if isinstance(possible_conditions, str):
            possible_conditions = [possible_conditions]

        possible_remedies = parsed.get("possible_remedies", [])
        if isinstance(possible_remedies, str):
            possible_remedies = [possible_remedies]

        red_flags = parsed.get("red_flags", [])
        if isinstance(red_flags, str):
            red_flags = [red_flags]

        specialist_types = parsed.get("specialist_types", [])
        if isinstance(specialist_types, str):
            specialist_types = [specialist_types]

        normalized = {
            "assistant_message": str(parsed.get("assistant_message") or parsed.get("summary") or "I am here to help. Tell me what you are feeling today."),
            "show_structured_output": True,
            "summary": str(parsed.get("summary") or "AI triage assessment generated."),
            "follow_up_questions": [str(item) for item in follow_up_questions],
            "possible_conditions": [str(item) for item in possible_conditions],
            "possible_remedies": [str(item) for item in possible_remedies],
            "urgency_level": urgency,
            "urgency_reason": str(parsed.get("urgency_reason") or "Estimated from symptoms and available context."),
            "seek_care_within": str(parsed.get("seek_care_within") or "Within 24-48 hours if symptoms persist or worsen."),
            "red_flags": [str(item) for item in red_flags],
            "specialist_types": [str(item) for item in specialist_types],
            "safety_disclaimer": str(
                parsed.get("safety_disclaimer")
                or "This is not a medical diagnosis. Seek urgent care for severe or worsening symptoms."
            ),
        }

        if not health_related:
            normalized["show_structured_output"] = False
            normalized["urgency_level"] = "low"
            normalized["urgency_reason"] = "No health symptoms were provided in this message."
            normalized["seek_care_within"] = "Not applicable unless you develop symptoms."
            normalized["possible_conditions"] = []
            normalized["possible_remedies"] = []
            normalized["follow_up_questions"] = []
            normalized["red_flags"] = []
            normalized["specialist_types"] = []
        elif not normalized["follow_up_questions"]:
            normalized["follow_up_questions"] = [
                "When did this start, and has it been getting better, worse, or staying the same?",
                "How severe is it right now on a scale of 0 to 10?",
                "Do you have any other symptoms like fever, shortness of breath, vomiting, or dizziness?",
                "What makes it better or worse, and have you tried any treatment so far?",
            ]

        return self._enforce_second_person_voice(normalized)

    def _enforce_second_person_voice(self, assessment: dict) -> dict:
        def rewrite(text: str) -> str:
            rewritten = text
            replacements = {
                "The user": "You",
                "the user": "you",
                "This user": "You",
                "this user": "you",
                "The patient": "You",
                "the patient": "you",
                "User reports": "You report",
                "user reports": "you report",
                "User is": "You are",
                "user is": "you are",
                "User has": "You have",
                "user has": "you have",
                "Patient reports": "You report",
                "patient reports": "you report",
                "Patient is": "You are",
                "patient is": "you are",
                "Patient has": "You have",
                "patient has": "you have",
            }
            for source, target in replacements.items():
                rewritten = rewritten.replace(source, target)
            return rewritten

        text_fields = [
            "assistant_message",
            "summary",
            "urgency_reason",
            "seek_care_within",
            "safety_disclaimer",
        ]
        list_fields = [
            "follow_up_questions",
            "possible_conditions",
            "possible_remedies",
            "red_flags",
            "specialist_types",
        ]

        for field in text_fields:
            value = assessment.get(field)
            if isinstance(value, str):
                assessment[field] = rewrite(value)

        for field in list_fields:
            value = assessment.get(field)
            if isinstance(value, list):
                assessment[field] = [rewrite(item) if isinstance(item, str) else item for item in value]

        return assessment

    def _normalize_urgency(self, value: object) -> str:
        if isinstance(value, str):
            candidate = value.strip().lower()
            if candidate in {"low", "medium", "high", "emergency"}:
                return candidate

        if isinstance(value, (int, float)):
            score = float(value)
            if score >= 8:
                return "emergency"
            if score >= 6:
                return "high"
            if score >= 3:
                return "medium"
            return "low"

        return "medium"

    def _fallback_for_any_message(self, payload: ChatAssessmentRequest) -> AssessmentData:
        if self._looks_like_health_message(payload):
            return self._fallback_assessment(payload)
        return self._fallback_general_message(payload)

    def _looks_like_health_message(
        self,
        payload: ChatAssessmentRequest,
        conversation_history: list[dict] | None = None,
    ) -> bool:
        if payload.symptoms:
            return True

        text = payload.message.lower()
        history_text = " ".join(
            str(turn.get("user_message", "")).lower()
            for turn in (conversation_history or [])
        )
        combined = f"{text} {history_text}".strip()
        health_terms = {
            "pain",
            "fever",
            "cough",
            "vomit",
            "nausea",
            "headache",
            "dizzy",
            "breath",
            "chest",
            "doctor",
            "symptom",
            "sick",
            "ill",
        }
        return any(term in combined for term in health_terms)

    def _fallback_general_message(self, payload: ChatAssessmentRequest) -> AssessmentData:
        message_excerpt = payload.message.strip()[:180]
        return AssessmentData(
            assistant_message=(
                f"I hear you — you said: '{message_excerpt}'. I can chat about that. "
                "Whenever you want, share how your body feels today and I can help with a health check-in."
            ),
            show_structured_output=False,
            summary=f"General conversational message received: '{message_excerpt}'.",
            follow_up_questions=[],
            possible_conditions=[],
            possible_remedies=[],
            urgency_level=UrgencyLevel.low,
            urgency_reason="No clear health-risk indicators were detected from this non-health message.",
            seek_care_within="Not applicable unless you have symptoms.",
            red_flags=[],
            specialist_types=[],
            safety_disclaimer="For urgent or severe symptoms, seek immediate in-person medical care.",
        )

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
            assistant_message=(
                "Thanks for sharing that. From what you described, here’s what I’m thinking right now. "
                "I’ll keep it simple, and if your symptoms get worse I’ll tell you when to escalate care."
            ),
            show_structured_output=True,
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
