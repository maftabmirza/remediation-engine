"""
Integration tests for Alert Clustering feature.

Tests:
1. Clustering service processes alerts
2. Clustering job creates clusters  
3. API endpoints return correct data
4. Cluster actions work (close)

Note: API tests may need to run individually due to async event loop
issues in the test environment. All tests pass when run individually:
    pytest tests/integration/test_clustering_integration.py::TestClusteringAPI::test_list_clusters -v
"""
import pytest
from datetime import timedelta
from uuid import uuid4

from app.models import Alert, AlertCluster, utc_now
from app.services.alert_clustering_service import AlertClusteringService
from app.services.clustering_worker import cluster_recent_alerts, cleanup_old_clusters


class TestClusteringService:
    """Test AlertClusteringService directly."""

    def test_exact_match_clustering(self, test_db_session):
        """Test that identical alerts cluster together."""
        # Create alerts
        alerts = []
        base_time = utc_now()
        for i in range(5):
            alert = Alert(
                id=uuid4(),
                fingerprint=f"exact-test-{uuid4()}",
                timestamp=base_time - timedelta(minutes=i),
                alert_name="ExactMatchTestAlert",
                severity="critical",
                instance="exact-test-server",
                job="node-exporter",
                status="firing",
                labels_json={"alertname": "ExactMatchTestAlert"},
                annotations_json={},
                raw_alert_json={},
                analyzed=False
            )
            test_db_session.add(alert)
            alerts.append(alert)
        test_db_session.commit()
        
        service = AlertClusteringService(test_db_session)
        clusters = service.cluster_alerts(alerts, strategy='exact')
        
        assert len(clusters) == 1
        cluster_key = list(clusters.keys())[0]
        assert len(clusters[cluster_key]) == 5

    def test_apply_clustering_creates_cluster(self, test_db_session):
        """Test that apply_clustering creates database records."""
        # Create alerts
        alerts = []
        base_time = utc_now()
        for i in range(3):
            alert = Alert(
                id=uuid4(),
                fingerprint=f"apply-test-{uuid4()}",
                timestamp=base_time - timedelta(minutes=i),
                alert_name="ApplyTestAlert",
                severity="warning",
                instance="apply-test-server",
                job="test-job",
                status="firing",
                labels_json={"alertname": "ApplyTestAlert"},
                annotations_json={},
                raw_alert_json={},
                analyzed=False
            )
            test_db_session.add(alert)
            alerts.append(alert)
        test_db_session.commit()
        
        service = AlertClusteringService(test_db_session)
        clusters = service.cluster_alerts(alerts, strategy='exact')
        created = service.apply_clustering(clusters)
        
        assert len(created) == 1
        
        # Verify cluster in database
        db_cluster = test_db_session.query(AlertCluster).filter(
            AlertCluster.id == created[0].id
        ).first()
        assert db_cluster is not None
        assert db_cluster.alert_count == 3
        assert db_cluster.is_active == True

    def test_alerts_linked_to_cluster(self, test_db_session):
        """Test that alerts are linked to their cluster."""
        # Create alerts
        alerts = []
        base_time = utc_now()
        for i in range(4):
            alert = Alert(
                id=uuid4(),
                fingerprint=f"link-test-{uuid4()}",
                timestamp=base_time - timedelta(minutes=i),
                alert_name="LinkTestAlert",
                severity="info",
                instance="link-test-server",
                job="test-job",
                status="firing",
                labels_json={"alertname": "LinkTestAlert"},
                annotations_json={},
                raw_alert_json={},
                analyzed=False
            )
            test_db_session.add(alert)
            alerts.append(alert)
        test_db_session.commit()
        
        service = AlertClusteringService(test_db_session)
        clusters = service.cluster_alerts(alerts, strategy='exact')
        created = service.apply_clustering(clusters)
        
        # Refresh alerts
        for alert in alerts:
            test_db_session.refresh(alert)
            assert alert.cluster_id == created[0].id
            assert alert.clustered_at is not None

    def test_close_inactive_clusters(self, test_db_session):
        """Test closing inactive clusters."""
        # Create a cluster with old last_seen
        old_cluster = AlertCluster(
            id=uuid4(),
            cluster_key=f"old_inactive_{uuid4()}",
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

    def test_cluster_recent_alerts_job(self, test_db_session):
        """Test the clustering job processes unclustered alerts."""
        # Create alerts
        alerts = []
        base_time = utc_now()
        for i in range(3):
            alert = Alert(
                id=uuid4(),
                fingerprint=f"worker-test-{uuid4()}",
                timestamp=base_time - timedelta(minutes=i*5),
                alert_name="WorkerJobTestAlert",
                severity="warning",
                instance="worker-job-server",
                job="test-job",
                status="firing",
                labels_json={"alertname": "WorkerJobTestAlert"},
                annotations_json={},
                raw_alert_json={},
                analyzed=False
            )
            test_db_session.add(alert)
            alerts.append(alert)
        test_db_session.commit()
        
        # Run job
        cluster_recent_alerts(test_db_session)
        
        # Check alerts are now clustered
        for alert in alerts:
            test_db_session.refresh(alert)
            assert alert.cluster_id is not None

    def test_cleanup_old_clusters(self, test_db_session):
        """Test cleanup job removes old inactive clusters."""
        # Create old inactive cluster
        old_cluster = AlertCluster(
            id=uuid4(),
            cluster_key=f"cleanup_test_{uuid4()}",
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


class TestClusteringAPIListClusters:
    """Test listing clusters API endpoint."""

    def test_list_clusters(self, test_client, admin_auth_headers, test_db_session):
        """Test GET /api/clusters returns cluster list."""
        # Create a cluster first
        cluster = AlertCluster(
            id=uuid4(),
            cluster_key=f"list_test_{uuid4()}",
            cluster_type="exact",
            severity="critical",
            alert_count=2,
            first_seen=utc_now() - timedelta(hours=1),
            last_seen=utc_now(),
            is_active=True,
            cluster_metadata={}
        )
        test_db_session.add(cluster)
        test_db_session.commit()
        
        response = test_client.get("/api/clusters", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1


class TestClusteringAPIDetail:
    """Test cluster detail API endpoint."""

    def test_get_cluster_detail(self, test_client, admin_auth_headers, test_db_session):
        """Test GET /api/clusters/{id} returns cluster details."""
        # Create a cluster
        cluster = AlertCluster(
            id=uuid4(),
            cluster_key=f"detail_test_{uuid4()}",
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
        
        response = test_client.get(
            f"/api/clusters/{cluster.id}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(cluster.id)
        assert data["cluster_type"] == "exact"
        assert data["is_active"] == True


class TestClusteringAPIClose:
    """Test cluster close API endpoint."""

    def test_close_cluster(self, test_client, admin_auth_headers, test_db_session):
        """Test POST /api/clusters/{id}/close closes the cluster."""
        # Create a cluster
        cluster = AlertCluster(
            id=uuid4(),
            cluster_key=f"close_test_{uuid4()}",
            cluster_type="exact",
            severity="warning",
            alert_count=2,
            first_seen=utc_now() - timedelta(hours=1),
            last_seen=utc_now(),
            is_active=True,
            cluster_metadata={}
        )
        test_db_session.add(cluster)
        test_db_session.commit()
        
        response = test_client.post(
            f"/api/clusters/{cluster.id}/close?reason=test",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify closed
        test_db_session.refresh(cluster)
        assert cluster.is_active == False
        assert cluster.closed_at is not None


class TestClusteringAPIStats:
    """Test cluster stats API endpoint."""

    def test_get_cluster_stats(self, test_client, admin_auth_headers, test_db_session):
        """Test GET /api/clusters/stats/overview returns statistics."""
        # Create a cluster with alerts
        cluster = AlertCluster(
            id=uuid4(),
            cluster_key=f"stats_test_{uuid4()}",
            cluster_type="exact",
            severity="critical",
            alert_count=5,
            first_seen=utc_now() - timedelta(hours=2),
            last_seen=utc_now(),
            is_active=True,
            cluster_metadata={}
        )
        test_db_session.add(cluster)
        
        # Create some alerts linked to the cluster
        for i in range(5):
            alert = Alert(
                id=uuid4(),
                fingerprint=f"stats-test-{uuid4()}",
                timestamp=utc_now() - timedelta(minutes=i*10),
                alert_name="StatsTestAlert",
                severity="critical",
                instance="stats-server",
                job="test-job",
                status="firing",
                labels_json={},
                annotations_json={},
                raw_alert_json={},
                analyzed=False,
                cluster_id=cluster.id,
                clustered_at=utc_now()
            )
            test_db_session.add(alert)
        
        test_db_session.commit()
        
        response = test_client.get(
            "/api/clusters/stats/overview",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "active_clusters" in data
        assert "noise_reduction_pct" in data
        assert "avg_cluster_size" in data
        assert data["active_clusters"] >= 1


class TestClusteringAPINotFound:
    """Test cluster not found API behavior."""

    def test_cluster_not_found(self, test_client, admin_auth_headers):
        """Test 404 for non-existent cluster."""
        fake_id = uuid4()
        response = test_client.get(
            f"/api/clusters/{fake_id}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 404


# Run all tests:
#   pytest tests/integration/test_clustering_integration.py -v
#
# Or run by class to avoid event loop issues:
#   pytest tests/integration/test_clustering_integration.py::TestClusteringService -v
#   pytest tests/integration/test_clustering_integration.py::TestClusteringWorker -v
#   pytest tests/integration/test_clustering_integration.py::TestClusteringAPIListClusters -v
