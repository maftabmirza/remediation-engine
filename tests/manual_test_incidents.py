import sys
import os
import logging
from datetime import datetime, timezone
import uuid
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models_itsm import IncidentEvent
from app.schemas_itsm import IncidentEventCreate, IncidentEventResponse
from app.services.itsm_connector import GenericAPIConnector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_incident_model():
    logger.info("Testing IncidentEvent model...")
    incident = IncidentEvent(
        incident_id="INC001",
        title="Test Incident",
        description="This is a test incident",
        status="New",
        severity="High",
        priority="P1",
        service_name="Test Service",
        created_at=datetime.now(timezone.utc),
        source="manual"
    )
    logger.info(f"Created incident object: {incident.incident_id} - {incident.title}")
    assert incident.incident_id == "INC001"
    assert incident.severity == "High"
    logger.info("✅ IncidentEvent model test passed")

def test_incident_schema():
    logger.info("Testing IncidentEvent schemas...")
    data = {
        "incident_id": "INC002",
        "title": "Schema Test",
        "description": "Testing schema validation",
        "status": "In Progress",
        "severity": "Medium",
        "priority": "P2",
        "service_name": "Schema Service",
        "created_at": datetime.now(timezone.utc),
        "source": "api"
    }
    create_schema = IncidentEventCreate(**data)
    logger.info(f"Validated values: {create_schema.incident_id}")
    assert create_schema.incident_id == "INC002"
    logger.info("✅ IncidentEventCreate schema test passed")

@patch('app.services.itsm_connector.GenericAPIConnector.fetch_changes')
def test_sync_incidents(mock_fetch):
    logger.info("Testing sync_incidents logic...")
    
    # Mock data
    mock_records = [
        {
            "incident_id": "INC003",
            "title": "Sync Test",
            "description": "Testing sync logic",
            "status": "Resolved",
            "severity": "Low",
            "priority": "P3",
            "service_name": "Test Service",
            "assignee": "Test User",
            "created_at": datetime.now(timezone.utc),
            "resolved_at": datetime.now(timezone.utc),
            "metadata": {"test": "val"}  # Original metadata from API
        }
    ]
    mock_fetch.return_value = mock_records
    
    # Mock DB session
    mock_db = MagicMock()
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_filter.first.return_value = None # Simulate new record
    
    # Initialize connector
    config = {
        "incident_config": {
            "api_config": {"base_url": "http://test"}
        }
    }
    connector = GenericAPIConnector(config)
    
    # Run sync
    integration_id = uuid.uuid4()
    created, updated, errors = connector.sync_incidents(mock_db, integration_id)
    
    logger.info(f"Sync result: created={created}, updated={updated}, errors={len(errors)}")
    
    assert created == 1
    assert updated == 0
    assert len(errors) == 0
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    
    logger.info("✅ sync_incidents logic test passed")

if __name__ == "__main__":
    try:
        test_incident_model()
        test_incident_schema()
        test_sync_incidents()
        logger.info("🎉 All tests passed successfully!")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
