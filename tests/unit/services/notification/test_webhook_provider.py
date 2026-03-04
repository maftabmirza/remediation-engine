"""
Unit tests for the generic Webhook notification provider.
"""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


def _make_message():
    from app.schemas_notification import NotificationMessage
    return NotificationMessage(
        event_type="execution.completed",
        title="Execution Done",
        body="Runbook completed successfully.",
        severity="info",
        metadata={"execution_id": "abc-123", "runbook_name": "Disk Cleanup"},
    )


@pytest.mark.unit
@pytest.mark.asyncio
class TestWebhookProvider:
    """Tests for WebhookProvider."""

    async def test_send_success_post(self):
        """Happy path: successful POST to webhook."""
        from app.services.notification.providers.webhook_provider import WebhookProvider

        provider = WebhookProvider()
        config = {"url": "https://api.pagerduty.com/hook", "method": "POST"}

        mock_response = MagicMock()
        mock_response.text = '{"result": "ok"}'
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(return_value=mock_response)

            result = await provider.send(config, _make_message())

        assert result.success is True
        assert result.recipient == "https://api.pagerduty.com/hook"

    async def test_send_missing_url(self):
        """Error case: missing url returns failure."""
        from app.services.notification.providers.webhook_provider import WebhookProvider

        provider = WebhookProvider()
        result = await provider.send({}, _make_message())
        assert result.success is False
        assert "url" in result.error

    async def test_send_http_error(self):
        """Error case: non-2xx response returns failure."""
        import httpx
        from app.services.notification.providers.webhook_provider import WebhookProvider

        provider = WebhookProvider()
        config = {"url": "https://api.example.com/hook"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response)
            )
            mock_client.request = AsyncMock(return_value=mock_response)

            result = await provider.send(config, _make_message())

        assert result.success is False
        assert "401" in result.error

    async def test_send_timeout(self):
        """Error case: timeout returns failure."""
        import httpx
        from app.services.notification.providers.webhook_provider import WebhookProvider

        provider = WebhookProvider()
        config = {"url": "https://slow.example.com/hook"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

            result = await provider.send(config, _make_message())

        assert result.success is False
        assert "timed out" in result.error.lower()

    async def test_validate_config_valid(self):
        """Valid webhook config passes validation."""
        from app.services.notification.providers.webhook_provider import WebhookProvider

        provider = WebhookProvider()
        errors = provider.validate_config({
            "url": "https://api.example.com/hook",
            "method": "POST",
            "headers": {"Authorization": "Token abc"},
        })
        assert errors == []

    async def test_validate_config_missing_url(self):
        """Missing url returns validation error."""
        from app.services.notification.providers.webhook_provider import WebhookProvider

        provider = WebhookProvider()
        errors = provider.validate_config({})
        assert any("url" in e for e in errors)

    async def test_validate_config_bad_method(self):
        """Invalid HTTP method returns validation error."""
        from app.services.notification.providers.webhook_provider import WebhookProvider

        provider = WebhookProvider()
        errors = provider.validate_config({"url": "https://example.com", "method": "SEND"})
        assert any("method" in e.lower() for e in errors)

    async def test_template_rendering(self):
        """Custom template has placeholders substituted."""
        from app.services.notification.providers.webhook_provider import _render_template, _default_payload

        msg = _make_message()
        template = {"event": "{{ event_type }}", "name": "{{ runbook_name }}"}
        result = _render_template(template, msg)
        assert result["event"] == "execution.completed"
        assert result["name"] == "Disk Cleanup"
