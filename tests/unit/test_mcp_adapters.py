import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.agentic.tools.mcp_adapters import MCPToolAdapter, SiftAdapter, OnCallAdapter
from app.services.mcp.types import MCPTool as MCPToolDef, MCPToolResult, MCPContent

@pytest.fixture
def mock_mcp_client():
    client = MagicMock()
    client.list_tools = AsyncMock()
    client.call_tool = AsyncMock()
    return client

@pytest.fixture
def mcp_adapter(mock_mcp_client):
    return MCPToolAdapter(mock_mcp_client)

@pytest.mark.asyncio
async def test_get_adapted_tools(mcp_adapter, mock_mcp_client):
    # Mock MCP tools
    mock_mcp_client.list_tools.return_value = [
        MCPToolDef(
            name="test_tool",
            description="A test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "Parameter 1"}
                }
            }
        )
    ]

    tools = await mcp_adapter.get_adapted_tools()
    
    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "test_tool"
    assert tool.description == "A test tool"
    assert tool.category == "troubleshooting"
    assert len(tool.parameters) == 1
    assert tool.parameters[0].name == "param1"
    assert tool.parameters[0].type == "string"

@pytest.mark.asyncio
async def test_execute_tool(mcp_adapter, mock_mcp_client):
    # Mock execution result
    mock_mcp_client.call_tool.return_value = MCPToolResult(
        content=[MCPContent(type="text", text="Tool execution result")],
        is_error=False
    )

    result = await mcp_adapter.execute("test_tool", {"arg": "value"})
    
    assert result == "Tool execution result"
    mock_mcp_client.call_tool.assert_called_once_with("test_tool", {"arg": "value"})

@pytest.mark.asyncio
async def test_sift_adapter_investigate(mcp_adapter, mock_mcp_client):
    sift_adapter = SiftAdapter(mcp_adapter)
    
    mock_mcp_client.call_tool.return_value = MCPToolResult(
        content=[MCPContent(type="text", text="Sift analysis result")],
        is_error=False
    )

    await sift_adapter.investigate_errors("app-1", "start", "end")
    
    mock_mcp_client.call_tool.assert_called_once_with(
        "investigate_sift",
        {
            "app_name": "app-1",
            "start_time": "start",
            "end_time": "end",
            "investigation_type": "errors"
        }
    )

@pytest.mark.asyncio
async def test_oncall_adapter_schedule(mcp_adapter, mock_mcp_client):
    oncall_adapter = OnCallAdapter(mcp_adapter)
    
    mock_mcp_client.call_tool.return_value = MCPToolResult(
        content=[MCPContent(type="text", text="OnCall schedule")],
        is_error=False
    )

    await oncall_adapter.get_schedule("team-a")
    
    mock_mcp_client.call_tool.assert_called_once_with(
        "get_oncall_schedule",
        {"team": "team-a"}
    )
