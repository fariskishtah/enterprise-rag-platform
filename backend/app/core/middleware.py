"""Lightweight production middleware for access, limits, and request telemetry."""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import Settings
from app.core.errors import error_payload
from app.core.security import decode_access_token

logger = logging.getLogger("enterprise_rag.requests")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def client_fingerprint(request: Request) -> str:
    """Return a bounded, non-reversible login/rate-limit key."""

    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    host = forwarded or (request.client.host if request.client else "unknown")
    agent = request.headers.get("user-agent", "")[:300]
    return hashlib.sha256(f"{host}|{agent}".encode()).hexdigest()


@dataclass
class _LoginRecord:
    failures: int = 0
    locked_until: float = 0.0
    last_seen: float = 0.0


class LoginAttemptLimiter:
    """Bounded in-memory lockout suitable for a single public-demo process."""

    def __init__(self, max_attempts: int, lockout_seconds: int, max_entries: int = 10000) -> None:
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self.max_entries = max_entries
        self._records: dict[str, _LoginRecord] = {}
        self._lock = threading.Lock()

    def is_locked(self, key: str, *, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return False
            record.last_seen = current
            if record.locked_until > current:
                return True
            if record.locked_until:
                self._records.pop(key, None)
            return False

    def failure(self, key: str, *, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        with self._lock:
            if len(self._records) >= self.max_entries and key not in self._records:
                oldest = min(self._records, key=lambda value: self._records[value].last_seen)
                self._records.pop(oldest, None)
            record = self._records.setdefault(key, _LoginRecord())
            record.failures += 1
            record.last_seen = current
            if record.failures >= self.max_attempts:
                record.locked_until = current + self.lockout_seconds
                return True
            return False

    def success(self, key: str) -> None:
        with self._lock:
            self._records.pop(key, None)


class FixedWindowRateLimiter:
    """A memory-bounded, dependency-free per-client request limiter."""

    def __init__(self, max_keys: int = 20000) -> None:
        self.max_keys = max_keys
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, *, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        cutoff = current - 60
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(current)
            if len(self._events) > self.max_keys:
                overflow = len(self._events) - self.max_keys
                candidates = sorted(
                    (value for value in self._events if value != key),
                    key=lambda value: (
                        self._events[value][-1] if self._events[value] else float("-inf")
                    ),
                )
                for value in candidates[:overflow]:
                    self._events.pop(value, None)
            return True


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logging_payload = {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": request.url.path,
                "status": status_code,
                "duration_ms": duration_ms,
            }
            logger.info(
                "HTTP request completed",
                extra={"enterprise_event": logging_payload},
            )
            if "response" in locals():
                response.headers["X-Request-ID"] = request_id


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.limit = settings.request_body_limit_mb * 1024 * 1024

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        length = request.headers.get("content-length")
        if length:
            try:
                too_large = int(length) > self.limit
            except ValueError:
                too_large = True
            if too_large:
                return JSONResponse(
                    status_code=413,
                    content=error_payload(
                        "request_body_too_large",
                        "The request body exceeds the public-demo size limit.",
                    ),
                )
        return await call_next(request)


class UploadConcurrencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.maximum = settings.max_concurrent_uploads
        self._active = 0
        self._lock = threading.Lock()

    @staticmethod
    def _is_upload(request: Request) -> bool:
        path = request.url.path
        return request.method == "POST" and (
            path.endswith("/documents")
            or (path.endswith("/media") and not path.endswith("/from-url"))
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._is_upload(request):
            return await call_next(request)
        with self._lock:
            if self._active >= self.maximum:
                return JSONResponse(
                    status_code=429,
                    content=error_payload(
                        "upload_concurrency_exceeded",
                        "The upload service is busy. Wait for an active upload "
                        "to finish and retry.",
                    ),
                )
            self._active += 1
        try:
            return await call_next(request)
        finally:
            with self._lock:
                self._active = max(0, self._active - 1)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.settings = settings
        self.limiter = FixedWindowRateLimiter()

    def _category(self, request: Request) -> tuple[str, int] | None:
        if request.method != "POST":
            return None
        path = request.url.path
        if path.endswith("/auth/demo/login") or path.endswith("/auth/login"):
            return "login", self.settings.login_max_attempts
        if path.endswith("/from-url"):
            return "url_import", self.settings.url_import_rate_limit_per_minute
        if (
            path.endswith("/documents")
            or path.endswith("/media")
            or path.endswith("/evaluation/datasets")
            or path.endswith("/evaluation/cases")
            or path.endswith("/convert-to-eval")
            or path.endswith("/feedback")
        ):
            return "upload", self.settings.upload_rate_limit_per_minute
        if path.endswith("/process") or path.endswith("/retry"):
            return "transcription", self.settings.transcription_rate_limit_per_minute
        if (
            "/ask" in path
            or "/intelligence/" in path
            or path.endswith("/evaluation/runs")
            or path.endswith("/rag/warmup")
            or path.endswith("/demo/seed")
        ):
            return "generation", self.settings.generation_rate_limit_per_minute
        return None

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        category = self._category(request)
        if category is not None:
            name, limit = category
            key = f"{name}:{client_fingerprint(request)}"
            if not self.limiter.allow(key, limit):
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": "60"},
                    content=error_payload(
                        "rate_limit_exceeded",
                        "Too many requests were received. Wait briefly and retry.",
                    ),
                )
        return await call_next(request)


class AccessControlMiddleware(BaseHTTPMiddleware):
    """Enforce open/demo-password/account access without leaking configuration secrets."""

    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.settings = settings
        prefix = settings.api_prefix.rstrip("/")
        self.public_api_paths = {
            f"{prefix}/health",
            f"{prefix}/readiness",
            f"{prefix}/ready",
            f"{prefix}/auth/config",
            f"{prefix}/auth/session",
            f"{prefix}/auth/demo/login",
            f"{prefix}/auth/login",
            f"{prefix}/auth/logout",
            f"{prefix}/auth/register",
        }
        self.public_pages = {"/", "/login", "/privacy", "/terms", "/security"}

    def _claims(self, request: Request) -> dict[str, object] | None:
        cookie_token = request.cookies.get(self.settings.session_cookie_name)
        authorization = request.headers.get("authorization", "")
        bearer_token = (
            authorization[7:].strip()
            if authorization.lower().startswith("bearer ")
            else None
        )
        token = cookie_token or bearer_token
        if not token:
            return None
        claims = decode_access_token(token, self.settings.session_secret)
        if claims is None:
            return None
        expected = "demo" if self.settings.access_mode == "demo_password" else "account"
        return claims if claims.get("kind") == expected else None

    @staticmethod
    def _csrf_safe(request: Request, used_cookie: bool) -> bool:
        if not used_cookie or request.method in SAFE_METHODS:
            return True
        if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
            return False
        origin = request.headers.get("origin")
        if not origin:
            return True
        return origin.rstrip("/") == str(request.base_url).rstrip("/")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        mode = self.settings.access_mode
        claims = (
            {"sub": "local-development", "kind": "open"}
            if mode == "open"
            else self._claims(request)
        )
        request.state.principal = claims
        path = request.url.path.rstrip("/") or "/"
        is_api = path == self.settings.api_prefix or path.startswith(f"{self.settings.api_prefix}/")
        is_public = (
            path in self.public_api_paths
            if is_api
            else path in self.public_pages or path.startswith("/assets/")
        )
        if not is_public and claims is None:
            if is_api:
                return JSONResponse(
                    status_code=401,
                    content=error_payload(
                        "authentication_required",
                        "Sign in to access the EnterpriseRAG demo.",
                    ),
                )
            return RedirectResponse(url=f"/login?next={path}", status_code=307)
        used_cookie = bool(request.cookies.get(self.settings.session_cookie_name))
        if not self._csrf_safe(request, used_cookie):
            return JSONResponse(
                status_code=403,
                content=error_payload(
                    "cross_site_request_rejected",
                    "The request origin could not be verified.",
                ),
            )
        return await call_next(request)
