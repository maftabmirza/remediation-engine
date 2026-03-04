"""
Unit tests for NotificationService.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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


def _make_policy(event_type="alert.firing", channel_id=None, severity_filter=None):
    from app.models_notification import NotificationPolicy
    p = NotificationPolicy(
        name="Test Policy",
        event_type=event_type,
        channel_ids=[channel_id or uuid.uuid4()],
        severity_filter=severity_filter,
        is_enabled=True,
    )
    p.id = uuid.uuid4()
    return p


@pytest.mark.unit
@pytest.mark.asyncio
class TestNotificationService:
    """Tests for the NotificationService orchestrator."""

    async def test_notify_queues_log_entries(self):
        """Happy path: notify() creates pending log entries for matching policies."""
        from app.services.notification.service import NotificationService

        ch = _make_channel()
        policy = _make_policy(event_type="alert.firing", channel_id=ch.id)

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[policy])))))
        db.get = AsyncMock(return_value=ch)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        svc = NotificationService(db)
        log_ids = await svc.notify("alert.firing", {"alert_name": "High CPU", "severity": "critical"})

        assert len(log_ids) == 1
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    async def test_notify_no_matching_policies(self):
        """No matching policies returns empty list."""
        from app.services.notification.service import NotificationService

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ))

        svc = NotificationService(db)
        log_ids = await svc.notify("alert.firing", {"severity": "critical"})

        assert log_ids == []
        db.add.assert_not_called()

    async def test_notify_severity_filter_excludes(self):
        """Policy with severity_filter excludes non-matching events."""
        from app.services.notification.service import NotificationService

        ch = _make_channel()
        policy = _make_policy(
            event_type="alert.firing",
            channel_id=ch.id,
            severity_filter=["critical"],
        )

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[policy])))
        ))

        svc = NotificationService(db)
        # Send "info" severity — should be excluded by filter
        log_ids = await svc.notify("alert.firing", {"severity": "info"})
        assert log_ids == []

    async def test_notify_disabled_channel_skipped(self):
        """Disabled channel is skipped even when policy matches."""
        from app.services.notification.service import NotificationService

        ch = _make_channel(is_enabled=False)
        policy = _make_policy(event_type="alert.firing", channel_id=ch.id)

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[policy])))
        ))
        db.get = AsyncMock(return_value=ch)

        svc = NotificationService(db)
        log_ids = await svc.notify("alert.firing", {"severity": "critical"})
        assert log_ids == []

    async def test_send_immediate_success(self):
        """send_immediate() calls provider and creates log entry."""
        from app.services.notification.service import NotificationService
        from app.schemas_notification import NotificationMessage, ProviderResult

        ch = _make_channel(channel_type="slack")
        db = AsyncMock()
        db.get = AsyncMock(return_value=ch)
        db.add = MagicMock()
        db.commit = AsyncMock()

        svc = NotificationService(db)
        msg = NotificationMessage(event_type="test", title="Test", body="test body")

        mock_result = ProviderResult(success=True, recipient="#general")
        with patch("app.services.notification.service._PROVIDERS", {"slack": AsyncMock(send=AsyncMock(return_value=mock_result))}):
            result = await svc.send_immediate(ch.id, msg)

        assert result.success is True
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    async def test_send_immediate_channel_not_found(self):
        """send_immediate() returns failure when channel doesn't exist."""
        from app.services.notification.service import NotificationService
        from app.schemas_notification import NotificationMessage

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)

        svc = NotificationService(db)
        msg = NotificationMessage(event_type="test", title="T", body="B")
        result = await svc.send_immediate(uuid.uuid4(), msg)

        assert result.success is False
        assert "not found" in result.error

    async def test_test_channel_success(self):
        """test_channel() sends a test message and returns success."""
        from app.services.notification.service import NotificationService
        from app.schemas_notification import ProviderResult

        ch = _make_channel(channel_type="webhook")
        db = AsyncMock()
        db.get = AsyncMock(return_value=ch)

        svc = NotificationService(db)
        mock_result = ProviderResult(success=True, recipient="https://example.com")
        with patch("app.services.notification.service._PROVIDERS", {"webhook": AsyncMock(send=AsyncMock(return_value=mock_result))}):
            result = await svc.test_channel(ch.id)

        assert result.success is True

    async def test_validate_channel_config_delegates_to_provider(self):
        """validate_channel_config() delegates to the provider's validate method."""
        from app.services.notification.service import NotificationService

        db = AsyncMock()
        svc = NotificationService(db)
        errors = await svc.validate_channel_config("slack", {"webhook_url": "https://hooks.slack.com/services/T/B/X"})
        assert errors == []
