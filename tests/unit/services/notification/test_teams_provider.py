"""
Unit tests for the MS Teams notification provider.
"""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


def _make_message(severity="critical"):
    from app.schemas_notification import NotificationMessage
    return NotificationMessage(
        event_type="execution.failed",
        title="Runbook Failed",
        body="Execution encountered an error.",
        severity=severity,
        metadata={"runbook_name": "Restart Nginx", "approval_url": "http://aiops/exec/1"},
    )


@pytest.mark.unit
@pytest.mark.asyncio
class TestTeamsProvider:
    """Tests for TeamsProvider."""

    async def test_send_success(self):
        """Happy path: successful POST to Teams webhook."""
        from app.services.notification.providers.teams_provider import TeamsProvider

        provider = TeamsProvider()
        config = {"webhook_url": "https://outlook.office.com/webhook/xxx"}
        message = _make_message()

        mock_response = MagicMock()
        mock_response.text = "1"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await provider.send(config, message)

        assert result.success is True

    async def test_send_missing_webhook_url(self):
        """Error case: missing webhook_url returns failed result."""
        from app.services.notification.providers.teams_provider import TeamsProvider

        provider = TeamsProvider()
        result = await provider.send({}, _make_message())
        assert result.success is False
        assert "webhook_url" in result.error

    async def test_send_http_error(self):
        """Error case: HTTP 400 from Teams returns failure."""
        import httpx
        from app.services.notification.providers.teams_provider import TeamsProvider

        provider = TeamsProvider()
        config = {"webhook_url": "https://outlook.office.com/webhook/BAD"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Summary or Text is required"
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError("400", request=MagicMock(), response=mock_response)
            )
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await provider.send(config, _make_message())

        assert result.success is False
        assert "400" in result.error

    async def test_send_timeout(self):
        """Error case: timeout returns failed result."""
        import httpx
        from app.services.notification.providers.teams_provider import TeamsProvider

        provider = TeamsProvider()
        config = {"webhook_url": "https://outlook.office.com/webhook/SLOW"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

            result = await provider.send(config, _make_message())

        assert result.success is False
        assert "timed out" in result.error.lower()

    async def test_validate_config_valid(self):
        """Valid Teams config passes validation."""
        from app.services.notification.providers.teams_provider import TeamsProvider

        provider = TeamsProvider()
        errors = provider.validate_config(
            {"webhook_url": "https://outlook.office.com/webhook/abc/IncomingWebhook/xyz"}
        )
        assert errors == []

    async def test_validate_config_missing_url(self):
        """Missing webhook_url returns an error."""
        from app.services.notification.providers.teams_provider import TeamsProvider

        provider = TeamsProvider()
        errors = provider.validate_config({})
        assert len(errors) == 1

    async def test_adaptive_card_has_facts(self):
        """Adaptive Card includes metadata facts."""
        from app.services.notification.providers.teams_provider import _build_adaptive_card

        msg = _make_message(severity="warning")
        card = _build_adaptive_card(msg)
        assert card["@type"] == "MessageCard"
        facts = card["sections"][0]["facts"]
        assert any(f["name"] == "Severity" for f in facts)
