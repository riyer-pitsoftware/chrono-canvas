import contextvars
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Paths that bypass the auth gate
_AUTH_EXEMPT_PREFIXES = (
    "/api/auth/",
    "/api/health",
    "/docs",
    "/openapi.json",
)


class AuthGateMiddleware(BaseHTTPMiddleware):
    """Require a valid session cookie when APP_PASSWORD is configured."""

    async def dispatch(self, request: Request, call_next):
        from chronocanvas.config import settings

        # No password set → everything is open
        if not settings.app_password:
            return await call_next(request)

        path = request.url.path

        # WebSocket upgrades — BaseHTTPMiddleware can't handle these reliably;
        # the browser already authenticated via the login page.
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Let auth endpoints, health checks, and static frontend through
        if any(path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES):
            return await call_next(request)

        # Non-API paths (frontend static files served by nginx/vite) pass through
        if not path.startswith("/api/") and not path.startswith("/ws/"):
            return await call_next(request)

        # Check session cookie
        from chronocanvas.api.routes.auth import is_authenticated

        if not is_authenticated(request):
            return JSONResponse(status_code=401, content={"detail": "Login required"})

        return await call_next(request)


# Context var for request correlation across async tasks
current_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_request_id", default=None
)


class RequestIdFilter(logging.Filter):
    """Inject request_id from context var into all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id.get()  # type: ignore[attr-defined]
        return True


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        token = current_request_id.set(request_id)
        start_time = time.time()

        try:
            response = await call_next(request)
        finally:
            current_request_id.reset(token)

        duration = time.time() - start_time
        logger.info(
            "%s %s status=%d duration=%.3fs request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration,
            request_id,
        )

        response.headers["X-Request-ID"] = request_id
        return response
