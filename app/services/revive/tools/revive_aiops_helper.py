"""
RE-VIVE AIOps Helper Tools (Read-Only)

These are informational tools for RE-VIVE quick help mode.
For actions (execute runbook, etc.), users should use /ai troubleshooting.
"""
from typing import List, Dict, Any, Optional
import logging

from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.services.agentic.tools.definitions import Tool, ToolParameter
from app.services.agentic.tools import ToolModule
from app.models import ServerCredential
from app.models_remediation import Runbook

logger = logging.getLogger(__name__)


class ReviveAIOpsHelper(ToolModule):
    """
    Read-only helper tools for RE-VIVE quick help mode.
    
    These tools provide information about runbooks and servers
    WITHOUT executing actions. Actions should be done via /ai troubleshooting.
    """

    def _register_tools(self):
        # Show Available Runbooks (informational only)
        self._register_tool(
            Tool(
                name="show_available_runbooks",
                description=(
                    "Show list of available remediation runbooks. "
                    "Use this ONLY if the user explicitly asks what runbooks exist "
                    "and the information is NOT already visible on the current page."
                ),
                category="aiops_info",
                risk_level="read",
                parameters=[
                    ToolParameter("keyword", "string", "Optional search keyword"),
                    ToolParameter("category", "string", "Optional category filter")
                ]
            ),
            self.show_available_runbooks
        )

        # Show Available Servers (informational only)
        self._register_tool(
            Tool(
                name="show_available_servers",
                description=(
                    "Show list of available servers/targets. "
                    "Use this ONLY if the user explicitly asks what servers exist "
                    "and the information is NOT already visible on the current page."
                ),
                category="aiops_info",
                risk_level="read",
                parameters=[
                    ToolParameter("os_type", "string", "Filter by OS type", enum=["linux", "windows"]),
                    ToolParameter("environment", "string", "Filter by environment")
                ]
            ),
            self.show_available_servers
        )

    async def show_available_runbooks(self, args: Dict[str, Any]) -> str:
        """
        List available runbooks (READ ONLY).
        Does NOT execute or modify anything.
        """
        keyword = args.get("keyword")
        category = args.get("category")

        logger.info(f"RE-VIVE: Listing runbooks (keyword={keyword}, category={category})")

        query = select(Runbook).where(Runbook.enabled == True)
        if keyword:
            query = query.where(or_(
                Runbook.name.ilike(f"%{keyword}%"),
                Runbook.description.ilike(f"%{keyword}%")
            ))
        if category:
            query = query.where(Runbook.category == category)

        runbooks = self.db.execute(query).scalars().all()

        if not runbooks:
            return "No runbooks found matching your criteria."

        result = "**Available Runbooks:**\n\n"
        for r in runbooks:
            result += f"- **{r.name}**"
            if r.description:
                result += f": {r.description}"
            if r.category:
                result += f" (Category: {r.category})"
            result += "\n"

        result += "\n💡 *To execute a runbook, use the UI or type '/ai troubleshooting' for automated execution.*"
        return result

    async def show_available_servers(self, args: Dict[str, Any]) -> str:
        """
        List available servers (READ ONLY).
        Does NOT execute or modify anything.
        """
        os_type = args.get("os_type")
        environment = args.get("environment")

        logger.info(f"RE-VIVE: Listing servers (os={os_type}, env={environment})")

        query = select(ServerCredential)
        if os_type:
            query = query.where(ServerCredential.os_type == os_type)
        if environment:
            query = query.where(ServerCredential.environment == environment)

        servers = self.db.execute(query).scalars().all()

        if not servers:
            return "No servers found matching your criteria."

        result = "**Available Servers:**\n\n"
        for s in servers:
            result += f"- **{s.hostname}**"
            if s.os_type:
                result += f" ({s.os_type}"
            if s.environment:
                result += f", {s.environment}"
            if s.os_type or s.environment:
                result += ")"
            result += "\n"

        return result
