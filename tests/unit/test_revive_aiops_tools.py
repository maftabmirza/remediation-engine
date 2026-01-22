import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4

from app.services.revive.tools.aiops_tools import AIOpsTools
from app.models import ServerCredential
from app.models_remediation import Runbook, RunbookExecution

@pytest.fixture
def mock_db():
    db = MagicMock()
    # Mock execute().scalars().all() chain
    db.execute.return_value.scalars.return_value.all.return_value = []
    # Mock execute().scalar_one_or_none()
    db.execute.return_value.scalar_one_or_none.return_value = None
    return db

@pytest.mark.asyncio
async def test_list_servers(mock_db):
    tools = AIOpsTools(mock_db, None)
    
    server = ServerCredential(hostname="server1.example.com", os_type="linux", environment="prod")
    mock_db.execute.return_value.scalars.return_value.all.return_value = [server]
    
    result = await tools.execute("list_servers", {})
    assert "server1.example.com" in result
    assert "linux" in result

@pytest.mark.asyncio
async def test_list_runbooks(mock_db):
    tools = AIOpsTools(mock_db, None)
    
    runbook = Runbook(name="Restart Nginx", description="Restarts Nginx service", category="web")
    mock_db.execute.return_value.scalars.return_value.all.return_value = [runbook]
    
    result = await tools.execute("list_runbooks", {"keyword": "restart"})
    assert "Restart Nginx" in result

@pytest.mark.asyncio
async def test_execute_runbook_success(mock_db):
    tools = AIOpsTools(mock_db, None)
    
    # Mock dependent data
    runbook_id = uuid4()
    runbook = Runbook(id=runbook_id, name="Restart Nginx")
    
    server_id = uuid4()
    server = ServerCredential(id=server_id, hostname="web01")
    
    # Setup mocks for resolution
    # First call for runbook, second for server
    mock_db.execute.return_value.scalar_one_or_none.side_effect = [runbook, server]
    
    result = await tools.execute("execute_runbook", {
        "runbook_name": "Restart Nginx",
        "target_server": "web01"
    })
    
    assert "queued successfully" in result
    # Verify DB add/commit
    assert mock_db.add.called
    assert mock_db.commit.called
    
    # Verify created execution
    created = mock_db.add.call_args[0][0]
    assert isinstance(created, RunbookExecution)
    assert created.runbook_id == runbook_id
    assert created.server_id == server_id
    assert created.status == "queued"

@pytest.mark.asyncio
async def test_execute_runbook_not_found(mock_db):
    tools = AIOpsTools(mock_db, None)
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    
    result = await tools.execute("execute_runbook", {"runbook_name": "Missing", "target_server": "web01"})
    assert "Error: Runbook 'Missing' not found" in result
