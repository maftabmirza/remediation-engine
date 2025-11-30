"""
Prometheus Metrics Definitions

This module defines all application metrics.
Import metrics from here to use them in other modules.
Separated from routers to avoid circular imports.
"""
from prometheus_client import Counter, Histogram, Gauge

# =============================================================================
# Alert Metrics
# =============================================================================

ALERTS_RECEIVED = Counter(
    'aiops_alerts_received_total',
    'Total number of alerts received from Alertmanager',
    ['severity', 'status']
)

ALERTS_PROCESSED = Counter(
    'aiops_alerts_processed_total',
    'Total number of alerts processed by action type',
    ['action']  # auto_analyze, ignore, manual, error
)

ALERTS_ANALYZED = Counter(
    'aiops_alerts_analyzed_total',
    'Total number of alerts analyzed by AI',
    ['provider', 'status']  # status: success, error
)

# =============================================================================
# LLM Metrics
# =============================================================================

LLM_REQUESTS = Counter(
    'aiops_llm_requests_total',
    'Total number of LLM API requests',
    ['provider', 'model', 'status']  # status: success, error
)

LLM_DURATION = Histogram(
    'aiops_llm_duration_seconds',
    'Time spent on LLM API calls',
    ['provider', 'model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0]
)

LLM_TOKENS = Counter(
    'aiops_llm_tokens_total',
    'Total tokens used in LLM requests',
    ['provider', 'model', 'type']  # type: prompt, completion
)

# =============================================================================
# Authentication Metrics
# =============================================================================

AUTH_ATTEMPTS = Counter(
    'aiops_auth_attempts_total',
    'Total authentication attempts',
    ['status']  # success, failed, disabled
)

ACTIVE_SESSIONS = Gauge(
    'aiops_active_sessions',
    'Number of active user sessions (approximate)'
)

# =============================================================================
# Terminal Metrics
# =============================================================================

TERMINAL_SESSIONS = Gauge(
    'aiops_terminal_sessions_active',
    'Number of active terminal sessions'
)

TERMINAL_CONNECTIONS = Counter(
    'aiops_terminal_connections_total',
    'Total terminal connection attempts',
    ['status']  # success, auth_failed, ssh_failed, error
)

# =============================================================================
# Webhook Metrics
# =============================================================================

WEBHOOK_REQUESTS = Counter(
    'aiops_webhook_requests_total',
    'Total webhook requests received'
)

WEBHOOK_DURATION = Histogram(
    'aiops_webhook_duration_seconds',
    'Time to process webhook requests',
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

# =============================================================================
# HTTP Metrics (general)
# =============================================================================

HTTP_REQUESTS = Counter(
    'aiops_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

HTTP_DURATION = Histogram(
    'aiops_http_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)
