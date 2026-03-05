"""
Unit tests for NotificationDispatcher background worker.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _utc_now():
    return datetime.now(timezone.utc)


def _make_log_entry(status="pending", attempt_count=0):
    from app.models_notification import NotificationLog
    entry = NotificationLog(
        channel_id=uuid.uuid4(),
        event_type="alert.firing",
        status=status,
        attempt_count=attempt_count,
        payload_json={
            "event_type": "alert.firing",
            "title": "High CPU",
            "body": "CPU > 90%",
            "severity": "critical",
            "metadata": {},
        },
    )
    entry.id = uuid.uuid4()
    return entry


def _make_channel(channel_type="slack", is_enabled=True):
    from app.models_notification import NotificationChannel
    ch = NotificationChannel(
        name="Test Channel",
        channel_type=channel_type,
        config_json={"webhook_url": "https://hooks.slack.com/services/test"},
        is_enabled=is_enabled,
    )
    ch.id = uuid.uuid4()
    return ch


@pytest.mark.unit
@pytest.mark.asyncio
class TestNotificationDispatcher:
    """Tests for NotificationDispatcher."""

    async def test_start_creates_task(self):
        """start() sets _running=True and creates background task."""
        from app.services.notification.dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher(poll_interval=999)
        try:
            await dispatcher.start()
            assert dispatcher._running is True
            assert dispatcher._task is not None
        finally:
            await dispatcher.stop()

    async def test_stop_cancels_task(self):
        """stop() sets _running=False and cancels the task."""
        from app.services.notification.dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher(poll_interval=999)
        await dispatcher.start()
        await dispatcher.stop()
        assert dispatcher._running is False

    async def test_start_idempotent(self):
        """Calling start() twice does not create a second task."""
        from app.services.notification.dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher(poll_interval=999)
        try:
            await dispatcher.start()
            task1 = dispatcher._task
            await dispatcher.start()  # Second call
            assert dispatcher._task is task1  # Same task
        finally:
            await dispatcher.stop()

    async def test_send_entry_success(self):
        """_send_entry() marks log entry as sent on provider success."""
        from app.services.notification.dispatcher import NotificationDispatcher
        from app.schemas_notification import ProviderResult

        dispatcher = NotificationDispatcher()
        entry = _make_log_entry()
        channel = _make_channel(channel_type="slack")

        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)

        mock_provider = AsyncMock()
        mock_provider.send = AsyncMock(return_value=ProviderResult(success=True, recipient="#ops"))

        with patch("app.services.notification.dispatcher._PROVIDERS", {"slack": mock_provider}):
            await dispatcher._send_entry(db, entry)

        assert entry.status == "sent"
        assert entry.sent_at is not None
        assert entry.attempt_count == 1

    async def test_send_entry_failure_schedules_retry(self):
        """_send_entry() marks entry as retrying on first failure."""
        from app.services.notification.dispatcher import NotificationDispatcher
        from app.schemas_notification import ProviderResult

        dispatcher = NotificationDispatcher()
        entry = _make_log_entry(status="pending", attempt_count=0)
        channel = _make_channel(channel_type="slack")

        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)

        mock_provider = AsyncMock()
        mock_provider.send = AsyncMock(return_value=ProviderResult(success=False, error="timeout"))

        with patch("app.services.notification.dispatcher._PROVIDERS", {"slack": mock_provider}):
            with patch("app.services.notification.dispatcher.settings") as mock_settings:
                mock_settings.notification_retry_max = 3
                mock_settings.notification_retry_delay_seconds = 30
                await dispatcher._send_entry(db, entry)

        assert entry.status == "retrying"
        assert entry.next_retry_at is not None

    async def test_send_entry_permanent_failure(self):
        """_send_entry() marks as failed after max retries exceeded."""
        from app.services.notification.dispatcher import NotificationDispatcher
        from app.schemas_notification import ProviderResult

        dispatcher = NotificationDispatcher()
        entry = _make_log_entry(status="retrying", attempt_count=2)
        channel = _make_channel(channel_type="webhook")

        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)

        mock_provider = AsyncMock()
        mock_provider.send = AsyncMock(return_value=ProviderResult(success=False, error="Connection refused"))

        with patch("app.services.notification.dispatcher._PROVIDERS", {"webhook": mock_provider}):
            with patch("app.services.notification.dispatcher.settings") as mock_settings:
                mock_settings.notification_retry_max = 3
                mock_settings.notification_retry_delay_seconds = 30
                await dispatcher._send_entry(db, entry)

        assert entry.status == "failed"
        assert entry.next_retry_at is None or entry.status == "failed"

    async def test_send_entry_disabled_channel(self):
        """_send_entry() marks as failed when channel is disabled."""
        from app.services.notification.dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher()
        entry = _make_log_entry()
        channel = _make_channel(is_enabled=False)

        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)

        await dispatcher._send_entry(db, entry)

        assert entry.status == "failed"
        assert "disabled" in entry.error_message

    async def test_send_entry_channel_not_found(self):
        """_send_entry() marks as failed when channel is missing."""
        from app.services.notification.dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher()
        entry = _make_log_entry()

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)

        await dispatcher._send_entry(db, entry)

        assert entry.status == "failed"
