"""
Generic outbound Webhook notification provider.

Sends a JSON payload to any HTTP endpoint via httpx.
Supports configurable method, headers, and a simple template override.
"""

import json
import logging
from typing import Any

import httpx

from app.schemas_notification import NotificationMessage, ProviderResult
from app.services.notification.providers.base import BaseNotificationProvider

logger = logging.getLogger(__name__)

_VALID_METHODS = {"GET", "POST", "PUT", "PATCH"}


class WebhookProvider(BaseNotificationProvider):
    """Delivers notifications to any HTTP endpoint as a JSON POST/PUT."""

    provider_name = "webhook"

    async def send(
        self,
        channel_config: dict[str, Any],
        message: NotificationMessage,
    ) -> ProviderResult:
        """
        Send an HTTP request to the configured webhook URL.

        Args:
            channel_config: Must contain ``url``.  Optionally accepts
                ``method`` (default POST), ``headers``, and ``template``
                (a dict rendered as the body).
            message: Rendered notification message.

        Returns:
            ProviderResult indicating success or failure.
        """
        url: str | None = channel_config.get("url")
        if not url:
            return ProviderResult(success=False, error="webhook url is required")

        method: str = str(channel_config.get("method", "POST")).upper()
        if method not in _VALID_METHODS:
            method = "POST"

        headers: dict[str, str] = dict(channel_config.get("headers", {}))
        headers.setdefault("Content-Type", "application/json")

        # Build payload from optional template override or default structure
        template: dict | None = channel_config.get("template")
        if template:
            payload = _render_template(template, message)
        else:
            payload = _default_payload(message)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()

            return ProviderResult(
                success=True,
                recipient=url,
                provider_response=response.text[:500],
            )

        except httpx.HTTPStatusError as exc:
            error = f"Webhook returned HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            logger.warning("Webhook send failed: %s", error)
            return ProviderResult(success=False, error=error)

        except httpx.TimeoutException:
            error = f"Webhook request timed out: {url}"
            logger.warning(error)
            return ProviderResult(success=False, error=error)

        except Exception as exc:  # noqa: BLE001
            error = f"Unexpected error sending webhook notification: {exc}"
            logger.exception("Webhook send unexpected error")
            return ProviderResult(success=False, error=error)

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """
        Validate webhook channel configuration.

        Args:
            config: Channel config dict.

        Returns:
            List of validation error messages.
        """
        errors: list[str] = []
        url = config.get("url", "")
        if not url:
            errors.append("url is required for webhook channels")
        elif not (str(url).startswith("http://") or str(url).startswith("https://")):
            errors.append("url must start with http:// or https://")
        method = str(config.get("method", "POST")).upper()
        if method not in _VALID_METHODS:
            errors.append(f"method must be one of {sorted(_VALID_METHODS)}")
        headers = config.get("headers", {})
        if not isinstance(headers, dict):
            errors.append("headers must be a JSON object (dict)")
        return errors


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------

def _default_payload(message: NotificationMessage) -> dict[str, Any]:
    """
    Build the default webhook JSON payload.

    Args:
        message: Notification message.

    Returns:
        JSON-serialisable dict.
    """
    return {
        "event_type": message.event_type,
        "event_id": str(message.event_id) if message.event_id else None,
        "title": message.title,
        "body": message.body,
        "severity": message.severity,
        "metadata": message.metadata,
    }


def _render_template(template: dict, message: NotificationMessage) -> dict[str, Any]:
    """
    Substitute simple ``{{ key }}`` placeholders in a template dict.

    Supported tokens: event_type, event_id, title, body, severity, plus any
    key from message.metadata.

    Args:
        template: Template dict with optional string values containing tokens.
        message: Notification message providing substitution values.

    Returns:
        Rendered dict.
    """
    context = {
        "event_type": message.event_type,
        "event_id": str(message.event_id) if message.event_id else "",
        "title": message.title,
        "body": message.body,
        "severity": message.severity or "",
        **{str(k): str(v) for k, v in message.metadata.items()},
    }

    rendered = json.dumps(template)
    for key, val in context.items():
        rendered = rendered.replace("{{ " + key + " }}", val)
        rendered = rendered.replace("{{" + key + "}}", val)

    try:
        return json.loads(rendered)
    except json.JSONDecodeError:
        logger.warning("Template rendering produced invalid JSON; falling back to default payload")
        return _default_payload(message)
