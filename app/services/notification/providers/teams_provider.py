"""
MS Teams notification provider.

Sends messages via Incoming Webhook using Adaptive Cards format.
No extra SDK required — plain httpx POST.
"""

import logging
from typing import Any

import httpx

from app.schemas_notification import NotificationMessage, ProviderResult
from app.services.notification.providers.base import BaseNotificationProvider

logger = logging.getLogger(__name__)


class TeamsProvider(BaseNotificationProvider):
    """Delivers notifications to Microsoft Teams via an Incoming Webhook URL."""

    provider_name = "msteams"

    async def send(
        self,
        channel_config: dict[str, Any],
        message: NotificationMessage,
    ) -> ProviderResult:
        """
        POST an Adaptive Card payload to a Teams Incoming Webhook.

        Args:
            channel_config: Must contain ``webhook_url``.
            message: Rendered notification message.

        Returns:
            ProviderResult indicating success or failure.
        """
        webhook_url: str | None = channel_config.get("webhook_url")
        if not webhook_url:
            return ProviderResult(
                success=False,
                error="Teams channel config is missing 'webhook_url'",
            )

        payload = _build_adaptive_card(message)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

            return ProviderResult(
                success=True,
                recipient=webhook_url,
                provider_response=response.text,
            )

        except httpx.HTTPStatusError as exc:
            error = f"Teams webhook returned HTTP {exc.response.status_code}: {exc.response.text}"
            logger.warning("Teams send failed: %s", error)
            return ProviderResult(success=False, error=error)

        except httpx.TimeoutException:
            logger.warning("Teams send timed out for %s", webhook_url)
            return ProviderResult(success=False, error="Teams webhook request timed out")

        except Exception as exc:  # noqa: BLE001
            logger.exception("Teams send unexpected error")
            return ProviderResult(success=False, error=f"Unexpected error: {exc}")

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """
        Validate Teams channel configuration.

        Args:
            config: Channel config dict.

        Returns:
            List of validation error messages.
        """
        errors: list[str] = []
        if not config.get("webhook_url"):
            errors.append("webhook_url is required for MS Teams channels")
        elif not (
            "outlook.office.com/webhook" in str(config["webhook_url"])
            or "webhook.office.com/webhookb2" in str(config["webhook_url"])
        ):
            errors.append(
                "webhook_url must be a valid Teams Incoming Webhook URL "
                "(outlook.office.com/webhook/... or webhook.office.com/webhookb2/...)"
            )
        return errors


# ---------------------------------------------------------------------------
# Adaptive Card builder
# ---------------------------------------------------------------------------

_SEVERITY_COLORS = {
    "critical": "attention",   # Red
    "warning": "warning",      # Yellow/orange
    "info": "accent",          # Blue
    "ok": "good",              # Green
    "resolved": "good",
}


def _build_adaptive_card(message: NotificationMessage) -> dict[str, Any]:
    """
    Build an Adaptive Card payload in the Office 365 Connector format.

    Args:
        message: Notification message to render.

    Returns:
        Teams-compatible payload dict.
    """
    severity = (message.severity or "info").lower()
    color = _SEVERITY_COLORS.get(severity, "accent")

    # Facts list from metadata
    facts: list[dict] = []
    if message.severity:
        facts.append({"name": "Severity", "value": message.severity.upper()})
    if source := message.metadata.get("source"):
        facts.append({"name": "Source", "value": source})
    if host := message.metadata.get("host"):
        facts.append({"name": "Host", "value": host})
    if runbook := message.metadata.get("runbook_name"):
        facts.append({"name": "Runbook", "value": runbook})

    # Potential action buttons
    potential_action: list[dict] = []
    if alert_url := message.metadata.get("alert_url"):
        potential_action.append({
            "@type": "OpenUri",
            "name": "View Alert",
            "targets": [{"os": "default", "uri": alert_url}],
        })
    if approval_url := message.metadata.get("approval_url"):
        potential_action.append({
            "@type": "OpenUri",
            "name": "Approve",
            "targets": [{"os": "default", "uri": approval_url}],
        })

    card: dict[str, Any] = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": _hex_from_color(color),
        "summary": message.title,
        "sections": [
            {
                "activityTitle": f"**{message.title}**",
                "activityText": message.body,
                "facts": facts,
                "markdown": True,
            }
        ],
    }

    if potential_action:
        card["potentialAction"] = potential_action

    return card


def _hex_from_color(color: str) -> str:
    _map = {
        "attention": "FF0000",
        "warning": "FFA500",
        "accent": "0078D4",
        "good": "28A745",
    }
    return _map.get(color, "0078D4")
