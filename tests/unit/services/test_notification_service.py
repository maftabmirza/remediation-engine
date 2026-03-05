"""
Unit tests for NotificationService.

Covers: notify, send_immediate, test_channel, validate_channel_config,
        _find_matching_policies, _decrypt_config.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas_notification import NotificationMessage, ProviderResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_channel(
    *,
    channel_type: str = "slack",
    is_enabled: bool = True,
    config_json: dict | None = None,
):
    """Return a mock NotificationChannel."""
    ch = MagicMock()
    ch.id = uuid.uuid4()
    ch.name = "test-channel"
    ch.channel_type = channel_type
    ch.is_enabled = is_enabled
    ch.config_json = config_json or {"webhook_url": "https://hooks.slack.com/xxx"}
    return ch


def _make_policy(*, event_type: str = "alert.firing", severity_filter=None, channel_ids=None):
    """Return a mock NotificationPolicy."""
    p = MagicMock()
    p.id = uuid.uuid4()
    p.name = "test-policy"
    p.event_type = event_type
    p.severity_filter = severity_filter
    p.channel_ids = channel_ids or [uuid.uuid4()]
    p.is_enabled = True
    p.template_key = None
    return p


# ===========================================================================
# decrypt_config
# ===========================================================================

@pytest.mark.unit
class TestDecryptConfig:
    """Tests for _decrypt_config helper."""

    def test_passthrough_when_no_key(self):
        """Without encryption key, config is returned as-is."""
        from app.services.notification.service import _decrypt_config

        cfg = {"webhook_url": "https://example.com"}
        with patch("app.services.notification.service.settings") as mock_settings:
            mock_settings.encryption_key = None
            result = _decrypt_config(cfg)
        assert result == cfg

    def test_non_encrypted_keys_pass_through(self):
        """Keys without _encrypted suffix pass through unchanged."""
        from app.services.notification.service import _decrypt_config

        cfg = {"webhook_url": "https://example.com", "channel": "#ops"}
        with patch("app.services.notification.service.settings") as mock_settings:
            mock_settings.encryption_key = None
            result = _decrypt_config(cfg)
        assert result["webhook_url"] == "https://example.com"

    def test_encrypted_key_decrypted(self):
        """Keys ending in _encrypted are decrypted and renamed."""
        from cryptography.fernet import Fernet

        from app.services.notification.service import _decrypt_config

        key = Fernet.generate_key()
        fernet = Fernet(key)
        encrypted_val = fernet.encrypt(b"my_secret_password").decode()

        cfg = {"smtp_host": "smtp.example.com", "smtp_password_encrypted": encrypted_val}
        with patch("app.services.notification.service.settings") as mock_settings:
            mock_settings.encryption_key = key.decode()
            result = _decrypt_config(cfg)

        assert "smtp_password" in result
        assert result["smtp_password"] == "my_secret_password"
        assert "smtp_password_encrypted" not in result


# ===========================================================================
# validate_channel_config
# ===========================================================================

@pytest.mark.unit
class TestValidateChannelConfig:
    """Tests for NotificationService.validate_channel_config."""

    @pytest.mark.asyncio
    async def test_valid_slack_config(self):
        """Slack config with webhook_url passes validation."""
        from app.services.notification.service import NotificationService

        db = AsyncMock()
        svc = NotificationService(db)
        errors = await svc.validate_channel_config(
            "slack", {"webhook_url": "https://hooks.slack.com/services/T/B/X"}
        )
        assert errors == []

    @pytest.mark.asyncio
    async def test_unknown_channel_type(self):
        """Unknown channel type returns error."""
        from app.services.notification.service import NotificationService

        db = AsyncMock()
        svc = NotificationService(db)
        errors = await svc.validate_channel_config("sms", {})
        assert len(errors) == 1
        assert "Unknown" in errors[0]

    @pytest.mark.asyncio
    async def test_email_missing_required_fields(self):
        """Email config without required fields returns errors."""
        from app.services.notification.service import NotificationService

        db = AsyncMock()
        svc = NotificationService(db)
        errors = await svc.validate_channel_config("email", {})
        assert len(errors) > 0


# ===========================================================================
# test_channel
# ===========================================================================

@pytest.mark.unit
class TestTestChannel:
    """Tests for NotificationService.test_channel."""

    @pytest.mark.asyncio
    async def test_channel_not_found(self):
        """Returns failure when channel does not exist."""
        from app.services.notification.service import NotificationService

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        svc = NotificationService(db)

        result = await svc.test_channel(uuid.uuid4())
        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_channel_success(self):
        """Successful test returns provider result."""
        from app.services.notification.service import NotificationService

        channel = _make_channel()
        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)

        mock_provider = AsyncMock()
        mock_provider.send = AsyncMock(
            return_value=ProviderResult(success=True, recipient="#ops")
        )

        svc = NotificationService(db)
        with patch.dict(
            "app.services.notification.service._PROVIDERS",
            {"slack": mock_provider},
        ):
            result = await svc.test_channel(channel.id)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_channel_no_provider(self):
        """Returns failure when no provider exists for channel type."""
        from app.services.notification.service import NotificationService

        channel = _make_channel(channel_type="fax")
        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)

        svc = NotificationService(db)
        with patch.dict("app.services.notification.service._PROVIDERS", {}, clear=True):
            result = await svc.test_channel(channel.id)

        assert result.success is False
        assert "No provider" in result.error


# ===========================================================================
# send_immediate
# ===========================================================================

@pytest.mark.unit
class TestSendImmediate:
    """Tests for NotificationService.send_immediate."""

    @pytest.mark.asyncio
    async def test_send_immediate_success(self):
        """Successful immediate send creates log entry with status=sent."""
        from app.services.notification.service import NotificationService

        channel = _make_channel()
        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)

        mock_provider = AsyncMock()
        mock_provider.send = AsyncMock(
            return_value=ProviderResult(success=True, recipient="#channel")
        )

        svc = NotificationService(db)
        msg = NotificationMessage(
            event_type="approval.requested",
            title="Approval needed",
            body="Please approve",
        )

        with patch.dict("app.services.notification.service._PROVIDERS", {"slack": mock_provider}):
            result = await svc.send_immediate(channel.id, msg)

        assert result.success is True
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_immediate_channel_not_found(self):
        """Returns failure when channel doesn't exist."""
        from app.services.notification.service import NotificationService

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        svc = NotificationService(db)
        msg = NotificationMessage(event_type="test", title="t", body="b")

        result = await svc.send_immediate(uuid.uuid4(), msg)
        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_send_immediate_channel_disabled(self):
        """Returns failure when channel is disabled."""
        from app.services.notification.service import NotificationService

        channel = _make_channel(is_enabled=False)
        db = AsyncMock()
        db.get = AsyncMock(return_value=channel)
        svc = NotificationService(db)
        msg = NotificationMessage(event_type="test", title="t", body="b")

        result = await svc.send_immediate(channel.id, msg)
        assert result.success is False
        assert "disabled" in result.error


# ===========================================================================
# notify (queue-based)
# ===========================================================================

@pytest.mark.unit
class TestNotify:
    """Tests for NotificationService.notify."""

    @pytest.mark.asyncio
    async def test_notify_no_matching_policies(self):
        """Returns empty list when no policies match."""
        from app.services.notification.service import NotificationService

        db = AsyncMock()
        # Simulate empty policy query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        svc = NotificationService(db)
        log_ids = await svc.notify("alert.firing", {"severity": "critical"})
        assert log_ids == []

    @pytest.mark.asyncio
    async def test_notify_queues_log_entries(self):
        """Matching policies create pending log entries."""
        from app.services.notification.service import NotificationService

        channel = _make_channel()
        policy = _make_policy(channel_ids=[channel.id])

        db = AsyncMock()
        # First call: policy query. Second+: other queries
        mock_policy_result = MagicMock()
        mock_policy_result.scalars.return_value.all.return_value = [policy]
        db.execute = AsyncMock(return_value=mock_policy_result)
        db.get = AsyncMock(return_value=channel)

        # Mock flush to set id on added objects
        async def mock_flush():
            for call_args in db.add.call_args_list:
                obj = call_args[0][0]
                if hasattr(obj, "id") and obj.id is None:
                    obj.id = uuid.uuid4()

        db.flush = AsyncMock(side_effect=mock_flush)

        svc = NotificationService(db)
        log_ids = await svc.notify("alert.firing", {"severity": "critical"})

        assert len(log_ids) == 1
        db.add.assert_called()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_notify_skips_disabled_channel(self):
        """Disabled channels are skipped even if policy matches."""
        from app.services.notification.service import NotificationService

        channel = _make_channel(is_enabled=False)
        policy = _make_policy(channel_ids=[channel.id])

        db = AsyncMock()
        mock_policy_result = MagicMock()
        mock_policy_result.scalars.return_value.all.return_value = [policy]
        db.execute = AsyncMock(return_value=mock_policy_result)
        db.get = AsyncMock(return_value=channel)

        svc = NotificationService(db)
        log_ids = await svc.notify("alert.firing", {})

        assert log_ids == []

    @pytest.mark.asyncio
    async def test_notify_severity_filter(self):
        """Policies with severity filter only match correct severity."""
        from app.services.notification.service import NotificationService

        channel = _make_channel()
        policy = _make_policy(
            severity_filter=["critical"],
            channel_ids=[channel.id],
        )

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [policy]
        db.execute = AsyncMock(return_value=mock_result)
        db.get = AsyncMock(return_value=channel)

        svc = NotificationService(db)

        # Warning severity should NOT match critical-only filter
        log_ids = await svc.notify("alert.firing", {"severity": "warning"})
        assert log_ids == []


# ===========================================================================
# _find_matching_policies
# ===========================================================================

@pytest.mark.unit
class TestFindMatchingPolicies:
    """Tests for NotificationService._find_matching_policies."""

    @pytest.mark.asyncio
    async def test_matches_all_severities_when_no_filter(self):
        """Policy without severity_filter matches any severity."""
        from app.services.notification.service import NotificationService

        policy = _make_policy(severity_filter=None)

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [policy]
        db.execute = AsyncMock(return_value=mock_result)

        svc = NotificationService(db)
        matched = await svc._find_matching_policies("alert.firing", {"severity": "info"})
        assert len(matched) == 1

    @pytest.mark.asyncio
    async def test_filters_by_severity(self):
        """Policy with severity_filter filters correctly."""
        from app.services.notification.service import NotificationService

        policy = _make_policy(severity_filter=["critical", "warning"])

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [policy]
        db.execute = AsyncMock(return_value=mock_result)

        svc = NotificationService(db)

        # Matching
        matched = await svc._find_matching_policies("alert.firing", {"severity": "critical"})
        assert len(matched) == 1

        # Not matching
        matched = await svc._find_matching_policies("alert.firing", {"severity": "info"})
        assert len(matched) == 0

    @pytest.mark.asyncio
    async def test_empty_when_no_policies(self):
        """Returns empty list when no policies exist."""
        from app.services.notification.service import NotificationService

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        svc = NotificationService(db)
        matched = await svc._find_matching_policies("alert.firing", {})
        assert matched == []
