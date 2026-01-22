import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.ai_audit_service import AIAuditService, AIActivitySummary, ToolUsageStats
from app.models import User
from app.models_ai import AISession, AIToolExecution, AIActionConfirmation


@pytest.fixture
def audit_service(db):
    return AIAuditService(db)


@pytest.fixture
def test_user(db):
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        role="operator"
    )
    db.add(user)
    db.commit()
    return user


def test_log_session_start(audit_service, test_user, db):
    """Test logging session start."""
    session = audit_service.log_session_start(
        user=test_user,
        pillar="inquiry",
        context_type="alert",
        context_id=uuid4()
    )
    
    assert session.id is not None
    assert session.user_id == test_user.id
    assert session.pillar == "inquiry"
    assert session.started_at is not None
    assert session.ended_at is None
    assert session.message_count == 0


def test_log_session_end(audit_service, test_user, db):
    """Test logging session end."""
    session = audit_service.log_session_start(test_user, "troubleshooting")
    
    audit_service.log_session_end(session)
    
    db.refresh(session)
    assert session.ended_at is not None
    assert session.ended_at > session.started_at


def test_increment_message_count(audit_service, test_user, db):
    """Test incrementing message count."""
    session = audit_service.log_session_start(test_user, "revive", revive_mode="grafana")
    
    audit_service.increment_message_count(session)
    audit_service.increment_message_count(session)
    
    db.refresh(session)
    assert session.message_count == 2


def test_log_tool_execution(audit_service, test_user, db):
    """Test logging tool execution."""
    session = audit_service.log_session_start(test_user, "inquiry")
    
    execution = audit_service.log_tool_execution(
        session=session,
        tool_name="query_alerts_history",
        tool_category="inquiry",
        arguments={"severity": "critical", "limit": 100},
        result="Found 5 alerts",
        status="success",
        execution_time_ms=250,
        permission_required="inquiry.query",
        permission_granted=True
    )
    
    assert execution.id is not None
    assert execution.session_id == session.id
    assert execution.user_id == test_user.id
    assert execution.tool_name == "query_alerts_history"
    assert execution.tool_category == "inquiry"
    assert execution.result_status == "success"
    assert execution.execution_time_ms == 250
    assert execution.permission_granted is True


def test_log_tool_execution_denied(audit_service, test_user, db):
    """Test logging denied tool execution."""
    session = audit_service.log_session_start(test_user, "revive", revive_mode="aiops")
    
    execution = audit_service.log_tool_execution(
        session=session,
        tool_name="delete_dashboard",
        tool_category="grafana",
        arguments={"uid": "test123"},
        result="Permission denied",
        status="denied",
        execution_time_ms=10,
        permission_required="grafana.delete",
        permission_granted=False
    )
    
    assert execution.result_status == "denied"
    assert execution.permission_granted is False


def test_log_action_confirmation(audit_service, test_user, db):
    """Test logging action confirmation."""
    session = audit_service.log_session_start(test_user, "revive", revive_mode="aiops")
    
    confirmation = audit_service.log_action_confirmation(
        session=session,
        action_type="execute_runbook",
        action_details={"runbook_id": "run-123", "server": "prod-web-01"},
        risk_level="high"
    )
    
    assert confirmation.id is not None
    assert confirmation.session_id == session.id
    assert confirmation.user_id == test_user.id
    assert confirmation.action_type == "execute_runbook"
    assert confirmation.risk_level == "high"
    assert confirmation.status == "pending"
    assert confirmation.expires_at is not None


def test_update_confirmation_decision(audit_service, test_user, db):
    """Test updating confirmation decision."""
    session = audit_service.log_session_start(test_user, "revive", revive_mode="grafana")
    
    confirmation = audit_service.log_action_confirmation(
        session=session,
        action_type="delete_dashboard",
        action_details={"uid": "dash-123"},
        risk_level="medium"
    )
    
    updated = audit_service.update_confirmation_decision(confirmation.id, "approved")
    
    assert updated.status == "approved"
    assert updated.user_decision == "approved"
    assert updated.decided_at is not None


def test_get_user_ai_activity(audit_service, test_user, db):
    """Test getting user activity summary."""
    # Create multiple sessions with different pillars
    session1 = audit_service.log_session_start(test_user, "inquiry")
    audit_service.increment_message_count(session1)
    audit_service.increment_message_count(session1)
    
    session2 = audit_service.log_session_start(test_user, "troubleshooting")
    audit_service.increment_message_count(session2)
    
    # Add tool executions
    audit_service.log_tool_execution(
        session1, "query_alerts", "inquiry", {}, "success", "success", 100
    )
    audit_service.log_tool_execution(
        session1, "get_mttr", "inquiry", {}, "success", "success", 150
    )
    
    # Get activity
    activity = audit_service.get_user_ai_activity(test_user.id, days=30)
    
    assert len(activity) == 2
    
    inquiry_activity = next(a for a in activity if a.pillar == "inquiry")
    assert inquiry_activity.session_count == 1
    assert inquiry_activity.message_count == 2
    assert inquiry_activity.tool_execution_count == 2
    assert inquiry_activity.total_execution_time_ms == 250


def test_get_user_ai_activity_filtered(audit_service, test_user, db):
    """Test getting user activity filtered by pillar."""
    audit_service.log_session_start(test_user, "inquiry")
    audit_service.log_session_start(test_user, "troubleshooting")
    
    activity = audit_service.get_user_ai_activity(test_user.id, pillar="inquiry")
    
    assert len(activity) == 1
    assert activity[0].pillar == "inquiry"


def test_get_tool_usage_stats(audit_service, test_user, db):
    """Test getting tool usage statistics."""
    session = audit_service.log_session_start(test_user, "inquiry")
    
    # Log multiple tool executions
    audit_service.log_tool_execution(
        session, "query_alerts", "inquiry", {}, "success", "success", 100
    )
    audit_service.log_tool_execution(
        session, "query_alerts", "inquiry", {}, "success", "success", 120
    )
    audit_service.log_tool_execution(
        session, "get_mttr", "inquiry", {}, "success", "success", 200
    )
    audit_service.log_tool_execution(
        session, "get_trends", "inquiry", {}, "error", "error", 50
    )
    
    stats = audit_service.get_tool_usage_stats(days=30)
    
    assert stats.total_executions == 4
    assert stats.unique_tools == 3
    assert stats.success_rate == 75.0  # 3 success out of 4
    assert stats.avg_execution_time_ms == 117.5  # (100+120+200+50)/4
    assert len(stats.top_tools) > 0
    assert stats.top_tools[0]['name'] == 'query_alerts'
    assert stats.top_tools[0]['count'] == 2
    assert stats.by_status['success'] == 3
    assert stats.by_status['error'] == 1


def test_get_pending_confirmations(audit_service, test_user, db):
    """Test getting pending confirmations."""
    session = audit_service.log_session_start(test_user, "revive", revive_mode="aiops")
    
    # Create pending confirmation
    conf1 = audit_service.log_action_confirmation(
        session, "execute_runbook", {}, "high"
    )
    
    # Create approved confirmation
    conf2 = audit_service.log_action_confirmation(
        session, "delete_dashboard", {}, "medium"
    )
    audit_service.update_confirmation_decision(conf2.id, "approved")
    
    # Create expired confirmation
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    conf3 = audit_service.log_action_confirmation(
        session, "update_rule", {}, "low", expires_at=expired_time
    )
    
    pending = audit_service.get_pending_confirmations(test_user.id)
    
    assert len(pending) == 1
    assert pending[0].id == conf1.id
    assert pending[0].status == "pending"


def test_expire_old_confirmations(audit_service, test_user, db):
    """Test expiring old confirmations."""
    session = audit_service.log_session_start(test_user, "revive", revive_mode="grafana")
    
    # Create expired confirmation
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    conf = audit_service.log_action_confirmation(
        session, "delete_dashboard", {}, "high", expires_at=expired_time
    )
    
    count = audit_service.expire_old_confirmations()
    
    assert count == 1
    
    db.refresh(conf)
    assert conf.status == "expired"
    assert conf.decided_at is not None


def test_tool_usage_stats_empty(audit_service, db):
    """Test tool usage stats with no data."""
    stats = audit_service.get_tool_usage_stats(days=30)
    
    assert stats.total_executions == 0
    assert stats.unique_tools == 0
    assert stats.success_rate == 0.0
    assert stats.avg_execution_time_ms == 0.0
    assert len(stats.top_tools) == 0
    assert len(stats.by_pillar) == 0
    assert len(stats.by_status) == 0


def test_user_activity_no_sessions(audit_service, test_user, db):
    """Test user activity with no sessions."""
    activity = audit_service.get_user_ai_activity(test_user.id)
    
    assert len(activity) == 0
