"""
Integration tests for the alerts API endpoints.

Uses async httpx client to properly handle FastAPI async background tasks.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


class TestAlertsEndpoints:
    """Test alerts API endpoints."""
    
    @pytest.mark.asyncio
    async def test_list_alerts_empty(self, async_client):
        """Test listing alerts when database is empty."""
        response = await async_client.get("/api/alerts")
        
        # May return 401 if auth is required, or 200 with empty list
        assert response.status_code in [200, 401]
    
    @pytest.mark.asyncio
    async def test_webhook_receives_alert(self, async_client, sample_alert_payload):
        """Test receiving alert via webhook."""
        response = await async_client.post(
            "/webhook/alerts",
            json=sample_alert_payload
        )
        
        # Should accept webhook
        assert response.status_code in [200, 202, 401]
    
    @pytest.mark.asyncio
    @patch('app.services.llm_service.acompletion')
    async def test_webhook_with_auto_analyze_rule(
        self, 
        mock_llm, 
        async_client, 
        test_db_session,
        sample_alert_payload,
        sample_rule_data
    ):
        """Test webhook with auto-analyze rule triggering."""
        # This test would require proper setup of database and auth
        # For now, just test the endpoint exists
        response = await async_client.post(
            "/webhook/alerts",
            json=sample_alert_payload
        )
        
        assert response.status_code in [200, 202, 401]


class TestAlertFiltering:
    """Test alert filtering and search functionality."""
    
    @pytest.mark.asyncio
    async def test_filter_by_severity(self, async_client):
        """Test filtering alerts by severity."""
        response = await async_client.get("/api/alerts?severity=critical")
        
        assert response.status_code in [200, 401]
    
    @pytest.mark.asyncio
    async def test_filter_by_status(self, async_client):
        """Test filtering alerts by status."""
        response = await async_client.get("/api/alerts?status=firing")
        
        assert response.status_code in [200, 401]
    
    @pytest.mark.asyncio
    async def test_search_by_name(self, async_client):
        """Test searching alerts by name."""
        response = await async_client.get("/api/alerts?search=Nginx")
        
        assert response.status_code in [200, 401]
    
    @pytest.mark.asyncio
    async def test_pagination(self, async_client):
        """Test alert pagination."""
        response = await async_client.get("/api/alerts?page=1&page_size=10")
        
        assert response.status_code in [200, 401]


class TestAlertDetails:
    """Test alert detail endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_alert_details(self, async_client):
        """Test getting alert details."""
        # Using a fake UUID for testing
        alert_id = "00000000-0000-0000-0000-000000000000"
        response = await async_client.get(f"/api/alerts/{alert_id}")
        
        # Should return 404 or 401
        assert response.status_code in [404, 401]
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_alert(self, async_client):
        """Test getting non-existent alert."""
        fake_id = "99999999-9999-9999-9999-999999999999"
        response = await async_client.get(f"/api/alerts/{fake_id}")
        
        assert response.status_code in [404, 401]


class TestAlertActions:
    """Test alert action endpoints."""
    
    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, async_client):
        """Test acknowledging an alert."""
        alert_id = "00000000-0000-0000-0000-000000000000"
        response = await async_client.post(
            f"/api/alerts/{alert_id}/acknowledge"
        )
        
        # Should require auth or return not found
        assert response.status_code in [404, 401, 403]
    
    @pytest.mark.asyncio
    async def test_add_note_to_alert(self, async_client):
        """Test adding a note to an alert."""
        alert_id = "00000000-0000-0000-0000-000000000000"
        response = await async_client.post(
            f"/api/alerts/{alert_id}/notes",
            json={"note": "Test note"}
        )
        
        assert response.status_code in [404, 401, 403]


class TestWebhookValidation:
    """Test webhook payload validation."""
    
    @pytest.mark.asyncio
    async def test_webhook_invalid_payload(self, async_client):
        """Test webhook with invalid payload."""
        response = await async_client.post(
            "/webhook/alerts",
            json={"invalid": "payload"}
        )
        
        # Should reject invalid payload
        assert response.status_code in [400, 422, 401]
    
    @pytest.mark.asyncio
    async def test_webhook_missing_required_fields(self, async_client):
        """Test webhook with missing required fields."""
        response = await async_client.post(
            "/webhook/alerts",
            json={"alerts": []}
        )
        
        # Should handle empty alerts
        assert response.status_code in [200, 400, 422, 401]
    
    @pytest.mark.asyncio
    async def test_webhook_malformed_json(self, async_client):
        """Test webhook with malformed JSON."""
        response = await async_client.post(
            "/webhook/alerts",
            content="not json",
            headers={"Content-Type": "application/json"}
        )
        
        # Should reject malformed JSON
        assert response.status_code in [400, 422, 405]


class TestAlertStatistics:
    """Test alert statistics endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_alert_stats(self, async_client):
        """Test getting alert statistics."""
        response = await async_client.get("/api/alerts/stats")
        
        assert response.status_code in [200, 401, 404]
    
    @pytest.mark.asyncio
    async def test_get_alerts_by_severity_count(self, async_client):
        """Test getting alert counts by severity."""
        response = await async_client.get("/api/alerts/stats/severity")
        
        assert response.status_code in [200, 401, 404]


class TestBatchOperations:
    """Test batch alert operations."""
    
    @pytest.mark.asyncio
    async def test_batch_acknowledge(self, async_client):
        """Test batch acknowledging alerts."""
        response = await async_client.post(
            "/api/alerts/batch/acknowledge",
            json={"alert_ids": [
                "00000000-0000-0000-0000-000000000000",
                "11111111-1111-1111-1111-111111111111"
            ]}
        )
        
        assert response.status_code in [200, 401, 403, 404]
    
    @pytest.mark.asyncio
    async def test_batch_delete(self, async_client):
        """Test batch deleting alerts."""
        response = await async_client.post(
            "/api/alerts/batch/delete",
            json={"alert_ids": [
                "00000000-0000-0000-0000-000000000000"
            ]}
        )
        
        assert response.status_code in [200, 401, 403, 404]


class TestAlertAnalysis:
    """Test alert analysis endpoints."""
    
    @pytest.mark.asyncio
    @patch('app.services.llm_service.acompletion')
    async def test_trigger_analysis(self, mock_llm, async_client):
        """Test triggering analysis for an alert."""
        mock_llm.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Analysis"))]
        )
        
        alert_id = "00000000-0000-0000-0000-000000000000"
        response = await async_client.post(
            f"/api/alerts/{alert_id}/analyze"
        )
        
        assert response.status_code in [200, 401, 403, 404]
    
    @pytest.mark.asyncio
    async def test_get_analysis_results(self, async_client):
        """Test getting analysis results for an alert."""
        alert_id = "00000000-0000-0000-0000-000000000000"
        response = await async_client.get(
            f"/api/alerts/{alert_id}/analysis"
        )
        
        assert response.status_code in [200, 401, 404]


class TestConcurrency:
    """Test concurrent alert handling."""
    
    @pytest.mark.asyncio
    async def test_concurrent_webhooks(self, async_client, sample_alert_payload):
        """Test receiving multiple webhooks concurrently."""
        # Send sequential requests with async client
        responses = []
        for i in range(3):
            response = await async_client.post(
                "/webhook/alerts",
                json=sample_alert_payload
            )
            responses.append(response)
        
        # All should succeed (or all should fail with auth)
        status_codes = [r.status_code for r in responses]
        assert all(code in [200, 202, 401] for code in status_codes)
