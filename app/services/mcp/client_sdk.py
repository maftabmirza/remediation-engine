"""
MCP Client using official Python MCP SDK

This replaces our custom SSE transport implementation with the official
Python MCP SDK from Anthropic, providing battle-tested, maintained connectivity
to MCP servers like Grafana MCP.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from contextlib import AsyncExitStack

# Official MCP SDK imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client

from .types import MCPTool, MCPToolResult, MCPContent
from .exceptions import MCPError, MCPConnectionError, MCPToolError

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP Client using official Python MCP SDK.
    
    Provides a consistent interface while leveraging the official SDK
    for robust MCP protocol handling.
    """
    
    def __init__(self, server_url: str, api_token: Optional[str] = None, timeout: float = 60.0):
        """
        Initialize MCP client.
        
        Args:
            server_url: URL of the MCP server (e.g., "http://mcp-grafana:8000")
            api_token: Optional API token for authentication
            timeout: Request timeout in seconds
        """
        self.server_url = server_url
        self.api_token = api_token
        self.timeout = timeout
        self._session: Optional[ClientSession] = None
        self._connected = False
        self._exit_stack = AsyncExitStack()
    
    async def connect(self):
        """
        Connect to the MCP server using SSE transport.
        
        Raises:
            MCPConnectionError: If connection fails
        """
        try:
            logger.info(f"Connecting to MCP server at {self.server_url}")
            
            # Create headers for authentication
            headers = {}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"
            
            # Use official SDK's SSE client - it's an async context manager
            sse_context = sse_client(
                url=self.server_url,
                headers=headers if headers else None,
                timeout=self.timeout
            )
            
            # Enter the context manager to get read/write streams
            read, write = await self._exit_stack.enter_async_context(sse_context)
            
            # Create SDK client session
            self._session = ClientSession(read, write)
            await self._exit_stack.enter_async_context(self._session)
            
            # Initialize the session
            await self._session.initialize()
            
            self._connected = True
            logger.info(f"Successfully connected to MCP server at {self.server_url}")
            
        except asyncio.TimeoutError as e:
            raise MCPConnectionError(f"Timeout connecting to MCP server: {e}") from e
        except Exception as e:
            raise MCPConnectionError(f"Failed to connect to MCP server: {e}") from e
    
    async def disconnect(self):
        """Disconnect from the MCP server and cleanup resources."""
        try:
            await self._exit_stack.aclose()
            self._session = None
            self._connected = False
            logger.info("Disconnected from MCP server")
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
    
    async def initialize(self):
        """
        Initialize the MCP client (connect if not already connected).
        
        For compatibility with existing code that calls initialize().
        """
        if not self._connected:
            await self.connect()
    
    @property
    def connected(self) -> bool:
        """Check if client is connected."""
        return self._connected and self._session is not None
    
    async def list_tools(self) -> List[MCPTool]:
        """
        List available tools from the MCP server.
        
        Returns:
            List of MCPTool objects
            
        Raises:
            MCPError: If not connected or request fails
        """
        if not self._session:
            raise MCPError("Not connected to MCP server. Call connect() first.")
        
        try:
            logger.debug("Listing tools from MCP server")
            result = await self._session.list_tools()
            
            # Convert SDK tools to our MCPTool format
            tools = []
            for tool in result.tools:
                tools.append(MCPTool(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.inputSchema
                ))
            
            logger.debug(f"Found {len(tools)} tools")
            return tools
            
        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            raise MCPError(f"Failed to list tools: {e}") from e
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> MCPToolResult:
        """
        Call a tool on the MCP server.
        
        Args:
            name: Tool name
            arguments: Tool arguments as dictionary
            
        Returns:
            MCPToolResult with content and error status
            
        Raises:
            MCPToolError: If tool execution fails
        """
        if not self._session:
            raise MCPError("Not connected to MCP server. Call connect() first.")
        
        try:
            logger.debug(f"Calling tool '{name}' with arguments: {arguments}")
            result = await self._session.call_tool(name, arguments)
            
            # Convert SDK result to our MCPToolResult format
            content_items = []
            for item in result.content:
                content_items.append(MCPContent(
                    type=item.type,
                    text=getattr(item, 'text', None),
                    data=getattr(item, 'data', None),
                    mimeType=getattr(item, 'mimeType', None)
                ))
            
            tool_result = MCPToolResult(
                content=content_items,
                isError=getattr(result, 'isError', False)
            )
            
            logger.debug(f"Tool '{name}' completed successfully")
            return tool_result
            
        except Exception as e:
            logger.error(f"Tool '{name}' execution failed: {e}")
            raise MCPToolError(f"Tool execution failed: {e}") from e
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
