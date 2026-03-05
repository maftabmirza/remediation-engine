"""
Unit tests for the Email notification provider.
"""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


def _make_message():
    from app.schemas_notification import NotificationMessage
    return NotificationMessage(
        event_type="alert.firing",
        title="High CPU Alert",
        body="CPU usage is above 90%.",
        severity="critical",
        metadata={"source": "prometheus", "host": "web-01"},
    )


def _email_config(**overrides):
    cfg = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_user": "alerts@example.com",
        "smtp_password": "password123",
        "from_address": "alerts@example.com",
        "to_addresses": ["oncall@example.com", "team@example.com"],
    }
    cfg.update(overrides)
    return cfg


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmailProvider:
    """Tests for EmailProvider."""

    async def test_send_success(self):
        """Happy path: successful email send via aiosmtplib."""
        from app.services.notification.providers.email_provider import EmailProvider

        provider = EmailProvider()

        with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            result = await provider.send(_email_config(), _make_message())

        assert result.success is True
        assert "oncall@example.com" in result.recipient
        mock_send.assert_awaited_once()

    async def test_send_missing_smtp_host(self):
        """Error case: missing smtp_host returns failure."""
        from app.services.notification.providers.email_provider import EmailProvider

        provider = EmailProvider()
        cfg = _email_config()
        del cfg["smtp_host"]
        result = await provider.send(cfg, _make_message())
        assert result.success is False
        assert "smtp_host" in result.error

    async def test_send_no_recipients(self):
        """Error case: empty to_addresses returns failure."""
        from app.services.notification.providers.email_provider import EmailProvider

        provider = EmailProvider()
        result = await provider.send(_email_config(to_addresses=[]), _make_message())
        assert result.success is False
        assert "to_addresses" in result.error

    async def test_send_smtp_error(self):
        """Error case: SMTP exception returns failure."""
        from app.services.notification.providers.email_provider import EmailProvider

        provider = EmailProvider()

        with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = Exception("Connection refused")
            result = await provider.send(_email_config(), _make_message())

        assert result.success is False
        assert "Connection refused" in result.error

    async def test_validate_config_valid(self):
        """Valid email config passes validation."""
        from app.services.notification.providers.email_provider import EmailProvider

        provider = EmailProvider()
        errors = provider.validate_config(_email_config())
        assert errors == []

    async def test_validate_config_missing_fields(self):
        """Missing required fields return errors."""
        from app.services.notification.providers.email_provider import EmailProvider

        provider = EmailProvider()
        errors = provider.validate_config({})
        assert any("smtp_host" in e for e in errors)
        assert any("from_address" in e for e in errors)
        assert any("to_addresses" in e for e in errors)

    async def test_html_body_contains_title(self):
        """HTML body contains the message title."""
        from app.services.notification.providers.email_provider import _build_html_body

        msg = _make_message()
        html = _build_html_body(msg)
        assert "High CPU Alert" in html
        assert "prometheus" in html
