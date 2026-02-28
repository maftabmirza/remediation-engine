import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.mcp.client import MCPClient
from app.services.mcp.exceptions import MCPConnectionError, MCPToolError, MCPRequestError
from app.services.mcp.types import MCPTool, MCPToolResult

@pytest.fixture
def mock_httpx_client():
    with patch("httpx.AsyncClient") as client_mock:
        client_instance = MagicMock()
        client_instance.post = AsyncMock()
        client_mock.return_value = client_instance
        yield client_instance

@pytest.fixture
def mcp_client():
    return MCPClient("http://test-server")

@pytest.mark.asyncio
async def test_connect_success(mcp_client, mock_httpx_client):
    # Mock SSE stream
    class MockStreamContext:
        async def __aenter__(self):
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            
            lines = [
                "event: endpoint",
                'data: "/api/message"',
                "",
                "event: data",
                'data: {"jsonrpc": "2.0", "id": "0", "result": {"serverInfo": {"name": "test-server"}}}',
                ""
            ]
            
            async def line_iterator():
                for line in lines:
                    yield line
                    await asyncio.sleep(0.01)
                while True:
                    await asyncio.sleep(1)

            mock_response.aiter_lines = line_iterator
            return mock_response

        async def __aexit__(self, exc_type, exc, tb):
            pass

    mock_httpx_client.stream.side_effect = lambda *args, **kwargs: MockStreamContext()
    mock_httpx_client.post.return_value.status_code = 202

    # Run connect
    await mcp_client.connect()
    
    assert mcp_client._connected
    assert mcp_client.transport.post_endpoint == "/api/message"
    
    await mcp_client.disconnect()

@pytest.mark.asyncio
async def test_list_tools(mcp_client, mock_httpx_client):
    # Setup connected state manually to avoid complex SSE mocking for each test
    mcp_client._connected = True
    mcp_client.transport._connected = True
    mcp_client.transport.post_endpoint = "/api/message"
    mcp_client.transport._client = mock_httpx_client
    
    # Mock sending request and receiving response via handle_message
    async def mock_post(*args, **kwargs):
        # When post is called, immediately trigger the response handler (simulating SSE return)
        request_json = kwargs['json']
        request_id = request_json['id']
        
        response_data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "test_tool",
                        "description": "A test tool",
                        "input_schema": {"type": "object"}
                    }
                ]
            }
        }
        
        # Trigger handler in background to simulate async response
        from app.services.mcp.types import JSONRPCResponse
        response_obj = JSONRPCResponse(**response_data)
        asyncio.create_task(mcp_client._handle_message(response_obj))
        
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    mock_httpx_client.post.side_effect = mock_post

    tools = await mcp_client.list_tools()
    
    assert len(tools) == 1
    assert tools[0].name == "test_tool"

@pytest.mark.asyncio
async def test_call_tool_success(mcp_client, mock_httpx_client):
    mcp_client._connected = True
    mcp_client.transport._connected = True
    mcp_client.transport.post_endpoint = "/api/message"
    mcp_client.transport._client = mock_httpx_client

    async def mock_post(*args, **kwargs):
        request_json = kwargs['json']
        request_id = request_json['id']
        
        response_data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": "Success"}],
                "isError": False
            }
        }
        
        # Simulate response object properly
        from app.services.mcp.types import JSONRPCResponse
        response_obj = JSONRPCResponse(**response_data)
        
        asyncio.create_task(mcp_client._handle_message(response_obj))
        
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    mock_httpx_client.post.side_effect = mock_post

    result = await mcp_client.call_tool("test_tool", {})
    
    assert result.isError is False
    assert result.content[0].text == "Success"

@pytest.mark.asyncio
async def test_call_tool_failure(mcp_client, mock_httpx_client):
    mcp_client._connected = True
    mcp_client.transport._connected = True
    mcp_client.transport.post_endpoint = "/api/message"
    mcp_client.transport._client = mock_httpx_client

    async def mock_post(*args, **kwargs):
        request_json = kwargs['json']
        request_id = request_json['id']
        
        # Simulate JSON-RPC error
        response_data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": "Tool failed"}
        }
        
        from app.services.mcp.types import JSONRPCResponse
        response_obj = JSONRPCResponse(**response_data)
        
        asyncio.create_task(mcp_client._handle_message(response_obj))
        
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    mock_httpx_client.post.side_effect = mock_post

    with pytest.raises(MCPToolError):
        await mcp_client.call_tool("test_tool", {})
