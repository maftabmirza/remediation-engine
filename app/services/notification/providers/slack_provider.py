"""
Slack notification provider.

Sends messages via Slack Incoming Webhooks using Block Kit JSON payloads.
No slack-sdk dependency — a plain httpx POST is sufficient.
"""

import json
import logging
from typing import Any

import httpx

from app.schemas_notification import NotificationMessage, ProviderResult
from app.services.notification.providers.base import BaseNotificationProvider
from app.services.notification.templates.renderer import render_template

logger = logging.getLogger(__name__)


class SlackProvider(BaseNotificationProvider):
    """Delivers notifications to Slack via an Incoming Webhook URL."""

    provider_name = "slack"

    async def send(
        self,
        channel_config: dict[str, Any],
        message: NotificationMessage,
    ) -> ProviderResult:
        """
        POST a Block Kit payload to the configured Slack webhook URL.

        Args:
            channel_config: Must contain ``webhook_url`` key.
            message: Rendered notification message.

        Returns:
            ProviderResult indicating success or failure.
        """
        webhook_url: str | None = channel_config.get("webhook_url")
        channel_name: str = channel_config.get("channel", "")

        if not webhook_url:
            return ProviderResult(
                success=False,
                error="Slack channel config is missing 'webhook_url'",
            )

        payload = _build_block_kit(message, channel_config)

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
                recipient=channel_name or webhook_url,
                provider_response=response.text,
            )

        except httpx.HTTPStatusError as exc:
            error = f"Slack webhook returned HTTP {exc.response.status_code}: {exc.response.text}"
            logger.warning("Slack send failed: %s", error)
            return ProviderResult(success=False, error=error)

        except httpx.TimeoutException:
            error = "Slack webhook request timed out"
            logger.warning("Slack send timed out for %s", webhook_url)
            return ProviderResult(success=False, error=error)

        except Exception as exc:  # noqa: BLE001
            error = f"Unexpected error sending Slack notification: {exc}"
            logger.exception("Slack send unexpected error")
            return ProviderResult(success=False, error=error)

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """
        Validate Slack channel configuration.

        Args:
            config: Channel config dict.

        Returns:
            List of validation error messages.
        """
        errors: list[str] = []
        if not config.get("webhook_url"):
            errors.append("webhook_url is required for Slack channels")
        elif not str(config["webhook_url"]).startswith("https://hooks.slack.com/"):
            errors.append("webhook_url must be a valid Slack Incoming Webhook URL (https://hooks.slack.com/...)")
        return errors


# ---------------------------------------------------------------------------
# Block Kit payload builder
# ---------------------------------------------------------------------------

_SEVERITY_EMOJI = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🔵",
    "ok": "🟢",
    "resolved": "🟢",
}


def _build_block_kit(
    message: NotificationMessage,
    channel_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Build a Slack Block Kit payload from a notification message.

    Args:
        message: The prepared notification message.
        channel_config: Channel-level config (may contain ``channel`` override).

    Returns:
        Slack API compatible payload dict.
    """
    severity = (message.severity or "info").lower()
    emoji = _SEVERITY_EMOJI.get(severity, "📢")
    header_text = f"{emoji} {message.title}"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text[:150], "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": message.body[:3000]},
        },
    ]

    # Optional metadata fields
    fields: list[dict] = []
    if message.severity:
        fields.append({"type": "mrkdwn", "text": f"*Severity:*\n{message.severity.upper()}"})
    if meta_source := message.metadata.get("source"):
        fields.append({"type": "mrkdwn", "text": f"*Source:*\n{meta_source}"})
    if meta_host := message.metadata.get("host"):
        fields.append({"type": "mrkdwn", "text": f"*Host:*\n{meta_host}"})
    if meta_runbook := message.metadata.get("runbook_name"):
        fields.append({"type": "mrkdwn", "text": f"*Runbook:*\n{meta_runbook}"})

    if fields:
        blocks.append({"type": "section", "fields": fields[:10]})

    # Action buttons
    actions: list[dict] = []
    if alert_url := message.metadata.get("alert_url"):
        actions.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "View Alert", "emoji": True},
            "url": alert_url,
            "style": "primary",
        })
    if approval_url := message.metadata.get("approval_url"):
        actions.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Approve", "emoji": True},
            "url": approval_url,
            "style": "primary",
        })

    if actions:
        blocks.append({"type": "actions", "elements": actions})

    blocks.append({"type": "divider"})

    payload: dict[str, Any] = {"blocks": blocks}

    # Optional channel override from config
    if channel := channel_config.get("channel"):
        payload["channel"] = channel

    return payload
