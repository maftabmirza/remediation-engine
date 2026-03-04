"""
Unit tests for notification Pydantic schemas.
"""
import uuid

import pytest
from pydantic import ValidationError


@pytest.mark.unit
class TestNotificationChannelSchemas:
    """Tests for NotificationChannel create/response schemas."""

    def test_create_slack_channel_valid(self):
        """Happy path: valid Slack channel creation schema."""
        from app.schemas_notification import NotificationChannelCreate

        ch = NotificationChannelCreate(
            name="Ops Slack",
            channel_type="slack",
            config_json={"webhook_url": "https://hooks.slack.com/services/xxx"},
            is_enabled=True,
        )
        assert ch.channel_type == "slack"
        assert ch.is_enabled is True

    def test_create_channel_invalid_type(self):
        """Invalid channel_type raises ValidationError."""
        from app.schemas_notification import NotificationChannelCreate

        with pytest.raises(ValidationError) as exc_info:
            NotificationChannelCreate(
                name="Bad",
                channel_type="sms",  # not valid
                config_json={},
            )
        assert "channel_type" in str(exc_info.value)

    def test_create_channel_default_enabled(self):
        """is_enabled defaults to True."""
        from app.schemas_notification import NotificationChannelCreate

        ch = NotificationChannelCreate(
            name="Webhook",
            channel_type="webhook",
            config_json={"url": "https://example.com"},
        )
        assert ch.is_enabled is True

    def test_update_channel_partial(self):
        """Update schema accepts partial fields."""
        from app.schemas_notification import NotificationChannelUpdate

        update = NotificationChannelUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.channel_type is None
        assert update.is_enabled is None

    def test_update_channel_invalid_type(self):
        """Invalid type in update raises ValidationError."""
        from app.schemas_notification import NotificationChannelUpdate

        with pytest.raises(ValidationError):
            NotificationChannelUpdate(channel_type="fax")

    def test_all_valid_channel_types(self):
        """All four channel types pass validation."""
        from app.schemas_notification import NotificationChannelCreate

        for ct in ("slack", "msteams", "email", "webhook"):
            ch = NotificationChannelCreate(name=f"ch-{ct}", channel_type=ct, config_json={})
            assert ch.channel_type == ct


@pytest.mark.unit
class TestNotificationPolicySchemas:
    """Tests for NotificationPolicy schemas."""

    def test_create_policy_valid(self):
        """Happy path: valid policy creation."""
        from app.schemas_notification import NotificationPolicyCreate

        p = NotificationPolicyCreate(
            name="Critical → Slack",
            event_type="alert.firing",
            severity_filter=["critical", "warning"],
            channel_ids=[uuid.uuid4()],
        )
        assert p.event_type == "alert.firing"
        assert "critical" in p.severity_filter

    def test_create_policy_no_severity_filter(self):
        """severity_filter is optional (None = all severities)."""
        from app.schemas_notification import NotificationPolicyCreate

        p = NotificationPolicyCreate(
            name="All events",
            event_type="execution.completed",
            channel_ids=[],
        )
        assert p.severity_filter is None

    def test_create_policy_empty_channel_ids(self):
        """channel_ids can be empty list."""
        from app.schemas_notification import NotificationPolicyCreate

        p = NotificationPolicyCreate(
            name="Empty",
            event_type="alert.resolved",
            channel_ids=[],
        )
        assert p.channel_ids == []

    def test_update_policy_partial(self):
        """Update schema is fully optional."""
        from app.schemas_notification import NotificationPolicyUpdate

        u = NotificationPolicyUpdate(is_enabled=False)
        assert u.is_enabled is False
        assert u.name is None


@pytest.mark.unit
class TestMessageSchemas:
    """Tests for NotificationMessage and ProviderResult schemas."""

    def test_notification_message_required_fields(self):
        """NotificationMessage requires event_type, title, body."""
        from app.schemas_notification import NotificationMessage

        msg = NotificationMessage(
            event_type="alert.firing",
            title="Alert!",
            body="Something went wrong.",
        )
        assert msg.event_type == "alert.firing"
        assert msg.metadata == {}

    def test_provider_result_success(self):
        """ProviderResult captures success correctly."""
        from app.schemas_notification import ProviderResult

        r = ProviderResult(success=True, recipient="#ops-alerts")
        assert r.success is True
        assert r.error is None

    def test_provider_result_failure(self):
        """ProviderResult captures failure correctly."""
        from app.schemas_notification import ProviderResult

        r = ProviderResult(success=False, error="Connection refused")
        assert r.success is False
        assert r.error == "Connection refused"
