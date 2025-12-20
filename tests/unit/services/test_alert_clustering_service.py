"""
Unit tests for Alert Clustering Service
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.models import Alert, AlertCluster, utc_now
from app.services.alert_clustering_service import AlertClusteringService


@pytest.fixture
def db_session(test_db_session):
    """Provide a database session for tests"""
    return test_db_session


@pytest.fixture
def clustering_service(db_session):
    """Create clustering service instance"""
    return AlertClusteringService(db_session)


@pytest.fixture
def sample_alerts(db_session):
    """Create sample alerts for testing"""
    now = utc_now()
    
    alerts = []
    
    # Create 5 identical alerts (should cluster together)
    for i in range(5):
        alert = Alert(
            id=uuid4(),
            alert_name="HighCPUUsage",
            instance="server-1",
            job="node-exporter",
            severity="critical",
            timestamp=now - timedelta(minutes=i),
            status="firing",
            labels_json={"env": "production"},
            annotations_json={"summary": "CPU usage above 90%"}
        )
        db_session.add(alert)
        alerts.append(alert)
    
    # Create 3 similar alerts with different instances
    for i in range(3):
        alert = Alert(
            id=uuid4(),
            alert_name="HighCPUUsage",
            instance=f"server-{i+2}",
            job="node-exporter",
            severity="warning",
            timestamp=now - timedelta(minutes=i),
            status="firing",
            labels_json={"env": "production"},
            annotations_json={"summary": "CPU usage above 80%"}
        )
        db_session.add(alert)
        alerts.append(alert)
    
    # Create 2 different alerts (should not cluster)
    for i in range(2):
        alert = Alert(
            id=uuid4(),
            alert_name="DiskSpaceLow",
            instance=f"server-{i}",
            job="node-exporter",
            severity="info",
            timestamp=now - timedelta(minutes=i),
            status="firing",
            labels_json={"env": "staging"},
            annotations_json={"summary": "Disk space below 20%"}
        )
        db_session.add(alert)
        alerts.append(alert)
    
    db_session.commit()
    return alerts


class TestExactMatchClustering:
    """Test exact match clustering layer"""
    
    def test_identical_alerts_cluster_together(self, clustering_service, sample_alerts):
        """Test that identical alerts are grouped into one cluster"""
        # Get only the 5 identical alerts
        identical_alerts = [a for a in sample_alerts if a.instance == "server-1"]
        
        clusters = clustering_service.cluster_alerts(identical_alerts, strategy='exact')
        
        # Should create 1 cluster with 5 alerts
        assert len(clusters) == 1
        cluster_key = list(clusters.keys())[0]
        assert len(clusters[cluster_key]) == 5
    
    def test_different_alerts_dont_cluster(self, clustering_service, sample_alerts):
        """Test that different alerts create separate clusters"""
        # Get alerts with different names
        high_cpu = [a for a in sample_alerts if a.alert_name == "HighCPUUsage"][:1]
        disk_space = [a for a in sample_alerts if a.alert_name == "DiskSpaceLow"][:1]
        
        mixed_alerts = high_cpu + disk_space
        clusters = clustering_service.cluster_alerts(mixed_alerts, strategy='exact')
        
        # Should create 2 separate clusters
        assert len(clusters) == 2
    
    def test_different_instances_create_separate_clusters(self, clustering_service, sample_alerts):
        """Test that same alert on different instances creates separate clusters"""
        # Get HighCPUUsage alerts from different instances
        cpu_alerts = [a for a in sample_alerts if a.alert_name == "HighCPUUsage"]
        
        clusters = clustering_service.cluster_alerts(cpu_alerts, strategy='exact')
        
        # Should create multiple clusters (one per instance)
        assert len(clusters) >= 2


class TestTemporalClustering:
    """Test temporal clustering layer"""
    
    def test_alerts_within_time_window_cluster(self, clustering_service, db_session):
        """Test that alerts within 5-minute window cluster together"""
        now = utc_now()
        
        # Create 3 alerts within 5 minutes
        alerts = []
        for i in range(3):
            alert = Alert(
                id=uuid4(),
                alert_name="MemoryLeak",
                instance=f"server-{i}",
                job="app",
                severity="warning",
                timestamp=now - timedelta(minutes=i),
                status="firing"
            )
            db_session.add(alert)
            alerts.append(alert)
        
        db_session.commit()
        
        clusters = clustering_service.cluster_alerts(alerts, strategy='temporal')
        
        # Should create 1 cluster
        assert len(clusters) == 1
        cluster_key = list(clusters.keys())[0]
        assert len(clusters[cluster_key]) == 3
    
    def test_alerts_outside_time_window_dont_cluster(self, clustering_service, db_session):
        """Test that alerts outside time window create separate clusters"""
        now = utc_now()
        
        # Create 2 alerts 10 minutes apart (outside 5-min window)
        alerts = []
        alert1 = Alert(
            id=uuid4(),
            alert_name="MemoryLeak",
            instance="server-1",
            job="app",
            severity="warning",
            timestamp=now,
            status="firing"
        )
        alert2 = Alert(
            id=uuid4(),
            alert_name="MemoryLeak",
            instance="server-2",
            job="app",
            severity="warning",
            timestamp=now - timedelta(minutes=10),
            status="firing"
        )
        db_session.add(alert1)
        db_session.add(alert2)
        alerts = [alert1, alert2]
        
        db_session.commit()
        
        clusters = clustering_service.cluster_alerts(alerts, strategy='temporal')
        
        # Should create 0 clusters (each has only 1 alert, minimum is 2)
        assert len(clusters) == 0


class TestAutoStrategy:
    """Test auto clustering strategy (combines all layers)"""
    
    def test_auto_strategy_uses_exact_match_first(self, clustering_service, sample_alerts):
        """Test that auto strategy prioritizes exact match"""
        clusters = clustering_service.cluster_alerts(sample_alerts, strategy='auto')
        
        # Should cluster the 5 identical alerts
        assert len(clusters) >= 1
        
        # Find the cluster with 5 alerts
        large_cluster = [c for c in clusters.values() if len(c) == 5]
        assert len(large_cluster) == 1


class TestApplyClustering:
    """Test applying clustering results to database"""
    
    def test_apply_clustering_creates_cluster_records(self, clustering_service, sample_alerts, db_session):
        """Test that apply_clustering creates AlertCluster records"""
        # Cluster the alerts
        clusters = clustering_service.cluster_alerts(sample_alerts, strategy='exact')
        
        # Apply clustering
        created_clusters = clustering_service.apply_clustering(clusters)
        
        # Should create cluster records
        assert len(created_clusters) > 0
        
        # Verify clusters exist in database
        db_clusters = db_session.query(AlertCluster).all()
        assert len(db_clusters) == len(created_clusters)
    
    def test_apply_clustering_links_alerts_to_clusters(self, clustering_service, sample_alerts, db_session):
        """Test that alerts are linked to their clusters"""
        # Cluster and apply
        clusters = clustering_service.cluster_alerts(sample_alerts, strategy='exact')
        clustering_service.apply_clustering(clusters)
        
        # Check that alerts have cluster_id set
        clustered_alerts = db_session.query(Alert).filter(
            Alert.cluster_id.isnot(None)
        ).all()
        
        assert len(clustered_alerts) > 0
    
    def test_apply_clustering_skips_single_alert_clusters(self, clustering_service, db_session):
        """Test that single-alert clusters are not created"""
        # Create a single alert
        alert = Alert(
            id=uuid4(),
            alert_name="UniqueAlert",
            instance="server-1",
            job="app",
            severity="info",
            timestamp=utc_now(),
            status="firing"
        )
        db_session.add(alert)
        db_session.commit()
        
        # Cluster it
        clusters = clustering_service.cluster_alerts([alert], strategy='exact')
        created_clusters = clustering_service.apply_clustering(clusters)
        
        # Should not create any clusters (minimum 2 alerts)
        assert len(created_clusters) == 0


class TestCloseInactiveClusters:
    """Test closing inactive clusters"""
    
    def test_close_inactive_clusters_closes_old_clusters(self, clustering_service, db_session):
        """Test that old inactive clusters are closed"""
        now = utc_now()
        
        # Create an old cluster
        old_cluster = AlertCluster(
            id=uuid4(),
            cluster_key="old_cluster",
            alert_count=5,
            first_seen=now - timedelta(hours=48),
            last_seen=now - timedelta(hours=25),  # 25 hours ago
            severity="critical",
            is_active=True
        )
        db_session.add(old_cluster)
        db_session.commit()
        
        # Close inactive clusters (24h threshold)
        closed_count = clustering_service.close_inactive_clusters(inactive_hours=24)
        
        # Should close 1 cluster
        assert closed_count == 1
        
        # Verify cluster is closed
        db_session.refresh(old_cluster)
        assert old_cluster.is_active == False
        assert old_cluster.closed_reason == 'timeout'
    
    def test_close_inactive_clusters_keeps_recent_clusters(self, clustering_service, db_session):
        """Test that recent clusters are not closed"""
        now = utc_now()
        
        # Create a recent cluster
        recent_cluster = AlertCluster(
            id=uuid4(),
            cluster_key="recent_cluster",
            alert_count=3,
            first_seen=now - timedelta(hours=2),
            last_seen=now - timedelta(hours=1),  # 1 hour ago
            severity="warning",
            is_active=True
        )
        db_session.add(recent_cluster)
        db_session.commit()
        
        # Close inactive clusters (24h threshold)
        closed_count = clustering_service.close_inactive_clusters(inactive_hours=24)
        
        # Should not close any clusters
        assert closed_count == 0
        
        # Verify cluster is still active
        db_session.refresh(recent_cluster)
        assert recent_cluster.is_active == True


class TestMetadataExtraction:
    """Test metadata extraction from alerts"""
    
    def test_extract_common_labels(self, clustering_service, db_session):
        """Test extraction of common labels"""
        now = utc_now()
        
        # Create alerts with common labels
        alerts = []
        for i in range(3):
            alert = Alert(
                id=uuid4(),
                alert_name="TestAlert",
                instance=f"server-{i}",
                job="app",
                severity="info",
                timestamp=now,
                status="firing",
                labels_json={"env": "production", "team": "platform"}
            )
            db_session.add(alert)
            alerts.append(alert)
        
        db_session.commit()
        
        # Extract metadata
        metadata = clustering_service._extract_metadata(alerts)
        
        # Should extract common labels
        assert "common_labels" in metadata
        assert metadata["common_labels"]["env"] == "production"
        assert metadata["common_labels"]["team"] == "platform"
    
    def test_extract_affected_services(self, clustering_service, db_session):
        """Test extraction of affected services"""
        now = utc_now()
        
        # Create alerts with different jobs
        alerts = []
        for job in ["app", "database", "cache"]:
            alert = Alert(
                id=uuid4(),
                alert_name="TestAlert",
                instance="server-1",
                job=job,
                severity="info",
                timestamp=now,
                status="firing"
            )
            db_session.add(alert)
            alerts.append(alert)
        
        db_session.commit()
        
        # Extract metadata
        metadata = clustering_service._extract_metadata(alerts)
        
        # Should extract affected services
        assert "affected_services" in metadata
        assert set(metadata["affected_services"]) == {"app", "database", "cache"}


class TestClusterModel:
    """Test AlertCluster model methods"""
    
    def test_duration_hours_calculation(self, db_session):
        """Test duration_hours computed property"""
        now = utc_now()
        
        cluster = AlertCluster(
            id=uuid4(),
            cluster_key="test",
            alert_count=5,
            first_seen=now - timedelta(hours=2),
            last_seen=now,
            severity="critical"
        )
        
        # Should calculate 2 hours
        assert cluster.duration_hours == pytest.approx(2.0, rel=0.1)
    
    def test_alerts_per_hour_calculation(self, db_session):
        """Test alerts_per_hour computed property"""
        now = utc_now()
        
        cluster = AlertCluster(
            id=uuid4(),
            cluster_key="test",
            alert_count=10,
            first_seen=now - timedelta(hours=2),
            last_seen=now,
            severity="critical"
        )
        
        # Should calculate 5 alerts per hour
        assert cluster.alerts_per_hour == pytest.approx(5.0, rel=0.1)
    
    def test_should_close_returns_true_for_old_clusters(self, db_session):
        """Test should_close method for old clusters"""
        now = utc_now()
        
        cluster = AlertCluster(
            id=uuid4(),
            cluster_key="test",
            alert_count=5,
            first_seen=now - timedelta(hours=48),
            last_seen=now - timedelta(hours=25),
            severity="critical",
            is_active=True
        )
        
        # Should return True (25 hours > 24 hours threshold)
        assert cluster.should_close(inactive_hours=24) == True
    
    def test_should_close_returns_false_for_recent_clusters(self, db_session):
        """Test should_close method for recent clusters"""
        now = utc_now()
        
        cluster = AlertCluster(
            id=uuid4(),
            cluster_key="test",
            alert_count=5,
            first_seen=now - timedelta(hours=2),
            last_seen=now - timedelta(hours=1),
            severity="critical",
            is_active=True
        )
        
        # Should return False (1 hour < 24 hours threshold)
        assert cluster.should_close(inactive_hours=24) == False
