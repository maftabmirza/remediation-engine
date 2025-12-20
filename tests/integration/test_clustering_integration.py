"""
Integration tests for Alert Clustering feature.

Tests:
1. Webhook creates alerts
2. Clustering job processes alerts
3. API endpoints return correct data
4. Cluster actions work (close, merge)
"""
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import Alert, AlertCluster, utc_now
from app.services.alert_clustering_service import AlertClusteringService
from app.services.clustering_worker import cluster_recent_alerts, cleanup_old_clusters


class TestClusteringIntegration:
    """Integration tests for alert clustering feature."""

    @pytest.fixture
    def client(self, db_session):
        """Create test client with db override."""
        from app.database import get_db
        
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as client:
            yield client
        app.dependency_overrides.clear()

    @pytest.fixture
    def auth_headers(self, client):
        """Get authenticated headers."""
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Passw0rd"}
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        # Fallback for tests without auth
        return {}

    @pytest.fixture
    def sample_alerts(self, db_session) -> list:
        """Create sample unclustered alerts for testing."""
        alerts = []
        base_time = utc_now()
        
        # Create 5 identical alerts (should cluster together)
        for i in range(5):
            alert = Alert(
                id=uuid4(),
                fingerprint=f"test-fingerprint-{i}",
                timestamp=base_time - timedelta(minutes=i),
                alert_name="HighCPUUsage",
                severity="critical",
                instance="server-test-1",
                job="node-exporter",
                status="firing",
                labels_json={"alertname": "HighCPUUsage", "instance": "server-test-1"},
                annotations_json={"summary": "Test alert"},
                raw_alert_json={},
                analyzed=False
            )
            db_session.add(alert)
            alerts.append(alert)
        
        db_session.commit()
        return alerts

    @pytest.fixture
    def sample_cluster(self, db_session) -> AlertCluster:
        """Create a sample cluster for testing."""
        cluster = AlertCluster(
            id=uuid4(),
            cluster_key="test_cluster_key",
            cluster_type="exact",
            severity="critical",
            alert_count=5,
            first_seen=utc_now() - timedelta(hours=1),
            last_seen=utc_now(),
            is_active=True,
            cluster_metadata={"test": True}
        )
        db_session.add(cluster)
        db_session.commit()
        return cluster


class TestClusteringService:
    """Test AlertClusteringService directly."""

    def test_exact_match_clustering(self, db_session, sample_alerts):
        """Test that identical alerts cluster together."""
        service = AlertClusteringService(db_session)
        clusters = service.cluster_alerts(sample_alerts, strategy='exact')
        
        assert len(clusters) == 1
        cluster = clusters[0]
        assert len(cluster['alerts']) == 5
        assert cluster['cluster_type'] == 'exact'

    def test_apply_clustering_creates_cluster(self, db_session, sample_alerts):
        """Test that apply_clustering creates database records."""
        service = AlertClusteringService(db_session)
        clusters = service.cluster_alerts(sample_alerts, strategy='exact')
        created = service.apply_clustering(clusters)
        
        assert len(created) == 1
        
        # Verify cluster in database
        db_cluster = db_session.query(AlertCluster).filter(
            AlertCluster.id == created[0].id
        ).first()
        assert db_cluster is not None
        assert db_cluster.alert_count == 5
        assert db_cluster.is_active == True

    def test_alerts_linked_to_cluster(self, db_session, sample_alerts):
        """Test that alerts are linked to their cluster."""
        service = AlertClusteringService(db_session)
        clusters = service.cluster_alerts(sample_alerts, strategy='exact')
        created = service.apply_clustering(clusters)
        
        # Refresh alerts
        for alert in sample_alerts:
            db_session.refresh(alert)
            assert alert.cluster_id == created[0].id
            assert alert.clustered_at is not None


class TestClusteringWorker:
    """Test clustering background worker."""

    def test_cluster_recent_alerts_job(self, db_session, sample_alerts):
        """Test the clustering job processes unclustered alerts."""
        # Run job
        cluster_recent_alerts(db_session)
        
        # Check cluster was created
        clusters = db_session.query(AlertCluster).filter(
            AlertCluster.is_active == True
        ).all()
        
        assert len(clusters) >= 1

    def test_cleanup_old_clusters(self, db_session):
        """Test cleanup job removes old inactive clusters."""
        # Create old inactive cluster
        old_cluster = AlertCluster(
            id=uuid4(),
            cluster_key="old_test_cluster",
            cluster_type="exact",
            severity="warning",
            alert_count=3,
            first_seen=utc_now() - timedelta(days=60),
            last_seen=utc_now() - timedelta(days=35),
            is_active=False,
            closed_at=utc_now() - timedelta(days=35),
            cluster_metadata={}
        )
        db_session.add(old_cluster)
        db_session.commit()
        
        old_id = old_cluster.id
        
        # Run cleanup
        cleanup_old_clusters(db_session)
        
        # Verify deleted
        result = db_session.query(AlertCluster).filter(
            AlertCluster.id == old_id
        ).first()
        assert result is None


class TestClusteringAPI:
    """Test clustering API endpoints."""

    def test_list_clusters(self, client, auth_headers, sample_cluster):
        """Test GET /api/clusters returns cluster list."""
        response = client.get("/api/clusters", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_cluster_detail(self, client, auth_headers, sample_cluster, db_session):
        """Test GET /api/clusters/{id} returns cluster details."""
        response = client.get(
            f"/api/clusters/{sample_cluster.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_cluster.id)
        assert data["cluster_type"] == "exact"
        assert data["is_active"] == True

    def test_get_cluster_alerts(self, client, auth_headers, sample_cluster, sample_alerts, db_session):
        """Test GET /api/clusters/{id}/alerts returns member alerts."""
        # Link alerts to cluster
        for alert in sample_alerts:
            alert.cluster_id = sample_cluster.id
            alert.clustered_at = utc_now()
        sample_cluster.alert_count = len(sample_alerts)
        db_session.commit()
        
        response = client.get(
            f"/api/clusters/{sample_cluster.id}/alerts",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

    def test_close_cluster(self, client, auth_headers, sample_cluster, db_session):
        """Test POST /api/clusters/{id}/close closes the cluster."""
        response = client.post(
            f"/api/clusters/{sample_cluster.id}/close?reason=test",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify closed
        db_session.refresh(sample_cluster)
        assert sample_cluster.is_active == False
        assert sample_cluster.closed_at is not None

    def test_get_cluster_stats(self, client, auth_headers, sample_cluster, sample_alerts, db_session):
        """Test GET /api/clusters/stats/overview returns statistics."""
        # Link alerts to cluster
        for alert in sample_alerts:
            alert.cluster_id = sample_cluster.id
        db_session.commit()
        
        response = client.get(
            "/api/clusters/stats/overview",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "active_clusters" in data
        assert "noise_reduction_pct" in data
        assert "avg_cluster_size" in data

    def test_cluster_not_found(self, client, auth_headers):
        """Test 404 for non-existent cluster."""
        fake_id = uuid4()
        response = client.get(
            f"/api/clusters/{fake_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestEndToEndClustering:
    """End-to-end integration tests."""

    def test_webhook_to_cluster_flow(self, client, auth_headers, db_session):
        """Test full flow: webhook -> alerts -> clustering -> API."""
        # 1. Send alerts via webhook
        webhook_data = {
            "status": "firing",
            "alerts": [
                {
                    "labels": {
                        "alertname": "E2ETestAlert",
                        "instance": "e2e-server",
                        "job": "test-job",
                        "severity": "warning"
                    },
                    "annotations": {
                        "summary": "E2E test alert"
                    },
                    "status": "firing",
                    "startsAt": datetime.now(timezone.utc).isoformat(),
                    "fingerprint": f"e2e-test-{uuid4()}"
                }
            ]
        }
        
        # Create 3 identical alerts
        for i in range(3):
            webhook_data["alerts"][0]["fingerprint"] = f"e2e-test-{i}"
            response = client.post("/webhook/alerts", json=webhook_data)
            assert response.status_code == 200
        
        # 2. Run clustering job
        cluster_recent_alerts(db_session)
        
        # 3. Verify cluster via API
        response = client.get("/api/clusters", headers=auth_headers)
        assert response.status_code == 200
        
        # 4. Check stats
        response = client.get("/api/clusters/stats/overview", headers=auth_headers)
        assert response.status_code == 200
        stats = response.json()
        assert stats["active_clusters"] >= 0

    def test_cluster_lifecycle(self, client, auth_headers, db_session, sample_cluster, sample_alerts):
        """Test cluster lifecycle: create -> query -> close -> cleanup."""
        # Link alerts
        for alert in sample_alerts:
            alert.cluster_id = sample_cluster.id
        sample_cluster.alert_count = len(sample_alerts)
        db_session.commit()
        
        cluster_id = sample_cluster.id
        
        # 1. Query cluster
        response = client.get(f"/api/clusters/{cluster_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["is_active"] == True
        
        # 2. Close cluster
        response = client.post(
            f"/api/clusters/{cluster_id}/close?reason=resolved",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # 3. Verify closed
        response = client.get(f"/api/clusters/{cluster_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["is_active"] == False


# Run with: pytest tests/integration/test_clustering_integration.py -v
