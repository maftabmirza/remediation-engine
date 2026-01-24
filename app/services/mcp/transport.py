import asyncio
import json
import logging
import httpx
from typing import Optional, Dict, Any, Callable, Awaitable
from .types import JSONRPCRequest, JSONRPCResponse
from .exceptions import MCPConnectionError, MCPProtocolError, MCPRequestError

logger = logging.getLogger(__name__)

class SSETransport:
    """
    Handles Server-Sent Events (SSE) transport for MCP.
    Connects to an SSE endpoint for receiving messages and uses a POST endpoint for sending.
    """
    def __init__(self, base_url: str, api_token: Optional[str] = None, timeout: float = 60.0):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self.post_endpoint: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._message_handler: Optional[Callable[[JSONRPCResponse], Awaitable[None]]] = None
        self._connected = False

    async def connect(self, message_handler: Callable[[JSONRPCResponse], Awaitable[None]]):
        """
        Connects to the SSE endpoint and starts listening for events.
        """
        self._message_handler = message_handler
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._get_headers()
        )
        
        try:
            # Start SSE connection
            # We don't await the infinite loop here; we start it as a background task
            self._listen_task = asyncio.create_task(self._listen_loop())
            
            # Wait for connection to be established (session_id received)
            # In a real implementation, we might use an asyncio.Event
            # For now, let's wait a bit for the initial handshake if needed
            # But standardized MCP over SSE usually gives the POST endpoint in the first event
            
            # Wait for the post_endpoint to be set by the listener
            for _ in range(50): # Wait up to 5 seconds
                if self.post_endpoint:
                    self._connected = True
                    return
                await asyncio.sleep(0.1)
                if self._listen_task.done():
                     # Check if task failed
                    try:
                        self._listen_task.result()
                    except Exception as e:
                        raise MCPConnectionError(f"SSE connection failed immediately: {e}")
                    break
            
            if not self.post_endpoint:
                raise MCPConnectionError("Timed out waiting for MCP endpoint discovery")

        except Exception as e:
            await self.disconnect()
            raise MCPConnectionError(f"Failed to connect to MCP server: {e}")

    async def disconnect(self):
        """Disconnects and cleans up resources."""
        self._connected = False
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None
        
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send(self, request: JSONRPCRequest):
        """Sends a JSON-RPC request to the discovered POST endpoint."""
        if not self._connected or not self.post_endpoint:
            raise MCPConnectionError("Not connected to MCP server")
        
        if not self._client:
             raise MCPConnectionError("Client is not initialized")

        try:
            # Construct full URL if endpoint is relative path
            url = self.post_endpoint
            if not url.startswith('http'):
                 url = f"{self.base_url}{url}"

            # The post_endpoint already contains sessionId in the URL from SSE
            # Don't add session_id as separate param - it's already in the URL
            response = await self._client.post(
                url,
                json=request.model_dump()
            )
            response.raise_for_status()
            
            # Note: The response might be just "Accepted" (202), and the actual result comes via SSE
            # Or it might return the result directly.
            # Standard MCP over SSE typically returns 202 and sends response over SSE.
            
        except httpx.HTTPError as e:
            raise MCPRequestError(f"Failed to send request: {e}")

    async def _listen_loop(self):
        """Background task to listen for SSE events."""
        if not self._client:
            return

        sse_url = f"{self.base_url}/sse"
        
        try:
            async with self._client.stream("GET", sse_url) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        event_type = line.split(":", 1)[1].strip()
                        # Read next line for data
                        # This is a simplified SSE parser
                        continue 
                        
                    if line.startswith("data:"):
                        data_str = line.split(":", 1)[1].strip()
                        await self._handle_sse_event(data_str)
                        
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"SSE Listener error: {e}")
            self._connected = False
            # In a real app, implement reconnection logic here

    async def _handle_sse_event(self, data_str: str):
        """Parses SSE data and routes it."""
        try:
            # First check if this looks like an endpoint URL (plain text, not JSON)
            # MCP servers often send the POST endpoint as plain text: "/message?sessionId=..."
            if data_str.startswith('/'):
                # This is the endpoint URL for sending POST requests
                logger.info(f"Discovered MCP POST endpoint: {data_str}")
                self.post_endpoint = data_str
                # Extract session ID if present for reference
                if 'sessionId=' in data_str:
                    import re
                    match = re.search(r'sessionId=([^&]+)', data_str)
                    if match:
                        self.session_id = match.group(1)
                        logger.debug(f"Extracted session ID: {self.session_id}")
                return
            
            # Try to parse as JSON
            data = json.loads(data_str)
            
            if "jsonrpc" in data:
                response = JSONRPCResponse(**data)
                if self._message_handler:
                    await self._message_handler(response)
            else:
                # Might be endpoint info in JSON format: {"endpoint": "/message?..."}
                if isinstance(data, dict) and "endpoint" in data:
                    self.post_endpoint = data["endpoint"]
                    logger.info(f"Discovered MCP POST endpoint from JSON: {self.post_endpoint}")
                      
        except json.JSONDecodeError:
            # Plain text that doesn't start with '/' - might be a message endpoint
            if 'message' in data_str.lower() or 'session' in data_str.lower():
                logger.info(f"Handling potential endpoint as plain text: {data_str}")
                self.post_endpoint = data_str
            else:
                logger.warning(f"Received non-JSON SSE data: {data_str}")
        except Exception as e:
            logger.error(f"Error handling SSE event: {e}")

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers
