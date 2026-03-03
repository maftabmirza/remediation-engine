"""Unit tests for git sync credential updates in remediation router."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.routers.remediation import update_git_sync_config
from app.schemas_remediation import GitSyncConfigUpdate


def _build_cfg() -> SimpleNamespace:
    """Create a minimal config-like object for router unit tests."""
    return SimpleNamespace(
        token_encrypted="enc-token",
        password_encrypted="enc-password",
        ssh_key_encrypted="enc-ssh",
        enabled=True,
    )


def _build_db_with_cfg(cfg: SimpleNamespace) -> AsyncMock:
    """Build a mocked async DB session that resolves the config object."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = cfg
    db = AsyncMock()
    db.execute.return_value = result
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_git_sync_config_clears_falsy_credentials_without_plain_attrs():
    """Falsy credential payloads clear encrypted fields and do not set plain attrs."""
    cfg = _build_cfg()
    db = _build_db_with_cfg(cfg)

    data = GitSyncConfigUpdate(token="", password=None, ssh_key="")
    with patch(
        "app.routers.remediation._build_git_sync_response", return_value={"ok": True}
    ):
        await update_git_sync_config(
            config_id=uuid4(),
            data=data,
            db=db,
            current_user=SimpleNamespace(id=uuid4(), role="admin"),
        )

    assert cfg.token_encrypted is None
    assert cfg.password_encrypted is None
    assert cfg.ssh_key_encrypted is None
    assert not hasattr(cfg, "token")
    assert not hasattr(cfg, "password")
    assert not hasattr(cfg, "ssh_key")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_git_sync_config_encrypts_non_empty_credentials():
    """Non-empty credential payloads are encrypted and mapped to encrypted columns."""
    cfg = _build_cfg()
    db = _build_db_with_cfg(cfg)

    data = GitSyncConfigUpdate(
        token="new-token", password="new-pass", ssh_key="new-ssh"
    )
    with (
        patch(
            "app.routers.remediation._build_git_sync_response",
            return_value={"ok": True},
        ),
        patch(
            "app.utils.crypto.encrypt_value", side_effect=lambda value: f"enc::{value}"
        ),
    ):
        await update_git_sync_config(
            config_id=uuid4(),
            data=data,
            db=db,
            current_user=SimpleNamespace(id=uuid4(), role="admin"),
        )

    assert cfg.token_encrypted == "enc::new-token"
    assert cfg.password_encrypted == "enc::new-pass"
    assert cfg.ssh_key_encrypted == "enc::new-ssh"
    assert not hasattr(cfg, "token")
    assert not hasattr(cfg, "password")
    assert not hasattr(cfg, "ssh_key")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_git_sync_config_omitted_credentials_remain_unchanged():
    """Omitted credential fields do not mutate stored encrypted values."""
    cfg = _build_cfg()
    db = _build_db_with_cfg(cfg)

    data = GitSyncConfigUpdate(enabled=False)
    with patch(
        "app.routers.remediation._build_git_sync_response", return_value={"ok": True}
    ):
        await update_git_sync_config(
            config_id=uuid4(),
            data=data,
            db=db,
            current_user=SimpleNamespace(id=uuid4(), role="admin"),
        )

    assert cfg.token_encrypted == "enc-token"
    assert cfg.password_encrypted == "enc-password"
    assert cfg.ssh_key_encrypted == "enc-ssh"
