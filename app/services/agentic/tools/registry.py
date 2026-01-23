"""
Composite Tool Registry

Combines all tool modules into a single registry that can be used
by the NativeToolAgent. This provides the same interface as the
original monolithic ToolRegistry but with modular internals.
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.agentic.tools import Tool, ToolModule
from app.services.agentic.tools.knowledge_tools import KnowledgeTools
from app.services.agentic.tools.observability_tools import ObservabilityTools
from app.services.agentic.tools.troubleshooting_tools import TroubleshootingTools
from app.services.agentic.tools.background_tools import BackgroundTools
from app.services.agentic.tools.system_info_tools import SystemInfoTools
from app.services.agentic.tools.inquiry_tools import InquiryTools
from app.services.revive.tools.grafana_tools import GrafanaTools
from app.services.revive.tools.aiops_tools import AIOpsTools
from app.services.revive.tools.revive_aiops_helper import ReviveAIOpsHelper

logger = logging.getLogger(__name__)


class CompositeToolRegistry:
    """
    Composite registry that combines all tool modules.
    
    Provides the same interface as the original ToolRegistry but
    internally delegates to modular tool modules. This allows
    different modes to use different combinations of tools.
    """
    
    AVAILABLE_MODULES = [
        'knowledge', 'observability', 'troubleshooting', 'system_info', 'inquiry',
        'revive_grafana', 'revive_aiops', 'revive_aiops_helper'
    ]
    
    def __init__(
        self, 
        db: Session, 
        alert_id: Optional[UUID] = None,
        modules: Optional[List[str]] = None,
        mcp_client: Optional[Any] = None  # Added for MCP-dependent modules
    ):
        """
        Initialize the composite tool registry.
        
        Args:
            db: Database session for tool execution
            alert_id: Current alert context (optional)
            modules: List of module names to load.
            mcp_client: Client for MCP tools (optional)
        """
        self.db = db
        self.alert_id = alert_id
        self.mcp_client = mcp_client
        self._tools: Dict[str, Tool] = {}
        self._handlers: Dict[str, Callable] = {}
        self._modules: List[ToolModule] = []
        
        modules_to_load = modules or ['knowledge', 'observability', 'troubleshooting', 'inquiry']
        
        # Initialize and register each module
        for module_name in modules_to_load:
            module = self._create_module(module_name)
            if module:
                self._modules.append(module)
                self._register_module(module)
    
    def _create_module(self, module_name: str) -> Optional[ToolModule]:
        """Create a tool module by name"""
        if module_name == 'knowledge':
            return KnowledgeTools(self.db, self.alert_id)
        elif module_name == 'observability':
            return ObservabilityTools(self.db, self.alert_id)
        elif module_name == 'troubleshooting':
            return TroubleshootingTools(self.db, self.alert_id)
        elif module_name == 'background':
            return BackgroundTools(self.db, self.alert_id)
        elif module_name == 'system_info':
            return SystemInfoTools(self.db, self.alert_id)
        elif module_name == 'inquiry':
            return InquiryTools(self.db, self.alert_id)
        elif module_name == 'revive_grafana':
            if not self.mcp_client:
                logger.warning("Revive Grafana tools requested but MCP Client not provided")
                return None
            return GrafanaTools(self.db, self.mcp_client, self.alert_id)
        elif module_name == 'revive_aiops':
            return AIOpsTools(self.db, self.alert_id)
        elif module_name == 'revive_aiops_helper':
            return ReviveAIOpsHelper(self.db, self.alert_id)
        else:
            logger.warning(f"Unknown tool module: {module_name}")
            return None
    
    def _register_module(self, module: ToolModule):
        """Register all tools from a module"""
        for tool in module.get_tools():
            self._tools[tool.name] = tool
            self._handlers[tool.name] = module.get_handler(tool.name)
    
    def get_tools(self) -> List[Tool]:
        """Get all registered tools"""
        return list(self._tools.values())
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a specific tool by name"""
        return self._tools.get(name)
    
    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Get tools in OpenAI function calling format"""
        return [tool.to_openai_schema() for tool in self._tools.values()]
    
    def get_anthropic_tools(self) -> List[Dict[str, Any]]:
        """Get tools in Anthropic tool format"""
        return [tool.to_anthropic_schema() for tool in self._tools.values()]
    
    def get_react_tools_description(self) -> str:
        """Get tools as text description for ReAct prompting"""
        return "\n".join([tool.to_react_description() for tool in self._tools.values()])
    
    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a tool and return the result as a string.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments for the tool
        
        Returns:
            Tool result as a formatted string
        """
        handler = self._handlers.get(tool_name)
        if not handler:
            return f"Error: Unknown tool '{tool_name}'"
        
        try:
            result = await handler(arguments)
            return str(result)
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}", exc_info=True)
            return f"Error executing {tool_name}: {str(e)}"


# Convenience factory functions for common configurations

def create_troubleshooting_registry(db: Session, alert_id: Optional[UUID] = None) -> CompositeToolRegistry:
    """
    Create a registry for Troubleshooting mode.
    
    Includes all core investigation and action tools.
    """
    return CompositeToolRegistry(db, alert_id, modules=['knowledge', 'observability', 'troubleshooting', 'inquiry'])

def create_full_registry(db: Session, alert_id: Optional[UUID] = None) -> CompositeToolRegistry:
    """Create a registry with all interactive tools (for back-compat)"""
    return create_troubleshooting_registry(db, alert_id)


def create_knowledge_registry(db: Session, alert_id: Optional[UUID] = None) -> CompositeToolRegistry:
    """Create a registry with knowledge tools only (read-only mode)"""
    return CompositeToolRegistry(db, alert_id, modules=['knowledge'])


def create_inquiry_registry(db: Session, alert_id: Optional[UUID] = None) -> CompositeToolRegistry:
    """
    Create a registry for Inquiry mode with MCP Grafana integration.
    
    Includes: knowledge, observability, inquiry tools, and MCP Grafana tools
    for comprehensive querying of dashboards, alerts, and metrics.
    """
    import os
    
    # Try to create MCP client for Grafana tools
    mcp_client = None
    try:
        from app.services.mcp.client import MCPClient
        mcp_server_url = os.getenv("MCP_GRAFANA_URL", "http://localhost:8081")
        mcp_client = MCPClient(server_url=mcp_server_url)
        logger.info(f"MCP client created for Inquiry: {mcp_server_url}")
    except Exception as e:
        logger.warning(f"MCP client not available for Inquiry: {e}")
    
    # Include MCP Grafana tools if client is available
    modules = ['knowledge', 'observability', 'inquiry']
    if mcp_client:
        modules.append('revive_grafana')
        logger.info("MCP Grafana tools added to Inquiry registry")
    
    return CompositeToolRegistry(db, alert_id, modules=modules, mcp_client=mcp_client)

def create_background_registry(db: Session, alert_id: Optional[UUID] = None) -> CompositeToolRegistry:
    """
    Create a registry for Background Agents (READ-ONLY + Safe System Info).
    
    SECURITY: Background agents can only read data.
    - knowledge: Search runbooks
    - observability: Query metrics, logs
    - system_info: Safe hardcoded system commands (uptime, ps, df)
    
    Excludes: troubleshooting (interactive), background (DISABLED for security)
    """
    return CompositeToolRegistry(db, alert_id, modules=['knowledge', 'observability', 'system_info'])
