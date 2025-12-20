"""
Integration tests for Alert Clustering feature.

Tests:
1. Clustering service processes alerts
2. Clustering job creates clusters
3. API endpoints return correct data
4. Cluster actions work (close)
"""
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from app.models import Alert, AlertCluster, utc_now
from app.services.alert_clustering_service import AlertClusteringService
from app.services.clustering_worker import cluster_recent_alerts, cleanup_old_clusters


class TestClusteringService:
    """Test AlertClusteringService directly."""

    @pytest.fixture
    def sample_alerts(self, test_db_session) -> list:
        """Create sample unclustered alerts for testing."""
        alerts = []
        base_time = utc_now()
        
        # Create 5 identical alerts (should cluster together)
        for i in range(5):
            alert = Alert(
                id=uuid4(),
                fingerprint=f"test-fingerprint-cluster-{i}",
                timestamp=base_time - timedelta(minutes=i),
                alert_name="TestClusterAlert",
                severity="critical",
                instance="test-server-1",
                job="node-exporter",
                status="firing",
                labels_json={"alertname": "TestClusterAlert", "instance": "test-server-1"},
                annotations_json={"summary": "Test alert for clustering"},
                raw_alert_json={},
                analyzed=False
            )
            test_db_session.add(alert)
            alerts.append(alert)
        
        test_db_session.commit()
        return alerts

    def test_exact_match_clustering(self, test_db_session, sample_alerts):
        """Test that identical alerts cluster together."""
        service = AlertClusteringService(test_db_session)
        clusters = service.cluster_alerts(sample_alerts, strategy='exact')
        
        assert len(clusters) == 1
        cluster = clusters[0]
        assert len(cluster['alerts']) == 5
        assert cluster['cluster_type'] == 'exact'

    def test_apply_clustering_creates_cluster(self, test_db_session, sample_alerts):
        """Test that apply_clustering creates database records."""
        service = AlertClusteringService(test_db_session)
        clusters = service.cluster_alerts(sample_alerts, strategy='exact')
        created = service.apply_clustering(clusters)
        
        assert len(created) == 1
        
        # Verify cluster in database
        db_cluster = test_db_session.query(AlertCluster).filter(
            AlertCluster.id == created[0].id
        ).first()
        assert db_cluster is not None
        assert db_cluster.alert_count == 5
        assert db_cluster.is_active == True

    def test_alerts_linked_to_cluster(self, test_db_session, sample_alerts):
        """Test that alerts are linked to their cluster."""
        service = AlertClusteringService(test_db_session)
        clusters = service.cluster_alerts(sample_alerts, strategy='exact')
        created = service.apply_clustering(clusters)
        
        # Refresh alerts
        for alert in sample_alerts:
            test_db_session.refresh(alert)
            assert alert.cluster_id == created[0].id
            assert alert.clustered_at is not None

    def test_close_inactive_clusters(self, test_db_session):
        """Test closing inactive clusters."""
        # Create a cluster with old last_seen
        old_cluster = AlertCluster(
            id=uuid4(),
            cluster_key="old_inactive_cluster",
            cluster_type="exact",
            severity="warning",
            alert_count=2,
            first_seen=utc_now() - timedelta(hours=48),
            last_seen=utc_now() - timedelta(hours=30),
            is_active=True,
            cluster_metadata={}
        )
        test_db_session.add(old_cluster)
        test_db_session.commit()
        
        service = AlertClusteringService(test_db_session)
        closed_count = service.close_inactive_clusters(inactive_hours=24)
        
        assert closed_count >= 1
        test_db_session.refresh(old_cluster)
        assert old_cluster.is_active == False


class TestClusteringWorker:
    """Test clustering background worker."""

    @pytest.fixture
    def unclustered_alerts(self, test_db_session) -> list:
        """Create unclustered alerts for worker test."""
        alerts = []
        base_time = utc_now()
        
        for i in range(3):
            alert = Alert(
                id=uuid4(),
                fingerprint=f"worker-test-{i}",
                timestamp=base_time - timedelta(minutes=i*5),
                alert_name="WorkerTestAlert",
                severity="warning",
                instance="worker-test-server",
                job="test-job",
                status="firing",
                labels_json={"alertname": "WorkerTestAlert"},
                annotations_json={},
                raw_alert_json={},
                analyzed=False
            )
            test_db_session.add(alert)
            alerts.append(alert)
        
        test_db_session.commit()
        return alerts

    def test_cluster_recent_alerts_job(self, test_db_session, unclustered_alerts):
        """Test the clustering job processes unclustered alerts."""
        # Run job
        cluster_recent_alerts(test_db_session)
        
        # Check alerts are now clustered
        for alert in unclustered_alerts:
            test_db_session.refresh(alert)
            assert alert.cluster_id is not None

    def test_cleanup_old_clusters(self, test_db_session):
        """Test cleanup job removes old inactive clusters."""
        # Create old inactive cluster
        old_cluster = AlertCluster(
            id=uuid4(),
            cluster_key="cleanup_test_cluster",
            cluster_type="exact",
            severity="info",
            alert_count=1,
            first_seen=utc_now() - timedelta(days=60),
            last_seen=utc_now() - timedelta(days=35),
            is_active=False,
            closed_at=utc_now() - timedelta(days=35),
            cluster_metadata={}
        )
        test_db_session.add(old_cluster)
        test_db_session.commit()
        
        old_id = old_cluster.id
        
        # Run cleanup
        cleanup_old_clusters(test_db_session)
        
        # Verify deleted
        result = test_db_session.query(AlertCluster).filter(
            AlertCluster.id == old_id
        ).first()
        assert result is None


class TestClusteringAPI:
    """Test clustering API endpoints."""

    @pytest.fixture
    def sample_cluster(self, test_db_session) -> AlertCluster:
        """Create a sample cluster for API testing."""
        cluster = AlertCluster(
            id=uuid4(),
            cluster_key="api_test_cluster",
            cluster_type="exact",
            severity="critical",
            alert_count=3,
            first_seen=utc_now() - timedelta(hours=1),
            last_seen=utc_now(),
            is_active=True,
            cluster_metadata={"test": True}
        )
        test_db_session.add(cluster)
        test_db_session.commit()
        return cluster

    def test_list_clusters(self, test_client, admin_auth_headers, sample_cluster):
        """Test GET /api/clusters returns cluster list."""
        response = test_client.get("/api/clusters", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_cluster_detail(self, test_client, admin_auth_headers, sample_cluster, test_db_session):
        """Test GET /api/clusters/{id} returns cluster details."""
        response = test_client.get(
            f"/api/clusters/{sample_cluster.id}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_cluster.id)
        assert data["cluster_type"] == "exact"
        assert data["is_active"] == True

    def test_close_cluster(self, test_client, admin_auth_headers, sample_cluster, test_db_session):
        """Test POST /api/clusters/{id}/close closes the cluster."""
        response = test_client.post(
            f"/api/clusters/{sample_cluster.id}/close?reason=test",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify closed
        test_db_session.refresh(sample_cluster)
        assert sample_cluster.is_active == False
        assert sample_cluster.closed_at is not None

    def test_get_cluster_stats(self, test_client, admin_auth_headers):
        """Test GET /api/clusters/stats/overview returns statistics."""
        response = test_client.get(
            "/api/clusters/stats/overview",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "active_clusters" in data
        assert "noise_reduction_pct" in data
        assert "avg_cluster_size" in data

    def test_cluster_not_found(self, test_client, admin_auth_headers):
        """Test 404 for non-existent cluster."""
        fake_id = uuid4()
        response = test_client.get(
            f"/api/clusters/{fake_id}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 404


# Run with: pytest tests/integration/test_clustering_integration.py -v
