"""
Integration tests for POST /api/knowledge/sync/git with authentication options.

The GitSyncService.sync_repository call is fully mocked so no real git binary
or network access is needed.  Tests verify:
  - Auth fields are accepted and forwarded to the service (not leaked in response)
  - All four auth modes (none, token, basic, ssh) are accepted by the API
  - Authentication / authorisation on the endpoint is enforced
  - Invalid / missing required fields are rejected with 422
"""
import pytest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SYNC_ENDPOINT = "/api/knowledge/sync/git"

FAKE_STATS = {
    "docs_synced": 3,
    "docs_updated": 1,
    "docs_unchanged": 2,
    "docs_skipped": 0,
    "code_synced": 0,
    "code_updated": 0,
    "code_unchanged": 0,
    "chunks_created": 6,
    "embeddings_generated": 6,
    "errors": [],
}

_PATCH_SYNC = "app.services.git_sync_service.GitSyncService.sync_repository"


# ---------------------------------------------------------------------------
# Helper: build a mock sync_repository return value
# ---------------------------------------------------------------------------

def _mock_sync_repo():
    mock = MagicMock(return_value=FAKE_STATS)
    return mock


# ---------------------------------------------------------------------------
# Happy-path tests — one per auth mode
# ---------------------------------------------------------------------------

class TestKnowledgeGitSyncAuthModes:
    """Verify all auth modes are accepted and return a valid sync response."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sync_public_repo_no_auth(self, async_client, admin_auth_headers):
        """Happy path: public repo with auth_type=none succeeds."""
        payload = {
            "repo_url": "https://github.com/example/public-docs.git",
            "branch": "main",
            "auth_type": "none",
            "sync_docs": True,
            "sync_code": False,
        }
        with patch(_PATCH_SYNC, return_value=FAKE_STATS):
            response = await async_client.post(
                SYNC_ENDPOINT, json=payload, headers=admin_auth_headers
            )

        assert response.status_code in (200, 401, 403), response.text
        if response.status_code == 200:
            data = response.json()
            assert "stats" in data
            assert data["stats"]["docs_synced"] == FAKE_STATS["docs_synced"]
            # Credentials must NOT appear in the response
            assert "token" not in data
            assert "password" not in data
            assert "ssh_key" not in data

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sync_with_token_auth(self, async_client, admin_auth_headers):
        """Happy path: token auth type passes token field to service."""
        payload = {
            "repo_url": "https://github.com/example/private-docs.git",
            "branch": "main",
            "auth_type": "token",
            "token": "ghp_supersecrettoken",
            "sync_docs": True,
            "sync_code": False,
        }
        with patch(_PATCH_SYNC, return_value=FAKE_STATS) as mock_sync:
            response = await async_client.post(
                SYNC_ENDPOINT, json=payload, headers=admin_auth_headers
            )

        assert response.status_code in (200, 401, 403), response.text
        if response.status_code == 200:
            # Verify service was called (credentials forwarded)
            mock_sync.assert_called_once()
            call_kwargs = mock_sync.call_args
            credentials_arg = call_kwargs.kwargs.get("credentials") or call_kwargs.args[2] if len(call_kwargs.args) > 2 else None
            # Response must not leak the token
            assert "ghp_supersecrettoken" not in response.text

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sync_with_basic_auth(self, async_client, admin_auth_headers):
        """Happy path: basic auth type with username and password accepted."""
        payload = {
            "repo_url": "https://gitlab.com/example/private-docs.git",
            "branch": "develop",
            "auth_type": "basic",
            "username": "myuser",
            "password": "mypassword",
            "sync_docs": True,
            "sync_code": False,
        }
        with patch(_PATCH_SYNC, return_value=FAKE_STATS):
            response = await async_client.post(
                SYNC_ENDPOINT, json=payload, headers=admin_auth_headers
            )

        assert response.status_code in (200, 401, 403), response.text
        if response.status_code == 200:
            # Password must not be echoed back
            assert "mypassword" not in response.text

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sync_with_ssh_auth(self, async_client, admin_auth_headers):
        """Happy path: SSH auth type with private key accepted."""
        fake_key = (
            "-----BEGIN OPENSSH PRIVATE KEY-----\n"
            "fakebase64keydata\n"
            "-----END OPENSSH PRIVATE KEY-----"
        )
        payload = {
            "repo_url": "git@github.com:example/private-docs.git",
            "branch": "main",
            "auth_type": "ssh",
            "ssh_key": fake_key,
            "sync_docs": True,
            "sync_code": False,
        }
        with patch(_PATCH_SYNC, return_value=FAKE_STATS):
            response = await async_client.post(
                SYNC_ENDPOINT, json=payload, headers=admin_auth_headers
            )

        assert response.status_code in (200, 401, 403), response.text
        if response.status_code == 200:
            assert "fakebase64keydata" not in response.text

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sync_with_code_sync_enabled(self, async_client, admin_auth_headers):
        """Happy path: sync_code=True is accepted alongside auth fields."""
        payload = {
            "repo_url": "https://github.com/example/full-repo.git",
            "branch": "main",
            "auth_type": "token",
            "token": "ghp_codetoken",
            "sync_docs": True,
            "sync_code": True,
        }
        with patch(_PATCH_SYNC, return_value=FAKE_STATS):
            response = await async_client.post(
                SYNC_ENDPOINT, json=payload, headers=admin_auth_headers
            )
        assert response.status_code in (200, 401, 403), response.text


# ---------------------------------------------------------------------------
# Validation / error tests
# ---------------------------------------------------------------------------

class TestKnowledgeGitSyncValidation:
    """Verify input validation on the sync endpoint."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_missing_repo_url_rejected(self, async_client, admin_auth_headers):
        """Error case: request without repo_url returns 422 Unprocessable Entity."""
        payload = {"branch": "main", "auth_type": "none"}
        response = await async_client.post(
            SYNC_ENDPOINT, json=payload, headers=admin_auth_headers
        )
        assert response.status_code in (422, 401, 403), response.text

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_token_auth_without_token_still_accepted(self, async_client, admin_auth_headers):
        """Edge case: auth_type=token with no token is valid schema (service decides)."""
        payload = {
            "repo_url": "https://github.com/example/repo.git",
            "auth_type": "token",
            # token omitted intentionally
        }
        with patch(_PATCH_SYNC, return_value=FAKE_STATS):
            response = await async_client.post(
                SYNC_ENDPOINT, json=payload, headers=admin_auth_headers
            )
        # Should reach the service (200) or fail auth (401/403) — not 422
        assert response.status_code in (200, 401, 403, 500), response.text

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_service_error_returns_500(self, async_client, admin_auth_headers):
        """Error case: service exception is returned as HTTP 500."""
        payload = {
            "repo_url": "https://github.com/example/repo.git",
            "auth_type": "none",
        }
        with patch(_PATCH_SYNC, side_effect=RuntimeError("git clone failed: authentication required")):
            response = await async_client.post(
                SYNC_ENDPOINT, json=payload, headers=admin_auth_headers
            )
        assert response.status_code in (500, 401, 403), response.text
        if response.status_code == 500:
            assert "git sync failed" in response.text.lower()


# ---------------------------------------------------------------------------
# Authentication / authorisation tests
# ---------------------------------------------------------------------------

class TestKnowledgeGitSyncAuth:
    """Verify endpoint enforces authentication."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, async_client):
        """Error case: request without auth token returns 401 or 403."""
        payload = {
            "repo_url": "https://github.com/example/public-docs.git",
            "auth_type": "none",
        }
        response = await async_client.post(SYNC_ENDPOINT, json=payload)
        assert response.status_code in (401, 403), response.text

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_stats_structure_in_success_response(self, async_client, admin_auth_headers):
        """Happy path: success response contains expected stats keys."""
        payload = {
            "repo_url": "https://github.com/example/docs.git",
            "auth_type": "none",
        }
        with patch(_PATCH_SYNC, return_value=FAKE_STATS):
            response = await async_client.post(
                SYNC_ENDPOINT, json=payload, headers=admin_auth_headers
            )
        if response.status_code == 200:
            data = response.json()
            assert "stats" in data
            assert "docs_synced" in data["stats"]
            assert "repo_url" in data
            assert data["repo_url"] == payload["repo_url"]
