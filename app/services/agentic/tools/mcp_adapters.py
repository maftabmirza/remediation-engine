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
        # Special handling for Prometheus query tool - ensure time parameters are set
        if tool_name == "query_prometheus":
            query_type = arguments.get("queryType", "instant")
            
            # For instant queries, ensure startTime/endTime are set to 'now' if not provided
            # Note: MCP Grafana uses 'startTime' and 'endTime' (camelCase)
            if query_type == "instant":
                if not arguments.get("startTime"):
                    arguments["startTime"] = "now"
                if not arguments.get("endTime"):
                    arguments["endTime"] = "now"
            else:
                # Range queries require explicit times
                if not arguments.get("startTime") or not arguments.get("endTime"):
                    return "Error: Range queries require 'startTime' and 'endTime' time parameters"
        
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
    On-call adapter for AI agents.

    Provides a ``get_current_oncall`` method that AI agents can call to find
    out who is on-call for a given application or group.  Uses the native
    :class:`~app.services.oncall_service.OnCallService` (not an external MCP
    tool) because on-call data lives in the local database.
    """

    def __init__(self, db, oncall_service=None):
        """
        Args:
            db: AsyncSession (or sync Session) for database access.
            oncall_service: Optional pre-built OnCallService instance.
        """
        self.db = db
        self._oncall_service = oncall_service

    def _get_service(self):
        if self._oncall_service is not None:
            return self._oncall_service
        from app.services.oncall_service import OnCallService  # noqa: PLC0415

        return OnCallService(self.db)

    async def get_current_oncall(
        self,
        app_id: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> dict:
        """
        Tool callable by AI agents: 'Who is on-call for this service?'

        Args:
            app_id: Optional application UUID string.
            group_id: Optional group UUID string.

        Returns:
            Dict with ``oncall`` list of contact dicts.
        """
        from uuid import UUID as _UUID  # noqa: PLC0415

        svc = self._get_service()
        result = await svc.get_current_oncall(
            group_id=_UUID(group_id) if group_id else None,
            app_id=_UUID(app_id) if app_id else None,
        )
        return {
            "oncall": [
                {
                    "name": c.user_name,
                    "email": c.user_email,
                    "role": c.role,
                    "level": c.escalation_level,
                    "escalates_in_minutes": c.escalates_in_minutes,
                    "schedule_name": c.schedule_name,
                    "is_override": c.is_override,
                }
                for c in result
            ]
        }

    async def get_schedule(self, team: Optional[str] = None) -> str:
        """
        Legacy compatibility shim.  Returns a human-readable summary of the
        current on-call schedule.

        Args:
            team: Ignored (kept for backward compatibility).

        Returns:
            Human-readable on-call summary string.
        """
        result = await self.get_current_oncall()
        contacts = result.get("oncall", [])
        if not contacts:
            return "No on-call schedule found."
        lines = []
        for c in contacts:
            lines.append(
                f"Level {c['level']}: {c['name']} ({c['email']}) — role: {c['role']}"
                + (f", escalates in {c['escalates_in_minutes']}min" if c.get("escalates_in_minutes") else "")
            )
        return "\n".join(lines)
