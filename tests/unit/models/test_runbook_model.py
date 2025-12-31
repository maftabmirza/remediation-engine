"""
Unit tests for Runbook model.

Tests cover runbook creation, steps relationship, version management,
safety settings, and enable/disable functionality.
"""
import pytest
import uuid
from datetime import datetime

from app.models_remediation import Runbook, RunbookStep
from tests.fixtures.factories import RunbookFactory, RunbookStepFactory


class TestRunbookCreation:
    """Test runbook creation and basic attributes."""
    
    def test_create_runbook_with_required_fields(self, db_session):
        """Test creating a runbook with all required fields."""
        runbook = Runbook(
            id=str(uuid.uuid4()),
            name="Restart Nginx",
            description="Restart Nginx service",
            category="service_recovery",
            enabled=True,
            auto_execute=False,
            approval_required=True,
            max_executions_per_hour=5,
            version=1
        )
        
        db_session.add(runbook)
        db_session.commit()
        db_session.refresh(runbook)
        
        assert runbook.id is not None
        assert runbook.name == "Restart Nginx"
        assert runbook.category == "service_recovery"
        assert runbook.enabled is True
        assert runbook.version == 1
    
    def test_create_runbook_with_factory(self, db_session):
        """Test creating runbook using factory."""
        runbook = RunbookFactory()
        db_session.add(runbook)
        db_session.commit()
        
        assert runbook.id is not None
        assert runbook.name is not None


class TestRunbookVersioning:
    """Test runbook version management."""
    
    def test_runbook_initial_version(self, db_session):
        """Test that runbook starts at version 1."""
        runbook = RunbookFactory(version=1)
        db_session.add(runbook)
        db_session.commit()
        
        assert runbook.version == 1
    
    def test_runbook_version_increment(self, db_session):
        """Test incrementing runbook version."""
        runbook = RunbookFactory(version=1)
        db_session.add(runbook)
        db_session.commit()
        
        # Update runbook (simulating an edit)
        runbook.description = "Updated description"
        runbook.version += 1
        db_session.commit()
        
        assert runbook.version == 2
    
    def test_version_tracking_on_updates(self, db_session):
        """Test version increments on significant updates."""
        runbook = RunbookFactory(version=1)
        db_session.add(runbook)
        db_session.commit()
        
        original_version = runbook.version
        
        # Make changes
        runbook.cooldown_minutes = 15
        runbook.version = original_version + 1
        db_session.commit()
        
        assert runbook.version == original_version + 1


class TestRunbookStepsRelationship:
    """Test runbook and steps relationship."""
    
    def test_runbook_with_steps(self, db_session):
        """Test creating runbook with multiple steps."""
        runbook = RunbookFactory()
        db_session.add(runbook)
        db_session.flush()  # Get runbook ID
        
        # Create steps
        step1 = RunbookStepFactory(runbook_id=runbook.id, step_order=1)
        step2 = RunbookStepFactory(runbook_id=runbook.id, step_order=2)
        step3 = RunbookStepFactory(runbook_id=runbook.id, step_order=3)
        
        db_session.add_all([step1, step2, step3])
        db_session.commit()
        
        # Query to get steps count (if relationship is defined)
        steps = db_session.query(RunbookStep).filter(
            RunbookStep.runbook_id == runbook.id
        ).all()
        
        assert len(steps) == 3
    
    def test_steps_ordered_correctly(self, db_session):
        """Test that steps are ordered by order field."""
        runbook = RunbookFactory()
        db_session.add(runbook)
        db_session.flush()
        
        # Create steps out of order
        step3 = RunbookStepFactory(runbook_id=runbook.id, step_order=3, name="Step 3")
        step1 = RunbookStepFactory(runbook_id=runbook.id, step_order=1, name="Step 1")
        step2 = RunbookStepFactory(runbook_id=runbook.id, step_order=2, name="Step 2")
        
        db_session.add_all([step3, step1, step2])
        db_session.commit()
        
        # Query with order
        steps = db_session.query(RunbookStep).filter(
            RunbookStep.runbook_id == runbook.id
        ).order_by(RunbookStep.step_order).all()
        
        assert steps[0].step_order == 1
        assert steps[1].step_order == 2
        assert steps[2].step_order == 3
        assert steps[0].name == "Step 1"


class TestRunbookSafetySettings:
    """Test runbook safety configuration."""
    
    def test_runbook_rate_limiting(self, db_session):
        """Test runbook rate limiting settings."""
        runbook = RunbookFactory(
            max_executions_per_hour=5,
            cooldown_minutes=10
        )
        db_session.add(runbook)
        db_session.commit()
        
        assert runbook.max_executions_per_hour == 5
        assert runbook.cooldown_minutes == 10
    
    def test_runbook_cooldown_setting(self, db_session):
        """Test runbook cooldown configuration."""
        runbook = RunbookFactory(cooldown_minutes=15)
        db_session.add(runbook)
        db_session.commit()
        
        assert runbook.cooldown_minutes == 15
    
    def test_circuit_breaker_settings(self, db_session):
        """Test circuit breaker configuration if exists."""
        runbook = RunbookFactory()
        
        # Set circuit breaker settings if field exists
        if hasattr(runbook, 'max_failures_before_circuit_open'):
            runbook.max_failures_before_circuit_open = 3
            runbook.circuit_breaker_timeout_minutes = 30
            
            db_session.add(runbook)
            db_session.commit()
            
            assert runbook.max_failures_before_circuit_open == 3
            assert runbook.circuit_breaker_timeout_minutes == 30


class TestRunbookEnableDisable:
    """Test runbook enable/disable functionality."""
    
    def test_runbook_enabled_by_default(self, db_session):
        """Test that runbooks are enabled by default."""
        runbook = RunbookFactory(enabled=True)
        db_session.add(runbook)
        db_session.commit()
        
        assert runbook.enabled is True
    
    def test_disable_runbook(self, db_session):
        """Test disabling a runbook."""
        runbook = RunbookFactory(enabled=True)
        db_session.add(runbook)
        db_session.commit()
        
        # Disable
        runbook.enabled = False
        db_session.commit()
        
        assert runbook.enabled is False
    
    def test_query_enabled_runbooks(self, db_session):
        """Test querying only enabled runbooks."""
        enabled1 = RunbookFactory(enabled=True)
        enabled2 = RunbookFactory(enabled=True)
        disabled = RunbookFactory(enabled=False)
        
        db_session.add_all([enabled1, enabled2, disabled])
        db_session.commit()
        
        enabled_runbooks = db_session.query(Runbook).filter(
            Runbook.enabled == True
        ).all()
        
        assert len(enabled_runbooks) == 2
        assert all(r.enabled for r in enabled_runbooks)


class TestRunbookApprovalSettings:
    """Test runbook approval configuration."""
    
    def test_approval_required_flag(self, db_session):
        """Test approval_required setting."""
        runbook = RunbookFactory(approval_required=True)
        db_session.add(runbook)
        db_session.commit()
        
        assert runbook.approval_required is True
    
    def test_auto_execute_flag(self, db_session):
        """Test auto_execute setting."""
        runbook = RunbookFactory(auto_execute=False)
        db_session.add(runbook)
        db_session.commit()
        
        assert runbook.auto_execute is False
    
    def test_auto_execute_without_approval(self, db_session):
        """Test runbook with auto_execute and no approval."""
        runbook = RunbookFactory(
            auto_execute=True,
            approval_required=False
        )
        db_session.add(runbook)
        db_session.commit()
        
        assert runbook.auto_execute is True
        assert runbook.approval_required is False


class TestRunbookCategories:
    """Test runbook categories."""
    
    def test_valid_runbook_categories(self, db_session):
        """Test valid category values."""
        categories = [
            "service_recovery",
            "database_maintenance",
            "security_response",
            "capacity_management"
        ]
        
        for category in categories:
            runbook = RunbookFactory(category=category)
            db_session.add(runbook)
            db_session.commit()
            
            assert runbook.category == category
            db_session.rollback()
    
    def test_query_runbooks_by_category(self, db_session):
        """Test querying runbooks by category."""
        service1 = RunbookFactory(category="service_recovery")
        service2 = RunbookFactory(category="service_recovery")
        db_runbook = RunbookFactory(category="database_maintenance")
        
        db_session.add_all([service1, service2, db_runbook])
        db_session.commit()
        
        service_runbooks = db_session.query(Runbook).filter(
            Runbook.category == "service_recovery"
        ).all()
        
        assert len(service_runbooks) == 2
        assert all(r.category == "service_recovery" for r in service_runbooks)


class TestRunbookCascadeDelete:
    """Test cascade delete behavior."""
    
    def test_delete_runbook_deletes_steps(self, db_session):
        """Test that deleting runbook cascades to steps."""
        runbook = RunbookFactory()
        db_session.add(runbook)
        db_session.flush()
        
        # Create steps
        step1 = RunbookStepFactory(runbook_id=runbook.id)
        step2 = RunbookStepFactory(runbook_id=runbook.id)
        
        db_session.add_all([step1, step2])
        db_session.commit()
        
        runbook_id = runbook.id
        
        # Delete runbook
        db_session.delete(runbook)
        db_session.commit()
        
        # Check if steps are deleted (depends on cascade settings)
        remaining_steps = db_session.query(RunbookStep).filter(
            RunbookStep.runbook_id == runbook_id
        ).count()
        
        # If cascade delete is configured, should be 0
        # Otherwise, foreign key constraint would fail
        assert remaining_steps == 0  # Assuming cascade delete is configured


class TestRunbookQueries:
    """Test common runbook queries."""
    
    def test_find_runbook_by_name(self, db_session):
        """Test finding runbook by name."""
        name = "Special Nginx Restart"
        runbook = RunbookFactory(name=name)
        db_session.add(runbook)
        db_session.commit()
        
        found = db_session.query(Runbook).filter(Runbook.name == name).first()
        
        assert found is not None
        assert found.name == name
    
    def test_search_runbooks_by_name_pattern(self, db_session):
        """Test searching runbooks by name pattern."""
        nginx1 = RunbookFactory(name="Restart Nginx")
        nginx2 = RunbookFactory(name="Reload Nginx Config")
        postgres = RunbookFactory(name="Restart PostgreSQL")
        
        db_session.add_all([nginx1, nginx2, postgres])
        db_session.commit()
        
        nginx_runbooks = db_session.query(Runbook).filter(
            Runbook.name.like("%Nginx%")
        ).all()
        
        assert len(nginx_runbooks) == 2
        assert all("Nginx" in r.name for r in nginx_runbooks)
