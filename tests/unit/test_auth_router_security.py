"""Unit tests for auth router security-sensitive behavior."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response

from app.routers import auth as auth_router
from app.schemas import LoginRequest


def _build_user(*, username: str = "alice") -> SimpleNamespace:
    """Create a minimal user-like object for router unit tests."""
    return SimpleNamespace(
        id=uuid4(),
        username=username,
        email=f"{username}@example.com",
        full_name=f"{username.title()} User",
        role="admin",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        last_login=None,
        failed_login_attempts=0,
        locked_until=None,
        password_changed_at=datetime.now(timezone.utc),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_rejects_locked_account_before_password_check():
    """Locked users are rejected before calling authenticate_user()."""
    locked_user = _build_user()
    locked_user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=5)

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = locked_user

    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    response = Response()
    login_data = LoginRequest(username=locked_user.username, password="secret")

    with patch("app.routers.auth.authenticate_user") as mock_authenticate:
        with pytest.raises(HTTPException) as exc:
            await auth_router.login(
                request=request,
                response=response,
                login_data=login_data,
                db=db,
            )

    assert exc.value.status_code == 403
    mock_authenticate.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_sets_password_expired_when_password_changed_at_missing():
    """Users with NULL password_changed_at are treated as expired when policy is enabled."""
    user = _build_user(username="expired_user")
    user.password_changed_at = None

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    db.commit = MagicMock()
    db.add = MagicMock()

    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    response = Response()
    login_data = LoginRequest(username=user.username, password="correct-password")

    with (
        patch("app.routers.auth.authenticate_user", return_value=user),
        patch(
            "app.routers.auth.get_password_policy",
            return_value={"password_expiry_days": 30},
        ),
        patch("app.routers.auth.create_access_token", return_value="jwt-token"),
        patch("app.routers.auth.get_permissions_for_role", return_value={"read"}),
    ):
        result = await auth_router.login(
            request=request,
            response=response,
            login_data=login_data,
            db=db,
        )

    assert result.password_expired is True
    user_data = result.user.model_dump()
    assert "failed_login_attempts" not in user_data
    assert "locked_until" not in user_data
    assert "password_changed_at" not in user_data


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_keeps_password_expired_false_for_recent_password_change():
    """Users with a recent password_changed_at are not marked expired."""
    user = _build_user(username="fresh_user")
    user.password_changed_at = datetime.now(timezone.utc)

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    db.commit = MagicMock()
    db.add = MagicMock()

    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    response = Response()
    login_data = LoginRequest(username=user.username, password="correct-password")

    with (
        patch("app.routers.auth.authenticate_user", return_value=user),
        patch(
            "app.routers.auth.get_password_policy",
            return_value={"password_expiry_days": 30},
        ),
        patch("app.routers.auth.create_access_token", return_value="jwt-token"),
        patch("app.routers.auth.get_permissions_for_role", return_value={"read"}),
    ):
        result = await auth_router.login(
            request=request,
            response=response,
            login_data=login_data,
            db=db,
        )

    assert result.password_expired is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_saml_acs_rejects_locked_user():
    """SAML ACS denies token issuance for locked accounts."""
    locked_user = _build_user(username="sso_locked")
    locked_user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)

    class _FakeSamlAuth:
        def process_response(self) -> None:
            return None

        def get_errors(self) -> list[str]:
            return []

        def is_authenticated(self) -> bool:
            return True

        def get_nameid(self) -> str:
            return "sso_locked@example.com"

        def get_attributes(self) -> dict:
            return {}

    db = MagicMock()
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    response = Response()

    with (
        patch("app.routers.auth.require_cyberark_config", return_value={}),
        patch("app.routers.auth.build_saml_auth", return_value=_FakeSamlAuth()),
        patch(
            "app.routers.auth.get_or_provision_sso_user",
            return_value=(locked_user, False),
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await auth_router.saml_acs(
                request=request,
                response=response,
                db=db,
            )

    assert exc.value.status_code == 403


@pytest.mark.unit
@pytest.mark.asyncio
async def test_saml_acs_allows_unlocked_user_and_returns_token():
    """Unlocked SSO users receive the standard login payload."""
    user = _build_user(username="sso_ok")
    user.locked_until = None

    class _FakeSamlAuth:
        def process_response(self) -> None:
            return None

        def get_errors(self) -> list[str]:
            return []

        def is_authenticated(self) -> bool:
            return True

        def get_nameid(self) -> str:
            return "sso_ok@example.com"

        def get_attributes(self) -> dict:
            return {}

    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    response = Response()

    with (
        patch("app.routers.auth.require_cyberark_config", return_value={}),
        patch("app.routers.auth.build_saml_auth", return_value=_FakeSamlAuth()),
        patch("app.routers.auth.get_or_provision_sso_user", return_value=(user, False)),
        patch("app.routers.auth.create_access_token", return_value="sso-token"),
        patch("app.routers.auth.get_permissions_for_role", return_value={"read"}),
    ):
        result = await auth_router.saml_acs(
            request=request,
            response=response,
            db=db,
        )

    assert result.access_token == "sso-token"
    assert result.user.username == user.username


@pytest.mark.unit
@pytest.mark.asyncio
async def test_saml_acs_allows_user_with_expired_lockout():
    """SSO users with an elapsed lockout timestamp are allowed."""
    user = _build_user(username="sso_expired_lockout")
    user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)

    class _FakeSamlAuth:
        def process_response(self) -> None:
            return None

        def get_errors(self) -> list[str]:
            return []

        def is_authenticated(self) -> bool:
            return True

        def get_nameid(self) -> str:
            return "sso_expired_lockout@example.com"

        def get_attributes(self) -> dict:
            return {}

    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    response = Response()

    with (
        patch("app.routers.auth.require_cyberark_config", return_value={}),
        patch("app.routers.auth.build_saml_auth", return_value=_FakeSamlAuth()),
        patch("app.routers.auth.get_or_provision_sso_user", return_value=(user, False)),
        patch("app.routers.auth.create_access_token", return_value="sso-token-2"),
        patch("app.routers.auth.get_permissions_for_role", return_value={"read"}),
    ):
        result = await auth_router.saml_acs(
            request=request,
            response=response,
            db=db,
        )

    assert result.access_token == "sso-token-2"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_me_response_excludes_sensitive_lockout_fields():
    """UserResponse payload for /me does not expose lockout metadata."""
    user = _build_user(username="me_user")
    user.failed_login_attempts = 3
    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=5)

    with patch("app.routers.auth.get_permissions_for_role", return_value={"read"}):
        payload = await auth_router.get_current_user_info(
            current_user=user,
            db=MagicMock(),
        )

    data = payload.model_dump()
    assert "failed_login_attempts" not in data
    assert "locked_until" not in data
    assert "password_changed_at" not in data
