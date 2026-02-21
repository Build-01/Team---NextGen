import json
from urllib import error, request


class GeminiClient:
    def __init__(self, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self._model = model

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def generate_json(
        self,
        system_prompt: str,
        user_payload: dict,
        temperature: float = 0.2,
    ) -> dict:
        if not self._api_key:
            raise RuntimeError("Gemini API key is not configured")

        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"
            f"?key={self._api_key}"
        )

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": json.dumps(user_payload)}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }

        request_data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=request_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=25) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Gemini HTTP error: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Gemini network error: {exc.reason}") from exc

        parsed = json.loads(body)

        candidates = parsed.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            raise RuntimeError("Gemini returned empty content")

        text_output = "".join(part.get("text", "") for part in parts)
        return json.loads(text_output)
