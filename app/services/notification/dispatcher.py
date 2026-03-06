"""
NotificationDispatcher — async background worker.

Polls the notification_log table for ``pending`` and ``retrying`` rows and
sends them via the appropriate provider.  Follows the same pattern as
:class:`~app.services.execution_worker.ExecutionWorker`.

On-Call integration: when routing a firing alert that belongs to an application
with an escalation policy, the dispatcher resolves the on-call contact and
sends an immediate notification to level-1, then schedules an escalation
timeout via APScheduler.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models_notification import NotificationChannel, NotificationLog
from app.schemas_notification import NotificationMessage
from app.services.notification.providers import (
    EmailProvider,
    SlackProvider,
    TeamsProvider,
    WebhookProvider,
)

logger = logging.getLogger(__name__)
settings = get_settings()

_PROVIDERS = {
    "slack": SlackProvider(),
    "msteams": TeamsProvider(),
    "email": EmailProvider(),
    "webhook": WebhookProvider(),
}

_MAX_CONCURRENT = 10  # Max in-flight sends per poll cycle


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NotificationDispatcher:
    """
    Background worker that delivers queued notifications.

    Lifecycle:
    - ``start()`` spawns an asyncio task running ``_worker_loop()``.
    - ``stop()`` cancels the task gracefully.

    The worker:
    1. Picks up ``pending`` log entries and sends them.
    2. Retries ``retrying`` entries whose ``next_retry_at`` has elapsed.
    3. Sleeps for ``poll_interval`` seconds between cycles.
    """

    def __init__(self, poll_interval: int = 3) -> None:
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the notification dispatcher background task."""
        if self._running:
            logger.warning("NotificationDispatcher is already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._worker_loop())
        logger.info("NotificationDispatcher started (poll_interval=%ds)", self.poll_interval)

    async def stop(self) -> None:
        """Stop the dispatcher gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("NotificationDispatcher stopped")

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    async def _worker_loop(self) -> None:
        """Main loop — processes pending and retrying notifications."""
        while self._running:
            try:
                await self._process_pending()
                await self._retry_failed()
            except Exception:  # noqa: BLE001
                logger.exception("Error in NotificationDispatcher loop")
            await asyncio.sleep(self.poll_interval)

    # ------------------------------------------------------------------
    # Pending processing
    # ------------------------------------------------------------------

    async def _process_pending(self) -> None:
        """Pick up pending notifications and send them."""
        from app.database import async_session_factory  # noqa: PLC0415

        async with async_session_factory() as db:
            result = await db.execute(
                select(NotificationLog)
                .where(NotificationLog.status == "pending")
                .limit(_MAX_CONCURRENT)
            )
            entries = result.scalars().all()

            if not entries:
                return

            logger.debug("Processing %d pending notification(s)", len(entries))
            tasks = [self._send_entry(db, entry) for entry in entries]
            await asyncio.gather(*tasks, return_exceptions=True)
            await db.commit()

    # ------------------------------------------------------------------
    # Retry logic
    # ------------------------------------------------------------------

    async def _retry_failed(self) -> None:
        """Retry notifications that are due for another attempt."""
        from app.database import async_session_factory  # noqa: PLC0415

        async with async_session_factory() as db:
            now = _utc_now()
            result = await db.execute(
                select(NotificationLog)
                .where(
                    and_(
                        NotificationLog.status == "retrying",
                        NotificationLog.next_retry_at <= now,
                    )
                )
                .limit(_MAX_CONCURRENT)
            )
            entries = result.scalars().all()

            if not entries:
                return

            logger.debug("Retrying %d notification(s)", len(entries))
            tasks = [self._send_entry(db, entry) for entry in entries]
            await asyncio.gather(*tasks, return_exceptions=True)
            await db.commit()

    # ------------------------------------------------------------------
    # Single entry sender
    # ------------------------------------------------------------------

    async def _send_entry(self, db: AsyncSession, entry: NotificationLog) -> None:
        """
        Attempt to send a single notification log entry.

        Args:
            db: Open async database session (caller commits).
            entry: NotificationLog row to deliver.
        """
        channel = await db.get(NotificationChannel, entry.channel_id)
        if not channel or not channel.is_enabled:
            entry.status = "failed"
            entry.error_message = "Channel not found or disabled"
            return

        provider = _PROVIDERS.get(channel.channel_type)
        if not provider:
            entry.status = "failed"
            entry.error_message = f"No provider for channel_type={channel.channel_type}"
            return

        # Reconstruct the message from stored payload
        try:
            payload = dict(entry.payload_json or {})
            message = NotificationMessage(**payload)
        except Exception as exc:  # noqa: BLE001
            entry.status = "failed"
            entry.error_message = f"Could not deserialise payload: {exc}"
            return

        from app.services.notification.service import _decrypt_config  # noqa: PLC0415

        config = _decrypt_config(dict(channel.config_json))

        entry.attempt_count = (entry.attempt_count or 0) + 1

        try:
            result = await provider.send(config, message)
        except Exception as exc:  # noqa: BLE001
            result_success = False
            result_error = f"Provider raised exception: {exc}"
            logger.exception(
                "Provider %s raised exception for log entry %s", provider.provider_name, entry.id
            )
        else:
            result_success = result.success
            result_error = result.error
            entry.recipient = result.recipient

        if result_success:
            entry.status = "sent"
            entry.sent_at = _utc_now()
            entry.error_message = None
            logger.info(
                "Notification sent: log_id=%s event=%s channel=%s",
                entry.id,
                entry.event_type,
                channel.name,
            )
        else:
            max_retries: int = settings.notification_retry_max
            if entry.attempt_count >= max_retries:
                entry.status = "failed"
                entry.error_message = result_error
                logger.warning(
                    "Notification permanently failed after %d attempts: log_id=%s error=%s",
                    entry.attempt_count,
                    entry.id,
                    result_error,
                )
            else:
                entry.status = "retrying"
                entry.error_message = result_error
                delay_seconds = settings.notification_retry_delay_seconds * (
                    2 ** (entry.attempt_count - 1)
                )  # Exponential back-off
                entry.next_retry_at = _utc_now() + timedelta(seconds=delay_seconds)
                logger.info(
                    "Notification will retry in %ds: log_id=%s attempt=%d error=%s",
                    delay_seconds,
                    entry.id,
                    entry.attempt_count,
                    result_error,
                )


# ---------------------------------------------------------------------------
# On-call aware alert routing
# ---------------------------------------------------------------------------


async def route_alert(alert, db: AsyncSession) -> bool:
    """
    Route a firing alert through the on-call escalation chain.

    Checks whether the alert's application has an escalation policy.
    If so, sends to the level-1 on-call contact immediately and schedules
    the escalation timeout job.

    Args:
        alert: Alert ORM object with ``id``, ``app_id`` and metadata fields.
        db: Open async database session.

    Returns:
        True if alert was routed via on-call policy, False if no policy found
        (caller should fall back to standard channel routing).
    """
    if not getattr(alert, "app_id", None):
        return False

    try:
        from app.services.oncall_service import OnCallService  # noqa: PLC0415

        svc = OnCallService(db)
        contacts = await svc.resolve_for_app(UUID(str(alert.app_id)))
        if not contacts:
            return False

        level_1 = contacts[0]
        from app.services.notification.service import NotificationService  # noqa: PLC0415

        notification_svc = NotificationService(db)
        await notification_svc.notify(
            "alert.firing",
            {
                "alert_id": str(alert.id),
                "alert_name": getattr(alert, "name", ""),
                "severity": getattr(alert, "severity", ""),
                "oncall_user": level_1.user.user_name,
                "oncall_email": level_1.user.user_email,
                "escalation_level": level_1.level,
            },
            event_id=alert.id,
        )

        # Schedule escalation timeout
        try:
            from apscheduler.triggers.date import DateTrigger  # noqa: PLC0415

            from app.services.oncall_service import _run_escalation  # noqa: PLC0415
            from app.services.scheduler_service import get_scheduler  # noqa: PLC0415

            scheduler = get_scheduler()
            run_at = _utc_now() + timedelta(minutes=level_1.timeout_minutes)
            job_id = f"escalation_{alert.id}_1"
            scheduler._scheduler.add_job(
                func=_run_escalation,
                trigger=DateTrigger(run_date=run_at),
                id=job_id,
                replace_existing=True,
                kwargs={
                    "alert_id": str(alert.id),
                    "current_level": 1,
                    "policy_id": str(level_1.policy_id),
                },
            )
            logger.info(
                "Scheduled escalation job %s for alert %s at %s",
                job_id,
                alert.id,
                run_at,
            )
        except Exception as exc:
            logger.warning("Failed to schedule escalation for alert %s: %s", alert.id, exc)

        return True

    except Exception as exc:
        logger.exception("on-call route_alert failed for alert %s: %s", alert.id, exc)
        return False


# ---------------------------------------------------------------------------
# Module-level singleton (registered in main.py lifespan)
# ---------------------------------------------------------------------------
_dispatcher: Optional[NotificationDispatcher] = None


def get_dispatcher() -> NotificationDispatcher:
    """Return (or create) the singleton NotificationDispatcher."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = NotificationDispatcher()
    return _dispatcher


async def start_notification_dispatcher() -> None:
    """Start the singleton dispatcher. Called from app lifespan."""
    if settings.notification_worker_enabled:
        await get_dispatcher().start()
    else:
        logger.info("NotificationDispatcher disabled via NOTIFICATION_WORKER_ENABLED=false")


async def stop_notification_dispatcher() -> None:
    """Stop the singleton dispatcher. Called from app lifespan."""
    if _dispatcher is not None:
        await _dispatcher.stop()
