from typing import List, Dict, Any, Optional
from uuid import UUID
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.agentic.tools.definitions import Tool, ToolParameter
from app.services.agentic.tools import ToolModule
from app.services.mcp.client import MCPClient

logger = logging.getLogger(__name__)

class GrafanaTools(ToolModule):
    """
    Tools for interacting with Grafana via MCP (Dashboards, Alerts, Queries).
    """

    def __init__(self, db: Session, mcp_client: MCPClient, alert_id: Optional[UUID] = None):
        self.mcp_client = mcp_client
        super().__init__(db, alert_id)

    def _register_tools(self):
        self._register_dashboard_tools()
        self._register_alert_tools()
        self._register_query_tools()
        self._register_misc_tools()

    def _register_dashboard_tools(self):
        # Search Dashboards
        self._register_tool(
            Tool(
                name="search_dashboards",
                description="Search for Grafana dashboards by query string.",
                category="revive_grafana",
                risk_level="read",
                parameters=[
                    ToolParameter("query", "string", "Search query (e.g., 'kafka', 'nodes')"),
                    ToolParameter("tag", "string", "Filter by tag (optional)"),
                    ToolParameter("limit", "integer", "Max results", default=10)
                ]
            ),
            self.search_dashboards
        )
        
        # Get Dashboard
        self._register_tool(
            Tool(
                name="get_dashboard_by_uid",
                description="Get full dashboard model by UID.",
                category="revive_grafana",
                risk_level="read",
                parameters=[
                    ToolParameter("uid", "string", "Dashboard UID")
                ]
            ),
            self.get_dashboard_by_uid
        )
        
        # Create Dashboard
        self._register_tool(
            Tool(
                name="create_dashboard",
                description="Create a new Grafana dashboard.",
                category="revive_grafana",
                risk_level="create",
                requires_confirmation=True,
                parameters=[
                    ToolParameter("title", "string", "Dashboard title"),
                    ToolParameter("folder_uid", "string", "Folder UID (optional)"),
                    ToolParameter("panels", "array", "List of panel definitions (JSON)")
                ]
            ),
            self.create_dashboard
        )

        # Update Dashboard
        self._register_tool(
            Tool(
                name="update_dashboard",
                description="Update an existing Grafana dashboard.",
                category="revive_grafana",
                risk_level="update",
                requires_confirmation=True,
                parameters=[
                    ToolParameter("uid", "string", "Dashboard UID"),
                    ToolParameter("dashboard_model", "object", "Full dashboard model JSON"),
                    ToolParameter("message", "string", "Commit message")
                ]
            ),
            self.update_dashboard
        )

    def _register_alert_tools(self):
        # List Alert Rules
        self._register_tool(
            Tool(
                name="list_alert_rules",
                description="List Grafana alert rules.",
                category="revive_grafana",
                risk_level="read",
                parameters=[
                    ToolParameter("folder_uid", "string", "Filter by folder UID (optional)")
                ]
            ),
            self.list_alert_rules
        )

        # List Alert Rules
        self._register_tool(
            Tool(
                name="list_alert_rules",
                description="List Grafana alert rules.",
                category="revive_grafana",
                risk_level="read",
                parameters=[
                    ToolParameter("folder_uid", "string", "Filter by folder UID (optional)")
                ]
            ),
            self.list_alert_rules
        )

    def _register_query_tools(self):
        # Query Prometheus
        self._register_tool(
            Tool(
                name="query_prometheus",
                description="Execute a PromQL query.",
                category="revive_grafana",
                risk_level="read",
                parameters=[
                    ToolParameter("query", "string", "PromQL query"),
                    ToolParameter("start", "string", "Start time (ISO 8601)"),
                    ToolParameter("end", "string", "End time (ISO 8601)"),
                    ToolParameter("step", "integer", "Step in seconds")
                ]
            ),
            self.query_prometheus
        )

    def _register_misc_tools(self):
        # OnCall Schedule
        self._register_tool(
            Tool(
                name="get_oncall_schedule",
                description="Get OnCall schedule for a team.",
                category="revive_grafana",
                risk_level="read",
                parameters=[
                    ToolParameter("team", "string", "Team name (optional)")
                ]
            ),
            self.get_oncall_schedule
        )

    # --- Handlers (Delegating to MCP Client) ---

    async def search_dashboards(self, args: Dict[str, Any]) -> str:
        return await self._call_mcp("search_dashboards", args)

    async def get_dashboard_by_uid(self, args: Dict[str, Any]) -> str:
        return await self._call_mcp("get_dashboard_by_uid", args)

    async def create_dashboard(self, args: Dict[str, Any]) -> str:
        # Construct dashboard object for MCP update_dashboard tool
        dashboard = {
            "title": args.get("title",("New Dashboard")),
            "panels": args.get("panels", []),
            "schemaVersion": 36,
        }
        
        mcp_args = {
            "dashboard": dashboard,
            "folderUid": args.get("folder_uid"),
            "overwrite": False
            # 'message' is optional
        }
        return await self._call_mcp("update_dashboard", mcp_args)

    async def update_dashboard(self, args: Dict[str, Any]) -> str:
        return await self._call_mcp("update_dashboard", args)

    async def list_alert_rules(self, args: Dict[str, Any]) -> str:
        return await self._call_mcp("list_alert_rules", args)

    async def query_prometheus(self, args: Dict[str, Any]) -> str:
        return await self._call_mcp("query_prometheus", args)

    async def get_oncall_schedule(self, args: Dict[str, Any]) -> str:
        return await self._call_mcp("get_current_oncall_users", args)

    # Helper
    async def _call_mcp(self, tool_name: str, args: Dict[str, Any]) -> str:
        if not self.mcp_client:
            return "Error: MCP Client not initialized"
        
        try:
            # Map simplified tool names to actual MCP tool names if needed
            # Assuming MCP server exposes them directly or we need a mapping
            # For now, assuming straightforward mapping or passing 'tool_name' directly
            # Logic: We registered 'search_dashboards' as our tool name.
            # But the args passed to this function are from the LLM based on OUR definition.
            # We need to call the MCP client with the MCP tool name.
            # Let's assume the MCP tool names match our registration for simplicity, 
            # OR use the 'tool_name' arg passed to this helper if mapped.
            
            # Note: arguments passed to _call_mcp are 'tool_name' (e.g. "dashboards/search") and 'args'
            result = await self.mcp_client.call_tool(tool_name, args)
            
            if result.isError:
                error_msg = result.content[0].text if result.content else "Unknown error"
                return f"MCP Error: {error_msg}"
            
            # Combine content
            return "\n".join([c.text for c in result.content])
        except Exception as e:
            logger.error(f"MCP Call Failed: {e}", exc_info=True)
            return f"Error executing {tool_name}: {str(e)}"
