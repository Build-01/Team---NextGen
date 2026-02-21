import json
from collections import defaultdict
from datetime import UTC, datetime
from functools import lru_cache

from app.core.config import get_settings
from app.db.models import ChatRecord
from app.models.chat import (
    ConditionAnalysis,
    EvidenceSource,
    StoredChatAnalysisResponse,
    UrgencyLevel,
)
from app.services.gemini_client import GeminiClient
from app.services.web_search import WebSearchService

ANALYSIS_PROMPT = """
You are a conservative medical triage assistant.
You must ONLY use facts present in the provided evidence list.
If evidence is weak, state uncertainty.
Never claim a diagnosis.
Return valid JSON with keys:
urgency_level, urgency_reason, seek_care_within, conditions, recommended_remedies, red_flags, disclaimer.
Each entry in conditions must include:
condition, confidence (0-1), rationale, related_symptoms, recommended_remedies, doctor_specialties, evidence_ids.
Rules:
- Use only evidence_ids that exist in the provided list.
- If no evidence exists for a condition, do not include that condition.
- Keep remedies low-risk and general.
- urgency_level must be one of: low, medium, high, emergency.
""".strip()


class ChatAnalysisService:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )
        self._search_service = WebSearchService()

    def analyze_stored_chat(self, chat_record: ChatRecord) -> StoredChatAnalysisResponse:
        evidence = self._build_evidence(chat_record)

        if self._client.enabled and evidence:
            try:
                return self._ai_grounded_analysis(chat_record, evidence)
            except Exception:
                pass

        return self._fallback_analysis(chat_record, evidence)

    def _build_evidence(self, chat_record: ChatRecord) -> list[EvidenceSource]:
        symptom_names = [symptom.name for symptom in chat_record.symptoms]
        if not symptom_names:
            return []

        query = " ".join(symptom_names[:4])
        query = f"{query} possible causes triage severity"
        return self._search_service.search_medical_evidence(query)

    def _ai_grounded_analysis(
        self,
        chat_record: ChatRecord,
        evidence: list[EvidenceSource],
    ) -> StoredChatAnalysisResponse:
        evidence_payload = [
            {
                "id": index + 1,
                "title": item.title,
                "url": item.url,
                "snippet": item.snippet,
            }
            for index, item in enumerate(evidence)
        ]

        symptom_payload = [
            {
                "name": symptom.name,
                "severity": symptom.severity,
                "body_location": symptom.body_location,
                "character": symptom.character,
                "aggravating_factors": symptom.aggravating_factors,
                "radiation": symptom.radiation,
                "duration_pattern": symptom.duration_pattern,
                "timing_pattern": symptom.timing_pattern,
                "associated_symptoms": symptom.associated_symptoms,
                "progression": symptom.progression,
                "is_constant": symptom.is_constant,
            }
            for symptom in chat_record.symptoms
        ]

        user_payload = {
            "chat_number": chat_record.chat_number,
            "message": chat_record.message,
            "patient": {
                "age": chat_record.age,
                "biological_sex": chat_record.biological_sex,
                "chronic_conditions": chat_record.chronic_conditions,
                "current_medications": chat_record.current_medications,
                "allergies": chat_record.allergies,
            },
            "symptoms": symptom_payload,
            "evidence": evidence_payload,
        }

        parsed = self._client.generate_json(
            system_prompt=ANALYSIS_PROMPT,
            user_payload=user_payload,
            temperature=0.1,
        )

        conditions: list[ConditionAnalysis] = []
        for item in parsed.get("conditions", []):
            evidence_ids = [evidence_id for evidence_id in item.get("evidence_ids", []) if isinstance(evidence_id, int)]
            mapped_evidence = [
                evidence[evidence_id - 1]
                for evidence_id in evidence_ids
                if 1 <= evidence_id <= len(evidence)
            ]
            if not mapped_evidence:
                continue

            conditions.append(
                ConditionAnalysis(
                    condition=item.get("condition", "Unknown condition"),
                    confidence=self._parse_confidence(item.get("confidence", 0.2)),
                    rationale=item.get("rationale", "Evidence suggests this may be related."),
                    related_symptoms=item.get("related_symptoms", []),
                    recommended_remedies=item.get("recommended_remedies", []),
                    doctor_specialties=item.get("doctor_specialties", []),
                    evidence=mapped_evidence,
                )
            )

        urgency_text = str(parsed.get("urgency_level", "medium")).lower()
        urgency = UrgencyLevel(urgency_text) if urgency_text in {"low", "medium", "high", "emergency"} else UrgencyLevel.medium

        return StoredChatAnalysisResponse(
            chat_number=chat_record.chat_number,
            session_id=chat_record.chat_id,
            analyzed_at=datetime.now(UTC),
            urgency_level=urgency,
            urgency_reason=parsed.get("urgency_reason", "Urgency estimated from symptom pattern and severity."),
            seek_care_within=parsed.get("seek_care_within", "Within 24 hours if symptoms persist or worsen."),
            conditions=conditions,
            recommended_remedies=parsed.get("recommended_remedies", []),
            red_flags=parsed.get("red_flags", ["Worsening breathing", "Chest pain", "Fainting", "Confusion"]),
            disclaimer=parsed.get(
                "disclaimer",
                "AI-assisted triage is not a diagnosis. Seek in-person care for severe or worsening symptoms.",
            ),
        )

    def _parse_confidence(self, value: object) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.2
        return max(0.0, min(1.0, score))

    def _fallback_analysis(
        self,
        chat_record: ChatRecord,
        evidence: list[EvidenceSource],
    ) -> StoredChatAnalysisResponse:
        symptom_map = defaultdict(list)
        max_severity = 0
        for symptom in chat_record.symptoms:
            symptom_map[symptom.name.lower()].append(symptom)
            max_severity = max(max_severity, symptom.severity)

        emergency_keywords = {"chest pain", "shortness of breath", "difficulty breathing", "seizure", "stroke"}
        high_keywords = {"high fever", "persistent vomiting", "blood in stool", "severe headache"}

        symptom_names = set(symptom_map.keys())
        if symptom_names.intersection(emergency_keywords) or max_severity >= 9:
            urgency = UrgencyLevel.emergency
            urgency_reason = "Emergency-pattern symptoms or very high severity are present."
            seek_care_within = "Immediately. Seek emergency care now."
        elif symptom_names.intersection(high_keywords) or max_severity >= 7:
            urgency = UrgencyLevel.high
            urgency_reason = "High-risk symptom pattern or high severity suggests urgent in-person care."
            seek_care_within = "Within 4-12 hours."
        elif max_severity >= 4:
            urgency = UrgencyLevel.medium
            urgency_reason = "Symptoms appear moderate and should be reviewed soon."
            seek_care_within = "Within 24-48 hours if not improving."
        else:
            urgency = UrgencyLevel.low
            urgency_reason = "Symptoms currently appear mild."
            seek_care_within = "Routine care if persistent or worsening."

        top_evidence = evidence[:3]
        conditions = [
            ConditionAnalysis(
                condition="Possible symptom-related condition",
                confidence=0.3,
                rationale="Based on stored symptom profile; evidence is limited.",
                related_symptoms=[symptom.name for symptom in chat_record.symptoms[:5]],
                recommended_remedies=[
                    "Rest and hydration.",
                    "Monitor symptom progression and severity.",
                    "Use only clinician- or pharmacist-approved medication.",
                ],
                doctor_specialties=["General Practice", "Internal Medicine"],
                evidence=top_evidence,
            )
        ] if top_evidence else []

        return StoredChatAnalysisResponse(
            chat_number=chat_record.chat_number,
            session_id=chat_record.chat_id,
            analyzed_at=datetime.now(UTC),
            urgency_level=urgency,
            urgency_reason=urgency_reason,
            seek_care_within=seek_care_within,
            conditions=conditions,
            recommended_remedies=[
                "Rest, fluids, and avoid known triggers.",
                "Track symptoms over time for clinician review.",
                "Seek urgent care if red flags appear.",
            ],
            red_flags=[
                "Severe chest pain",
                "Difficulty breathing",
                "Fainting or confusion",
                "Uncontrolled bleeding",
            ],
            disclaimer="This output is decision support, not a diagnosis. It may be incomplete without clinical examination.",
        )


@lru_cache
def get_chat_analysis_service() -> ChatAnalysisService:
    return ChatAnalysisService()
