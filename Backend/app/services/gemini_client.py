import json
from urllib import error, request


class LLMClient:
    def __init__(
        self,
        provider: str,
        api_key: str | None,
        model: str,
        app_name: str = "HealthBud",
        site_url: str = "http://localhost",
    ) -> None:
        self._provider = provider.strip().lower()
        self._api_key = api_key.strip() if isinstance(api_key, str) else api_key
        self._model = model.strip() if isinstance(model, str) else model
        self._app_name = app_name.strip() if isinstance(app_name, str) else app_name
        self._site_url = site_url.strip() if isinstance(site_url, str) else site_url

    @property
    def enabled(self) -> bool:
        if not self._api_key:
            return False
        normalized = self._api_key.strip().lower()
        return normalized != "" and not normalized.startswith("your_")

    @property
    def provider(self) -> str:
        return self._provider

    def generate_json(
        self,
        system_prompt: str,
        user_payload: dict,
        temperature: float = 0.2,
    ) -> dict:
        if not self.enabled:
            raise RuntimeError(f"{self._provider} API key is not configured")

        if self._provider == "openrouter":
            return self._generate_openrouter_json(system_prompt, user_payload, temperature)
        if self._provider == "gemini":
            return self._generate_gemini_json(system_prompt, user_payload, temperature)
        raise RuntimeError(f"Unsupported provider: {self._provider}")

    def _generate_openrouter_json(
        self,
        system_prompt: str,
        user_payload: dict,
        temperature: float,
    ) -> dict:
        endpoint = "https://openrouter.ai/api/v1/chat/completions"

        payload = {
            "model": self._model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
            "response_format": {"type": "json_object"},
        }

        request_data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=request_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "HTTP-Referer": self._site_url,
                "X-Title": self._app_name,
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=35) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenRouter HTTP error: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"OpenRouter network error: {exc.reason}") from exc

        parsed = json.loads(body)
        choices = parsed.get("choices", [])
        if not choices:
            raise RuntimeError("OpenRouter returned no choices")

        message = choices[0].get("message", {})
        content = self._extract_openrouter_text(message)
        if not content:
            fallback_text = choices[0].get("text", "")
            content = fallback_text if isinstance(fallback_text, str) else ""
        return self._safe_parse_json(content)

    def _extract_openrouter_text(self, message: dict) -> str:
        if not isinstance(message, dict):
            return ""

        content = message.get("content", "")
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text_value = item.get("text") or item.get("content")
                    if isinstance(text_value, str):
                        parts.append(text_value)
            if parts:
                return "".join(parts)

        tool_calls = message.get("tool_calls", [])
        if isinstance(tool_calls, list):
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                function_payload = call.get("function", {})
                if isinstance(function_payload, dict):
                    arguments = function_payload.get("arguments")
                    if isinstance(arguments, str) and arguments.strip():
                        return arguments

        return ""

    def _generate_gemini_json(
        self,
        system_prompt: str,
        user_payload: dict,
        temperature: float,
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
        return self._safe_parse_json(text_output)

    def _safe_parse_json(self, text: str) -> dict:
        cleaned = str(text or "").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        try:
            parsed = json.loads(cleaned)
            if not isinstance(parsed, dict):
                raise RuntimeError("Model did not return a JSON object")
            return parsed
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = cleaned[start : end + 1]
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            if cleaned:
                return {
                    "assistant_message": cleaned,
                    "summary": cleaned,
                }
            raise RuntimeError("Model response was not valid JSON")


GeminiClient = LLMClient
