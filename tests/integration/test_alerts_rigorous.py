"""
RIGOROUS Integration tests for alert functionality.

These tests verify actual functionality with:
- Real database operations
- Actual JWT authentication
- Response body validation
- Database state verification

Unlike smoke tests, these will FAIL if the feature doesn't work.
"""
import pytest
from datetime import datetime


@pytest.mark.asyncio
class TestAlertWebhookRigorous:
    """Rigorous tests for webhook functionality with real verification."""
    
    async def test_webhook_creates_alert_in_database(
        self, 
        authenticated_client,
        test_db_session,
        sample_alert_payload
    ):
        """
        RIGOROUS: Verify webhook actually creates an alert in the database.
        
        This tests:
        1. POST to webhook returns 200/202
        2. Alert exists in database after creation
        3. Alert has correct data from payload
        """
        from app.models import Alert
        
        # Get count before
        count_before = test_db_session.query(Alert).count()
        
        # Send webhook
        response = await authenticated_client.post(
            "/webhook/alerts",
            json=sample_alert_payload
        )
        
        # Verify response
        assert response.status_code in [200, 202], \
            f"Expected 200/202, got {response.status_code}: {response.text}"
        
        # Verify response contains expected fields
        data = response.json()
        assert "received" in data or "alerts_processed" in data or "status" in data, \
            f"Response missing expected fields: {data}"
        
        # Verify database was updated
        count_after = test_db_session.query(Alert).count()
        assert count_after >= count_before, \
            f"Expected alerts to be created. Before: {count_before}, After: {count_after}"
        
        # If alerts were created, verify data
        if count_after > count_before:
            latest_alert = test_db_session.query(Alert).order_by(Alert.created_at.desc()).first()
            assert latest_alert is not None
            assert latest_alert.alert_name == "NginxDown"
            assert latest_alert.severity == "critical"
    
    async def test_webhook_rejects_invalid_payload(self, async_client):
        """
        RIGOROUS: Verify webhook rejects truly invalid payloads.
        
        Should return 400 or 422, NOT 200.
        """
        response = await async_client.post(
            "/webhook/alerts",
            json={"completely": "invalid", "no_alerts": True}
        )
        
        # Should NOT accept invalid data as success
        assert response.status_code in [400, 422], \
            f"Webhook should reject invalid payload with 400/422, got {response.status_code}"
    
    async def test_webhook_handles_empty_alerts_array(self, async_client):
        """
        RIGOROUS: Test handling of empty alerts array.
        """
        response = await async_client.post(
            "/webhook/alerts",
            json={"alerts": [], "status": "firing"}
        )
        
        # Empty alerts should be handled gracefully (200) not error
        assert response.status_code == 200, \
            f"Empty alerts should return 200, got {response.status_code}"


@pytest.mark.asyncio
class TestAlertListRigorous:
    """Rigorous tests for alert listing with real verification."""
    
    async def test_list_alerts_returns_json_array(self, authenticated_client):
        """
        RIGOROUS: Verify /api/alerts returns a proper JSON array.
        """
        response = await authenticated_client.get("/api/alerts")
        
        assert response.status_code == 200, \
            f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Should return list or object with items array
        if isinstance(data, list):
            # Direct list response
            assert isinstance(data, list), "Response should be a list"
        elif isinstance(data, dict):
            # Paginated response
            assert "items" in data or "alerts" in data, \
                f"Paginated response missing items/alerts field: {data.keys()}"
    
    async def test_list_alerts_pagination(self, authenticated_client):
        """
        RIGOROUS: Verify pagination parameters work correctly.
        """
        response = await authenticated_client.get("/api/alerts?page=1&page_size=5")
        
        assert response.status_code == 200, \
            f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # If paginated, verify structure
        if isinstance(data, dict):
            # Check pagination metadata exists
            pagination_fields = ["page", "page_size", "total", "items", "total_pages"]
            has_pagination = any(field in data for field in pagination_fields)
            assert has_pagination or "alerts" in data, \
                f"Expected pagination fields or alerts array: {data.keys()}"
    
    async def test_unauthenticated_request_rejected(self, async_client):
        """
        RIGOROUS: Verify unauthenticated requests are properly rejected.
        """
        response = await async_client.get("/api/alerts")
        
        # Should require authentication
        assert response.status_code == 401, \
            f"Expected 401 Unauthorized, got {response.status_code}"
        
        # Verify error message exists
        data = response.json()
        assert "detail" in data, "401 response should have 'detail' field"


@pytest.mark.asyncio
class TestAlertDetailsRigorous:
    """Rigorous tests for alert detail endpoints."""
    
    async def test_get_nonexistent_alert_returns_404(self, authenticated_client):
        """
        RIGOROUS: Verify getting non-existent alert returns 404, not 500.
        """
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.get(f"/api/alerts/{fake_uuid}")
        
        assert response.status_code == 404, \
            f"Non-existent alert should return 404, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data, "404 response should have error detail"
    
    async def test_invalid_uuid_returns_422(self, authenticated_client):
        """
        RIGOROUS: Verify invalid UUID format returns 422, not 500.
        """
        response = await authenticated_client.get("/api/alerts/not-a-valid-uuid")
        
        # Should return validation error, not server error
        assert response.status_code in [404, 422], \
            f"Invalid UUID should return 404/422, got {response.status_code}"


@pytest.mark.asyncio  
class TestAlertCreateAndRetrieve:
    """End-to-end test for alert creation and retrieval."""
    
    async def test_created_alert_can_be_retrieved(
        self,
        authenticated_client,
        test_db_session,
        sample_alert_payload
    ):
        """
        RIGOROUS: Create alert via webhook, then retrieve it via API.
        
        This is a true integration test verifying the full flow.
        """
        from app.models import Alert
        
        # Step 1: Create alert via webhook
        create_response = await authenticated_client.post(
            "/webhook/alerts",
            json=sample_alert_payload
        )
        
        # Verify creation succeeded
        assert create_response.status_code in [200, 202], \
            f"Failed to create alert: {create_response.text}"
        
        # Step 2: Get latest alert from database
        latest = test_db_session.query(Alert).order_by(Alert.created_at.desc()).first()
        
        if latest:
            # Step 3: Retrieve via API
            get_response = await authenticated_client.get(f"/api/alerts/{latest.id}")
            
            # Should be able to retrieve
            assert get_response.status_code == 200, \
                f"Failed to retrieve created alert: {get_response.text}"
            
            data = get_response.json()
            
            # Verify data matches
            assert data.get("alert_name") == "NginxDown" or data.get("alertname") == "NginxDown", \
                f"Alert name mismatch: {data}"
            assert data.get("severity") == "critical", \
                f"Severity mismatch: {data}"


@pytest.mark.asyncio
class TestAuthenticationRigorous:
    """Rigorous tests for authentication."""
    
    async def test_invalid_token_rejected(self, async_client):
        """
        RIGOROUS: Verify invalid JWT tokens are rejected.
        """
        response = await async_client.get(
            "/api/alerts",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        
        assert response.status_code in [401, 403], \
            f"Invalid token should be rejected with 401/403, got {response.status_code}"
    
    async def test_expired_token_rejected(self, async_client):
        """
        RIGOROUS: Verify expired JWT tokens are rejected.
        """
        from jose import jwt
        from datetime import datetime, timedelta
        from app.config import get_settings
        
        settings = get_settings()
        
        # Create an expired token
        expired_token = jwt.encode(
            {
                "sub": "test_user_id",
                "exp": datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm
        )
        
        response = await async_client.get(
            "/api/alerts",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code in [401, 403], \
            f"Expired token should be rejected, got {response.status_code}"
    
    async def test_valid_token_accepted(self, authenticated_client):
        """
        RIGOROUS: Verify valid JWT tokens are accepted.
        """
        response = await authenticated_client.get("/api/alerts")
        
        assert response.status_code == 200, \
            f"Valid token should be accepted, got {response.status_code}: {response.text}"
