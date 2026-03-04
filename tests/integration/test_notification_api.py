"""
Integration tests for the Notification API endpoints.

Tests CRUD for channels and policies, the test-send endpoint, and the
delivery log. Uses async_client and admin_auth_headers fixtures from conftest.
"""
import pytest


@pytest.mark.integration
class TestNotificationChannelsAPI:
    """Tests for /api/notifications/channels endpoints."""

    @pytest.mark.asyncio
    async def test_list_channels_requires_auth(self, async_client):
        """GET /api/notifications/channels returns 401 without auth."""
        response = await async_client.get("/api/notifications/channels")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_list_channels_authenticated(self, async_client, admin_auth_headers):
        """Authenticated user can list channels (may be empty)."""
        response = await async_client.get(
            "/api/notifications/channels",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_create_channel_slack(self, async_client, admin_auth_headers):
        """Admin can create a Slack channel."""
        payload = {
            "name": "Test Slack Channel",
            "channel_type": "slack",
            "config_json": {"webhook_url": "https://hooks.slack.com/services/T/B/X"},
            "is_enabled": True,
        }
        response = await async_client.post(
            "/api/notifications/channels",
            json=payload,
            headers=admin_auth_headers,
        )
        assert response.status_code in (200, 201)
        data = response.json()
        assert data["name"] == "Test Slack Channel"
        assert data["channel_type"] == "slack"

    @pytest.mark.asyncio
    async def test_create_channel_invalid_type(self, async_client, admin_auth_headers):
        """Invalid channel_type returns 422."""
        payload = {
            "name": "Bad Channel",
            "channel_type": "sms",
            "config_json": {},
        }
        response = await async_client.post(
            "/api/notifications/channels",
            json=payload,
            headers=admin_auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_channel_not_found(self, async_client, admin_auth_headers):
        """GET a non-existent channel returns 404."""
        import uuid
        response = await async_client.get(
            f"/api/notifications/channels/{uuid.uuid4()}",
            headers=admin_auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_update_delete_channel(self, async_client, admin_auth_headers):
        """Full lifecycle: create → update → delete a channel."""
        # Create
        payload = {
            "name": "Lifecycle Webhook",
            "channel_type": "webhook",
            "config_json": {"url": "https://example.com/hook"},
        }
        create_resp = await async_client.post(
            "/api/notifications/channels",
            json=payload,
            headers=admin_auth_headers,
        )
        assert create_resp.status_code in (200, 201)
        channel_id = create_resp.json()["id"]

        # Update
        update_resp = await async_client.put(
            f"/api/notifications/channels/{channel_id}",
            json={"name": "Updated Webhook"},
            headers=admin_auth_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "Updated Webhook"

        # Delete
        del_resp = await async_client.delete(
            f"/api/notifications/channels/{channel_id}",
            headers=admin_auth_headers,
        )
        assert del_resp.status_code in (200, 204)

        # Verify gone
        get_resp = await async_client.get(
            f"/api/notifications/channels/{channel_id}",
            headers=admin_auth_headers,
        )
        assert get_resp.status_code == 404


@pytest.mark.integration
class TestNotificationPoliciesAPI:
    """Tests for /api/notifications/policies endpoints."""

    @pytest.mark.asyncio
    async def test_list_policies_requires_auth(self, async_client):
        """Listing policies requires authentication."""
        response = await async_client.get("/api/notifications/policies")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_create_and_list_policy(self, async_client, admin_auth_headers):
        """Admin can create a policy and it appears in list."""
        import uuid

        # First create a channel to reference
        ch_payload = {
            "name": "Policy Test Slack",
            "channel_type": "slack",
            "config_json": {"webhook_url": "https://hooks.slack.com/services/T/B/Z"},
        }
        ch_resp = await async_client.post(
            "/api/notifications/channels",
            json=ch_payload,
            headers=admin_auth_headers,
        )
        assert ch_resp.status_code in (200, 201)
        channel_id = ch_resp.json()["id"]

        # Create policy
        policy_payload = {
            "name": "Critical → Test Slack",
            "event_type": "alert.firing",
            "severity_filter": ["critical"],
            "channel_ids": [channel_id],
            "is_enabled": True,
        }
        p_resp = await async_client.post(
            "/api/notifications/policies",
            json=policy_payload,
            headers=admin_auth_headers,
        )
        assert p_resp.status_code in (200, 201)
        data = p_resp.json()
        assert data["event_type"] == "alert.firing"
        assert channel_id in data["channel_ids"]

    @pytest.mark.asyncio
    async def test_delete_policy(self, async_client, admin_auth_headers):
        """Admin can delete a policy."""
        import uuid

        # Create a temp channel
        ch_resp = await async_client.post(
            "/api/notifications/channels",
            json={"name": "Temp", "channel_type": "webhook", "config_json": {"url": "https://example.com"}},
            headers=admin_auth_headers,
        )
        channel_id = ch_resp.json()["id"]

        # Create policy
        p_resp = await async_client.post(
            "/api/notifications/policies",
            json={"name": "Temp policy", "event_type": "alert.resolved", "channel_ids": [channel_id]},
            headers=admin_auth_headers,
        )
        policy_id = p_resp.json()["id"]

        # Delete it
        del_resp = await async_client.delete(
            f"/api/notifications/policies/{policy_id}",
            headers=admin_auth_headers,
        )
        assert del_resp.status_code in (200, 204)


@pytest.mark.integration
class TestNotificationLogAPI:
    """Tests for /api/notifications/log endpoints."""

    @pytest.mark.asyncio
    async def test_log_requires_auth(self, async_client):
        """Log endpoint requires authentication."""
        response = await async_client.get("/api/notifications/log")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_log_list_authenticated(self, async_client, admin_auth_headers):
        """Authenticated user can query log."""
        response = await async_client.get(
            "/api/notifications/log",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    @pytest.mark.asyncio
    async def test_log_stats(self, async_client, admin_auth_headers):
        """Log stats endpoint returns correct shape."""
        response = await async_client.get(
            "/api/notifications/log/stats",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "sent" in data
        assert "failed" in data
        assert "success_rate" in data

    @pytest.mark.asyncio
    async def test_log_filter_by_event_type(self, async_client, admin_auth_headers):
        """Log can be filtered by event_type query param."""
        response = await async_client.get(
            "/api/notifications/log?event_type=alert.firing",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_log_filter_by_status(self, async_client, admin_auth_headers):
        """Log can be filtered by status query param."""
        response = await async_client.get(
            "/api/notifications/log?status=sent",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    @pytest.mark.asyncio
    async def test_log_filter_by_channel_id(self, async_client, admin_auth_headers):
        """Log can be filtered by channel_id query param (even non-existent)."""
        import uuid

        response = await async_client.get(
            f"/api/notifications/log?channel_id={uuid.uuid4()}",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 0


@pytest.mark.integration
class TestNotificationChannelTestSend:
    """Tests for POST /api/notifications/channels/{id}/test endpoint."""

    @pytest.mark.asyncio
    async def test_test_send_requires_auth(self, async_client):
        """Test-send endpoint requires authentication."""
        import uuid

        response = await async_client.post(
            f"/api/notifications/channels/{uuid.uuid4()}/test",
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_test_send_not_found(self, async_client, admin_auth_headers):
        """Test-send for non-existent channel returns 404."""
        import uuid

        response = await async_client.post(
            f"/api/notifications/channels/{uuid.uuid4()}/test",
            headers=admin_auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_test_send_channel(self, async_client, admin_auth_headers):
        """Test-send on existing channel returns a result (may fail since webhook is fake)."""
        # Create a channel first
        payload = {
            "name": "Test-Send Channel",
            "channel_type": "webhook",
            "config_json": {"url": "https://example.com/hook"},
        }
        create_resp = await async_client.post(
            "/api/notifications/channels",
            json=payload,
            headers=admin_auth_headers,
        )
        channel_id = create_resp.json()["id"]

        response = await async_client.post(
            f"/api/notifications/channels/{channel_id}/test",
            headers=admin_auth_headers,
        )
        # Endpoint should respond (success or delivery failure — not a 500)
        assert response.status_code in (200, 400, 502)

    @pytest.mark.asyncio
    async def test_test_send_get_returns_405(self, async_client, admin_auth_headers):
        """GET on the test endpoint returns 405 — only POST is allowed.

        This guards against the frontend accidentally using GET instead of POST.
        """
        import uuid

        response = await async_client.get(
            f"/api/notifications/channels/{uuid.uuid4()}/test",
            headers=admin_auth_headers,
        )
        assert response.status_code == 405


@pytest.mark.integration
class TestNotificationPolicyUpdate:
    """Tests for PUT /api/notifications/policies/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_policy(self, async_client, admin_auth_headers):
        """Admin can update a policy name and severity."""
        # Setup: create channel + policy
        ch_resp = await async_client.post(
            "/api/notifications/channels",
            json={
                "name": "Update-Test Slack",
                "channel_type": "slack",
                "config_json": {"webhook_url": "https://hooks.slack.com/services/T/B/U"},
            },
            headers=admin_auth_headers,
        )
        channel_id = ch_resp.json()["id"]

        p_resp = await async_client.post(
            "/api/notifications/policies",
            json={
                "name": "Original Name",
                "event_type": "alert.firing",
                "channel_ids": [channel_id],
            },
            headers=admin_auth_headers,
        )
        policy_id = p_resp.json()["id"]

        # Update
        update_resp = await async_client.put(
            f"/api/notifications/policies/{policy_id}",
            json={
                "name": "Renamed Policy",
                "severity_filter": ["critical", "warning"],
            },
            headers=admin_auth_headers,
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["name"] == "Renamed Policy"

    @pytest.mark.asyncio
    async def test_update_policy_not_found(self, async_client, admin_auth_headers):
        """Updating a non-existent policy returns 404."""
        import uuid

        response = await async_client.put(
            f"/api/notifications/policies/{uuid.uuid4()}",
            json={"name": "Ghost"},
            headers=admin_auth_headers,
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestNotificationAdditionalChannelTypes:
    """Tests for creating email and MS Teams channels."""

    @pytest.mark.asyncio
    async def test_create_email_channel(self, async_client, admin_auth_headers):
        """Admin can create an email channel."""
        payload = {
            "name": "Test Email Channel",
            "channel_type": "email",
            "config_json": {
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "from_address": "ops@example.com",
                "to_addresses": ["team@example.com"],
            },
            "is_enabled": True,
        }
        response = await async_client.post(
            "/api/notifications/channels",
            json=payload,
            headers=admin_auth_headers,
        )
        assert response.status_code in (200, 201)
        assert response.json()["channel_type"] == "email"

    @pytest.mark.asyncio
    async def test_create_msteams_channel(self, async_client, admin_auth_headers):
        """Admin can create an MS Teams channel."""
        payload = {
            "name": "Test Teams Channel",
            "channel_type": "msteams",
            "config_json": {
                "webhook_url": "https://outlook.office.com/webhook/xxx",
            },
            "is_enabled": True,
        }
        response = await async_client.post(
            "/api/notifications/channels",
            json=payload,
            headers=admin_auth_headers,
        )
        assert response.status_code in (200, 201)
        assert response.json()["channel_type"] == "msteams"

    @pytest.mark.asyncio
    async def test_create_channel_missing_name(self, async_client, admin_auth_headers):
        """Channel creation requires a name — returns 422 when missing."""
        payload = {
            "channel_type": "slack",
            "config_json": {"webhook_url": "https://hooks.slack.com/services/T/B/X"},
        }
        response = await async_client.post(
            "/api/notifications/channels",
            json=payload,
            headers=admin_auth_headers,
        )
        assert response.status_code == 422
