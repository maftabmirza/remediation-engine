"""
Request ID middleware — correlation ID propagation.

Every inbound HTTP request is assigned a UUID (or reuses the incoming
``X-Request-ID`` header value).  The ID is:

1. Stored in a ``contextvars.ContextVar`` so that FastAPI background tasks
   (which copy the calling context on creation) automatically carry it forward.
2. Injected into every ``logging.LogRecord`` via a chained ``LogRecordFactory``
   so it is available as ``%(request_id)s`` regardless of logger hierarchy.
   (Note: a plain ``logging.Filter`` on the root *logger* does not fire for
   records propagated from child loggers—only the factory approach is reliable.)
3. Returned as an ``X-Request-ID`` response header so clients and load
   balancers can correlate their own records.

This works whether OpenTelemetry is enabled or not, complementing the
``%(otelTraceID)s`` / ``%(otelSpanID)s`` fields that OTEL injects when enabled.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# ── ContextVar ──────────────────────────────────────────────────────────────
# Holds the request-ID for the current async task / request context.
# Default is "-" so log lines outside a request context render cleanly.
_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_factory_installed = False


def get_request_id() -> str:
    """Return the current request ID (or '-' if called outside a request)."""
    return _request_id_var.get()


# ── LogRecordFactory ─────────────────────────────────────────────────────────

def install_request_id_log_factory() -> None:
    """Chain a LogRecordFactory that injects ``request_id`` into every record.

    Using a factory (rather than a Filter on the root logger) is the reliable
    approach: filters added to a *logger* are not invoked for records that
    merely propagate *through* that logger from a child—only handler filters
    and the factory run unconditionally.

    Safe to call multiple times; idempotent.
    """
    global _factory_installed
    if _factory_installed:
        return

    original_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = original_factory(*args, **kwargs)
        record.request_id = _request_id_var.get()
        return record

    logging.setLogRecordFactory(record_factory)
    _factory_installed = True


# ── Legacy filter (kept for any handlers that configure their own filters) ──

class RequestIDLogFilter(logging.Filter):
    """Injects the current request ID into a LogRecord.

    Prefer ``install_request_id_log_factory()`` for broad coverage.
    This filter is useful when added to a specific handler rather than a logger.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        return True


# ── Middleware ───────────────────────────────────────────────────────────────

class RequestIDMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that sets a per-request correlation ID.

    - Reads ``X-Request-ID`` from the incoming request headers if present.
    - Otherwise generates a new UUID4.
    - Sets the ``_request_id_var`` ContextVar for the duration of the request.
    - Appends ``X-Request-ID`` to the response headers.
    """

    HEADER = "X-Request-ID"

    def __init__(self, app: ASGIApp, header_name: str = HEADER) -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(self.header_name)
        request_id = incoming if incoming else str(uuid.uuid4())

        token = _request_id_var.set(request_id)
        try:
            response: Response = await call_next(request)
        finally:
            _request_id_var.reset(token)

        response.headers[self.header_name] = request_id
        return response

