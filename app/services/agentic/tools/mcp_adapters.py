from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID

from app.services.mcp.client import MCPClient
from app.services.agentic.tools.definitions import Tool, ToolParameter

class MCPToolAdapter:
    """
    Adapts MCP tools for use within the internal ToolRegistry.
    Handles converting MCP tool definitions to internal Tool objects
    and delegating execution to the MCPClient.
    """
    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client

    async def get_adapted_tools(self) -> List[Tool]:
        """
        Fetches tools from MCP server and converts them to internal Tool definitions.
        """
        mcp_tools = await self.mcp_client.list_tools()
        adapted_tools = []

        for mcp_tool in mcp_tools:
            # Convert JSON schema parameters to ToolParameters
            parameters = []
            if mcp_tool.input_schema and "properties" in mcp_tool.input_schema:
                for param_name, param_schema in mcp_tool.input_schema["properties"].items():
                    parameters.append(ToolParameter(
                        name=param_name,
                        type=param_schema.get("type", "string"),
                        description=param_schema.get("description", ""),
                        enum=param_schema.get("enum"),
                        default=param_schema.get("default")
                    ))
            
            adapted_tools.append(Tool(
                name=mcp_tool.name,
                description=mcp_tool.description or "",
                category="troubleshooting", # Default category, can be overridden
                risk_level="read", # Default risk, should be mapped based on tool name/type
                parameters=parameters
            ))
        
        return adapted_tools

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Executes an MCP tool via the client.
        """
        result = await self.mcp_client.call_tool(tool_name, arguments)
        
        # Format result content
        output = []
        for content in result.content:
            if content.type == 'text':
                output.append(content.text)
            elif content.type == 'image':
                output.append(f"[Image: {content.resource or 'embedded'}]")
            elif content.type == 'resource':
                 output.append(f"[Resource: {content.resource.uri}]")
        
        return "\n".join(output)

class SiftAdapter:
    """
    Specialized adapter logic for Sift investigations using MCP.
    """
    def __init__(self, mcp_adapter: MCPToolAdapter):
        self.mcp_adapter = mcp_adapter

    async def investigate_errors(
        self,
        app_name: str,
        start_time: str,
        end_time: str
    ) -> str:
        """
        Uses 'investigate_sift' tool to analyze errors.
        """
        return await self.mcp_adapter.execute("investigate_sift", {
            "app_name": app_name,
            "start_time": start_time,
            "end_time": end_time,
            "investigation_type": "errors"
        })

class OnCallAdapter:
    """
    Specialized adapter logic for OnCall information using MCP.
    """
    def __init__(self, mcp_adapter: MCPToolAdapter):
        self.mcp_adapter = mcp_adapter

    async def get_schedule(self, team: Optional[str] = None) -> str:
        """
        Uses 'get_oncall_schedule' tool.
        """
        args = {}
        if team:
            args["team"] = team
        return await self.mcp_adapter.execute("get_oncall_schedule", args)
