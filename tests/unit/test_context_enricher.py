import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime

from app.services.agentic.context_enricher import TroubleshootingContextEnricher
from app.models import Alert

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_mcp_client():
    return MagicMock()

@pytest.fixture
def mock_alert():
    alert = MagicMock(spec=Alert)
    alert.id = uuid4()
    alert.name = "Test Alert"
    alert.severity = "critical"
    alert.instance = "server-01"
    alert.timestamp = datetime.now()
    alert.labels = {"service": "test-service"}
    return alert

@pytest.mark.asyncio
async def test_enrich_with_full_context(mock_db, mock_mcp_client, mock_alert):
    # Setup DB
    mock_db.query.return_value.filter.return_value.first.return_value = mock_alert
    
    # Mock Adapters
    with patch('app.services.agentic.context_enricher.SiftAdapter') as MockSift, \
         patch('app.services.agentic.context_enricher.OnCallAdapter') as MockOnCall, \
         patch('app.services.agentic.context_enricher.SimilarityService') as MockSimService:
        
        # Setup Sift
        sift_instance = MockSift.return_value
        sift_instance.investigate_errors = AsyncMock(return_value="Sift Analysis Found")
        
        # Setup OnCall
        oncall_instance = MockOnCall.return_value
        oncall_instance.get_schedule = AsyncMock(return_value="OnCall Schedule")
        
        # Setup Similarity
        sim_instance = MockSimService.return_value
        sim_instance.find_similar_alerts.return_value = MagicMock(similar_incidents=[
            MagicMock(alert_name="Past Alert 1", similarity_score=0.9)
        ])

        enricher = TroubleshootingContextEnricher(mock_db, mock_mcp_client, mock_alert.id)
        
        # Mock Runbook query
        # This is complex to mock via chain, so we might need to rely on the side_effect or return value structure
        # mock_db.query(Runbook)...
        # Since we already mocked db.query for Alert, we need to handle the second call for Runbook
        def query_side_effect(model):
            query_mock = MagicMock()
            if model == Alert:
                query_mock.filter.return_value.first.return_value = mock_alert
            else: # Runbook
                query_mock.filter.return_value.filter.return_value.first.return_value = MagicMock(name="Test Runbook", id=1)
            return query_mock
        
        mock_db.query.side_effect = query_side_effect

        context = await enricher.enrich()
        
        assert context.sift_analysis == "Sift Analysis Found"
        assert context.oncall_info == "OnCall Schedule"
        assert len(context.similar_incidents) == 1
        assert "Past Alert 1" in context.similar_incidents[0]
        assert "Test Alert" in context.alert_summary

@pytest.mark.asyncio
async def test_enrich_no_mcp(mock_db, mock_alert):
    # Setup DB
    mock_db.query.return_value.filter.return_value.first.return_value = mock_alert

    enricher = TroubleshootingContextEnricher(mock_db, mcp_client=None, alert_id=mock_alert.id)
    
    # Mock implementation details that would fail without mocks if called
    with patch('app.services.agentic.context_enricher.SimilarityService') as MockSimService:
         sim_instance = MockSimService.return_value
         sim_instance.find_similar_alerts.return_value = None
         
         # Mock runbook to return None
         mock_db.query.side_effect = lambda m: MagicMock(filter=lambda *args: MagicMock(filter=lambda *args: MagicMock(first=lambda: None)))

         context = await enricher.enrich()
         
         assert context.sift_analysis is None
         assert context.oncall_info is None
         assert context.similar_incidents == []
