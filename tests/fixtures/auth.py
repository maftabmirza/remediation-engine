"""
Authentication fixtures for pytest tests.

This module provides reusable authentication fixtures including users and tokens.
"""
import pytest
from typing import Dict
import uuid

from app.models import User
from app.services.auth_service import get_password_hash, create_access_token


@pytest.fixture
def test_password() -> str:
    """Standard test password used across all test users."""
    return "TestPassword123!"


@pytest.fixture
def admin_user(db_session, test_password) -> User:
    """Create and return an admin user."""
    user = User(
        id=str(uuid.uuid4()),
        username=f"admin_{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash(test_password),
        role="admin",
        is_active=True,
        email=f"admin_{uuid.uuid4().hex[:8]}@test.com"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def engineer_user(db_session, test_password) -> User:
    """Create and return an engineer user."""
    user = User(
        id=str(uuid.uuid4()),
        username=f"engineer_{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash(test_password),
        role="engineer",
        is_active=True,
        email=f"engineer_{uuid.uuid4().hex[:8]}@test.com"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def operator_user(db_session, test_password) -> User:
    """Create and return an operator user."""
    user = User(
        id=str(uuid.uuid4()),
        username=f"operator_{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash(test_password),
        role="operator",
        is_active=True,
        email=f"operator_{uuid.uuid4().hex[:8]}@test.com"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def viewer_user(db_session, test_password) -> User:
    """Create and return a viewer user (read-only)."""
    user = User(
        id=str(uuid.uuid4()),
        username=f"viewer_{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash(test_password),
        role="viewer",
        is_active=True,
        email=f"viewer_{uuid.uuid4().hex[:8]}@test.com"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session, test_password) -> User:
    """Create and return an inactive user."""
    user = User(
        id=str(uuid.uuid4()),
        username=f"inactive_{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash(test_password),
        role="operator",
        is_active=False,
        email=f"inactive_{uuid.uuid4().hex[:8]}@test.com"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user) -> str:
    """Generate a valid JWT token for admin user."""
    return create_access_token(data={"sub": str(admin_user.id)})


@pytest.fixture
def engineer_token(engineer_user) -> str:
    """Generate a valid JWT token for engineer user."""
    return create_access_token(data={"sub": str(engineer_user.id)})


@pytest.fixture
def operator_token(operator_user) -> str:
    """Generate a valid JWT token for operator user."""
    return create_access_token(data={"sub": str(operator_user.id)})


@pytest.fixture
def viewer_token(viewer_user) -> str:
    """Generate a valid JWT token for viewer user."""
    return create_access_token(data={"sub": str(viewer_user.id)})


@pytest.fixture
def expired_token() -> str:
    """Generate an expired JWT token for testing token validation."""
    from datetime import datetime, timedelta
    import jwt
    from app.config import get_settings
    
    settings = get_settings()
    expire = datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
    
    to_encode = {"sub": str(uuid.uuid4()), "exp": expire}
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


@pytest.fixture
def invalid_token() -> str:
    """Generate an invalid/malformed JWT token."""
    return "invalid.jwt.token.here"


@pytest.fixture
def admin_auth_headers(admin_token) -> Dict[str, str]:
    """Get HTTP headers with admin authentication."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def engineer_auth_headers(engineer_token) -> Dict[str, str]:
    """Get HTTP headers with engineer authentication."""
    return {"Authorization": f"Bearer {engineer_token}"}


@pytest.fixture
def operator_auth_headers(operator_token) -> Dict[str, str]:
    """Get HTTP headers with operator authentication."""
    return {"Authorization": f"Bearer {operator_token}"}


@pytest.fixture
def viewer_auth_headers(viewer_token) -> Dict[str, str]:
    """Get HTTP headers with viewer authentication."""
    return {"Authorization": f"Bearer {viewer_token}"}


@pytest.fixture
def no_auth_headers() -> Dict[str, str]:
    """Get HTTP headers without authentication (for testing auth failures)."""
    return {}
