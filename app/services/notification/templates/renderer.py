"""
Notification message template renderer.

Templates are stored as Python dicts (no filesystem dependency) and rendered
using simple string substitution so they can be easily tested and extended.

Each event type defines title/body templates for each channel type.
"""

from __future__ import annotations

import logging
from string import Template
from typing import Any

from app.schemas_notification import NotificationMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------
# Each entry: event_type → dict with "title" and "body" Template strings.
# Use $variable or ${variable} placeholders.
# Available variables come from the event_data dict passed to notify().
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------
    # Alert lifecycle
    # ------------------------------------------------------------------
    "alert.firing": {
        "title": "Alert Firing: ${alert_name}",
        "body": (
            "An alert is firing.\n\n"
            "Alert: ${alert_name}\n"
            "Severity: ${severity}\n"
            "Source: ${source}\n"
            "Description: ${description}"
        ),
    },
    "alert.resolved": {
        "title": "Alert Resolved: ${alert_name}",
        "body": (
            "The alert has been resolved.\n\n"
            "Alert: ${alert_name}\n"
            "Duration: ${duration}\n"
            "Source: ${source}"
        ),
    },
    "alert.analyzed": {
        "title": "AI Analysis Complete: ${alert_name}",
        "body": (
            "AI analysis has been completed for an alert.\n\n"
            "Alert: ${alert_name}\n"
            "Severity: ${severity}\n"
            "Analysis: ${analysis_summary}"
        ),
    },
    # ------------------------------------------------------------------
    # Execution lifecycle
    # ------------------------------------------------------------------
    "execution.triggered": {
        "title": "Remediation Triggered: ${runbook_name}",
        "body": (
            "A remediation runbook has been triggered.\n\n"
            "Runbook: ${runbook_name}\n"
            "Alert: ${alert_name}\n"
            "Execution ID: ${execution_id}"
        ),
    },
    "execution.started": {
        "title": "Remediation Started: ${runbook_name}",
        "body": (
            "Runbook execution has started.\n\n"
            "Runbook: ${runbook_name}\n"
            "Target: ${target_host}\n"
            "Execution ID: ${execution_id}"
        ),
    },
    "execution.completed": {
        "title": "Remediation Completed: ${runbook_name}",
        "body": (
            "Runbook execution completed successfully.\n\n"
            "Runbook: ${runbook_name}\n"
            "Target: ${target_host}\n"
            "Duration: ${duration}\n"
            "Execution ID: ${execution_id}"
        ),
    },
    "execution.failed": {
        "title": "Remediation Failed: ${runbook_name}",
        "body": (
            "Runbook execution has failed.\n\n"
            "Runbook: ${runbook_name}\n"
            "Target: ${target_host}\n"
            "Error: ${error_message}\n"
            "Execution ID: ${execution_id}"
        ),
    },
    "execution.step_failed": {
        "title": "Step Failed: ${step_name} in ${runbook_name}",
        "body": (
            "A runbook step has failed.\n\n"
            "Runbook: ${runbook_name}\n"
            "Step: ${step_name}\n"
            "Error: ${error_message}\n"
            "Execution ID: ${execution_id}"
        ),
    },
    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------
    "approval.requested": {
        "title": "Approval Required: ${runbook_name}",
        "body": (
            "A runbook execution requires your approval.\n\n"
            "Runbook: ${runbook_name}\n"
            "Alert: ${alert_name}\n"
            "Requested by: ${requested_by}\n"
            "Expires at: ${expires_at}\n\n"
            "Please review and approve or reject this request."
        ),
    },
    "approval.expired": {
        "title": "Approval Timeout: ${runbook_name}",
        "body": (
            "A pending approval has expired without a response.\n\n"
            "Runbook: ${runbook_name}\n"
            "Execution ID: ${execution_id}"
        ),
    },
    # ------------------------------------------------------------------
    # Safety / circuit breaker
    # ------------------------------------------------------------------
    "circuit.opened": {
        "title": "Circuit Breaker Opened: ${runbook_name}",
        "body": (
            "The circuit breaker for a runbook has opened due to repeated failures.\n\n"
            "Runbook: ${runbook_name}\n"
            "Failure count: ${failure_count}\n"
            "Reset at: ${reset_at}"
        ),
    },
    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------
    "schedule.failed": {
        "title": "Scheduled Job Failed: ${job_name}",
        "body": (
            "A scheduled job failed to execute.\n\n"
            "Job: ${job_name}\n"
            "Error: ${error_message}\n"
            "Next run: ${next_run}"
        ),
    },
    # ------------------------------------------------------------------
    # Generic fallback
    # ------------------------------------------------------------------
    "generic": {
        "title": "${title}",
        "body": "${body}",
    },
}

# ---------------------------------------------------------------------------
# Default values used when event_data is missing a key
# ---------------------------------------------------------------------------
_DEFAULTS: dict[str, str] = {
    "alert_name": "Unknown Alert",
    "runbook_name": "Unknown Runbook",
    "severity": "unknown",
    "source": "aiops",
    "description": "",
    "analysis_summary": "",
    "execution_id": "",
    "target_host": "",
    "duration": "",
    "error_message": "",
    "step_name": "",
    "requested_by": "",
    "expires_at": "",
    "failure_count": "0",
    "reset_at": "",
    "job_name": "",
    "next_run": "",
    "title": "Notification",
    "body": "",
}


def render_template(
    event_type: str,
    event_data: dict[str, Any],
    template_key: str | None = None,
) -> NotificationMessage:
    """
    Render a notification message for the given event.

    Args:
        event_type: The event that occurred (e.g. "alert.firing").
        event_data: Arbitrary dict of values to substitute into the template.
        template_key: Optional override to select a specific template entry.
                      Falls back to ``event_type``, then ``"generic"``.

    Returns:
        A fully-rendered :class:`~app.schemas_notification.NotificationMessage`.
    """
    key = template_key or event_type
    tmpl = TEMPLATES.get(key) or TEMPLATES.get("generic") or {
        "title": "Notification",
        "body": "",
    }

    # Merge defaults with provided data (provided data takes priority)
    context = {**_DEFAULTS, **{str(k): str(v) for k, v in event_data.items() if v is not None}}

    def _safe_substitute(pattern: str) -> str:
        try:
            return Template(pattern).safe_substitute(context)
        except Exception:  # noqa: BLE001
            return pattern

    title = _safe_substitute(tmpl.get("title", "Notification"))
    body = _safe_substitute(tmpl.get("body", ""))

    return NotificationMessage(
        event_type=event_type,
        event_id=event_data.get("event_id"),  # type: ignore[arg-type]
        title=title,
        body=body,
        severity=event_data.get("severity"),  # type: ignore[arg-type]
        metadata=event_data,
        template_key=key,
    )
