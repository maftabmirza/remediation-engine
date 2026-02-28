"""
Security Headers Middleware.

Adds a standard set of security-related HTTP response headers to every
response emitted by the application, regardless of the route handler.
Individual route handlers may still add or override specific headers
(e.g. Content-Security-Policy for iframe embedding).
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject security headers on every HTTP response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent MIME-type sniffing
        response.headers.setdefault("X-Content-Type-Options", "nosniff")

        # Deny framing by default (individual routes override where needed)
        response.headers.setdefault("X-Frame-Options", "DENY")

        # Disable legacy XSS filter (modern browsers, defence-in-depth)
        response.headers.setdefault("X-XSS-Protection", "0")

        # Use HTTPS for all future requests (only effective when served over TLS)
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )

        # Restrict referrer information on cross-origin navigations
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        # Limit browser feature access
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )

        return response
