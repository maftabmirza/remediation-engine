import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.revive.tools.grafana_tools import GrafanaTools
from app.services.mcp.client import MCPClient
from app.services.agentic.tools.definitions import Tool

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_mcp_client():
    client = MagicMock(spec=MCPClient)
    client.call_tool = AsyncMock()
    return client

def test_tool_registration(mock_db, mock_mcp_client):
    tools_module = GrafanaTools(mock_db, mock_mcp_client)
    tools = tools_module.get_tools()
    
    assert len(tools) > 0
    tool_names = [t.name for t in tools]
    assert "search_dashboards" in tool_names
    assert "create_dashboard" in tool_names
    assert "query_prometheus" in tool_names

@pytest.mark.asyncio
async def test_search_dashboards_delegation(mock_db, mock_mcp_client):
    tools_module = GrafanaTools(mock_db, mock_mcp_client)
    
    # Mock MCP response
    mock_result = MagicMock()
    mock_result.is_error = False
    mock_result.content = [MagicMock(text="Dashboard 1")]
    mock_mcp_client.call_tool.return_value = mock_result
    
    # Execute
    result = await tools_module.execute("search_dashboards", {"query": "test"})
    
    # Verify delegation
    mock_mcp_client.call_tool.assert_called_with("dashboards/search", {"query": "test"})
    assert result == "Dashboard 1"

@pytest.mark.asyncio
async def test_mcp_error_handling(mock_db, mock_mcp_client):
    tools_module = GrafanaTools(mock_db, mock_mcp_client)
    
    # Mock MCP error
    mock_result = MagicMock()
    mock_result.is_error = True
    mock_result.content = [MagicMock(text="Auth failed")]
    mock_mcp_client.call_tool.return_value = mock_result
    
    # Execute
    result = await tools_module.execute("query_prometheus", {"query": "up"})
    
    # Verify
    assert "MCP Error: Auth failed" in result

@pytest.mark.asyncio
async def test_missing_client(mock_db):
    tools_module = GrafanaTools(mock_db, None)
    result = await tools_module.execute("search_dashboards", {})
    assert "Error: MCP Client not initialized" in result
