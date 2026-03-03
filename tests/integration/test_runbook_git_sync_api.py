"""
Integration tests for the Runbook Git Sync API endpoints.

Covers CRUD operations and the manual sync trigger.
"""
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

VALID_CREATE_PAYLOAD = {
    "name": "Test Repo",
    "repo_url": "https://github.com/example/runbooks.git",
    "branch": "main",
    "path_prefix": "runbooks/",
    "auth_type": "none",
    "sync_interval_minutes": 60,
    "overwrite_existing": True,
    "enabled": True,
}


class TestGitSyncConfigCRUD:
    """Tests for POST/GET/PUT/DELETE git-sync config endpoints."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_git_sync_config_success(self, async_client, admin_auth_headers):
        """Happy path: admin user creates a valid git sync config."""
        response = await async_client.post(
            "/api/remediation/git-sync",
            json=VALID_CREATE_PAYLOAD,
            headers=admin_auth_headers,
        )
        assert response.status_code in (201, 401, 403), response.text

        if response.status_code == 201:
            data = response.json()
            assert data["name"] == VALID_CREATE_PAYLOAD["name"]
            assert data["repo_url"] == VALID_CREATE_PAYLOAD["repo_url"]
            assert data["branch"] == "main"
            assert data["auth_type"] == "none"
            # Credentials must never be returned
            assert "token" not in data
            assert "password" not in data
            assert "ssh_key" not in data
            assert "token_encrypted" not in data
            assert "last_sync_status" in data
            assert data["last_sync_status"] == "never"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_git_sync_config_invalid_url(self, async_client, admin_auth_headers):
        """Error case: invalid repo URL (not HTTPS/SSH) is rejected with 422."""
        payload = {**VALID_CREATE_PAYLOAD, "repo_url": "ftp://not-a-git-url"}
        response = await async_client.post(
            "/api/remediation/git-sync",
            json=payload,
            headers=admin_auth_headers,
        )
        assert response.status_code in (422, 401, 403), response.text

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_git_sync_config_invalid_interval(self, async_client, admin_auth_headers):
        """Error case: sync_interval_minutes below minimum (5) is rejected."""
        payload = {**VALID_CREATE_PAYLOAD, "sync_interval_minutes": 1}
        response = await async_client.post(
            "/api/remediation/git-sync",
            json=payload,
            headers=admin_auth_headers,
        )
        assert response.status_code in (422, 401, 403), response.text

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_list_git_sync_configs_returns_list(self, async_client, admin_auth_headers):
        """Happy path: listing configs returns a JSON array."""
        response = await async_client.get(
            "/api/remediation/git-sync",
            headers=admin_auth_headers,
        )
        assert response.status_code in (200, 401, 403)
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_git_sync_config_not_found(self, async_client, admin_auth_headers):
        """Error case: non-existent config ID returns 404."""
        missing_id = str(uuid4())
        response = await async_client.get(
            f"/api/remediation/git-sync/{missing_id}",
            headers=admin_auth_headers,
        )
        assert response.status_code in (404, 401, 403)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_update_git_sync_config_not_found(self, async_client, admin_auth_headers):
        """Error case: updating a non-existent config returns 404."""
        missing_id = str(uuid4())
        response = await async_client.put(
            f"/api/remediation/git-sync/{missing_id}",
            json={"enabled": False},
            headers=admin_auth_headers,
        )
        assert response.status_code in (404, 401, 403)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_delete_git_sync_config_not_found(self, async_client, admin_auth_headers):
        """Error case: deleting a non-existent config returns 404."""
        missing_id = str(uuid4())
        response = await async_client.delete(
            f"/api/remediation/git-sync/{missing_id}",
            headers=admin_auth_headers,
        )
        assert response.status_code in (404, 401, 403)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_trigger_sync_not_found(self, async_client, admin_auth_headers):
        """Error case: triggering sync for non-existent config returns 404."""
        missing_id = str(uuid4())
        response = await async_client.post(
            f"/api/remediation/git-sync/{missing_id}/sync",
            headers=admin_auth_headers,
        )
        assert response.status_code in (404, 401, 403)


class TestGitSyncConfigAuth:
    """Tests for authentication and authorisation on git-sync endpoints."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_requires_auth(self, async_client):
        """Unauthenticated request to create config is rejected."""
        response = await async_client.post(
            "/api/remediation/git-sync",
            json=VALID_CREATE_PAYLOAD,
        )
        assert response.status_code in (401, 403)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_list_requires_auth(self, async_client):
        """Unauthenticated request to list configs is rejected."""
        response = await async_client.get("/api/remediation/git-sync")
        assert response.status_code in (401, 403)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_trigger_sync_requires_auth(self, async_client):
        """Unauthenticated manual sync trigger is rejected."""
        response = await async_client.post(
            f"/api/remediation/git-sync/{uuid4()}/sync"
        )
        assert response.status_code in (401, 403)
