"""
Unit tests for the Slack notification provider.
"""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


def _make_message(event_type="alert.firing", title="Test Alert", body="Test body", severity="critical"):
    from app.schemas_notification import NotificationMessage
    return NotificationMessage(
        event_type=event_type,
        title=title,
        body=body,
        severity=severity,
        metadata={"source": "prometheus", "alert_url": "http://aiops/alerts/1"},
    )


@pytest.mark.unit
@pytest.mark.asyncio
class TestSlackProvider:
    """Tests for SlackProvider."""

    async def test_send_success(self):
        """Happy path: successful POST to Slack webhook."""
        from app.services.notification.providers.slack_provider import SlackProvider

        provider = SlackProvider()
        config = {"webhook_url": "https://hooks.slack.com/services/TEST", "channel": "#ops"}
        message = _make_message()

        mock_response = MagicMock()
        mock_response.text = "ok"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await provider.send(config, message)

        assert result.success is True
        assert result.recipient == "#ops"

    async def test_send_missing_webhook_url(self):
        """Error case: missing webhook_url returns failed result."""
        from app.services.notification.providers.slack_provider import SlackProvider

        provider = SlackProvider()
        result = await provider.send({}, _make_message())
        assert result.success is False
        assert "webhook_url" in result.error

    async def test_send_http_error(self):
        """Error case: non-2xx HTTP response returns failed result."""
        import httpx
        from app.services.notification.providers.slack_provider import SlackProvider

        provider = SlackProvider()
        config = {"webhook_url": "https://hooks.slack.com/services/BAD"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.text = "invalid_token"
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError("403", request=MagicMock(), response=mock_response)
            )
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await provider.send(config, _make_message())

        assert result.success is False
        assert "403" in result.error

    async def test_send_timeout(self):
        """Error case: timeout returns failed result."""
        import httpx
        from app.services.notification.providers.slack_provider import SlackProvider

        provider = SlackProvider()
        config = {"webhook_url": "https://hooks.slack.com/services/SLOW"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

            result = await provider.send(config, _make_message())

        assert result.success is False
        assert "timed out" in result.error.lower()

    async def test_validate_config_valid(self):
        """Valid Slack config returns no errors."""
        from app.services.notification.providers.slack_provider import SlackProvider

        provider = SlackProvider()
        errors = provider.validate_config({"webhook_url": "https://hooks.slack.com/services/T/B/X"})
        assert errors == []

    async def test_validate_config_missing_url(self):
        """Missing webhook_url returns an error."""
        from app.services.notification.providers.slack_provider import SlackProvider

        provider = SlackProvider()
        errors = provider.validate_config({})
        assert len(errors) == 1
        assert "webhook_url" in errors[0]

    async def test_validate_config_bad_url(self):
        """Non-Slack URL returns a validation error."""
        from app.services.notification.providers.slack_provider import SlackProvider

        provider = SlackProvider()
        errors = provider.validate_config({"webhook_url": "https://example.com/hook"})
        assert len(errors) == 1
