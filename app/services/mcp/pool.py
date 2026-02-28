"""
MCP Client Connection Pool

Implements singleton pattern with connection pooling for MCP clients.
Ensures efficient reuse of connections with health monitoring and automatic reconnection.
"""
import asyncio
import logging
import os
from contextlib import AsyncExitStack
from typing import Optional, Dict
from datetime import datetime, timedelta

from .client import MCPClient  # Use custom client (SDK has dependency conflicts)
from .exceptions import MCPConnectionError

logger = logging.getLogger(__name__)


class MCPConnectionPool:
    """
    Singleton connection pool for MCP clients.
    
    Maintains long-lived connections with health monitoring and automatic reconnection.
    """
    
    _instance: Optional['MCPConnectionPool'] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self._clients: Dict[str, MCPClient] = {}
        self._health_status: Dict[str, datetime] = {}
        self._exit_stack = AsyncExitStack()
        self._health_check_interval = 60.0  # seconds
        self._health_check_task: Optional[asyncio.Task] = None
        self._reconnect_delay = 5.0  # Initial backoff
        self._max_reconnect_delay = 300.0  # Max 5 minutes
        
    @classmethod
    async def get_instance(cls) -> 'MCPConnectionPool':
        """Get or create singleton instance."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance._start_health_monitor()
        return cls._instance
    
    async def get_client(self, server_url: str, api_token: Optional[str] = None) -> MCPClient:
        """
        Get or create an MCP client for the specified server.
        
        Reuses existing connections when possible.
        """
        cache_key = f"{server_url}:{api_token or 'no-token'}"
        
        if cache_key in self._clients:
            client = self._clients[cache_key]
            # Check if connection is healthy
            if await self._is_healthy(cache_key):
                logger.debug(f"Reusing existing MCP connection to {server_url}")
                return client
            else:
                logger.warning(f"Unhealthy connection to {server_url}, reconnecting...")
                await self._reconnect_client(cache_key, server_url, api_token)
                return self._clients[cache_key]
        
        # Create new client
        logger.info(f"Creating new MCP connection to {server_url}")
        client = MCPClient(server_url=server_url, api_token=api_token)
        
        # Initialize with reconnection logic
        await self._connect_with_retry(client, cache_key)
        
        self._clients[cache_key] = client
        self._health_status[cache_key] = datetime.now()
        
        # Register cleanup
        self._exit_stack.push_async_callback(client.disconnect)
        
        return client
    
    async def _connect_with_retry(self, client: MCPClient, cache_key: str, max_retries: int = 3):
        """Connect with exponential backoff retry logic."""
        delay = self._reconnect_delay
        
        for attempt in range(max_retries):
            try:
                await client.connect()
                logger.info(f"MCP client connected successfully")
                self._health_status[cache_key] = datetime.now()
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Connection attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self._max_reconnect_delay)  # Exponential backoff
                else:
                    logger.error(f"Failed to connect after {max_retries} attempts")
                    raise MCPConnectionError(f"Failed to connect to MCP server after {max_retries} attempts") from e
    
    async def _reconnect_client(self, cache_key: str, server_url: str, api_token: Optional[str]):
        """Reconnect a failed client."""
        old_client = self._clients.pop(cache_key, None)
        if old_client:
            try:
                await old_client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting old client: {e}")
        
        # Create and connect new client
        new_client = MCPClient(server_url=server_url, api_token=api_token)
        await self._connect_with_retry(new_client, cache_key)
        
        self._clients[cache_key] = new_client
        self._exit_stack.push_async_callback(new_client.disconnect)
    
    async def _is_healthy(self, cache_key: str) -> bool:
        """Check if a connection is healthy."""
        if cache_key not in self._clients:
            return False
        
        client = self._clients[cache_key]
        
        # Check connection status
        if not client._connected:
            return False
        
        # Check last health check timestamp
        last_check = self._health_status.get(cache_key)
        if last_check and (datetime.now() - last_check) > timedelta(seconds=self._health_check_interval):
            # Perform health check by listing tools
            try:
                await asyncio.wait_for(client.list_tools(), timeout=5.0)
                self._health_status[cache_key] = datetime.now()
                return True
            except Exception as e:
                logger.warning(f"Health check failed for {cache_key}: {e}")
                return False
        
        return True
    
    async def _start_health_monitor(self):
        """Start background health monitoring task."""
        if self._health_check_task:
            return
        
        async def health_monitor_loop():
            while True:
                try:
                    await asyncio.sleep(self._health_check_interval)
                    for cache_key in list(self._clients.keys()):
                        await self._is_healthy(cache_key)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Health monitor error: {e}")
        
        self._health_check_task = asyncio.create_task(health_monitor_loop())
    
    async def close_all(self):
        """Close all connections and cleanup resources."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        await self._exit_stack.aclose()
        self._clients.clear()
        self._health_status.clear()
        
        # Reset singleton
        MCPConnectionPool._instance = None


# Convenience function
async def get_mcp_client(server_url: Optional[str] = None, api_token: Optional[str] = None) -> MCPClient:
    """
    Get an MCP client from the connection pool.
    
    Args:
        server_url: MCP server URL (defaults to MCP_GRAFANA_URL env var)
        api_token: Optional API token for authentication
    
    Returns:
        Connected MCP client instance
    """
    if not server_url:
        server_url = os.getenv("MCP_GRAFANA_URL")
        if not server_url:
            raise ValueError("MCP server URL not provided and MCP_GRAFANA_URL not set")
    
    pool = await MCPConnectionPool.get_instance()
    return await pool.get_client(server_url, api_token)
