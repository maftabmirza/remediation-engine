"""
Unit tests for Alert model.

Tests cover alert creation, validation, status transitions, relationships,
and database constraints.
"""
import pytest
from datetime import datetime, timedelta
import uuid

from app.models import Alert, AutoAnalyzeRule as Rule, AlertCluster
from tests.fixtures.factories import AlertFactory, RuleFactory


class TestAlertCreation:
    """Test alert creation and basic attributes."""
    
    def test_create_alert_with_required_fields(self, db_session):
        """Test creating an alert with all required fields."""
        alert = Alert(
            id=str(uuid.uuid4()),
            fingerprint="test-fingerprint-123",
            alert_name="HighCPUUsage",
            severity="critical",
            instance="web-server-01",
            job="node-exporter",
            status="firing",
            summary="CPU usage is high",
            description="CPU usage above 90%",
            starts_at=datetime.utcnow(),
            labels={"alertname": "HighCPUUsage", "severity": "critical"},
            annotations={"summary": "CPU usage is high"}
        )
        
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        
        assert alert.id is not None
        assert alert.fingerprint == "test-fingerprint-123"
        assert alert.alert_name == "HighCPUUsage"
        assert alert.severity == "critical"
        assert alert.status == "firing"
        assert alert.created_at is not None
    
    def test_create_alert_with_factory(self, db_session):
        """Test creating alert using factory."""
        alert = AlertFactory()
        db_session.add(alert)
        db_session.commit()
        
        assert alert.id is not None
        assert alert.fingerprint is not None
        assert alert.alert_name is not None
    
    def test_alert_timestamps_auto_set(self, db_session):
        """Test that created_at timestamp is automatically set."""
        before = datetime.utcnow()
        alert = AlertFactory()
        db_session.add(alert)
        db_session.commit()
        after = datetime.utcnow()
        
        assert before <= alert.created_at <= after


class TestAlertFingerprint:
    """Test alert fingerprint functionality."""
    
    def test_fingerprint_uniqueness(self, db_session):
        """Test that fingerprint must be unique."""
        fingerprint = "unique-fingerprint-123"
        
        alert1 = AlertFactory(fingerprint=fingerprint)
        db_session.add(alert1)
        db_session.commit()
        
        # Try to create another alert with same fingerprint
        alert2 = AlertFactory(fingerprint=fingerprint)
        db_session.add(alert2)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()
    
    def test_fingerprint_generation(self, db_session):
        """Test that fingerprint is generated if not provided."""
        alert = AlertFactory()
        
        assert alert.fingerprint is not None
        assert len(alert.fingerprint) > 0


class TestAlertStatusTransitions:
    """Test alert status transitions."""
    
    def test_firing_to_resolved_transition(self, db_session):
        """Test transitioning alert from firing to resolved."""
        alert = AlertFactory(status="firing", ends_at=None)
        db_session.add(alert)
        db_session.commit()
        
        # Resolve the alert
        alert.status = "resolved"
        alert.ends_at = datetime.utcnow()
        db_session.commit()
        
        assert alert.status == "resolved"
        assert alert.ends_at is not None
    
    def test_resolved_alert_has_end_time(self, db_session):
        """Test that resolved alerts have ends_at set."""
        alert = AlertFactory(
            status="resolved",
            ends_at=datetime.utcnow()
        )
        db_session.add(alert)
        db_session.commit()
        
        assert alert.status == "resolved"
        assert alert.ends_at is not None
        assert alert.ends_at > alert.starts_at


class TestAlertLabelsAndAnnotations:
    """Test alert labels and annotations (JSON fields)."""
    
    def test_alert_labels_stored_as_json(self, db_session):
        """Test that labels are stored as JSON."""
        labels = {
            "alertname": "NginxDown",
            "severity": "critical",
            "instance": "web-01",
            "environment": "production"
        }
        
        alert = AlertFactory(labels=labels)
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        
        assert alert.labels == labels
        assert alert.labels["alertname"] == "NginxDown"
        assert alert.labels["environment"] == "production"
    
    def test_alert_annotations_stored_as_json(self, db_session):
        """Test that annotations are stored as JSON."""
        annotations = {
            "summary": "Nginx is down",
            "description": "Service not responding",
            "runbook_url": "http://wiki/nginx-down"
        }
        
        alert = AlertFactory(annotations=annotations)
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        
        assert alert.annotations == annotations
        assert alert.annotations["summary"] == "Nginx is down"


class TestAlertRelationships:
    """Test alert relationships with other models."""
    
    def test_alert_rule_relationship(self, db_session):
        """Test alert can be linked to a rule."""
        rule = RuleFactory()
        db_session.add(rule)
        db_session.commit()
        
        alert = AlertFactory(matched_rule_id=rule.id)
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        
        assert alert.matched_rule_id == rule.id
        # Test relationship access if defined in model
        # assert alert.matched_rule.id == rule.id
    
    def test_alert_cluster_relationship(self, db_session):
        """Test alert can belong to a cluster."""
        from app.models import AlertCluster
        
        cluster = AlertCluster(
            id=str(uuid.uuid4()),
            cluster_key="cpu-high-cluster",
            representative_alert_name="HighCPUUsage"
        )
        db_session.add(cluster)
        db_session.commit()
        
        alert = AlertFactory(cluster_id=cluster.id)
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        
        assert alert.cluster_id == cluster.id


class TestAlertValidation:
    """Test alert validation and constraints."""
    
    def test_alert_requires_fingerprint(self, db_session):
        """Test that alert requires fingerprint."""
        alert = Alert(
            id=str(uuid.uuid4()),
            # fingerprint missing
            alert_name="Test",
            severity="warning",
            instance="test",
            job="test",
            status="firing",
            starts_at=datetime.utcnow(),
            labels={},
            annotations={}
        )
        
        db_session.add(alert)
        
        with pytest.raises(Exception):  # Should raise validation error
            db_session.commit()
    
    def test_alert_severity_values(self, db_session):
        """Test valid severity values."""
        valid_severities = ["critical", "warning", "info"]
        
        for severity in valid_severities:
            alert = AlertFactory(severity=severity)
            db_session.add(alert)
            db_session.commit()
            
            assert alert.severity == severity
            db_session.rollback()  # Rollback for next iteration


class TestAlertQueries:
    """Test common alert queries."""
    
    def test_query_firing_alerts(self, db_session):
        """Test querying only firing alerts."""
        # Create mix of firing and resolved
        firing1 = AlertFactory(status="firing")
        firing2 = AlertFactory(status="firing")
        resolved = AlertFactory(status="resolved")
        
        db_session.add_all([firing1, firing2, resolved])
        db_session.commit()
        
        firing_alerts = db_session.query(Alert).filter(
            Alert.status == "firing"
        ).all()
        
        assert len(firing_alerts) == 2
        assert all(a.status == "firing" for a in firing_alerts)
    
    def test_query_alerts_by_severity(self, db_session):
        """Test querying alerts by severity."""
        critical1 = AlertFactory(severity="critical")
        critical2 = AlertFactory(severity="critical")
        warning = AlertFactory(severity="warning")
        
        db_session.add_all([critical1, critical2, warning])
        db_session.commit()
        
        critical_alerts = db_session.query(Alert).filter(
            Alert.severity == "critical"
        ).all()
        
        assert len(critical_alerts) == 2
        assert all(a.severity == "critical" for a in critical_alerts)
    
    def test_query_alerts_by_instance(self, db_session):
        """Test querying alerts by instance."""
        instance = "web-server-01"
        
        alert1 = AlertFactory(instance=instance)
        alert2 = AlertFactory(instance=instance)
        alert3 = AlertFactory(instance="other-server")
        
        db_session.add_all([alert1, alert2, alert3])
        db_session.commit()
        
        instance_alerts = db_session.query(Alert).filter(
            Alert.instance == instance
        ).all()
        
        assert len(instance_alerts) == 2
        assert all(a.instance == instance for a in instance_alerts)


class TestAlertAnalysis:
    """Test alert analysis tracking."""
    
    def test_alert_analyzed_flag(self, db_session):
        """Test tracking whether alert has been analyzed."""
        alert = AlertFactory(analyzed=False)
        db_session.add(alert)
        db_session.commit()
        
        assert alert.analyzed is False
        
        # Mark as analyzed
        alert.analyzed = True
        alert.analysis_result = {"root_cause": "Test cause"}
        db_session.commit()
        
        assert alert.analyzed is True
        assert alert.analysis_result is not None
    
    def test_analysis_result_stored_as_json(self, db_session):
        """Test that analysis result is stored as JSON."""
        analysis = {
            "root_cause": "Nginx crashed",
            "impact": "Service unavailable",
            "remediation_steps": ["Step 1", "Step 2"]
        }
        
        alert = AlertFactory(
            analyzed=True,
            analysis_result=analysis
        )
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        
        assert alert.analysis_result == analysis
        assert alert.analysis_result["root_cause"] == "Nginx crashed"
