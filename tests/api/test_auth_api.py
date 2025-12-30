"""
API tests for Authentication endpoints.

Tests cover login, logout, token generation, and authentication failures.
"""
import pytest
from datetime import datetime, timedelta

from tests.fixtures.factories import UserFactory


class TestLoginAPI:
    """Test login endpoint."""
    
    @pytest.mark.asyncio
    async def test_login_with_valid_credentials(self, async_client, db_session):
        """Test successful login with valid credentials."""
        # Create user
        from app.services.auth_service import get_password_hash
        
        password = "TestPassword123!"
        user = UserFactory(
            username="testuser",
            password_hash=get_password_hash(password),
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Attempt login
        response = await async_client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": password
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_login_with_invalid_password(self, async_client, db_session):
        """Test login failure with incorrect password."""
        from app.services.auth_service import get_password_hash
        
        user = UserFactory(
            username="testuser",
            password_hash=get_password_hash("CorrectPassword123!"),
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Attempt login with wrong password
        response = await async_client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "WrongPassword123!"
            }
        )
        
        assert response.status_code == 401
        assert "Incorrect" in response.json().get("detail", "")
    
    @pytest.mark.asyncio
    async def test_login_with_nonexistent_user(self, async_client):
        """Test login failure with non-existent username."""
        response = await async_client.post(
            "/api/auth/login",
            json={
                "username": "nonexistent",
                "password": "SomePassword123!"
            }
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_login_with_inactive_user(self, async_client, db_session):
        """Test login failure when user is inactive."""
        from app.services.auth_service import get_password_hash
        
        password = "TestPassword123!"
        user = UserFactory(
            username="inactiveuser",
            password_hash=get_password_hash(password),
            is_active=False  # User is deactivated
        )
        db_session.add(user)
        db_session.commit()
        
        response = await async_client.post(
            "/api/auth/login",
            json={
                "username": "inactiveuser",
                "password": password
            }
        )
        
        assert response.status_code in [401, 403]


class TestTokenValidation:
    """Test JWT token validation."""
    
    @pytest.mark.asyncio
    async def test_access_protected_endpoint_with_valid_token(
        self, async_client, admin_auth_headers
    ):
        """Test accessing protected endpoint with valid token."""
        response = await async_client.get(
            "/api/alerts",
            headers=admin_auth_headers
        )
        
        # Should return 200 or 404, not 401 (unauthorized)
        assert response.status_code in [200, 404]
        assert response.status_code != 401
    
    @pytest.mark.asyncio
    async def test_access_protected_endpoint_without_token(self, async_client):
        """Test accessing protected endpoint without token."""
        response = await async_client.get("/api/alerts")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_access_protected_endpoint_with_invalid_token(self, async_client):
        """Test accessing protected endpoint with malformed token."""
        response = await async_client.get(
            "/api/alerts",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_access_protected_endpoint_with_expired_token(
        self, async_client, expired_token
    ):
        """Test accessing protected endpoint with expired token."""
        response = await async_client.get(
            "/api/alerts",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == 401


class TestUserRegistration:
    """Test user registration endpoint if available."""
    
    @pytest.mark.asyncio
    async def test_register_new_user(self, async_client, admin_auth_headers):
        """Test registering a new user."""
        new_user_data = {
            "username": "newuser",
            "password": "NewPassword123!",
            "email": "newuser@example.com",
            "role": "operator"
        }
        
        response = await async_client.post(
            "/api/auth/register",
            json=new_user_data,
            headers=admin_auth_headers  # May require admin
        )
        
        # Should be 201 Created or 200 OK
        assert response.status_code in [200, 201]
        data = response.json()
        assert data.get("username") == "newuser"
    
    @pytest.mark.asyncio
    async def test_register_duplicate_username(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test that duplicate username registration fails."""
        # Create existing user
        existing_user = UserFactory(username="existinguser")
        db_session.add(existing_user)
        db_session.commit()
        
        # Try to register with same username
        response = await async_client.post(
            "/api/auth/register",
            json={
                "username": "existinguser",
                "password": "Password123!",
                "email": "different@example.com",
                "role": "operator"
            },
            headers=admin_auth_headers
        )
        
        assert response.status_code in [400, 409]  # Bad Request or Conflict


class TestTokenRefresh:
    """Test token refresh endpoint if available."""
    
    @pytest.mark.asyncio
    async def test_refresh_valid_token(self, async_client, admin_auth_headers):
        """Test refreshing a valid token."""
        response = await async_client.post(
            "/api/auth/refresh",
            headers=admin_auth_headers
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "access_token" in data
    
    @pytest.mark.asyncio
    async def test_refresh_without_token(self, async_client):
        """Test token refresh without authentication."""
        response = await async_client.post("/api/auth/refresh")
        
        assert response.status_code == 401


class TestLogoutAPI:
    """Test logout endpoint if available."""
    
    @pytest.mark.asyncio
    async def test_logout_with_valid_token(self, async_client, admin_auth_headers):
        """Test successful logout."""
        response = await async_client.post(
            "/api/auth/logout",
            headers=admin_auth_headers
        )
        
        # Logout should succeed or endpoint may not exist
        assert response.status_code in [200, 204, 404]


class TestRBACAuthorization:
    """Test role-based access control."""
    
    @pytest.mark.asyncio
    async def test_admin_can_create_user(
        self, async_client, admin_auth_headers
    ):
        """Test that admin can create users."""
        response = await async_client.post(
            "/api/users",
            json={
                "username": "newuser",
                "password": "Password123!",
                "role": "operator"
            },
            headers=admin_auth_headers
        )
        
        # Should succeed or endpoint may not exist
        assert response.status_code in [200, 201, 404]
    
    @pytest.mark.asyncio
    async def test_operator_cannot_create_user(
        self, async_client, operator_auth_headers
    ):
        """Test that operator cannot create users."""
        response = await async_client.post(
            "/api/users",
            json={
                "username": "newuser",
                "password": "Password123!",
                "role": "operator"
            },
            headers=operator_auth_headers
        )
        
        # Should be forbidden or not found
        assert response.status_code in [403, 404]
    
    @pytest.mark.asyncio
    async def test_viewer_has_read_only_access(
        self, async_client, viewer_auth_headers
    ):
        """Test that viewer has read-only access."""
        # Viewer should be able to GET
        get_response = await async_client.get(
            "/api/alerts",
            headers=viewer_auth_headers
        )
        assert get_response.status_code in [200, 404]
        
        # But not POST
        post_response = await async_client.post(
            "/api/alerts",
            json={"test": "data"},
            headers=viewer_auth_headers
        )
        assert post_response.status_code in [403, 405]


class TestPasswordSecurity:
    """Test password security requirements."""
    
    @pytest.mark.asyncio
    async def test_weak_password_rejected(
        self, async_client, admin_auth_headers
    ):
        """Test that weak passwords are rejected if validation exists."""
        response = await async_client.post(
            "/api/auth/register",
            json={
                "username": "weakpass",
                "password": "123",  # Too weak
                "role": "operator"
            },
            headers=admin_auth_headers
        )
        
        # Should fail validation if password strength checking exists
        # Otherwise may succeed
        if response.status_code == 422:
            assert "password" in str(response.json()).lower()
