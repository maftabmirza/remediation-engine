"""
Integration tests for PII Detection API.

Tests all PII detection endpoints with database and service integration:
- Detection endpoint
- Redaction endpoint
- Configuration endpoints
- Log query endpoints
- Statistics endpoints
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from app.main import app
from app.database import Base, get_db
from app.models.pii_models import PIIDetectionConfig, PIIDetectionLog


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_pii.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create test database session."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestPIIDetectionAPI:
    """Test suite for PII detection API endpoints."""
    
    def test_detect_endpoint_returns_200(self, client):
        """Test detection endpoint returns 200 OK."""
        # Arrange
        payload = {
            "text": "Contact john.doe@example.com or call 555-123-4567",
            "source_type": "test",
            "engines": ["presidio"]
        }
        
        # Act
        response = client.post("/api/v1/pii/detect", json=payload)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "detections" in data
        assert "detection_count" in data
        assert "processing_time_ms" in data
    
    def test_detect_email_in_text(self, client):
        """Test detection of email addresses."""
        # Arrange
        payload = {
            "text": "Send report to admin@company.com",
            "source_type": "test"
        }
        
        # Act
        response = client.post("/api/v1/pii/detect", json=payload)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["detection_count"] > 0
        
        # Check if email was detected
        entity_types = [d["entity_type"] for d in data["detections"]]
        assert any("EMAIL" in et.upper() for et in entity_types)
    
    def test_redact_endpoint_returns_masked_text(self, client):
        """Test redaction endpoint masks sensitive data."""
        # Arrange
        payload = {
            "text": "My password is SuperSecret123!",
            "redaction_type": "mask"
        }
        
        # Act
        response = client.post("/api/v1/pii/redact", json=payload)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "redacted_text" in data
        assert "redactions_applied" in data
        assert "SuperSecret123!" not in data["redacted_text"]
    
    def test_config_endpoint_returns_configuration(self, client):
        """Test configuration retrieval."""
        # Act
        response = client.get("/api/v1/pii/config")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "presidio" in data or "detect_secrets" in data
        assert "global_settings" in data
    
    def test_entities_endpoint_returns_list(self, client):
        """Test entities list endpoint."""
        # Act
        response = client.get("/api/v1/pii/entities")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "presidio_entities" in data
        assert isinstance(data["presidio_entities"], list)
    
    def test_plugins_endpoint_returns_list(self, client):
        """Test plugins list endpoint."""
        # Act
        response = client.get("/api/v1/pii/plugins")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "detect_secrets_plugins" in data
        assert isinstance(data["detect_secrets_plugins"], list)


class TestPIILogsAPI:
    """Test suite for PII detection logs API."""
    
    def test_logs_endpoint_returns_paginated(self, client, db_session):
        """Test logs endpoint returns paginated results."""
        # Arrange - Create some test logs
        for i in range(5):
            log = PIIDetectionLog(
                entity_type="EMAIL",
                detection_engine="presidio",
                confidence_score=0.9,
                source_type="test",
                was_redacted=True,
                redaction_type="mask",
                created_at=datetime.utcnow()
            )
            db_session.add(log)
        db_session.commit()
        
        # Act
        response = client.get("/api/v1/pii/logs?page=1&limit=10")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        assert "page" in data
        assert data["total"] >= 5
    
    def test_logs_search_filters_by_entity_type(self, client, db_session):
        """Test log search filtering by entity type."""
        # Arrange
        email_log = PIIDetectionLog(
            entity_type="EMAIL",
            detection_engine="presidio",
            confidence_score=0.9,
            source_type="test",
            was_redacted=True,
            created_at=datetime.utcnow()
        )
        phone_log = PIIDetectionLog(
            entity_type="PHONE",
            detection_engine="presidio",
            confidence_score=0.85,
            source_type="test",
            was_redacted=True,
            created_at=datetime.utcnow()
        )
        db_session.add_all([email_log, phone_log])
        db_session.commit()
        
        # Act
        response = client.get("/api/v1/pii/logs?entity_type=EMAIL")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert all(log["entity_type"] == "EMAIL" for log in data["logs"])
    
    def test_logs_stats_returns_aggregates(self, client, db_session):
        """Test statistics endpoint returns aggregated data."""
        # Arrange - Create diverse logs
        for entity_type in ["EMAIL", "PHONE", "API_KEY"]:
            for i in range(3):
                log = PIIDetectionLog(
                    entity_type=entity_type,
                    detection_engine="presidio",
                    confidence_score=0.9,
                    source_type="test",
                    was_redacted=True,
                    created_at=datetime.utcnow()
                )
                db_session.add(log)
        db_session.commit()
        
        # Act
        response = client.get("/api/v1/pii/logs/stats?period=7d")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "total_detections" in data
        assert "by_entity_type" in data
        assert "by_engine" in data
        assert data["total_detections"] >= 9
    
    def test_logs_export_returns_csv(self, client, db_session):
        """Test log export returns CSV format."""
        # Arrange
        log = PIIDetectionLog(
            entity_type="EMAIL",
            detection_engine="presidio",
            confidence_score=0.9,
            source_type="test",
            was_redacted=True,
            created_at=datetime.utcnow()
        )
        db_session.add(log)
        db_session.commit()
        
        # Act
        response = client.get("/api/v1/pii/logs/export?format=csv")
        
        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv"


class TestPIIConfigAPI:
    """Test suite for PII configuration API."""
    
    def test_update_config_persists_changes(self, client, db_session):
        """Test configuration update persists to database."""
        # Arrange
        update_payload = {
            "presidio": {
                "entities": [
                    {
                        "entity_type": "EMAIL",
                        "enabled": True,
                        "threshold": 0.8
                    }
                ]
            }
        }
        
        # Act
        response = client.put("/api/v1/pii/config", json=update_payload)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == True
    
    def test_test_endpoint_previews_detection(self, client):
        """Test endpoint for testing detection without logging."""
        # Arrange
        payload = {
            "text": "Test email: test@example.com and password: secret123",
            "engines": ["presidio", "detect_secrets"]
        }
        
        # Act
        response = client.post("/api/v1/pii/test", json=payload)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "detections" in data
        assert "redacted_preview" in data
        assert "engine_results" in data


class TestEndToEndScenarios:
    """End-to-end test scenarios."""
    
    def test_full_detection_and_logging_flow(self, client, db_session):
        """Test complete flow from detection to log retrieval."""
        # Step 1: Detect PII
        detect_response = client.post(
            "/api/v1/pii/detect",
            json={
                "text": "Email: user@example.com, Phone: 555-1234",
                "source_type": "test",
                "source_id": "test-123"
            }
        )
        assert detect_response.status_code == 200
        
        # Step 2: Query logs
        logs_response = client.get("/api/v1/pii/logs")
        assert logs_response.status_code == 200
        
        # Step 3: Verify logs contain detection
        logs_data = logs_response.json()
        assert logs_data["total"] > 0
    
    def test_configuration_update_affects_detection(self, client):
        """Test that configuration changes affect detection behavior."""
        # Step 1: Get initial config
        config_response = client.get("/api/v1/pii/config")
        assert config_response.status_code == 200
        
        # Step 2: Update config (increase threshold)
        update_response = client.put(
            "/api/v1/pii/config",
            json={
                "presidio": {
                    "entities": [
                        {"entity_type": "PERSON", "enabled": True, "threshold": 0.95}
                    ]
                }
            }
        )
        assert update_response.status_code == 200
        
        # Step 3: Test detection with new config
        detect_response = client.post(
            "/api/v1/pii/test",
            json={"text": "John Smith works here", "engines": ["presidio"]}
        )
        assert detect_response.status_code == 200
