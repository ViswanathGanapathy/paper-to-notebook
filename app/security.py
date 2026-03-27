"""Security middleware and configuration for Paper-to-Notebook."""
import os

from fastapi import Request as FastAPIRequest
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ── Rate Limiter ─────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request: FastAPIRequest, exc: RateLimitExceeded) -> JSONResponse:
    """Return a clear 429 error when rate limit is exceeded."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please wait before making another request.",
            "error": "rate_limit_exceeded",
        },
    )

# Security headers applied to every response
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin, no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    ),
    "X-DNS-Prefetch-Control": "off",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


def is_production() -> bool:
    """Check if running in production mode."""
    return os.environ.get("ENV", "development").lower() == "production"
