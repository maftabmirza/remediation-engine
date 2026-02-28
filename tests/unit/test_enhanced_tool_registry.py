import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.agentic.enhanced_tool_registry import EnhancedToolRegistry
from app.services.agentic.tools.definitions import Tool

@pytest.fixture
def mock_db_session():
    return MagicMock()

@pytest.fixture
def mock_mcp_client():
    client = MagicMock()
    # Mock list_tools to return something so adapter works
    client.list_tools = AsyncMock(return_value=[]) 
    return client

@pytest.mark.asyncio
async def test_initialization(mock_db_session, mock_mcp_client):
    registry = EnhancedToolRegistry(mock_db_session, mcp_client=mock_mcp_client)
    # Check if parent tools are registered (we mock _register_tool calls effectively by checking internal dict)
    assert len(registry.get_tools()) > 0

@pytest.mark.asyncio
async def test_register_mcp_tools(mock_db_session, mock_mcp_client):
    # Setup MCP adapter mock to return tools
    with patch('app.services.agentic.enhanced_tool_registry.MCPToolAdapter') as MockAdapter:
        mock_adapter_instance = MockAdapter.return_value
        mock_adapter_instance.get_adapted_tools = AsyncMock(return_value=[
            Tool(name="mcp_tool_1", description="Test MCP Tool", category="troubleshooting", risk_level="read")
        ])
        
        registry = EnhancedToolRegistry(mock_db_session, mcp_client=mock_mcp_client)
        
        # Manually trigger initialization as it's async and not in __init__
        await registry.initialize()
        
        # Check if tool was added
        tool = registry.get_tool("mcp_tool_1")
        assert tool is not None
        assert tool.name == "mcp_tool_1"

@pytest.mark.asyncio
async def test_execute_mcp_tool(mock_db_session, mock_mcp_client):
    with patch('app.services.agentic.enhanced_tool_registry.MCPToolAdapter') as MockAdapter:
        mock_adapter_instance = MockAdapter.return_value
        mock_adapter_instance.get_adapted_tools = AsyncMock(return_value=[
            Tool(name="mcp_tool_1", description="Test MCP Tool", category="troubleshooting", risk_level="read")
        ])
        mock_adapter_instance.execute = AsyncMock(return_value="MCP Result")

        registry = EnhancedToolRegistry(mock_db_session, mcp_client=mock_mcp_client)
        await registry.initialize()

        result = await registry.execute("mcp_tool_1", {"arg": "val"})
        assert result == "MCP Result"
        mock_adapter_instance.execute.assert_called_once_with("mcp_tool_1", {"arg": "val"})
