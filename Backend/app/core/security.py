from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, UTC
from threading import Lock

from fastapi import Depends, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import Settings, get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none';"

        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        if request.url.scheme == "https" or forwarded_proto.lower() == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        return response


_rate_limit_store: dict[str, deque[datetime]] = defaultdict(deque)
_rate_limit_lock = Lock()


def _enforce_rate_limit(request: Request, max_requests: int, window_seconds: int, bucket: str) -> None:
    if max_requests <= 0:
        return

    xff = request.headers.get("x-forwarded-for", "")
    client_ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")
    key = f"{bucket}:{client_ip}"

    now = datetime.now(UTC)
    window_start = now - timedelta(seconds=window_seconds)

    with _rate_limit_lock:
        entries = _rate_limit_store[key]
        while entries and entries[0] < window_start:
            entries.popleft()

        if len(entries) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait and try again.",
            )

        entries.append(now)


def rate_limit_chat_assess(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    _enforce_rate_limit(
        request=request,
        max_requests=settings.chat_assess_rate_limit_per_min,
        window_seconds=60,
        bucket="chat_assess",
    )


def rate_limit_chat_analyze(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    _enforce_rate_limit(
        request=request,
        max_requests=settings.chat_analyze_rate_limit_per_min,
        window_seconds=60,
        bucket="chat_analyze",
    )
