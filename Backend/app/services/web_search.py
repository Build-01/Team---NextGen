from urllib.parse import urlparse
import importlib

from app.core.config import get_settings
from app.models.chat import EvidenceSource


class WebSearchService:
    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = settings.enable_web_search
        self._max_results = settings.web_search_max_results
        self._trusted_domains = [domain.lower() for domain in settings.trusted_medical_domains]
        self._ddgs_class = self._load_ddgs_class()

    def _load_ddgs_class(self):
        try:
            module = importlib.import_module("duckduckgo_search")
            return getattr(module, "DDGS", None)
        except Exception:
            return None

    def search_medical_evidence(self, query: str) -> list[EvidenceSource]:
        if not self._enabled or self._ddgs_class is None:
            return []

        try:
            results = self._ddgs_class().text(
                query,
                max_results=self._max_results,
                safesearch="moderate",
            )
        except Exception:
            return []

        evidence: list[EvidenceSource] = []
        for item in results or []:
            url = item.get("href") or ""
            if not url or not self._is_trusted(url):
                continue

            title = (item.get("title") or "").strip()
            snippet = (item.get("body") or "").strip()
            if not title:
                continue

            evidence.append(
                EvidenceSource(
                    title=title,
                    url=url,
                    snippet=snippet,
                )
            )

            if len(evidence) >= self._max_results:
                break

        return evidence

    def _is_trusted(self, url: str) -> bool:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return any(host == domain or host.endswith(f".{domain}") for domain in self._trusted_domains)
