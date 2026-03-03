"""
Unit tests for runbook_git_sync_service.py.

Git subprocess calls are fully mocked so no real network or git binary is needed.
All SQLAlchemy model modules are imported upfront so mapper relationships resolve.
"""
import hashlib
import os
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

# Import ALL model modules so SQLAlchemy can configure cross-model relationships
# (e.g. ScheduledJob → ServerCredential) before any mapper is accessed.
import app.models  # noqa: F401
import app.models_agent  # noqa: F401
import app.models_agent_pool  # noqa: F401
import app.models_ai  # noqa: F401
import app.models_application  # noqa: F401
import app.models_application_knowledge  # noqa: F401
import app.models_changeset  # noqa: F401
import app.models_dashboards  # noqa: F401
import app.models_group  # noqa: F401
import app.models_iteration  # noqa: F401
import app.models_itsm  # noqa: F401
import app.models_knowledge  # noqa: F401
import app.models_learning  # noqa: F401
import app.models_remediation  # noqa: F401
import app.models_revive  # noqa: F401
import app.models_runbook_acl  # noqa: F401
import app.models_scheduler  # noqa: F401
import app.models_troubleshooting  # noqa: F401
import app.models_zombies  # noqa: F401

from sqlalchemy.orm import configure_mappers
configure_mappers()

from app.services.runbook_git_sync_service import (
    _build_git_env,
    _build_clone_url,
    import_runbook_from_dict,
    sync_git_config,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_fake_path(path_str: str = "/tmp/fake_repo", *, files=None):
    """Return a MagicMock that behaves like pathlib.Path for sync tests."""
    if files is None:
        files = []
    p = MagicMock(spec=Path)
    p.__truediv__ = lambda self, other: _make_fake_path(f"{path_str}/{other}", files=files)
    p.is_dir.return_value = True
    p.rglob.return_value = iter(files)
    p.__str__ = lambda self: path_str
    return p


def _make_config(
    *,
    auth_type: str = "none",
    token_encrypted: str | None = None,
    username: str | None = None,
    password_encrypted: str | None = None,
    ssh_key_encrypted: str | None = None,
    overwrite_existing: bool = True,
    path_prefix: str = "",
    branch: str = "main",
) -> MagicMock:
    cfg = MagicMock()
    cfg.id = "test-config-id"
    cfg.name = "Test Config"
    cfg.repo_url = "https://github.com/example/runbooks.git"
    cfg.branch = branch
    cfg.path_prefix = path_prefix
    cfg.auth_type = auth_type
    cfg.token_encrypted = token_encrypted
    cfg.username = username
    cfg.password_encrypted = password_encrypted
    cfg.ssh_key_encrypted = ssh_key_encrypted
    cfg.overwrite_existing = overwrite_existing
    cfg.sync_interval_minutes = 60
    cfg.last_sync_at = None
    cfg.last_sync_status = "never"
    cfg.last_sync_message = None
    cfg.runbooks_synced = 0
    cfg.created_by = None
    return cfg


def _valid_runbook_dict(name: str = "Test Runbook") -> dict:
    """Return a runbook YAML dict matching the service's expected schema."""
    return {
        "kind": "Runbook",
        "metadata": {
            "name": name,
            "description": "A test runbook",
            "tags": ["test"],
        },
        "spec": {
            "execution": {"auto_execute": False, "approval_required": True},
        },
        "steps": [
            {
                "name": "First Step",
                "description": "Do something",
            }
        ],
    }


def _checksum(d: dict) -> str:
    return hashlib.sha256(
        yaml.dump(d, sort_keys=True).encode()
    ).hexdigest()


# ---------------------------------------------------------------------------
# Tests: _build_clone_url
# ---------------------------------------------------------------------------

class TestBuildCloneUrl:
    """Tests for _build_clone_url helper function."""

    def test_no_auth_returns_url_unchanged(self):
        """Happy path: auth_type='none' keeps URL as-is."""
        cfg = _make_config(auth_type="none")
        result = _build_clone_url(cfg)
        assert result == cfg.repo_url

    def test_token_auth_embeds_token(self):
        """Happy path: auth_type='token' embeds decrypted token in URL."""
        cfg = _make_config(auth_type="token", token_encrypted="enc_tok")
        with patch(
            "app.services.runbook_git_sync_service.decrypt_value",
            return_value="mytoken",
        ):
            result = _build_clone_url(cfg)
        assert "mytoken@" in result
        assert result.startswith("https://")

    def test_basic_auth_embeds_credentials(self):
        """Happy path: auth_type='basic' embeds username:password in URL."""
        cfg = _make_config(
            auth_type="basic",
            username="user",
            password_encrypted="enc_pw",
        )
        with patch(
            "app.services.runbook_git_sync_service.decrypt_value",
            return_value="secret",
        ):
            result = _build_clone_url(cfg)
        assert "user:secret@" in result

    def test_ssh_returns_original_url(self):
        """Edge case: auth_type='ssh' does not modify the URL."""
        cfg = _make_config(auth_type="ssh", ssh_key_encrypted="enc_key")
        result = _build_clone_url(cfg)
        assert result == cfg.repo_url


# ---------------------------------------------------------------------------
# Tests: _build_git_env
# ---------------------------------------------------------------------------

class TestBuildGitEnv:
    """Tests for _build_git_env helper function."""

    def test_build_git_env_without_ssh_returns_no_key_path(self):
        """Happy path: non-SSH auth returns env and no temp key file."""
        cfg = _make_config(auth_type="none")
        env, ssh_key_path = _build_git_env(cfg)

        assert env["GIT_TERMINAL_PROMPT"] == "0"
        assert ssh_key_path is None
        assert "GIT_SSH_COMMAND" not in env

    def test_build_git_env_ssh_creates_temp_key_file(self):
        """Happy path: SSH auth creates a temp key file and command."""
        cfg = _make_config(auth_type="ssh", ssh_key_encrypted="enc_key")
        with patch(
            "app.services.runbook_git_sync_service.decrypt_value",
            return_value="FAKE_PRIVATE_KEY",
        ):
            env, ssh_key_path = _build_git_env(cfg)

        assert ssh_key_path is not None
        assert os.path.exists(ssh_key_path)
        assert ssh_key_path in env["GIT_SSH_COMMAND"]

        os.remove(ssh_key_path)

    def test_build_git_env_non_ssh_ignores_encrypted_key(self):
        """Edge case: encrypted key is ignored when auth_type is not ssh."""
        cfg = _make_config(auth_type="token", ssh_key_encrypted="enc_key")
        env, ssh_key_path = _build_git_env(cfg)

        assert ssh_key_path is None
        assert "GIT_SSH_COMMAND" not in env


# ---------------------------------------------------------------------------
# Tests: import_runbook_from_dict
# ---------------------------------------------------------------------------

class TestImportRunbookFromDict:
    """Tests for import_runbook_from_dict function."""

    @staticmethod
    def _make_db(existing_runbook):
        """
        Build a mock AsyncSession whose execute() returns ``existing_runbook``
        as the scalar result, and whose select/options chain is fully mocked so
        that SQLAlchemy mapper configuration is never triggered.
        """
        db = AsyncMock()
        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        mock_query.options.return_value = mock_query

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_runbook
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.delete = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db, mock_query

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_creates_new_runbook_when_not_exists(self):
        """Happy path: new runbook dict is inserted and result action is 'created'."""
        db, mock_query = self._make_db(existing_runbook=None)
        data = _valid_runbook_dict("Brand New Runbook")

        with patch("app.services.runbook_git_sync_service.select", return_value=mock_query):
            result = await import_runbook_from_dict(
                db=db, data=data, overwrite=True,
                source_path="runbooks/brand_new.yaml", created_by=None,
            )

        assert result["action"] == "created"
        assert result["name"] == "Brand New Runbook"
        assert result["error"] is None
        db.add.assert_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_skips_unchanged_checksum(self):
        """Happy path: existing runbook with matching checksum is skipped."""
        data = _valid_runbook_dict("Unchanged Runbook")
        existing = MagicMock()
        existing.checksum = _checksum(data)

        db, mock_query = self._make_db(existing_runbook=existing)

        with patch("app.services.runbook_git_sync_service.select", return_value=mock_query):
            result = await import_runbook_from_dict(
                db=db, data=data, overwrite=True,
                source_path="runbooks/unchanged.yaml", created_by=None,
            )

        assert result["action"] == "skipped"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_skips_existing_when_overwrite_false(self):
        """Error case: existing runbook is not overwritten when overwrite=False."""
        data = _valid_runbook_dict("Existing Runbook")
        existing = MagicMock()
        existing.checksum = "old_checksum"

        db, mock_query = self._make_db(existing_runbook=existing)

        with patch("app.services.runbook_git_sync_service.select", return_value=mock_query):
            result = await import_runbook_from_dict(
                db=db, data=data, overwrite=False,
                source_path="runbooks/existing.yaml", created_by=None,
            )

        assert result["action"] == "skipped"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_updates_existing_when_checksum_differs(self):
        """Happy path: existing runbook with changed content is updated."""
        data = _valid_runbook_dict("Updated Runbook")
        existing = MagicMock()
        existing.checksum = "old_different_checksum"
        existing.steps = []
        existing.triggers = []
        existing.version = 1

        db, mock_query = self._make_db(existing_runbook=existing)

        with patch("app.services.runbook_git_sync_service.select", return_value=mock_query):
            result = await import_runbook_from_dict(
                db=db, data=data, overwrite=True,
                source_path="runbooks/updated.yaml", created_by=None,
            )

        assert result["action"] == "updated"
        assert existing.version == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rejects_wrong_kind(self):
        """Error case: dict without kind='Runbook' is skipped."""
        data = {"kind": "Policy", "name": "Not A Runbook"}
        db = AsyncMock()

        result = await import_runbook_from_dict(
            db=db, data=data, overwrite=True,
            source_path="policies/policy.yaml", created_by=None,
        )

        assert result["action"] == "skipped"
        db.add.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rejects_missing_name(self):
        """Edge case: dict missing metadata.name is reported as skipped."""
        data = {"kind": "Runbook", "metadata": {}, "steps": []}
        db = AsyncMock()

        result = await import_runbook_from_dict(
            db=db, data=data, overwrite=True,
            source_path="runbooks/nameless.yaml", created_by=None,
        )

        assert result["action"] == "skipped"
        db.add.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: sync_git_config (high-level)
# ---------------------------------------------------------------------------

class TestSyncGitConfig:
    """Tests for the sync_git_config orchestrator function."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sync_returns_stats_dict(self):
        """Happy path: sync_git_config always returns a dict with required keys."""
        cfg = _make_config()

        db = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

        with (
            patch(
                "app.services.runbook_git_sync_service.subprocess.run",
                return_value=MagicMock(returncode=0, stderr=""),
            ),
            patch(
                "app.services.runbook_git_sync_service.tempfile.mkdtemp",
                return_value="/tmp/fake_repo",
            ),
            patch(
                "app.services.runbook_git_sync_service.shutil.rmtree"
            ),
            # scan_root.is_dir() → True, scan_root.rglob() → [] (empty repo)
            patch(
                "app.services.runbook_git_sync_service.Path",
                side_effect=lambda *a, **kw: _make_fake_path(*a, files=[]),
            ),
        ):
            result = await sync_git_config(db=db, config=cfg)

        assert "synced" in result
        assert "created" in result
        assert "updated" in result
        assert "skipped" in result
        assert "errors" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sync_records_error_on_clone_failure(self):
        """Error case: git clone failure is captured and status set to 'error'."""
        cfg = _make_config()

        db = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

        # Patch update of config last_sync_status
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = cfg
        db.execute = AsyncMock(return_value=mock_select_result)

        with (
            patch(
                "app.services.runbook_git_sync_service.subprocess.run",
                return_value=MagicMock(
                    returncode=1,
                    stderr="fatal: repository not found",
                ),
            ),
            patch(
                "app.services.runbook_git_sync_service.tempfile.mkdtemp",
                return_value="/tmp/fake_repo",
            ),
            patch(
                "app.services.runbook_git_sync_service.shutil.rmtree"
            ),
        ):
            result = await sync_git_config(db=db, config=cfg)

        assert len(result["errors"]) > 0
        assert result["synced"] == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sync_removes_temporary_ssh_key_file(self):
        """Happy path: temp SSH key file is deleted in finally cleanup."""
        cfg = _make_config(auth_type="ssh", ssh_key_encrypted="enc_key")

        db = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_key:
            tmp_key.write("FAKE_PRIVATE_KEY")
            key_path = tmp_key.name

        with (
            patch(
                "app.services.runbook_git_sync_service.tempfile.mkdtemp",
                return_value="/tmp/fake_repo",
            ),
            patch(
                "app.services.runbook_git_sync_service._build_git_env",
                return_value=({"GIT_TERMINAL_PROMPT": "0"}, key_path),
            ),
            patch(
                "app.services.runbook_git_sync_service.subprocess.run",
                return_value=MagicMock(returncode=1, stderr="fatal: clone failed"),
            ),
            patch("app.services.runbook_git_sync_service.shutil.rmtree"),
        ):
            await sync_git_config(db=db, config=cfg)

        assert not os.path.exists(key_path)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sync_commits_each_successful_import_before_later_failure(self):
        """Error case: successful imports are committed even if a later file fails."""
        cfg = _make_config()
        db = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

        yaml_a = MagicMock(spec=Path)
        yaml_a.relative_to.return_value = Path("a.yaml")
        yaml_a.read_text.return_value = yaml.dump(_valid_runbook_dict("A"))
        yaml_a.resolve.return_value = Path("/tmp/repo/a.yaml")

        yaml_b = MagicMock(spec=Path)
        yaml_b.relative_to.return_value = Path("b.yaml")
        yaml_b.read_text.return_value = yaml.dump(_valid_runbook_dict("B"))
        yaml_b.resolve.return_value = Path("/tmp/repo/b.yaml")

        yaml_c = MagicMock(spec=Path)
        yaml_c.relative_to.return_value = Path("c.yaml")
        yaml_c.read_text.return_value = yaml.dump(_valid_runbook_dict("C"))
        yaml_c.resolve.return_value = Path("/tmp/repo/c.yaml")

        with (
            patch(
                "app.services.runbook_git_sync_service.subprocess.run",
                return_value=MagicMock(returncode=0, stderr=""),
            ),
            patch(
                "app.services.runbook_git_sync_service.tempfile.mkdtemp",
                return_value="/tmp/fake_repo",
            ),
            patch(
                "app.services.runbook_git_sync_service.shutil.rmtree"
            ),
            patch(
                "app.services.runbook_git_sync_service.Path",
                side_effect=lambda *a, **kw: _make_fake_path(*a, files=[yaml_a, yaml_b, yaml_c]),
            ),
            patch(
                "app.services.runbook_git_sync_service.import_runbook_from_dict",
                side_effect=[
                    {"action": "created", "name": "A", "error": None},
                    RuntimeError("boom"),
                    {"action": "updated", "name": "C", "error": None},
                ],
            ),
        ):
            result = await sync_git_config(db=db, config=cfg)

        # One commit per successful create/update plus a final no-op commit.
        assert db.commit.await_count >= 3
        assert db.rollback.await_count == 1
        assert result["created"] == 1
        assert result["updated"] == 1
        assert result["synced"] == 2
