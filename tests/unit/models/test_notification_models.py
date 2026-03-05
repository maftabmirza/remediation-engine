"""
Unit tests for notification SQLAlchemy models.
"""
import uuid
from datetime import datetime, timezone

import pytest


@pytest.mark.unit
class TestNotificationChannelModel:
    """Tests for NotificationChannel model."""

    def test_create_slack_channel(self):
        """Happy path: create a Slack channel with required fields."""
        from app.models_notification import NotificationChannel

        ch = NotificationChannel(
            name="Engineering Slack",
            channel_type="slack",
            config_json={"webhook_url": "https://hooks.slack.com/services/xxx"},
            is_enabled=True,
        )
        assert ch.name == "Engineering Slack"
        assert ch.channel_type == "slack"
        assert ch.is_enabled is True

    def test_channel_defaults(self):
        """Column defaults are None before INSERT (applied server-side)."""
        from app.models_notification import NotificationChannel

        ch = NotificationChannel(
            name="Test",
            channel_type="webhook",
            config_json={},
        )
        # Column defaults are applied at INSERT time, not construction
        assert ch.id is None  # Not persisted yet
        # Explicitly-set is_enabled=True works:
        ch2 = NotificationChannel(
            name="Test2", channel_type="webhook", config_json={}, is_enabled=True,
        )
        assert ch2.is_enabled is True

    def test_valid_channel_types(self):
        """All valid channel types can be instantiated."""
        from app.models_notification import NotificationChannel

        for ct in ("slack", "msteams", "email", "webhook"):
            ch = NotificationChannel(name=f"ch-{ct}", channel_type=ct, config_json={})
            assert ch.channel_type == ct

    def test_repr(self):
        """__repr__ includes name and type."""
        from app.models_notification import NotificationChannel

        ch = NotificationChannel(
            name="Ops Email", channel_type="email", config_json={}
        )
        r = repr(ch)
        assert "Ops Email" in r
        assert "email" in r


@pytest.mark.unit
class TestNotificationPolicyModel:
    """Tests for NotificationPolicy model."""

    def test_create_policy(self):
        """Happy path: create a policy with required fields."""
        from app.models_notification import NotificationPolicy

        p = NotificationPolicy(
            name="Critical → Slack",
            event_type="alert.firing",
            channel_ids=[uuid.uuid4()],
            is_enabled=True,
        )
        assert p.name == "Critical → Slack"
        assert p.event_type == "alert.firing"
        assert p.is_enabled is True

    def test_policy_severity_filter_optional(self):
        """severity_filter defaults to None (match all)."""
        from app.models_notification import NotificationPolicy

        p = NotificationPolicy(
            name="Any Alert",
            event_type="alert.resolved",
            channel_ids=[],
        )
        assert p.severity_filter is None

    def test_policy_defaults(self):
        """Explicit is_enabled=True works; template_key defaults to None."""
        from app.models_notification import NotificationPolicy

        p = NotificationPolicy(
            name="Default",
            event_type="execution.completed",
            channel_ids=[],
            is_enabled=True,
        )
        assert p.is_enabled is True
        assert p.template_key is None


@pytest.mark.unit
class TestNotificationLogModel:
    """Tests for NotificationLog model."""

    def test_create_log_entry(self):
        """Happy path: create a log entry."""
        from app.models_notification import NotificationLog

        entry = NotificationLog(
            channel_id=uuid.uuid4(),
            event_type="alert.firing",
            status="pending",
            attempt_count=0,
        )
        assert entry.status == "pending"
        assert entry.attempt_count == 0
        assert entry.sent_at is None

    def test_log_defaults(self):
        """Column defaults for nullable fields are None before INSERT."""
        from app.models_notification import NotificationLog

        entry = NotificationLog(
            channel_id=uuid.uuid4(),
            event_type="execution.failed",
            status="pending",
        )
        # attempt_count default applied at INSERT time; None until persisted
        assert entry.error_message is None
        assert entry.next_retry_at is None
        # Explicit attempt_count works:
        entry2 = NotificationLog(
            channel_id=uuid.uuid4(),
            event_type="execution.failed",
            status="pending",
            attempt_count=0,
        )
        assert entry2.attempt_count == 0

    def test_log_all_statuses(self):
        """All valid statuses can be set."""
        from app.models_notification import NotificationLog

        for s in ("pending", "sent", "failed", "retrying"):
            entry = NotificationLog(
                channel_id=uuid.uuid4(),
                event_type="test",
                status=s,
            )
            assert entry.status == s
