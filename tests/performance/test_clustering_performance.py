import time
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from app.models import Alert, utc_now
from app.services.alert_clustering_service import AlertClusteringService

def test_clustering_performance(test_db_session):
    """
    Performance test: Cluster 1000 alerts in < 5 seconds
    """
    service = AlertClusteringService(test_db_session)
    now = utc_now()
    
    print("\nGenerating 1000 test alerts...")
    alerts = []
    # Create 100 sets of 10 identical alerts
    for i in range(100):
        for j in range(10):
            alert = Alert(
                id=uuid4(),
                alert_name=f"PerformanceAlert-{i}",
                instance=f"server-{i}",
                job="performance-test",
                severity="critical",
                timestamp=now - timedelta(minutes=j),
                status="firing",
                labels_json={"test_run": "perf-1000"},
                annotations_json={"summary": f"Performance test alert {i}-{j}"}
            )
            test_db_session.add(alert)
            alerts.append(alert)
    
    test_db_session.commit()
    print(f"Generated {len(alerts)} alerts.")
    
    start_time = time.time()
    
    # Run clustering with auto strategy
    print("Starting clustering...")
    clusters = service.cluster_alerts(alerts, strategy='auto')
    
    # Apply clustering to DB
    print("Applying clustering to DB...")
    service.apply_clustering(clusters)
    
    duration = time.time() - start_time
    
    print(f"\nClustering performance results:")
    print(f"Total alerts: {len(alerts)}")
    print(f"Total clusters created: {len(clusters)}")
    print(f"Total time: {duration:.4f} seconds")
    
    # Target is < 5 seconds
    assert duration < 5.0, f"Clustering took too long: {duration:.2f}s"
    print("✅ Performance target met!")
