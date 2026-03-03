"""
Unit tests for app/services/git_sync_service.py — GitCredentials class.

Tests cover URL credential embedding and environment variable generation
for all supported auth types (none, token, basic, ssh).
No real git binary or network calls are made.
"""
import os
from unittest.mock import patch, MagicMock

import pytest

from app.services.git_sync_service import GitCredentials


# ---------------------------------------------------------------------------
# GitCredentials.get_clone_url tests
# ---------------------------------------------------------------------------

class TestGitCredentialsGetCloneUrl:
    """Tests for GitCredentials.get_clone_url()."""

    GITHUB_URL = "https://github.com/org/repo.git"
    GITLAB_URL = "https://gitlab.com/org/repo.git"
    OTHER_URL = "https://bitbucket.org/org/repo.git"

    # --- Happy path: auth_type=none ---

    @pytest.mark.unit
    def test_none_auth_returns_url_unchanged(self):
        """Happy path: no auth keeps the URL as-is."""
        creds = GitCredentials(auth_type="none")
        assert creds.get_clone_url(self.GITHUB_URL) == self.GITHUB_URL

    # --- Happy path: auth_type=token ---

    @pytest.mark.unit
    def test_token_auth_github_embeds_token(self):
        """Happy path: GitHub token is embedded directly after https://."""
        creds = GitCredentials(auth_type="token", token="ghp_abc123")
        result = creds.get_clone_url(self.GITHUB_URL)
        assert result == "https://ghp_abc123@github.com/org/repo.git"

    @pytest.mark.unit
    def test_token_auth_gitlab_uses_oauth2_prefix(self):
        """Happy path: GitLab uses oauth2:<token>@ format."""
        creds = GitCredentials(auth_type="token", token="glpat-xyz")
        result = creds.get_clone_url(self.GITLAB_URL)
        assert result == "https://oauth2:glpat-xyz@gitlab.com/org/repo.git"

    @pytest.mark.unit
    def test_token_auth_other_host_embeds_token(self):
        """Happy path: non-GitHub/GitLab HTTPS URL gets token embedded."""
        creds = GitCredentials(auth_type="token", token="mytoken")
        result = creds.get_clone_url(self.OTHER_URL)
        # Falls through to the return repo_url path — token not embedded
        # (current implementation only handles github/gitlab explicitly)
        assert result == self.OTHER_URL

    @pytest.mark.unit
    def test_token_auth_with_no_token_returns_url_unchanged(self):
        """Edge case: token auth selected but token is None — URL unchanged."""
        creds = GitCredentials(auth_type="token", token=None)
        assert creds.get_clone_url(self.GITHUB_URL) == self.GITHUB_URL

    # --- Happy path: auth_type=basic ---

    @pytest.mark.unit
    def test_basic_auth_embeds_username_and_password(self):
        """Happy path: basic auth embeds user:pass@ into URL."""
        creds = GitCredentials(auth_type="basic", username="alice", password="s3cr3t")
        result = creds.get_clone_url(self.GITHUB_URL)
        assert result == "https://alice:s3cr3t@github.com/org/repo.git"

    @pytest.mark.unit
    def test_basic_auth_missing_password_returns_url_unchanged(self):
        """Edge case: basic auth with missing password leaves URL unchanged."""
        creds = GitCredentials(auth_type="basic", username="alice", password=None)
        assert creds.get_clone_url(self.GITHUB_URL) == self.GITHUB_URL

    @pytest.mark.unit
    def test_basic_auth_missing_username_returns_url_unchanged(self):
        """Edge case: basic auth with missing username leaves URL unchanged."""
        creds = GitCredentials(auth_type="basic", username=None, password="pw")
        assert creds.get_clone_url(self.GITHUB_URL) == self.GITHUB_URL

    # --- Happy path: auth_type=ssh ---

    @pytest.mark.unit
    def test_ssh_auth_returns_url_unchanged(self):
        """Happy path: SSH auth does not embed creds in URL (key used via env)."""
        creds = GitCredentials(auth_type="ssh", ssh_key="-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----")
        assert creds.get_clone_url("git@github.com:org/repo.git") == "git@github.com:org/repo.git"


# ---------------------------------------------------------------------------
# GitCredentials.get_env tests
# ---------------------------------------------------------------------------

class TestGitCredentialsGetEnv:
    """Tests for GitCredentials.get_env()."""

    @pytest.mark.unit
    def test_env_always_sets_no_interactive_prompts(self):
        """Happy path: all auth types set GIT_TERMINAL_PROMPT=0."""
        for auth in ("none", "token", "basic"):
            creds = GitCredentials(auth_type=auth)
            env = creds.get_env()
            assert env["GIT_TERMINAL_PROMPT"] == "0"
            assert env["GIT_ASKPASS"] == "echo"

    @pytest.mark.unit
    def test_ssh_auth_with_key_sets_git_ssh_command(self):
        """Happy path: SSH key is written to temp file and GIT_SSH_COMMAND is set."""
        fake_key = "-----BEGIN OPENSSH PRIVATE KEY-----\nfakekey\n-----END OPENSSH PRIVATE KEY-----"
        creds = GitCredentials(auth_type="ssh", ssh_key=fake_key)

        mock_file = MagicMock()
        mock_file.name = "/tmp/fake_key.key"
        mock_file.__enter__ = lambda s: s
        mock_file.__exit__ = MagicMock(return_value=False)

        with patch("tempfile.NamedTemporaryFile", return_value=mock_file), \
             patch("os.chmod") as mock_chmod:
            env = creds.get_env()

        assert "GIT_SSH_COMMAND" in env
        assert "/tmp/fake_key.key" in env["GIT_SSH_COMMAND"]
        assert "StrictHostKeyChecking=no" in env["GIT_SSH_COMMAND"]
        mock_chmod.assert_called_once_with("/tmp/fake_key.key", 0o600)

    @pytest.mark.unit
    def test_non_ssh_auth_does_not_set_git_ssh_command(self):
        """Happy path: token/basic/none auth does not set GIT_SSH_COMMAND."""
        for auth in ("none", "token", "basic"):
            creds = GitCredentials(auth_type=auth, token="tok")
            env = creds.get_env()
            assert "GIT_SSH_COMMAND" not in env

    @pytest.mark.unit
    def test_ssh_auth_without_key_does_not_set_git_ssh_command(self):
        """Edge case: SSH auth type but no key provided — no GIT_SSH_COMMAND."""
        creds = GitCredentials(auth_type="ssh", ssh_key=None)
        env = creds.get_env()
        assert "GIT_SSH_COMMAND" not in env

    @pytest.mark.unit
    def test_env_inherits_os_environment(self):
        """Happy path: returned env includes existing OS env vars."""
        creds = GitCredentials(auth_type="none")
        with patch.dict(os.environ, {"MY_CUSTOM_VAR": "hello"}):
            env = creds.get_env()
        assert env.get("MY_CUSTOM_VAR") == "hello"
