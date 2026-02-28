from typing import List, Dict, Any, Optional
from uuid import UUID
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.services.agentic.tools.definitions import Tool, ToolParameter
from app.services.agentic.tools import ToolModule
from app.models import ServerCredential
from app.models_remediation import Runbook, RunbookExecution

logger = logging.getLogger(__name__)

class AIOpsTools(ToolModule):
    """
    Tools for interacting with AIOps Platform (Runbooks, Servers).
    """

    def _register_tools(self):
        # List Servers
        self._register_tool(
            Tool(
                name="list_servers",
                description="List available servers/targets for remediation.",
                category="aiops_platform",
                risk_level="read",
                parameters=[
                    ToolParameter("os_type", "string", "Filter by OS (linux/windows)", enum=["linux", "windows"]),
                    ToolParameter("environment", "string", "Filter by environment (prod/stage)")
                ]
            ),
            self.list_servers
        )

        # List Runbooks
        self._register_tool(
            Tool(
                name="list_runbooks",
                description="List available remediation runbooks.",
                category="aiops_platform",
                risk_level="read",
                parameters=[
                    ToolParameter("keyword", "string", "Search keyword"),
                    ToolParameter("category", "string", "Filter by category")
                ]
            ),
            self.list_runbooks
        )

        # Execute Runbook
        self._register_tool(
            Tool(
                name="execute_runbook",
                description="Execute a runbook on a target server.",
                category="aiops_platform",
                risk_level="execute",
                requires_confirmation=True,
                parameters=[
                    ToolParameter("runbook_name", "string", "Name of the runbook"),
                    ToolParameter("target_server", "string", "Hostname or ID of target server"),
                    ToolParameter("parameters", "object", "Optional parameters for execution")
                ]
            ),
            self.execute_runbook
        )
    
    async def list_servers(self, args: Dict[str, Any]) -> str:
        os_type = args.get("os_type")
        environment = args.get("environment")
        
        query = select(ServerCredential)
        if os_type:
            query = query.where(ServerCredential.os_type == os_type)
        if environment:
            query = query.where(ServerCredential.environment == environment)
            
        servers = self.db.execute(query).scalars().all()
        
        if not servers:
            return "No servers found matching criteria."
            
        return "\n".join([f"- {s.hostname} ({s.os_type}, {s.environment})" for s in servers])

    async def list_runbooks(self, args: Dict[str, Any]) -> str:
        keyword = args.get("keyword")
        category = args.get("category")
        
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
            return "No runbooks found."
            
        return "\n".join([f"- {r.name}: {r.description or 'No description'} (Category: {r.category})" for r in runbooks])

    async def execute_runbook(self, args: Dict[str, Any]) -> str:
        runbook_name = args.get("runbook_name")
        target_server = args.get("target_server")
        params = args.get("parameters") or {}
        
        # 1. Resolve Runbook
        runbook = self.db.execute(select(Runbook).where(Runbook.name == runbook_name)).scalar_one_or_none()
        if not runbook:
            return f"Error: Runbook '{runbook_name}' not found."
            
        # 2. Resolve Server
        # Try exact match on ID or Hostname
        server_query = select(ServerCredential).where(
            or_(
                ServerCredential.hostname == target_server,
                # Startswith for partial match convenience? No, unsafe. Exact match preferred.
            )
        )
        try:
            # Check if UUID
            uuid_obj = UUID(target_server)
            server_query = select(ServerCredential).where(ServerCredential.id == uuid_obj)
        except ValueError:
            pass
            
        server = self.db.execute(server_query).scalar_one_or_none()
        if not server:
            return f"Error: Target server '{target_server}' not found."
            
        # 3. Create Execution Record
        execution = RunbookExecution(
            runbook_id=runbook.id,
            server_id=server.id,
            execution_mode="manual", # Triggered by AI assumes manual intent unless fully auto
            status="queued",
            queued_at=datetime.now(timezone.utc),
            triggered_by_system=True, # AI Agent triggers it
            variables_json=params,
            alert_id=self.alert_id
        )
        
        self.db.add(execution)
        self.db.commit()
        
        return f"Runbook execution queued successfully. Execution ID: {execution.id}. Status: queued."
