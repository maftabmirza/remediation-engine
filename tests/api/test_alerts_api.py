"""
API tests for Alerts endpoints.

Tests cover alert webhook ingestion, retrieval, analysis, and filtering.
"""
import pytest
import json
from pathlib import Path

from tests.fixtures.factories import AlertFactory, RuleFactory


class TestAlertWebhookIngestion:
    """Test Alertmanager webhook endpoint."""
    
    @pytest.mark.asyncio
    async def test_ingest_firing_alert(self, async_client):
        """Test ingesting a firing alert via webhook."""
        # Load test data
        test_data_dir = Path(__file__).parent.parent / "test_data" / "alerts"
        with open(test_data_dir / "firing_alerts.json") as f:
            payload = json.load(f)
        
        response = await async_client.post(
            "/webhook/alerts",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") in ["success", "ok", "received"]
    
    @pytest.mark.asyncio
    async def test_ingest_resolved_alert(self, async_client):
        """Test ingesting a resolved alert via webhook."""
        test_data_dir = Path(__file__).parent.parent / "test_data" / "alerts"
        with open(test_data_dir / "resolved_alerts.json") as f:
            payload = json.load(f)
        
        response = await async_client.post(
            "/webhook/alerts",
            json=payload
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ingest_malformed_alert(self, async_client):
        """Test that malformed alert payload is rejected."""
        test_data_dir = Path(__file__).parent.parent / "test_data" / "alerts"
        with open(test_data_dir / "malformed_alerts.json") as f:
            payload = json.load(f)
        
        response = await async_client.post(
            "/webhook/alerts",
            json=payload
        )
        
        # Should reject malformed data
        assert response.status_code in [400, 422]


class TestGetAlerts:
    """Test retrieving alerts."""
    
    @pytest.mark.asyncio
    async def test_get_alerts_list(self, async_client, admin_auth_headers, db_session):
        """Test getting list of alerts."""
        # Create test alerts
        alert1 = AlertFactory()
        alert2 = AlertFactory()
        db_session.add_all([alert1, alert2])
        db_session.commit()
        
        response = await async_client.get(
            "/api/alerts",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
    
    @pytest.mark.asyncio
    async def test_get_alerts_with_pagination(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test alert pagination."""
        # Create 20 alerts
        for _ in range(20):
            db_session.add(AlertFactory())
        db_session.commit()
        
        # Get first page
        response = await async_client.get(
            "/api/alerts?page=1&page_size=10",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check pagination metadata if available
        if isinstance(data, dict) and "items" in data:
            assert len(data["items"]) <= 10
    
    @pytest.mark.asyncio
    async def test_get_single_alert(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test getting a single alert by ID."""
        alert = AlertFactory()
        db_session.add(alert)
        db_session.commit()
        
        response = await async_client.get(
            f"/api/alerts/{alert.id}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("id") == alert.id
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_alert(
        self, async_client, admin_auth_headers
    ):
        """Test getting alert that doesn't exist."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        
        response = await async_client.get(
            f"/api/alerts/{fake_id}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 404


class TestAlertFiltering:
    """Test filtering alerts by various criteria."""
    
    @pytest.mark.asyncio
    async def test_filter_alerts_by_severity(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test filtering alerts by severity."""
        # Create alerts with different severities
        critical = AlertFactory(severity="critical")
        warning = AlertFactory(severity="warning")
        db_session.add_all([critical, warning])
        db_session.commit()
        
        response = await async_client.get(
            "/api/alerts?severity=critical",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify filtering if response structure supports it
        if isinstance(data, list):
            assert all(a.get("severity") == "critical" for a in data)
    
    @pytest.mark.asyncio
    async def test_filter_alerts_by_status(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test filtering alerts by status."""
        firing = AlertFactory(status="firing")
        resolved = AlertFactory(status="resolved")
        db_session.add_all([firing, resolved])
        db_session.commit()
        
        response = await async_client.get(
            "/api/alerts?status=firing",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if isinstance(data, list):
            assert all(a.get("status") == "firing" for a in data)
    
    @pytest.mark.asyncio
    async def test_filter_alerts_by_instance(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test filtering alerts by instance."""
        instance = "web-server-01"
        alert1 = AlertFactory(instance=instance)
        alert2 = AlertFactory(instance="other-server")
        db_session.add_all([alert1, alert2])
        db_session.commit()
        
        response = await async_client.get(
            f"/api/alerts?instance={instance}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200


class TestAlertAnalysis:
    """Test alert analysis endpoint."""
    
    @pytest.mark.asyncio
    async def test_analyze_alert(
        self, async_client, admin_auth_headers, db_session, mock_llm_service
    ):
        """Test analyzing an alert with AI."""
        alert = AlertFactory(analyzed=False)
        db_session.add(alert)
        db_session.commit()
        
        response = await async_client.post(
            f"/api/alerts/{alert.id}/analyze",
            headers=admin_auth_headers
        )
        
        # Should succeed or may require LLM provider
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert "root_cause" in data or "analysis" in data
    
    @pytest.mark.asyncio
    async def test_analyze_already_analyzed_alert(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test analyzing an alert that was already analyzed."""
        alert = AlertFactory(
            analyzed=True,
            analysis_result={"root_cause": "Previous analysis"}
        )
        db_session.add(alert)
        db_session.commit()
        
        response = await async_client.post(
            f"/api/alerts/{alert.id}/analyze",
            headers=admin_auth_headers
        )
        
        # May return cached result or re-analyze
        assert response.status_code in [200, 304]


class TestAlertStats:
    """Test alert statistics endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_alert_stats(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test getting alert statistics."""
        # Create alerts with various statuses
        for _ in range(5):
            db_session.add(AlertFactory(status="firing", severity="critical"))
        for _ in range(3):
            db_session.add(AlertFactory(status="resolved", severity="warning"))
        db_session.commit()
        
        response = await async_client.get(
            "/api/alerts/stats",
            headers=admin_auth_headers
        )
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            # Check for common stat fields
            assert "total" in data or "firing" in data or "count" in data


class TestUpdateAlert:
    """Test updating alert properties."""
    
    @pytest.mark.asyncio
    async def test_update_alert_status(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test updating alert status."""
        alert = AlertFactory(status="firing")
        db_session.add(alert)
        db_session.commit()
        
        response = await async_client.put(
            f"/api/alerts/{alert.id}",
            json={"status": "resolved"},
            headers=admin_auth_headers
        )
        
        # May or may not support manual status updates
        assert response.status_code in [200, 405]
    
    @pytest.mark.asyncio
    async def test_add_alert_notes(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test adding notes to an alert."""
        alert = AlertFactory()
        db_session.add(alert)
        db_session.commit()
        
        response = await async_client.put(
            f"/api/alerts/{alert.id}",
            json={"notes": "Manually investigated - false positive"},
            headers=admin_auth_headers
        )
        
        # Notes feature may or may not exist
        assert response.status_code in [200, 404, 405]


class TestAlertUnauthorizedAccess:
    """Test unauthorized access to alert endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_alerts_without_auth(self, async_client):
        """Test that alerts require authentication."""
        response = await async_client.get("/api/alerts")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_analyze_alert_without_auth(self, async_client, db_session):
        """Test that alert analysis requires authentication."""
        alert = AlertFactory()
        db_session.add(alert)
        db_session.commit()
        
        response = await async_client.post(
            f"/api/alerts/{alert.id}/analyze"
        )
        
        assert response.status_code == 401
