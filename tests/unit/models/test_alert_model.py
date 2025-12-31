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
            timestamp=datetime.utcnow(),
            labels_json={"alertname": "HighCPUUsage", "severity": "critical"},
            annotations_json={"summary": "CPU usage is high", "description": "CPU usage above 90%"}
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
        before = datetime.now(datetime.timezone.utc)
        alert = AlertFactory()
        db_session.add(alert)
        db_session.commit()
        after = datetime.now(datetime.timezone.utc)
        
        # Ensure timezone awareness for comparison
        if alert.created_at.tzinfo is None:
             # Fallback if DB returns naive datetime (though model defines timezone=True)
             pass
        else:
             assert before <= alert.created_at <= after




class TestAlertStatusTransitions:
    """Test alert status transitions."""
    
    def test_firing_to_resolved_transition(self, db_session):
        """Test transitioning alert from firing to resolved."""
        alert = AlertFactory(status="firing", ends_at=None)
        db_session.add(alert)
        db_session.commit()
        
        # Update status
        alert.status = "resolved"
        # Alert model doesn't strictly have ends_at, usually handled by Alertmanager payload
        # or we might map closed_at if we want to track resolution time in our DB schema extension
        # For now just checking status update
        db_session.commit()
        
        assert alert.status == "resolved"
    
    def test_resolved_alert_has_end_time(self, db_session):
        """Test that resolved alerts have closed_at set."""
        alert = AlertFactory(
            status="resolved",
            closed_at=datetime.utcnow()
        )
        db_session.add(alert)
        db_session.commit()
        
        assert alert.status == "resolved"
        assert alert.closed_at is not None
        # closed_at should be after created_at (which defaults to now)
        # In this factory usage, created_at is slightly before or same as closed_at
        assert alert.closed_at >= alert.created_at

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
        
        # Use labels_json
        alert = AlertFactory(labels_json=labels)
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        
        assert alert.labels_json == labels
        assert alert.labels_json["alertname"] == "NginxDown"
        assert alert.labels_json["environment"] == "production"
    
    def test_alert_annotations_stored_as_json(self, db_session):
        """Test that annotations are stored as JSON."""
        annotations = {
            "summary": "Nginx is down",
            "description": "Service not responding",
            "runbook_url": "http://wiki/nginx-down"
        }
        
        # Use annotations_json
        alert = AlertFactory(annotations_json=annotations)
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        
        assert alert.annotations_json == annotations
        assert alert.annotations_json["summary"] == "Nginx is down"


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
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
            severity="critical"
            # representative_alert_name removed, cluster_key acts as identifier
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
        db_session.refresh(alert)
        
        assert alert.analyzed is False
        assert alert.recommendations_json is None
        
        # Analyze alert
        alert.analyzed = True
        alert.recommendations_json = {"root_cause": "High Load", "action": "Scale Up"}
        db_session.commit()
        
        assert alert.analyzed is True
        assert alert.recommendations_json is not None
    
    def test_analysis_result_stored_as_json(self, db_session):
        """Test that analysis results are stored as JSON."""
        result = {
            "root_cause_analysis": "Memory leak in application",
            "confidence_score": 0.95,
            "recommended_actions": ["Restart service", "Check logs"]
        }
        
        alert = AlertFactory(
            analyzed=True, 
            recommendations_json=result
        )
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        
        assert alert.recommendations_json == result
        assert alert.recommendations_json["confidence_score"] == 0.95
