import asyncio
import logging
from typing import Optional, Dict, Any, List
from .transport import SSETransport
from .types import (
    JSONRPCRequest, JSONRPCResponse, MCPTool, 
    MCPToolResult, MCPContent, MCPToolParameter
)
from .exceptions import MCPError, MCPRequestError, MCPToolError

logger = logging.getLogger(__name__)

class MCPClient:
    """
    Client for communicating with an MCP server (e.g., Grafana MCP).
    """
    def __init__(self, server_url: str, api_token: Optional[str] = None, timeout: float = 60.0):
        self.transport = SSETransport(server_url, api_token, timeout)
        self._request_id = 0
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._connected = False

    async def connect(self):
        """Connects to the MCP server."""
        await self.transport.connect(self._handle_message)
        self._connected = True
        
        # Initialize handshake
        await self._initialize()

    async def disconnect(self):
        """Disconnects from the server."""
        await self.transport.disconnect()
        self._connected = False
        # Cancel all pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()

    async def list_tools(self) -> List[MCPTool]:
        """Lists available tools from the MCP server."""
        response = await self._send_request("tools/list")
        
        tools_data = response.get("tools", [])
        return [MCPTool(**tool) for tool in tools_data]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> MCPToolResult:
        """Calls a tool on the MCP server."""
        try:
            result_data = await self._send_request("tools/call", {
                "name": name,
                "arguments": arguments
            })
            return MCPToolResult(**result_data)
        except MCPError as e:
            # Wrap in tool error if it's application level
            raise MCPToolError(f"Tool execution failed: {e}") from e

    async def _initialize(self):
        """Performs the MCP initialization handshake."""
        # Standard MCP initialization
        # Client sends 'initialize' with protocol version and capabilities
        # Server responds with its info
        
        init_params = {
            "protocolVersion": "2024-11-05", # Example version, adjust as needed
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {}
            },
            "clientInfo": {
                "name": "remediate-engine-client",
                "version": "1.0.0"
            }
        }
        
        result = await self._send_request("initialize", init_params)
        logger.info(f"MCP Initialized. Server: {result.get('serverInfo', {}).get('name')}")
        
        # Send initialized notification
        await self._send_notification("notifications/initialized")

    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Sends a JSON-RPC request and waits for the response."""
        if not self._connected:
            raise MCPError("Client not connected")

        request_id = str(self._request_id)
        self._request_id += 1
        
        request = JSONRPCRequest(
            method=method,
            params=params,
            id=request_id
        )
        
        future = asyncio.get_running_loop().create_future()
        self._pending_requests[request_id] = future
        
        try:
            await self.transport.send(request)
            return await future
        except Exception:
            self._pending_requests.pop(request_id, None)
            raise

    async def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """Sends a JSON-RPC notification (no response expected)."""
        # Per JSON-RPC 2.0 spec, notifications omit the 'id' field
        request = JSONRPCRequest(
            method=method,
            params=params,
            id=None  # Notifications have no ID
        )
        await self.transport.send(request)

    async def _handle_message(self, response: JSONRPCResponse):
        """Handles incoming JSON-RPC messages."""
        request_id = str(response.id)
        
        if request_id in self._pending_requests:
            future = self._pending_requests.pop(request_id)
            if not future.done():
                if response.error:
                    future.set_exception(MCPRequestError(f"RPC Error: {response.error}"))
                else:
                    future.set_result(response.result)
        else:
            # Might be a server notification or request (reversed direction)
            # Not fully implemented yet
            pass
