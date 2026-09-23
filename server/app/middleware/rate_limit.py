from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

_LIMITED_SUFFIXES = ("/uploads", "/regenerate")


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        if not settings.rate_limit_enabled or settings.eventai_env == "test":
            return await call_next(request)
        if request.method != "POST":
            return await call_next(request)
        path = request.url.path
        if not any(path.endswith(suffix) for suffix in _LIMITED_SUFFIXES):
            return await call_next(request)
        ip = request.client.host if request.client else "unknown"
        key = f"{ip}:{path}"
        now = time.monotonic()
        window = 60.0
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_per_minute:
            return JSONResponse(
                {
                    "detail": "Too many requests. Slow down uploads/regenerations.",
                    "code": "rate_limited",
                },
                status_code=429,
            )
        bucket.append(now)
        return await call_next(request)
