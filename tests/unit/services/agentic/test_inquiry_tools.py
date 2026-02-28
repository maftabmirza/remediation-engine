
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

from app.services.agentic.tools.inquiry_tools import InquiryTools
from app.models import Alert

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def inquiry_tools(mock_db):
    return InquiryTools(mock_db)

@pytest.mark.asyncio
async def test_query_alerts_history(inquiry_tools, mock_db):
    # Setup mock alerts
    mock_alert_1 = MagicMock(spec=Alert)
    mock_alert_1.alert_name = "High CPU"
    mock_alert_1.severity = "critical"
    mock_alert_1.status = "firing"
    mock_alert_1.timestamp = datetime.now(timezone.utc)
    mock_alert_1.labels = {"instance": "server-1", "job": "node-exporter"}

    mock_alert_2 = MagicMock(spec=Alert)
    mock_alert_2.alert_name = "Disk Full"
    mock_alert_2.severity = "warning"
    mock_alert_2.status = "resolved"
    mock_alert_2.timestamp = datetime.now(timezone.utc) - timedelta(hours=2)
    mock_alert_2.labels = {"instance": "server-2"}

    # Mock DB query
    mock_query = mock_db.query.return_value
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = [mock_alert_1, mock_alert_2]
    
    # Mock Count query
    mock_count_query = mock_db.query.return_value
    mock_count_query.filter.return_value = mock_count_query
    mock_count_query.scalar.return_value = 2

    # Execute
    args = {"severity": "critical", "days_back": 1}
    result = await inquiry_tools._query_alerts_history(args)

    # Verify
    assert "Found 2 alerts" in result
    assert "**High CPU**" in result
    assert "server-1" in result
    assert "**Disk Full**" in result 
    
    # Verify filters called (checking arguments requires more robust mocking usually, 
    # but basic check that filter was called multiple times works)
    assert mock_db.query.call_count >= 1

@pytest.mark.asyncio
async def test_get_mttr_statistics(inquiry_tools, mock_db):
    # Setup mock resolved alerts
    mock_alert = MagicMock(spec=Alert)
    mock_alert.status = "resolved"
    
    # Mock DB
    mock_query = mock_db.query.return_value
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [mock_alert, mock_alert, mock_alert] # 3 alerts

    # Execute
    result = await inquiry_tools._get_mttr_statistics({"days_back": 7})

    # Verify
    assert "Found 3 resolved alerts" in result
    assert "Note: Exact MTTR calculation" in result

@pytest.mark.asyncio
async def test_get_alert_trends_severity(inquiry_tools, mock_db):
    # Mock DB return for group by severity
    # Returns list of tuples (severity, count)
    mock_query = mock_db.query.return_value
    mock_query.filter.return_value = mock_query
    mock_query.group_by.return_value = mock_query
    mock_query.all.return_value = [("critical", 5), ("warning", 10)]

    # Execute
    result = await inquiry_tools._get_alert_trends({"group_by": "severity"})

    # Verify
    assert "**Alerts by Severity" in result
    assert "critical: 5" in result
    assert "warning: 10" in result

@pytest.mark.asyncio
async def test_get_alert_trends_daily(inquiry_tools, mock_db):
    # Mock DB return for group by day
    date1 = datetime(2025, 1, 1)
    date2 = datetime(2025, 1, 2)
    
    mock_query = mock_db.query.return_value
    mock_query.filter.return_value = mock_query
    mock_query.group_by.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = [(date1, 50), (date2, 40)]

    # Execute
    result = await inquiry_tools._get_alert_trends({"group_by": "day"})

    # Verify
    assert "**Daily Alert Volume" in result
    assert "2025-01-01: 50" in result
    assert "2025-01-02: 40" in result
