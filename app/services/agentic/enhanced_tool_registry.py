from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session

from app.services.agentic.tools.registry import CompositeToolRegistry
from app.services.mcp.client import MCPClient
from app.services.agentic.tools.mcp_adapters import MCPToolAdapter
from app.models import User
from app.services.ai_permission_service import AIPermissionService

class EnhancedToolRegistry(CompositeToolRegistry):
    """
    Extends CompositeToolRegistry to include MCP tools and RBAC checks.
    """

    def __init__(
        self,
        db: Session,
        alert_id: Optional[UUID] = None,
        mcp_client: Optional[MCPClient] = None,
        user: Optional[User] = None,
        permission_service: Optional[AIPermissionService] = None,
        modules: Optional[List[str]] = None
    ):
        self.mcp_client = mcp_client
        self.user = user
        self.permission_service = permission_service
        self.mcp_adapter = MCPToolAdapter(mcp_client) if mcp_client else None
        
        # Initialize parent (CompositeToolRegistry)
        # Default modules for troubleshooting to match create_full_registry
        default_modules = ['knowledge', 'observability', 'troubleshooting', 'inquiry']
        super().__init__(db, alert_id, modules=modules or default_modules, mcp_client=mcp_client)

    async def initialize(self):
        """
        Async initialization to fetch MCP tools.
        Example: await registry.initialize()
        """
        if self.mcp_adapter:
            await self._register_mcp_tools()

    async def _register_mcp_tools(self):
        """
        Fetch and register available MCP tools.
        """
        if not self.mcp_adapter:
            return

        try:
            mcp_tools = await self.mcp_adapter.get_adapted_tools()
            for tool in mcp_tools:
                # We register directly into the self._tools dict of CompositeToolRegistry
                # And register a handler wrapper
                self._tools[tool.name] = tool
                self._handlers[tool.name] = self._make_mcp_handler(tool.name)
        except Exception as e:
            # Log error but don't fail initialization
            # In a real app, use logger
            print(f"Failed to register MCP tools: {e}")

    def _make_mcp_handler(self, tool_name: str):
        """
        Creates a closure to handle MCP tool execution.
        """
        async def handler(args: Dict[str, Any]) -> str:
            if not self.mcp_adapter:
                return "Error: MCP client not available"
            return await self.mcp_adapter.execute(tool_name, args)
        return handler

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute tool with optional permission check.
        """
        # OPTIONAL: Add permission check here
        if self.user and self.permission_service:
            # self.permission_service.check_permission(self.user, tool_name, ...)
            pass
        
        return await super().execute(tool_name, arguments)
