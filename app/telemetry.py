"""OpenTelemetry tracing setup.

This module is intentionally lightweight and safe-by-default:
- Tracing is enabled only when OTEL_ENABLED=true OR OTEL_EXPORTER_OTLP_ENDPOINT is set.
- Export is configured to use OTLP over gRPC to Tempo by default.

Env vars (common):
- OTEL_ENABLED=true|false
- OTEL_SERVICE_NAME=remediation-engine
- OTEL_EXPORTER_OTLP_ENDPOINT=tempo:4317
- OTEL_TRACES_SAMPLER=parentbased_traceidratio
- OTEL_TRACES_SAMPLER_ARG=0.1
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import FastAPI

logger = logging.getLogger(__name__)

_otel_record_factory_installed = False


def _env_truthy(name: str, default: str = "false") -> bool:
    value = os.getenv(name, default).strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


class _EnsureOtelLogFields(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # If LoggingInstrumentor isn't enabled, these fields won't exist.
        # Ensure formatting never crashes.
        if not hasattr(record, "otelTraceID"):
            record.otelTraceID = "-"
        if not hasattr(record, "otelSpanID"):
            record.otelSpanID = "-"
        if not hasattr(record, "otelServiceName"):
            record.otelServiceName = os.getenv("OTEL_SERVICE_NAME", "-")
        return True


def install_otel_log_filter() -> None:
    """Ensure log records always have otel correlation fields.

    This prevents formatting errors if the main log format includes
    %(otelTraceID)s / %(otelSpanID)s while OpenTelemetry is disabled.
    """

    global _otel_record_factory_installed

    # Install a LogRecordFactory so *all* loggers/handlers (including uvicorn's)
    # can safely format %(otelTraceID)s / %(otelSpanID)s.
    if not _otel_record_factory_installed:
        original_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = original_factory(*args, **kwargs)
            if not hasattr(record, "otelTraceID"):
                record.otelTraceID = "-"
            if not hasattr(record, "otelSpanID"):
                record.otelSpanID = "-"
            if not hasattr(record, "otelServiceName"):
                record.otelServiceName = os.getenv("OTEL_SERVICE_NAME", "-")
            return record

        logging.setLogRecordFactory(record_factory)
        _otel_record_factory_installed = True

    # Also add a filter (cheap extra safety for custom handlers).
    logging.getLogger().addFilter(_EnsureOtelLogFields())


def setup_telemetry(app: FastAPI) -> bool:
    """Configure OpenTelemetry tracing and instrument common libraries.

    Returns True if telemetry was enabled and configured.
    """

    # Always make logging safe first.
    install_otel_log_filter()

    enabled = _env_truthy("OTEL_ENABLED") or bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
    if not enabled:
        return False

    # Prevent duplicate instrumentation if lifespan is invoked multiple times.
    if getattr(app.state, "otel_configured", False):
        return True
    app.state.otel_configured = True

    # Import opentelemetry lazily so local dev/test environments without deps
    # can still import the app if OTEL isn't enabled.
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except Exception as exc:
        logger.warning("OpenTelemetry enabled but dependencies missing: %s", exc)
        return False

    service_name = os.getenv("OTEL_SERVICE_NAME", "remediation-engine")
    sampler_arg = os.getenv("OTEL_TRACES_SAMPLER_ARG", "0.1")

    sampler = None
    sampler_name = os.getenv("OTEL_TRACES_SAMPLER", "parentbased_traceidratio").strip().lower()
    if sampler_name in {"parentbased_traceidratio", "traceidratio", "ratio"}:
        try:
            ratio = float(sampler_arg)
        except ValueError:
            ratio = 0.1
        ratio = max(0.0, min(1.0, ratio))
        base = TraceIdRatioBased(ratio)
        sampler = ParentBased(base) if sampler_name.startswith("parentbased") else base

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource, sampler=sampler)

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "tempo:4317")
    # For the gRPC exporter, the endpoint is typically host:port.
    endpoint = endpoint.replace("https://", "").replace("http://", "")

    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    # Instrument logging to inject trace/span IDs as LogRecord fields.
    try:
        LoggingInstrumentor().instrument()
    except Exception as exc:
        logger.debug("Logging instrumentation unavailable: %s", exc)

    # Instrument inbound/outbound.
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()

    # Instrument DB (best effort).
    try:
        from app.database import engine, async_engine

        SQLAlchemyInstrumentor().instrument(
            engine=engine,
            enable_commenter=True,
            commenter_options={"db_driver": True, "dbapi_level": True},
        )
        # Async engine wraps a sync engine internally.
        SQLAlchemyInstrumentor().instrument(
            engine=async_engine.sync_engine,
            enable_commenter=True,
            commenter_options={"db_driver": True, "dbapi_level": True},
        )
    except Exception as exc:
        logger.debug("SQLAlchemy instrumentation skipped: %s", exc)

    logger.info("OpenTelemetry tracing enabled (service=%s, otlp_grpc=%s)", service_name, endpoint)
    return True
