"""
NotificationService — main entry point for the notification system.

Responsibilities:
- Find policies that match an incoming event
- Queue notification_log rows with status="pending"
- Provide send_immediate() for time-critical sends (approvals)
- Provide test_channel() for config verification
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models_notification import (
    NotificationChannel,
    NotificationLog,
    NotificationPolicy,
)
from app.schemas_notification import NotificationMessage, ProviderResult
from app.services.notification.providers import (
    EmailProvider,
    SlackProvider,
    TeamsProvider,
    WebhookProvider,
)
from app.services.notification.templates.renderer import render_template

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------
_PROVIDERS = {
    "slack": SlackProvider(),
    "msteams": TeamsProvider(),
    "email": EmailProvider(),
    "webhook": WebhookProvider(),
}


def _get_fernet() -> Fernet | None:
    """Return a Fernet instance if an encryption key is configured."""
    key = settings.encryption_key
    if not key:
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        return None


def _decrypt_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of config with any ``_encrypted`` suffixed values decrypted.

    Args:
        config: Raw config_json from the database row.

    Returns:
        Config dict with plaintext values.
    """
    fernet = _get_fernet()
    if not fernet:
        return config

    result = {}
    for key, val in config.items():
        if key.endswith("_encrypted") and isinstance(val, str):
            plain_key = key[: -len("_encrypted")]
            try:
                result[plain_key] = fernet.decrypt(val.encode()).decode()
            except (InvalidToken, Exception):
                result[plain_key] = val  # Fallback — pass through
        else:
            result[key] = val
    return result


class NotificationService:
    """
    High-level notification orchestrator.

    Callers should always use :meth:`notify` for standard event notifications.
    Only use :meth:`send_immediate` for approval requests or other time-critical
    paths where queue latency is unacceptable.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def notify(
        self,
        event_type: str,
        event_data: dict[str, Any],
        event_id: UUID | None = None,
    ) -> list[UUID]:
        """
        Queue notifications for an event.

        Finds all enabled policies matching ``event_type`` (and severity if
        applicable), then creates ``notification_log`` rows with
        ``status='pending'``.  The actual delivery is handled by the
        :class:`~app.services.notification.dispatcher.NotificationDispatcher`
        background worker.

        Args:
            event_type: Dot-notation event string, e.g. ``"alert.firing"``.
            event_data: Arbitrary context dict used for template rendering and
                        severity-filter matching.
            event_id: Optional foreign-key UUID (alert ID, execution ID, etc.).

        Returns:
            List of newly created :class:`NotificationLog` UUIDs.
        """
        if event_id:
            event_data = {**event_data, "event_id": str(event_id)}

        policies = await self._find_matching_policies(event_type, event_data)
        if not policies:
            logger.debug("No notification policies match event_type=%s", event_type)
            return []

        # Collect (policy, channel) pairs, de-duplicating channels per policy set
        log_ids: list[UUID] = []
        seen_channel_ids: set[UUID] = set()

        for policy in policies:
            message = render_template(
                event_type, event_data, template_key=policy.template_key
            )

            for channel_id in policy.channel_ids:
                if channel_id in seen_channel_ids:
                    continue
                seen_channel_ids.add(channel_id)

                channel = await self.db.get(NotificationChannel, channel_id)
                if not channel or not channel.is_enabled:
                    continue

                log_entry = NotificationLog(
                    policy_id=policy.id,
                    channel_id=channel.id,
                    event_type=event_type,
                    event_id=event_id,
                    status="pending",
                    attempt_count=0,
                    payload_json=message.model_dump(mode="json"),
                )
                self.db.add(log_entry)
                await self.db.flush()
                log_ids.append(log_entry.id)

        await self.db.commit()
        logger.info(
            "Queued %d notification(s) for event_type=%s", len(log_ids), event_type
        )
        return log_ids

    async def send_immediate(
        self,
        channel_id: UUID,
        message: NotificationMessage,
    ) -> ProviderResult:
        """
        Send a single notification immediately, bypassing the queue.

        Intended for approval requests where queue latency is unacceptable.
        Still creates a log entry for the audit trail.

        Args:
            channel_id: UUID of the target NotificationChannel.
            message: Pre-built message to send.

        Returns:
            ProviderResult with delivery outcome.
        """
        channel = await self.db.get(NotificationChannel, channel_id)
        if not channel:
            return ProviderResult(success=False, error=f"Channel {channel_id} not found")
        if not channel.is_enabled:
            return ProviderResult(success=False, error=f"Channel {channel_id} is disabled")

        provider = _PROVIDERS.get(channel.channel_type)
        if not provider:
            return ProviderResult(
                success=False, error=f"No provider for channel_type={channel.channel_type}"
            )

        config = _decrypt_config(dict(channel.config_json))
        result = await provider.send(config, message)

        # Audit log
        log_entry = NotificationLog(
            channel_id=channel.id,
            event_type=message.event_type,
            event_id=message.event_id,
            recipient=result.recipient,
            status="sent" if result.success else "failed",
            attempt_count=1,
            error_message=result.error,
            payload_json=message.model_dump(mode="json"),
            sent_at=datetime.now(timezone.utc) if result.success else None,
        )
        self.db.add(log_entry)
        await self.db.commit()

        return result

    async def test_channel(self, channel_id: UUID) -> ProviderResult:
        """
        Send a test notification to verify channel configuration.

        Args:
            channel_id: UUID of the channel to test.

        Returns:
            ProviderResult with outcome.
        """
        channel = await self.db.get(NotificationChannel, channel_id)
        if not channel:
            return ProviderResult(success=False, error=f"Channel {channel_id} not found")

        provider = _PROVIDERS.get(channel.channel_type)
        if not provider:
            return ProviderResult(
                success=False, error=f"No provider for channel_type={channel.channel_type}"
            )

        config = _decrypt_config(dict(channel.config_json))
        test_message = NotificationMessage(
            event_type="test",
            title="🧪 Test Notification",
            body=(
                f"This is a test notification from AIOps Remediation Engine.\n"
                f"Channel: {channel.name} ({channel.channel_type})"
            ),
            severity="info",
            metadata={"source": "aiops", "test": "true"},
        )
        return await provider.send(config, test_message)

    async def validate_channel_config(
        self, channel_type: str, config: dict[str, Any]
    ) -> list[str]:
        """
        Validate a channel config dict before saving.

        Args:
            channel_type: One of slack, msteams, email, webhook.
            config: The config_json to validate.

        Returns:
            List of error strings (empty = valid).
        """
        provider = _PROVIDERS.get(channel_type)
        if not provider:
            return [f"Unknown channel_type: {channel_type}"]
        return provider.validate_config(config)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _find_matching_policies(
        self, event_type: str, event_data: dict[str, Any]
    ) -> list[NotificationPolicy]:
        """
        Return all enabled policies matching the given event_type and severity.

        Args:
            event_type: Event to match.
            event_data: Event context; ``severity`` key is used for filtering.

        Returns:
            List of matching NotificationPolicy rows.
        """
        result = await self.db.execute(
            select(NotificationPolicy).where(
                NotificationPolicy.event_type == event_type,
                NotificationPolicy.is_enabled.is_(True),
            )
        )
        policies = result.scalars().all()

        event_severity = str(event_data.get("severity", "")).lower()
        matched: list[NotificationPolicy] = []

        for policy in policies:
            # If policy has a severity filter, check it
            if policy.severity_filter:
                filter_values = [s.lower() for s in policy.severity_filter]
                if event_severity and event_severity not in filter_values:
                    continue
            matched.append(policy)

        return matched
