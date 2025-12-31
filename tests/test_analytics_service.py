
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock
from sqlalchemy.orm import Session

from app.services.metrics_analytics_service import MetricsAnalyticsService
from app.models import IncidentMetrics
from app.schemas import MTTRAnalytics

# Mock data helper
def create_mock_metrics(count=10, base_duration=100):
    metrics = []
    now = datetime.now(timezone.utc)
    for i in range(count):
        # Create timestamps with varying durations
        started = now - timedelta(days=i)
        detected = started + timedelta(seconds=10) # 10s to detect
        processed_duration = base_duration + (i * 10) # increasing duration
        resolved = detected + timedelta(seconds=processed_duration)
        
        m = IncidentMetrics(
            id=f"metric-{i}",
            incident_started=started,
            incident_detected=detected,
            incident_resolved=resolved,
            time_to_resolve=int((resolved - detected).total_seconds()),
            service_name="payment-service" if i % 2 == 0 else "auth-service",
            severity="critical" if i < 2 else "warning"
        )
        metrics.append(m)
    return metrics

@pytest.fixture
def mock_db():
    db = MagicMock(spec=Session)
    return db

def test_calculate_percentiles(mock_db):
    service = MetricsAnalyticsService(mock_db)
    
    # Test dataset: [10, 20, 30, 40, 50]
    values = [10, 20, 30, 40, 50]
    p50, p95, p99 = service._calculate_percentiles(values)
    
    assert p50 == 30.0
    assert p95 == 48.0 # Linear interpolation: 0.95 * 4 = 3.8 -> index 3(40) + 0.8*(50-40) = 48
    assert p99 == 50.0

def test_get_aggregate_stats_empty(mock_db):
    service = MetricsAnalyticsService(mock_db)
    
    # Mock query returning empty list
    mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = []
    
    stats = service.get_aggregate_stats(metric_type="time_to_resolve")
    
    assert stats.avg == 0
    assert stats.sample_size == 0
    assert stats.p50 == 0

def test_get_aggregate_stats_with_data(mock_db):
    service = MetricsAnalyticsService(mock_db)
    
    # Mock return values [100, 200, 300]
    # We need to mock the entire chain: db.query().filter()...all()
    # The implementation does: query(col).filter(...).filter(...).all()
    # verify_metrics.py approach of creating real objects in memory is better for integration, 
    # but for unit test we'll trust the logic if logic is simple. 
    # Actually, the logic *is* dependent on SQL alchemy execution for filtering?
    # No, the filtering happens in SQL, we just get result.
    
    # Let's mock the result of .all()
    mock_query = mock_db.query.return_value
    mock_filter1 = mock_query.filter.return_value
    # It might have multiple filters depending on args
    mock_final_query = MagicMock()
    mock_final_query.all.return_value = [(100,), (200,), (300,)]
    
    # We need to make sure the chain returns this
    mock_db.query.return_value.filter.return_value = mock_final_query
    # Handle apply_date_filter chain 
    mock_final_query.filter.return_value = mock_final_query
    
    stats = service.get_aggregate_stats(metric_type="time_to_resolve")
    
    assert stats.avg == 200.0
    assert stats.sample_size == 3
    assert stats.p50 == 200.0

def test_detect_regressions(mock_db):
    service = MetricsAnalyticsService(mock_db)
    
    # Mock get_service_avgs helper logic by mocking the db query
    # The method calls db.query twice.
    # First call: current period. Second call: previous period.
    
    # We can mock the side_effect of .all() to return different data
    
    # Data structure: [(service_name, avg_val)]
    current_data = [("payment-service", 150.0), ("auth-service", 50.0)] # High payment latency
    previous_data = [("payment-service", 100.0), ("auth-service", 50.0)] # Lower before
    
    # Mocking chain is complex with group_by, but simplified:
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_group = mock_filter.group_by.return_value
    
    mock_group.all.side_effect = [current_data, previous_data]
    
    regressions = service.detect_regressions(threshold_percent=20.0)
    
    assert len(regressions) == 1
    reg = regressions[0]
    assert reg.service_name == "payment-service"
    assert reg.change_percent == 50.0 # (150-100)/100 * 100
    assert reg.severity == "critical" # >= 50 is critical

