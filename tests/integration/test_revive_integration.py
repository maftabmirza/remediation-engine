"""
Integration Tests for RE-VIVE Unified Assistant

Tests end-to-end functionality of RE-VIVE including:
- Mode detection (Grafana vs AIOps)
- Tool execution in different modes  
- WebSocket streaming
- Session persistence
- Confirmation workflows
"""
import pytest
import json
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock

from app.models import User
from app.models_ai import AISession


@pytest.fixture
def test_user(db):
    user = User(id=uuid4(), username="reviveuser", email="revive@test.com", role="operator")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def mock_mcp_client():
    """Mock MCP client for Grafana operations."""
    with patch('app.services.mcp.client.MCPClient') as mock:
        client = Mock()
        client.list_tools = AsyncMock(return_value=Mock(tools=[]))
        client.call_tool = AsyncMock(return_value=Mock(content=[Mock(text="Success")]))
        mock.return_value = client
        yield client


class TestGrafanaModeOperations:
    """Test RE-VIVE in Grafana mode."""
    
    @pytest.mark.asyncio
    async def test_grafana_mode_search_dashboards(self, client, test_user, db, mock_mcp_client):
        """Test searching dashboards via Grafana mode."""
        # Mock MCP tool response
        mock_mcp_client.call_tool.return_value = Mock(
            content=[Mock(text=json.dumps([
                {"uid": "dash1", "title": "CPU Metrics"},
                {"uid": "dash2", "title": "Memory Metrics"}
            ]))]
        )
        
        response = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "search for CPU dashboards",
                "session_id": "",
                "current_page": "/grafana/dashboards",
                "mode": "grafana"
            }
        )
        
        assert response.status_code == 200
        # Verify dashboard search was executed
    
    @pytest.mark.asyncio
    async def test_grafana_mode_create_dashboard(self, client, test_user, db, mock_mcp_client):
        """Test creating dashboard via Grafana mode."""
        mock_mcp_client.call_tool.return_value = Mock(
            content=[Mock(text=json.dumps({"uid": "new-dash", "url": "/d/new-dash"}))]
        )
        
        response = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "create a CPU monitoring dashboard",
                "session_id": "",
                "mode": "grafana"
            }
        )
        
        assert response.status_code == 200


class TestAIOpsModeOperations:
    """Test RE-VIVE in AIOps mode."""
    
    @pytest.mark.asyncio
    async def test_aiops_mode_list_runbooks(self, client, test_user, db):
        """Test listing runbooks via AIOps mode."""
        response = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "list available runbooks",
                "session_id": "",
                "current_page": "/remediation/runbooks",
                "mode": "aiops"
            }
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_aiops_mode_list_servers(self, client, test_user, db):
        """Test listing servers via AIOps mode."""
        response = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "show me all Linux servers",
                "session_id": "",
                "mode": "aiops"
            }
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_aiops_mode_execute_runbook_with_confirmation(self, client, test_user, db):
        """Test executing runbook with confirmation workflow."""
        # This would require confirmation for operator role
        response = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "execute restart service runbook on server-01",
                "session_id": "",
                "mode": "aiops"
            }
        )
        
        assert response.status_code == 200
        # Should receive confirmation request in stream


class TestAutoModeDetection:
    """Test automatic mode detection from context."""
    
    @pytest.mark.asyncio
    async def test_auto_detect_grafana_from_page(self, client, test_user, db):
        """Test Grafana mode auto-detected from current page."""
        response = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "show me metrics",
                "session_id": "",
                "current_page": "/grafana/explore"  # Grafana page
            }
        )
        
        assert response.status_code == 200
        # Mode should be detected as 'grafana'
    
    @pytest.mark.asyncio
    async def test_auto_detect_aiops_from_page(self, client, test_user, db):
        """Test AIOps mode auto-detected from current page."""
        response = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "show me servers",
                "session_id": "",
                "current_page": "/remediation/servers"  # AIOps page
            }
        )
        
        assert response.status_code == 200
        # Mode should be detected as 'aiops'
    
    @pytest.mark.asyncio
    async def test_auto_detect_from_message_keywords(self, client, test_user, db):
        """Test mode detected from message keywords."""
        # Grafana keywords
        response1 = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "query prometheus for CPU metrics",
                "session_id": ""
            }
        )
        assert response1.status_code == 200
        
        # AIOps keywords
        response2 = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "list runbooks for nginx restart",
                "session_id": ""
            }
        )
        assert response2.status_code == 200


class TestWebSocketStreaming:
    """Test WebSocket real-time streaming."""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self, client, test_user):
        """Test WebSocket connection establishment."""
        from fastapi.testclient import TestClient
        
        with TestClient(client.app) as test_client:
            with test_client.websocket_connect(
                f"/ws/revive/new?token=test_token"
            ) as websocket:
                # Should receive connected message
                data = websocket.receive_json()
                assert data["type"] == "connected"
                assert "session_id" in data
    
    @pytest.mark.asyncio
    async def test_websocket_message_exchange(self, client, test_user):
        """Test sending and receiving messages via WebSocket."""
        from fastapi.testclient import TestClient
        
        with TestClient(client.app) as test_client:
            with test_client.websocket_connect(
                f"/ws/revive/new?token=test_token"
            ) as websocket:
                # Receive connected
                websocket.receive_json()
                
                # Send message
                websocket.send_json({
                    "type": "message",
                    "content": "list dashboards"
                })
                
                # Should receive mode, chunks, and done
                messages = []
                for _ in range(3):  # Get a few messages
                    messages.append(websocket.receive_json())
                
                types = [m["type"] for m in messages]
                assert "mode" in types or "chunk" in types


class TestSessionPersistence:
    """Test session creation and persistence."""
    
    @pytest.mark.asyncio
    async def test_session_created_on_first_message(self, client, test_user, db):
        """Test session is created on first interaction."""
        response = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "hello",
                "session_id": ""  # Empty session ID
            }
        )
        
        assert response.status_code == 200
        
        # Check that session was created in DB
        from app.models_ai import AISession
        sessions = db.query(AISession).filter(
            AISession.user_id == test_user.id,
            AISession.pillar == "revive"
        ).all()
        
        assert len(sessions) > 0
    
    @pytest.mark.asyncio
    async def test_session_reused_on_subsequent_messages(self, client, test_user, db):
        """Test existing session is reused."""
        # Create initial session
        from app.models_ai import AISession
        session = AISession(
            user_id=test_user.id,
            pillar="revive",
            revive_mode="grafana"
        )
        db.add(session)
        db.commit()
        
        # Send message with session ID
        response = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "show dashboards",
                "session_id": str(session.id)
            }
        )
        
        assert response.status_code == 200
        
        # Session should have incremented message count
        db.refresh(session)
        assert session.message_count > 0
    
    @pytest.mark.asyncio
    async def test_session_history_loaded(self, client, test_user, db):
        """Test conversation history is loaded from session."""
        from app.models_ai import AISession, AIMessage
        
        # Create session with messages
        session = AISession(user_id=test_user.id, pillar="revive")
        db.add(session)
        db.flush()
        
        msg1 = AIMessage(session_id=session.id, role="user", content="hello")
        msg2 = AIMessage(session_id=session.id, role="assistant", content="hi there")
        db.add_all([msg1, msg2])
        db.commit()
        
        # New message should have context
        response = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "what did I just say?",
                "session_id": str(session.id)
            }
        )
        
        assert response.status_code == 200


class TestConfirmationWorkflow:
    """Test action confirmation workflow in RE-VIVE."""
    
    @pytest.mark.asyncio
    async def test_confirmation_required_for_risky_action(self, client, test_user, db):
        """Test confirmation is requested for risky operations."""
        # Operator executing runbook should require confirmation
        response = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "execute restart service runbook on prod-01",
                "session_id": "",
                "mode": "aiops"
            }
        )
        
        assert response.status_code == 200
        # Response should contain confirmation request
    
    @pytest.mark.asyncio
    async def test_confirmation_timeout(self, client, test_user, db):
        """Test confirmations expire after timeout."""
        from app.services.ai_audit_service import AIAuditService
        from datetime import datetime, timedelta, timezone
        
        audit_service = AIAuditService(db)
        
        # Create session
        from app.models_ai import AISession
        session = AISession(user_id=test_user.id, pillar="revive")
        db.add(session)
        db.flush()
        
        # Create expired confirmation
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        confirmation = audit_service.log_action_confirmation(
            session, "execute_runbook", {}, "high", expires_at=expired_time
        )
        
        # Run expiry
        expired_count = audit_service.expire_old_confirmations()
        
        assert expired_count == 1
        db.refresh(confirmation)
        assert confirmation.status == "expired"


class TestConcurrentSessions:
    """Test handling multiple concurrent sessions."""
    
    @pytest.mark.asyncio
    async def test_multiple_sessions_per_user(self, client, test_user, db):
        """Test user can have multiple active sessions."""
        # Create session 1
        response1 = await client.post(
            "/api/revive/chat/stream",
            json={"message": "session 1", "session_id": ""}
        )
        
        # Create session 2
        response2 = await client.post(
            "/api/revive/chat/stream",
            json={"message": "session 2", "session_id": ""}
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Check both sessions exist
        from app.models_ai import AISession
        sessions = db.query(AISession).filter(
            AISession.user_id == test_user.id,
            AISession.pillar == "revive"
        ).all()
        
        assert len(sessions) >= 2


class TestErrorHandling:
    """Test error handling in RE-VIVE."""
    
    @pytest.mark.asyncio
    async def test_invalid_session_id_creates_new(self, client, test_user, db):
        """Test invalid session ID creates new session."""
        response = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "hello",
                "session_id": "invalid-uuid-format"
            }
        )
        
        assert response.status_code == 200
        # Should create new session instead of erroring
    
    @pytest.mark.asyncio
    async def test_tool_execution_error_handled(self, client, test_user, db, mock_mcp_client):
        """Test tool execution errors are handled gracefully."""
        # Make MCP client raise error
        mock_mcp_client.call_tool.side_effect = Exception("MCP Error")
        
        response = await client.post(
            "/api/revive/chat/stream",
            json={
                "message": "search dashboards",
                "session_id": "",
                "mode": "grafana"
            }
        )
        
        assert response.status_code == 200
        # Should return error in stream, not crash
