"""
Unit tests for NotificationDispatcher.

Covers: start/stop lifecycle, _process_pending, _retry_failed, _send_entry.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas_notification import NotificationMessage, ProviderResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_channel(channel_type: str = "slack", is_enabled: bool = True):
    ch = MagicMock()
    ch.id = uuid.uuid4()
    ch.name = "test-channel"
    ch.channel_type = channel_type
    ch.is_enabled = is_enabled
    ch.config_json = {"webhook_url": "https://hooks.slack.com/xxx"}
    return ch


def _make_log_entry(
    *,
    status: str = "pending",
    attempt_count: int = 0,
    channel_id=None,
    payload: dict | None = None,
):
    entry = MagicMock()
    entry.id = uuid.uuid4()
    entry.channel_id = channel_id or uuid.uuid4()
    entry.event_type = "alert.firing"
    entry.status = status
    entry.attempt_count = attempt_count
    entry.error_message = None
    entry.next_retry_at = None
    entry.sent_at = None
    entry.recipient = None
    entry.payload_json = payload or {
        "event_type": "alert.firing",
        "title": "Test Alert",
        "body": "Something went wrong.",
    }
    return entry


# ===========================================================================
# Dispatcher lifecycle
# ===========================================================================

@pytest.mark.unit
class TestDispatcherLifecycle:
    """Tests for start/stop dispatcher."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        """start() sets running=True and creates a background task."""
        from app.services.notification.dispatcher import NotificationDispatcher

        d = NotificationDispatcher(poll_interval=60)
        with patch.object(d, "_worker_loop", new_callable=AsyncMock):
            await d.start()
            assert d._running is True
            assert d._task is not None
            await d.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        """stop() sets running=False."""
        from app.services.notification.dispatcher import NotificationDispatcher

        d = NotificationDispatcher(poll_interval=60)
        with patch.object(d, "_worker_loop", new_callable=AsyncMock):
            await d.start()
            await d.stop()
            assert d._running is False

    @pytest.mark.asyncio
    async def test_double_start_warns(self):
        """Calling start() twice doesn't create duplicate tasks."""
        from app.services.notification.dispatcher import NotificationDispatcher

        d = NotificationDispatcher(poll_interval=60)
        with patch.object(d, "_worker_loop", new_callable=AsyncMock):
            await d.start()
            await d.start()  # Should warn, not crash
            assert d._running is True
            await d.stop()


# ===========================================================================
# _send_entry
# ===========================================================================

@pytest.mark.unit
class TestSendEntry:
    """Tests for NotificationDispatcher._send_entry."""

    @pytest.mark.asyncio
    async def test_successful_send(self):
        """Entry status set to 'sent' on successful delivery."""
        from app.services.notification.dispatcher import NotificationDispatcher

        channel = _make_channel()
        entry = _make_log_entry(channel_id=channel.id)

        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)

        mock_provider = AsyncMock()
        mock_provider.send = AsyncMock(
            return_value=ProviderResult(success=True, recipient="#ops")
        )
        mock_provider.provider_name = "slack"

        d = NotificationDispatcher()
        with (
            patch.dict("app.services.notification.dispatcher._PROVIDERS", {"slack": mock_provider}),
            patch("app.services.notification.service._decrypt_config", return_value={"webhook_url": "https://hooks.slack.com/xxx"}),
        ):
            await d._send_entry(db, entry)

        assert entry.status == "sent"
        assert entry.sent_at is not None
        assert entry.attempt_count == 1

    @pytest.mark.asyncio
    async def test_channel_not_found(self):
        """Entry marked as failed when channel doesn't exist."""
        from app.services.notification.dispatcher import NotificationDispatcher

        entry = _make_log_entry()
        db = AsyncMock()
        db.get = AsyncMock(return_value=None)

        d = NotificationDispatcher()
        await d._send_entry(db, entry)

        assert entry.status == "failed"
        assert "not found" in entry.error_message.lower() or "disabled" in entry.error_message.lower()

    @pytest.mark.asyncio
    async def test_channel_disabled(self):
        """Entry marked as failed when channel is disabled."""
        from app.services.notification.dispatcher import NotificationDispatcher

        channel = _make_channel(is_enabled=False)
        entry = _make_log_entry(channel_id=channel.id)
        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)

        d = NotificationDispatcher()
        await d._send_entry(db, entry)

        assert entry.status == "failed"

    @pytest.mark.asyncio
    async def test_no_provider(self):
        """Entry marked as failed when no provider for channel type."""
        from app.services.notification.dispatcher import NotificationDispatcher

        channel = _make_channel(channel_type="fax")
        entry = _make_log_entry(channel_id=channel.id)
        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)

        d = NotificationDispatcher()
        with patch.dict("app.services.notification.dispatcher._PROVIDERS", {}, clear=True):
            await d._send_entry(db, entry)

        assert entry.status == "failed"
        assert "No provider" in entry.error_message

    @pytest.mark.asyncio
    async def test_bad_payload(self):
        """Entry marked as failed when payload can't be deserialized."""
        from app.services.notification.dispatcher import NotificationDispatcher

        channel = _make_channel()
        # NotificationMessage requires event_type, title, body — provide invalid
        entry = _make_log_entry(channel_id=channel.id, payload={"bad": True})
        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)

        mock_provider = AsyncMock()
        mock_provider.provider_name = "slack"

        d = NotificationDispatcher()
        with (
            patch.dict("app.services.notification.dispatcher._PROVIDERS", {"slack": mock_provider}),
            patch("app.services.notification.service._decrypt_config", return_value={}),
        ):
            await d._send_entry(db, entry)

        assert entry.status == "failed"
        assert "payload" in entry.error_message.lower() or "deseriali" in entry.error_message.lower()

    @pytest.mark.asyncio
    async def test_provider_exception_triggers_retry(self):
        """Provider exception sets status to retrying with next_retry_at."""
        from app.services.notification.dispatcher import NotificationDispatcher

        channel = _make_channel()
        entry = _make_log_entry(channel_id=channel.id)

        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)

        mock_provider = AsyncMock()
        mock_provider.send = AsyncMock(side_effect=ConnectionError("timeout"))
        mock_provider.provider_name = "slack"

        d = NotificationDispatcher()
        with (
            patch.dict("app.services.notification.dispatcher._PROVIDERS", {"slack": mock_provider}),
            patch("app.services.notification.service._decrypt_config", return_value={}),
            patch("app.services.notification.dispatcher.settings") as mock_settings,
        ):
            mock_settings.notification_retry_max = 3
            mock_settings.notification_retry_delay_seconds = 10
            await d._send_entry(db, entry)

        assert entry.status == "retrying"
        assert entry.next_retry_at is not None
        assert entry.attempt_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_sets_failed(self):
        """Entry marked as permanently failed after max retries exceeded."""
        from app.services.notification.dispatcher import NotificationDispatcher

        channel = _make_channel()
        entry = _make_log_entry(channel_id=channel.id, attempt_count=2)

        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)

        mock_provider = AsyncMock()
        mock_provider.send = AsyncMock(
            return_value=ProviderResult(success=False, error="Server error")
        )
        mock_provider.provider_name = "slack"

        d = NotificationDispatcher()
        with (
            patch.dict("app.services.notification.dispatcher._PROVIDERS", {"slack": mock_provider}),
            patch("app.services.notification.service._decrypt_config", return_value={}),
            patch("app.services.notification.dispatcher.settings") as mock_settings,
        ):
            mock_settings.notification_retry_max = 3
            mock_settings.notification_retry_delay_seconds = 10
            await d._send_entry(db, entry)

        # attempt_count was 2, now incremented to 3 which == max → failed
        assert entry.status == "failed"
        assert entry.error_message == "Server error"


# ===========================================================================
# _process_pending
# ===========================================================================

@pytest.mark.unit
class TestProcessPending:
    """Tests for NotificationDispatcher._process_pending."""

    @pytest.mark.asyncio
    async def test_no_pending_entries(self):
        """No work done when there are no pending entries."""
        from app.services.notification.dispatcher import NotificationDispatcher

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        d = NotificationDispatcher()
        with patch("app.database.async_session_factory", return_value=mock_session):
            await d._process_pending()

        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_processes_pending_entries(self):
        """Pending entries are picked up and _send_entry is called."""
        from app.services.notification.dispatcher import NotificationDispatcher

        entry = _make_log_entry()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entry]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        d = NotificationDispatcher()
        with (
            patch("app.database.async_session_factory", return_value=mock_session),
            patch.object(d, "_send_entry", new_callable=AsyncMock) as mock_send,
        ):
            await d._process_pending()

        mock_send.assert_awaited_once()
        mock_session.commit.assert_awaited_once()


# ===========================================================================
# _retry_failed
# ===========================================================================

@pytest.mark.unit
class TestRetryFailed:
    """Tests for NotificationDispatcher._retry_failed."""

    @pytest.mark.asyncio
    async def test_no_retrying_entries(self):
        """No work done when there are no retrying entries."""
        from app.services.notification.dispatcher import NotificationDispatcher

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        d = NotificationDispatcher()
        with patch("app.database.async_session_factory", return_value=mock_session):
            await d._retry_failed()

        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retries_due_entries(self):
        """Retrying entries past next_retry_at are re-sent."""
        from app.services.notification.dispatcher import NotificationDispatcher

        entry = _make_log_entry(status="retrying", attempt_count=1)
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entry]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        d = NotificationDispatcher()
        with (
            patch("app.database.async_session_factory", return_value=mock_session),
            patch.object(d, "_send_entry", new_callable=AsyncMock) as mock_send,
        ):
            await d._retry_failed()

        mock_send.assert_awaited_once()
        mock_session.commit.assert_awaited_once()


# ===========================================================================
# Module-level helpers
# ===========================================================================

@pytest.mark.unit
class TestModuleHelpers:
    """Tests for get_dispatcher, start/stop functions."""

    def test_get_dispatcher_returns_singleton(self):
        """get_dispatcher returns the same instance on repeated calls."""
        from app.services.notification import dispatcher

        # Reset singleton
        dispatcher._dispatcher = None
        d1 = dispatcher.get_dispatcher()
        d2 = dispatcher.get_dispatcher()
        assert d1 is d2
        dispatcher._dispatcher = None  # Cleanup

    @pytest.mark.asyncio
    async def test_start_dispatcher_disabled(self):
        """start does nothing when notification_worker_enabled=False."""
        from app.services.notification import dispatcher

        dispatcher._dispatcher = None
        with patch.object(dispatcher, "settings") as mock_settings:
            mock_settings.notification_worker_enabled = False
            await dispatcher.start_notification_dispatcher()
        # Should not start
        assert dispatcher._dispatcher is None

    @pytest.mark.asyncio
    async def test_start_dispatcher_enabled(self):
        """start creates and starts the dispatcher when enabled."""
        from app.services.notification import dispatcher

        dispatcher._dispatcher = None
        mock_d = AsyncMock()
        with (
            patch.object(dispatcher, "settings") as mock_settings,
            patch.object(dispatcher, "get_dispatcher", return_value=mock_d),
        ):
            mock_settings.notification_worker_enabled = True
            await dispatcher.start_notification_dispatcher()

        mock_d.start.assert_awaited_once()
        dispatcher._dispatcher = None  # Cleanup
