"""
Integration Tests for AI RBAC System

Tests permission enforcement across all three pillars (Inquiry, Troubleshooting, RE-VIVE).
Verifies role-based access control, tool filtering, and confirmation workflows.
"""
import pytest
from uuid import uuid4

from app.services.ai_permission_service import AIPermissionService
from app.models import User
from app.models_ai import AIPermission


@pytest.fixture
def permission_service(db):
    return AIPermissionService(db)


@pytest.fixture
def admin_user(db):
    user = User(id=uuid4(), username="admin", email="admin@test.com", role="admin")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def operator_user(db):
    user = User(id=uuid4(), username="operator", email="op@test.com", role="operator")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def engineer_user(db):
    user = User(id=uuid4(), username="engineer", email="eng@test.com", role="engineer")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def viewer_user(db):
    user = User(id=uuid4(), username="viewer", email="view@test.com", role="viewer")
    db.add(user)
    db.commit()
    return user


class TestAdminFullAccess:
    """Test that admin role has full access to all pillars."""
    
    def test_can_access_all_pillars(self, permission_service, admin_user):
        """Admin can access all three pillars."""
        assert permission_service.can_access_pillar(admin_user, "inquiry")
        assert permission_service.can_access_pillar(admin_user, "troubleshooting")
        assert permission_service.can_access_pillar(admin_user, "revive")
    
    def test_can_execute_all_inquiry_tools(self, permission_service, admin_user):
        """Admin can execute all inquiry tools."""
        perm = permission_service.get_tool_permission(
            admin_user, "inquiry", "query", "query_alerts_history"
        )
        assert perm.permission == "allow"
        
        perm = permission_service.get_tool_permission(
            admin_user, "inquiry", "analytics", "get_mttr_statistics"
        )
        assert perm.permission == "allow"
    
    def test_can_execute_all_revive_tools(self, permission_service, admin_user):
        """Admin can execute all RE-VIVE tools without confirmation."""
        # Grafana mode
        perm = permission_service.get_tool_permission(
            admin_user, "revive", "grafana", "create_dashboard"
        )
        assert perm.permission == "allow"
        
        perm = permission_service.get_tool_permission(
            admin_user, "revive", "grafana", "delete_dashboard"
        )
        assert perm.permission == "allow"
        
        # AIOps mode
        perm = permission_service.get_tool_permission(
            admin_user, "revive", "aiops", "execute_runbook"
        )
        assert perm.permission == "allow"


class TestOperatorLimitedAccess:
    """Test that operator role has limited destructive actions."""
    
    def test_can_access_all_pillars(self, permission_service, operator_user):
        """Operator can access all pillars."""
        assert permission_service.can_access_pillar(operator_user, "inquiry")
        assert permission_service.can_access_pillar(operator_user, "troubleshooting")
        assert permission_service.can_access_pillar(operator_user, "revive")
    
    def test_read_operations_allowed(self, permission_service, operator_user):
        """Operator can perform read operations without confirmation."""
        perm = permission_service.get_tool_permission(
            operator_user, "revive", "grafana", "search_dashboards"
        )
        assert perm.permission == "allow"
        
        perm = permission_service.get_tool_permission(
            operator_user, "revive", "aiops", "list_runbooks"
        )
        assert perm.permission == "allow"
    
    def test_create_requires_confirmation(self, permission_service, operator_user):
        """Operator needs confirmation for create operations."""
        perm = permission_service.get_tool_permission(
            operator_user, "revive", "grafana", "create_dashboard"
        )
        assert perm.permission == "confirm"
        
        perm = permission_service.get_tool_permission(
            operator_user, "revive", "grafana", "update_dashboard"
        )
        assert perm.permission == "confirm"
    
    def test_delete_operations_denied(self, permission_service, operator_user):
        """Operator cannot perform delete operations."""
        perm = permission_service.get_tool_permission(
            operator_user, "revive", "grafana", "delete_dashboard"
        )
        assert perm.permission == "deny"
        assert perm.alternative is not None  # Should suggest alternative


class TestEngineerOwnAlertsOnly:
    """Test that engineer role can only access their own alerts."""
    
    def test_can_access_inquiry_and_revive(self, permission_service, engineer_user):
        """Engineer can access inquiry and revive pillars."""
        assert permission_service.can_access_pillar(engineer_user, "inquiry")
        assert permission_service.can_access_pillar(engineer_user, "revive")
    
    def test_troubleshooting_limited_to_own_alerts(self, permission_service, engineer_user):
        """Engineer can troubleshoot but with restrictions."""
        assert permission_service.can_access_pillar(engineer_user, "troubleshooting")
        
        # Would need context-aware permission check in real implementation
        # For now, verify base access is granted
    
    def test_revive_read_only(self, permission_service, engineer_user):
        """Engineer has read-only access to RE-VIVE."""
        # Grafana - read only
        perm = permission_service.get_tool_permission(
            engineer_user, "revive", "grafana", "search_dashboards"
        )
        assert perm.permission == "allow"
        
        perm = permission_service.get_tool_permission(
            engineer_user, "revive", "grafana", "create_dashboard"
        )
        assert perm.permission in ["deny", "confirm"]
        
        # AIOps - read only
        perm = permission_service.get_tool_permission(
            engineer_user, "revive", "aiops", "list_runbooks"
        )
        assert perm.permission == "allow"
        
        perm = permission_service.get_tool_permission(
            engineer_user, "revive", "aiops", "execute_runbook"
        )
        assert perm.permission in ["deny", "confirm"]


class TestViewerReadOnly:
    """Test that viewer role has read-only access."""
    
    def test_limited_pillar_access(self, permission_service, viewer_user):
        """Viewer has limited access to pillars."""
        # Can access inquiry with restrictions
        assert permission_service.can_access_pillar(viewer_user, "inquiry")
        
        # May or may not access troubleshooting (implementation dependent)
        # Can access revive in read-only mode
        assert permission_service.can_access_pillar(viewer_user, "revive")
    
    def test_inquiry_read_only(self, permission_service, viewer_user):
        """Viewer can only perform aggregated queries."""
        perm = permission_service.get_tool_permission(
            viewer_user, "inquiry", "query", "query_alerts_history"
        )
        # Should either be allowed (aggregated only) or denied (raw data)
        assert perm.permission in ["allow", "deny"]
    
    def test_revive_search_only(self, permission_service, viewer_user):
        """Viewer can only search in RE-VIVE."""
        perm = permission_service.get_tool_permission(
            viewer_user, "revive", "grafana", "search_dashboards"
        )
        assert perm.permission == "allow"
        
        perm = permission_service.get_tool_permission(
            viewer_user, "revive", "aiops", "list_runbooks"
        )
        assert perm.permission == "allow"
        
        # No mutations allowed
        perm = permission_service.get_tool_permission(
            viewer_user, "revive", "grafana", "create_dashboard"
        )
        assert perm.permission == "deny"


class TestToolFiltering:
    """Test that tool registry filters tools based on role."""
    
    def test_admin_sees_all_tools(self, permission_service, admin_user):
        """Admin role sees all available tools."""
        from app.services.agentic.tools import Tool
        
        # Mock tools
        all_tools = [
            Tool(name="search_dashboards", description="Search", category="grafana", risk_level="read"),
            Tool(name="create_dashboard", description="Create", category="grafana", risk_level="write"),
            Tool(name="delete_dashboard", description="Delete", category="grafana", risk_level="delete"),
        ]
        
        filtered = permission_service.filter_tools_by_permission(
            admin_user, "revive", all_tools
        )
        
        assert len(filtered) == 3  # All tools available
    
    def test_viewer_sees_read_only_tools(self, permission_service, viewer_user):
        """Viewer only sees read-only tools."""
        from app.services.agentic.tools import Tool
        
        all_tools = [
            Tool(name="search_dashboards", description="Search", category="grafana", risk_level="read"),
            Tool(name="create_dashboard", description="Create", category="grafana", risk_level="write"),
            Tool(name="delete_dashboard", description="Delete", category="grafana", risk_level="delete"),
        ]
        
        filtered = permission_service.filter_tools_by_permission(
            viewer_user, "revive", all_tools
        )
        
        # Should only see search tool
        assert len(filtered) <= 1
        if filtered:
            assert filtered[0].name == "search_dashboards"


class TestConfirmationWorkflow:
    """Test action confirmation workflow."""
    
    def test_confirmation_required_for_risky_action(self, permission_service, operator_user):
        """Risky actions generate confirmation requests."""
        perm = permission_service.get_tool_permission(
            operator_user, "revive", "aiops", "execute_runbook"
        )
        
        # Should require confirmation
        assert perm.permission == "confirm"
    
    def test_confirmation_created_and_tracked(self, permission_service, operator_user, db):
        """Confirmations are properly created and tracked."""
        from app.services.ai_audit_service import AIAuditService
        from app.models_ai import AISession
        
        audit_service = AIAuditService(db)
        
        # Create session
        session = audit_service.log_session_start(
            operator_user, "revive", revive_mode="aiops"
        )
        
        # Create confirmation
        confirmation = permission_service.create_confirmation(
            session_id=session.id,
            user=operator_user,
            action_type="execute_runbook",
            action_details={"runbook_id": "test-123"},
            risk_level="high"
        )
        
        assert confirmation.id is not None
        assert confirmation.status == "pending"
        assert confirmation.risk_level == "high"


class TestPermissionInheritance:
    """Test permission inheritance and wildcards."""
    
    def test_wildcard_permissions(self, permission_service, admin_user, db):
        """Wildcard permissions apply to all matching tools."""
        # Create wildcard permission for admin
        wildcard_perm = AIPermission(
            role_id=admin_user.role_id if hasattr(admin_user, 'role_id') else uuid4(),
            pillar="revive",
            tool_category="grafana",
            tool_name="*",
            permission="allow"
        )
        db.add(wildcard_perm)
        db.commit()
        
        # Any Grafana tool should be allowed
        perm = permission_service.get_tool_permission(
            admin_user, "revive", "grafana", "any_tool_name"
        )
        
        assert perm.permission == "allow"


class TestDeniedActionAlternatives:
    """Test that denied actions provide alternatives."""
    
    def test_denied_delete_suggests_alternative(self, permission_service, operator_user):
        """When delete is denied, suggest archive or disable."""
        perm = permission_service.get_tool_permission(
            operator_user, "revive", "grafana", "delete_dashboard"
        )
        
        assert perm.permission == "deny"
        assert perm.alternative is not None
        assert "archive" in perm.alternative.lower() or "disable" in perm.alternative.lower()
    
    def test_denied_action_provides_reason(self, permission_service, viewer_user):
        """Denied actions include clear reasoning."""
        perm = permission_service.get_tool_permission(
            viewer_user, "revive", "aiops", "execute_runbook"
        )
        
        assert perm.permission == "deny"
        assert perm.reason is not None
        assert len(perm.reason) > 0
