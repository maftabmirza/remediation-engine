"""
Tool Registry for Agentic RAG System

Defines all available tools that the LLM can call to gather information
during troubleshooting. Each tool wraps an existing service.
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from uuid import UUID
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
import sqlalchemy as sa

logger = logging.getLogger(__name__)


from app.services.agentic.tools.definitions import Tool, ToolParameter

class ToolRegistry:
    """
    Registry of all available tools for the agentic system.

    Handles tool definition, schema generation, and execution.
    """

    def __init__(self, db: Session, alert_id: Optional[UUID] = None):
        """
        Initialize the tool registry.

        Args:
            db: Database session for tool execution
            alert_id: Current alert context (optional)
        """
        self.db = db
        self.alert_id = alert_id
        self._tools: Dict[str, Tool] = {}
        self._handlers: Dict[str, Callable] = {}

        # Register all tools
        self._register_tools()

    def _register_tools(self):
        """Register all available tools"""

        # 1. Search Knowledge Base
        self._register_tool(
            Tool(
                name="search_knowledge",
                description="Search the knowledge base for runbooks, SOPs, architecture docs, troubleshooting guides, and postmortems. Use this to find documented procedures and past solutions.",
                parameters=[
                    ToolParameter(
                        name="query",
                        type="string",
                        description="Search query - describe what you're looking for",
                        required=True
                    ),
                    ToolParameter(
                        name="doc_type",
                        type="string",
                        description="Filter by document type",
                        required=False,
                        enum=["runbook", "sop", "architecture", "troubleshooting", "postmortem", "design_doc"]
                    ),
                    ToolParameter(
                        name="limit",
                        type="integer",
                        description="Maximum number of results (default 5)",
                        required=False,
                        default=5
                    )
                ]
            ),
            self._search_knowledge
        )

        # 2. Get Similar Incidents
        self._register_tool(
            Tool(
                name="get_similar_incidents",
                description="Find past incidents similar to the current alert using vector similarity. Returns past incidents with their resolutions and what worked.",
                parameters=[
                    ToolParameter(
                        name="limit",
                        type="integer",
                        description="Maximum number of similar incidents to return (default 3)",
                        required=False,
                        default=3
                    )
                ]
            ),
            self._get_similar_incidents
        )

        # 3. Get Recent Changes
        self._register_tool(
            Tool(
                name="get_recent_changes",
                description="Get recent deployments, config changes, and other change events. Useful for correlating incidents with changes.",
                parameters=[
                    ToolParameter(
                        name="service",
                        type="string",
                        description="Filter by service name (optional)",
                        required=False
                    ),
                    ToolParameter(
                        name="hours_back",
                        type="integer",
                        description="How many hours to look back (default 24)",
                        required=False,
                        default=24
                    ),
                    ToolParameter(
                        name="limit",
                        type="integer",
                        description="Maximum number of changes to return (default 10)",
                        required=False,
                        default=10
                    )
                ]
            ),
            self._get_recent_changes
        )

        # 4. Get Runbook
        self._register_tool(
            Tool(
                name="get_runbook",
                description="Get a specific runbook for a service, server, or alert type. Returns step-by-step remediation procedures. ALWAYS check for runbooks when user asks to restart/check/fix something!",
                parameters=[
                    ToolParameter(
                        name="service",
                        type="string",
                        description="Service name to find runbook for (e.g., 'apache', 'nginx', 'mysql')",
                        required=False
                    ),
                    ToolParameter(
                        name="alert_type",
                        type="string",
                        description="Alert type/name to find runbook for",
                        required=False
                    ),
                    ToolParameter(
                        name="server",
                        type="string",
                        description="Server name to find runbook for (e.g., 't-aiops-01')",
                        required=False
                    )
                ]
            ),
            self._get_runbook
        )

        # 5. Query Grafana Metrics
        self._register_tool(
            Tool(
                name="query_grafana_metrics",
                description="Query Prometheus metrics via Grafana. Use PromQL syntax. Returns metric values and trends.",
                parameters=[
                    ToolParameter(
                        name="promql",
                        type="string",
                        description="PromQL query (e.g., 'rate(http_requests_total[5m])')",
                        required=True
                    ),
                    ToolParameter(
                        name="time_range",
                        type="string",
                        description="Time range (e.g., '1h', '30m', '6h'). Default '1h'",
                        required=False,
                        default="1h"
                    )
                ]
            ),
            self._query_grafana_metrics
        )

        # 6. Query Grafana Logs
        self._register_tool(
            Tool(
                name="query_grafana_logs",
                description="Search logs via Grafana/Loki. Use LogQL syntax. Returns recent log entries matching the query.",
                parameters=[
                    ToolParameter(
                        name="logql",
                        type="string",
                        description="LogQL query (e.g., '{job=\"api\"} |= \"error\"')",
                        required=True
                    ),
                    ToolParameter(
                        name="limit",
                        type="integer",
                        description="Maximum log entries to return (default 50)",
                        required=False,
                        default=50
                    ),
                    ToolParameter(
                        name="time_range",
                        type="string",
                        description="Time range (e.g., '1h', '30m'). Default '1h'",
                        required=False,
                        default="1h"
                    )
                ]
            ),
            self._query_grafana_logs
        )

        # 7. Get Correlated Alerts
        self._register_tool(
            Tool(
                name="get_correlated_alerts",
                description="Get other alerts that are correlated with the current alert (same incident group). Returns related alerts and root cause analysis if available.",
                parameters=[]
            ),
            self._get_correlated_alerts
        )

        # 8. Get Service Dependencies
        self._register_tool(
            Tool(
                name="get_service_dependencies",
                description="Get upstream and downstream service dependencies for a component. Helps understand blast radius and potential causes.",
                parameters=[
                    ToolParameter(
                        name="service",
                        type="string",
                        description="Service name to get dependencies for",
                        required=True
                    )
                ]
            ),
            self._get_service_dependencies
        )

        # 9. Get User Feedback History
        self._register_tool(
            Tool(
                name="get_feedback_history",
                description="Get past user feedback on similar analyses. Shows what worked and what didn't in past troubleshooting sessions.",
                parameters=[
                    ToolParameter(
                        name="limit",
                        type="integer",
                        description="Maximum feedback entries to return (default 5)",
                        required=False,
                        default=5
                    )
                ]
            ),
            self._get_feedback_history
        )

        # 10. Get Alert Details
        self._register_tool(
            Tool(
                name="get_alert_details",
                description="Get full details of the current alert including all labels, annotations, and metadata.",
                parameters=[]
            ),
            self._get_alert_details
        )

        # 11. Suggest Server Command
        self._register_tool(
            Tool(
                name="suggest_ssh_command",
                description="Suggest a command for the user to run on a server. Use this when you need to gather info or perform an action. The USER will execute it and paste the output. Do NOT try to execute paths yourself.",
                parameters=[
                    ToolParameter(
                        name="server",
                        type="string",
                        description="Server IP address or hostname",
                        required=True
                    ),
                    ToolParameter(
                        name="command",
                        type="string",
                        description="Shell command to suggest (Bash for Linux, PowerShell for Windows)",
                        required=True
                    ),
                    ToolParameter(
                        name="explanation",
                        type="string",
                        description="Brief explanation of why this command is needed",
                        required=True
                    )
                ]
            ),
            self._suggest_ssh_command
        )

        # 12. Get Proven Solutions (Learning System)
        self._register_tool(
            Tool(
                name="get_proven_solutions",
                description="Find solutions that WORKED for similar problems in the past. Returns commands, runbooks, or knowledge docs that successfully resolved similar issues. Use this before suggesting new solutions to check if we've solved this before.",
                parameters=[
                    ToolParameter(
                        name="problem_description",
                        type="string",
                        description="Description of the current problem to find similar past solutions",
                        required=True
                    ),
                    ToolParameter(
                        name="limit",
                        type="integer",
                        description="Maximum number of solutions to return (default 5)",
                        required=False,
                        default=5
                    )
                ]
            ),
            self._get_proven_solutions
        )

    def _register_tool(self, tool: Tool, handler: Callable):
        """Register a tool with its handler"""
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler

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
        descriptions = [tool.to_react_description() for tool in self._tools.values()]
        return "\n\n".join(descriptions)

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a tool and return the result as a string.

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments for the tool

        Returns:
            Tool result as a formatted string
        """
        if tool_name not in self._handlers:
            return f"Error: Unknown tool '{tool_name}'"

        try:
            handler = self._handlers[tool_name]
            result = await handler(arguments)
            return result
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            return f"Error executing {tool_name}: {str(e)}"

    # ========== Tool Implementations ==========

    async def _search_knowledge(self, args: Dict[str, Any]) -> str:
        """Search knowledge base"""
        from app.services.knowledge_search_service import KnowledgeSearchService

        query = args.get("query", "")
        doc_type = args.get("doc_type")
        limit = args.get("limit", 5)

        if not query:
            return "Error: query parameter is required"

        try:
            service = KnowledgeSearchService(self.db)
            doc_types = [doc_type] if doc_type else None
            results = service.search_similar(
                query=query,
                doc_types=doc_types,
                limit=limit,
                min_similarity=0.3
            )

            if not results:
                return f"No knowledge base documents found matching '{query}'"

            output = [f"Found {len(results)} relevant documents:\n"]
            for i, result in enumerate(results, 1):
                title = result.get('source_title', 'Untitled')
                doc_type = result.get('doc_type', 'unknown')
                similarity = result.get('similarity', 0)
                content = result.get('content', '')[:500]  # Truncate

                output.append(f"{i}. **{title}** (type: {doc_type}, relevance: {similarity:.2f})")
                output.append(f"   {content}...")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Knowledge search error: {e}")
            return f"Error searching knowledge base: {str(e)}"

    async def _get_similar_incidents(self, args: Dict[str, Any]) -> str:
        """Get similar past incidents"""
        from app.services.similarity_service import SimilarityService

        if not self.alert_id:
            return "No alert context available - cannot find similar incidents"

        limit = args.get("limit", 3)

        try:
            service = SimilarityService(self.db)
            result = service.find_similar_alerts(self.alert_id, limit=limit)

            if not result or not result.similar_incidents:
                return "No similar past incidents found"

            output = [f"Found {len(result.similar_incidents)} similar past incidents:\n"]
            for i, incident in enumerate(result.similar_incidents, 1):
                output.append(f"{i}. **{incident.alert_name}**")
                output.append(f"   - Similarity: {incident.similarity_score:.2%}")
                output.append(f"   - Severity: {incident.severity}")
                output.append(f"   - Instance: {incident.instance}")
                output.append(f"   - Occurred: {incident.occurred_at}")

                if incident.resolution:
                    res = incident.resolution
                    output.append(f"   - Resolution: {res.method}")
                    if res.runbook_name:
                        output.append(f"   - Runbook used: {res.runbook_name}")
                    if res.time_minutes:
                        output.append(f"   - Time to resolve: {res.time_minutes} minutes")
                    output.append(f"   - Success: {'Yes' if res.success else 'No'}")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Similar incidents error: {e}")
            return f"Error finding similar incidents: {str(e)}"

    async def _get_recent_changes(self, args: Dict[str, Any]) -> str:
        """Get recent change events"""
        from app.models_itsm import ChangeEvent

        service_filter = args.get("service")
        hours_back = args.get("hours_back", 24)
        limit = args.get("limit", 10)

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

            query = self.db.query(ChangeEvent).filter(
                ChangeEvent.timestamp >= cutoff
            )

            if service_filter:
                query = query.filter(
                    ChangeEvent.service_name.ilike(f"%{service_filter}%")
                )

            changes = query.order_by(ChangeEvent.timestamp.desc()).limit(limit).all()

            if not changes:
                return f"No changes found in the last {hours_back} hours"

            output = [f"Found {len(changes)} recent changes:\n"]
            for i, change in enumerate(changes, 1):
                output.append(f"{i}. **{change.change_type}**: {change.description or 'No description'}")
                output.append(f"   - Service: {change.service_name or 'Unknown'}")
                output.append(f"   - Time: {change.timestamp}")
                output.append(f"   - Change ID: {change.change_id}")
                if change.impact_level:
                    output.append(f"   - Impact: {change.impact_level}")
                if change.correlation_score:
                    output.append(f"   - Correlation Score: {change.correlation_score:.1f}")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Recent changes error: {e}")
            return f"Error fetching recent changes: {str(e)}"

    async def _get_runbook(self, args: Dict[str, Any]) -> str:
        """Get runbook for service/alert type"""
        from app.models_remediation import Runbook, RunbookStep

        service = args.get("service")
        alert_type = args.get("alert_type")
        server = args.get("server")  # Also search by server name

        if not service and not alert_type and not server:
            return "Error: At least one parameter (service, alert_type, or server) is required"

        try:
            query = self.db.query(Runbook).filter(Runbook.enabled == True)

            # Build search conditions - use OR to match any
            conditions = []
            from sqlalchemy import or_
            
            if service:
                conditions.append(Runbook.name.ilike(f"%{service}%"))
                conditions.append(Runbook.description.ilike(f"%{service}%"))

            if alert_type:
                conditions.append(Runbook.name.ilike(f"%{alert_type}%"))
                conditions.append(Runbook.trigger_conditions.cast(str).ilike(f"%{alert_type}%"))
            
            if server:
                conditions.append(Runbook.name.ilike(f"%{server}%"))
                conditions.append(Runbook.description.ilike(f"%{server}%"))

            if conditions:
                query = query.filter(or_(*conditions))

            runbooks = query.limit(3).all()

            if not runbooks:
                search_terms = []
                if service:
                    search_terms.append(f"service='{service}'")
                if alert_type:
                    search_terms.append(f"alert_type='{alert_type}'")
                if server:
                    search_terms.append(f"server='{server}'")
                return f"No runbooks found for {', '.join(search_terms)}"

            output = [f"Found {len(runbooks)} relevant runbooks:\n"]
            for runbook in runbooks:
                output.append(f"## {runbook.name}")
                output.append(f"📖 **[View Runbook →](/runbooks/{runbook.id}/view)** (Open in AIOps Platform)")
                output.append(f"Description: {runbook.description or 'No description'}")
                output.append(f"Severity: {runbook.severity}")
                output.append(f"Auto-execute: {'Yes' if runbook.auto_execute else 'No'}")
                output.append("\n**Steps:**")

                # Get steps
                steps = self.db.query(RunbookStep).filter(
                    RunbookStep.runbook_id == runbook.id
                ).order_by(RunbookStep.order).all()

                for step in steps:
                    output.append(f"\n{step.order}. **{step.name}**")
                    output.append(f"   Type: {step.step_type}")
                    if step.description:
                        output.append(f"   {step.description}")
                    if step.command:
                        output.append(f"   Command: `{step.command}`")

                output.append("\n---\n")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Runbook fetch error: {e}")
            return f"Error fetching runbooks: {str(e)}"

    async def _query_grafana_metrics(self, args: Dict[str, Any]) -> str:
        """Query Prometheus metrics via Grafana"""
        from app.services.prometheus_service import PrometheusClient

        promql = args.get("promql", "")
        time_range = args.get("time_range", "1h")

        if not promql:
            return "Error: promql parameter is required"

        try:
            client = PrometheusClient()

            # Parse time range
            end_time = datetime.now()
            if time_range.endswith('m'):
                minutes = int(time_range[:-1])
                start_time = end_time - timedelta(minutes=minutes)
            elif time_range.endswith('h'):
                hours = int(time_range[:-1])
                start_time = end_time - timedelta(hours=hours)
            else:
                start_time = end_time - timedelta(hours=1)

            # Determine step
            delta = end_time - start_time
            if delta.total_seconds() <= 3600:
                step = "15s"
            elif delta.total_seconds() <= 21600:
                step = "1m"
            else:
                step = "5m"

            result = await client.query_range(
                query=promql,
                start=start_time,
                end=end_time,
                step=step
            )

            if not result:
                return f"No data returned for query: {promql}"

            output = [f"Metrics query: `{promql}` (last {time_range})\n"]

            for series in result[:5]:  # Limit to 5 series
                metric = series.get("metric", {})
                values = series.get("values", [])

                metric_labels = ", ".join([f"{k}={v}" for k, v in metric.items()])
                output.append(f"**{metric_labels or 'metric'}**")

                if values:
                    # Show latest value and trend
                    latest = float(values[-1][1]) if values else 0
                    first = float(values[0][1]) if values else 0
                    trend = "↑" if latest > first else "↓" if latest < first else "→"
                    output.append(f"  Current: {latest:.4f} {trend}")
                    output.append(f"  Points: {len(values)}")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Grafana metrics error: {e}")
            return f"Error querying metrics: {str(e)}"

    async def _query_grafana_logs(self, args: Dict[str, Any]) -> str:
        """Query logs via Grafana/Loki"""
        from app.services.loki_client import LokiClient

        logql = args.get("logql", "")
        limit = args.get("limit", 50)
        time_range = args.get("time_range", "1h")

        if not logql:
            return "Error: logql parameter is required"

        try:
            client = LokiClient()

            # Parse time range
            end_time = datetime.now()
            if time_range.endswith('m'):
                minutes = int(time_range[:-1])
                start_time = end_time - timedelta(minutes=minutes)
            elif time_range.endswith('h'):
                hours = int(time_range[:-1])
                start_time = end_time - timedelta(hours=hours)
            else:
                start_time = end_time - timedelta(hours=1)

            entries = await client.query_range(
                query=logql,
                start=start_time,
                end=end_time,
                limit=limit
            )

            if not entries:
                return f"No logs found for query: {logql}"

            output = [f"Log query: `{logql}` (last {time_range}, showing {min(len(entries), limit)} entries)\n"]

            for entry in entries[:limit]:
                timestamp = entry.timestamp.strftime("%H:%M:%S") if entry.timestamp else "N/A"
                level = entry.labels.get("level", "")
                line = entry.line[:200] + "..." if len(entry.line) > 200 else entry.line
                output.append(f"[{timestamp}] {level}: {line}")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Grafana logs error: {e}")
            return f"Error querying logs: {str(e)}"

    async def _get_correlated_alerts(self, args: Dict[str, Any]) -> str:
        """Get correlated alerts"""
        from app.models import Alert
        from app.models_troubleshooting import AlertCorrelation

        if not self.alert_id:
            return "No alert context available"

        try:
            # Get current alert
            alert = self.db.query(Alert).filter(Alert.id == self.alert_id).first()
            if not alert:
                return "Alert not found"

            if not alert.correlation_id:
                return "This alert is not part of a correlation group"

            # Get correlation
            correlation = self.db.query(AlertCorrelation).filter(
                AlertCorrelation.id == alert.correlation_id
            ).first()

            if not correlation:
                return "Correlation group not found"

            # Get related alerts
            related_alerts = self.db.query(Alert).filter(
                Alert.correlation_id == correlation.id
            ).order_by(Alert.timestamp.asc()).all()

            output = [f"**Correlation Group**: {correlation.id}"]
            output.append(f"Summary: {correlation.summary or 'No summary'}")

            if correlation.root_cause_analysis:
                output.append(f"\n**Root Cause Analysis:**")
                output.append(f"{correlation.root_cause_analysis}")

            output.append(f"\n**Related Alerts ({len(related_alerts)}):**\n")

            for i, related in enumerate(related_alerts, 1):
                current = " ← (current)" if related.id == self.alert_id else ""
                output.append(f"{i}. [{related.timestamp.strftime('%H:%M:%S')}] {related.severity.upper()}: {related.alert_name}{current}")
                output.append(f"   Instance: {related.instance}")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Correlated alerts error: {e}")
            return f"Error fetching correlated alerts: {str(e)}"

    async def _get_service_dependencies(self, args: Dict[str, Any]) -> str:
        """Get service dependencies from architecture docs"""
        from app.models_knowledge import DesignDocument, DesignImage

        service = args.get("service", "")

        if not service:
            return "Error: service parameter is required"

        try:
            # Search architecture documents
            docs = self.db.query(DesignDocument).filter(
                DesignDocument.doc_type == "architecture",
                DesignDocument.content.ilike(f"%{service}%")
            ).limit(3).all()

            # Search analyzed architecture images
            images = self.db.query(DesignImage).filter(
                DesignImage.image_type == "architecture",
                DesignImage.ai_analysis.cast(str).ilike(f"%{service}%")
            ).limit(2).all()

            if not docs and not images:
                return f"No architecture information found for service '{service}'"

            output = [f"**Service Dependencies for '{service}':**\n"]

            for doc in docs:
                output.append(f"**From: {doc.title}**")
                # Extract relevant section (simplified)
                content = doc.content or ""
                # Find paragraphs mentioning the service
                paragraphs = content.split('\n\n')
                relevant = [p for p in paragraphs if service.lower() in p.lower()][:2]
                for p in relevant:
                    output.append(f"  {p[:300]}...")
                output.append("")

            for img in images:
                output.append(f"**From Architecture Diagram: {img.title}**")
                analysis = img.ai_analysis or {}

                # Extract components and connections
                components = analysis.get("components", [])
                connections = analysis.get("connections", [])

                if components:
                    relevant_components = [c for c in components if service.lower() in str(c).lower()]
                    if relevant_components:
                        output.append(f"  Components: {relevant_components[:5]}")

                if connections:
                    relevant_connections = [c for c in connections if service.lower() in str(c).lower()]
                    if relevant_connections:
                        output.append(f"  Connections: {relevant_connections[:5]}")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Service dependencies error: {e}")
            return f"Error fetching service dependencies: {str(e)}"

    async def _get_feedback_history(self, args: Dict[str, Any]) -> str:
        """Get past user feedback"""
        from app.models_learning import AnalysisFeedback

        limit = args.get("limit", 5)

        try:
            # Get recent feedback
            feedback_list = self.db.query(AnalysisFeedback).order_by(
                AnalysisFeedback.created_at.desc()
            ).limit(limit).all()

            if not feedback_list:
                return "No feedback history available"

            output = [f"**Recent Feedback ({len(feedback_list)} entries):**\n"]

            for i, fb in enumerate(feedback_list, 1):
                output.append(f"{i}. Score: {fb.effectiveness_score}/5")
                if fb.feedback_text:
                    output.append(f"   Comment: {fb.feedback_text[:200]}")
                if fb.what_worked:
                    output.append(f"   What worked: {fb.what_worked[:200]}")
                if fb.what_was_missing:
                    output.append(f"   What was missing: {fb.what_was_missing[:200]}")
                output.append(f"   Date: {fb.created_at}")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Feedback history error: {e}")
            return f"Error fetching feedback: {str(e)}"

    async def _get_alert_details(self, args: Dict[str, Any]) -> str:
        """Get full alert details"""
        from app.models import Alert

        if not self.alert_id:
            return "No alert context available"

        try:
            alert = self.db.query(Alert).filter(Alert.id == self.alert_id).first()
            if not alert:
                return "Alert not found"

            output = [f"**Alert Details**\n"]
            output.append(f"- **Name:** {alert.alert_name}")
            output.append(f"- **Severity:** {alert.severity}")
            output.append(f"- **Status:** {alert.status}")
            output.append(f"- **Instance:** {alert.instance}")
            output.append(f"- **Job:** {alert.job}")
            output.append(f"- **Timestamp:** {alert.timestamp}")

            if alert.fingerprint:
                output.append(f"- **Fingerprint:** {alert.fingerprint}")

            # Annotations
            annotations = alert.annotations_json or {}
            if annotations:
                output.append(f"\n**Annotations:**")
                for key, value in annotations.items():
                    output.append(f"  - {key}: {value}")

            # Labels
            labels = alert.labels_json or {}
            if labels:
                output.append(f"\n**Labels:**")
                for key, value in labels.items():
                    output.append(f"  - {key}: {value}")

            if alert.ai_analysis:
                output.append(f"\n**Previous AI Analysis:**")
                output.append(f"{alert.ai_analysis[:500]}...")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Alert details error: {e}")
            return f"Error fetching alert details: {str(e)}"


    async def _suggest_ssh_command(self, args: Dict[str, Any]) -> str:
        """Suggest a command for the user to run, with safety validation"""
        from app.services.command_validator import CommandValidator, ValidationResult
        
        server = args.get("server", "").strip()
        command = args.get("command", "").strip()
        explanation = args.get("explanation", "").strip()

        if not server or not command:
            return "Error: server and command are required"
        
        # BLOCK: Reject tool names being suggested as shell commands (AI hallucination)
        tool_names = [
            'query_grafana_metrics', 'query_grafana_logs', 'get_recent_changes',
            'get_similar_incidents', 'search_knowledge', 'get_correlated_alerts',
            'get_service_dependencies', 'get_feedback_history', 'get_alert_details',
            'get_proven_solutions', 'suggest_ssh_command'
        ]
        cmd_base = command.strip().split()[0] if command.strip() else ''
        if cmd_base in tool_names:
            return (
                f"⛔ INVALID COMMAND\n\n"
                f"'{cmd_base}' is an INTERNAL TOOL NAME, not a shell command.\n\n"
                f"**You called suggest_ssh_command with a tool name instead of a real shell command.**\n\n"
                f"If you need to use '{cmd_base}', call it directly as a tool_call, do NOT suggest it to the user.\n\n"
                f"Please suggest a REAL shell command (like systemctl, cat, grep, etc.) or call the internal tool directly."
            )
        
        # Auto-fix: Add --no-pager to systemctl commands to prevent pager blocking terminal
        if 'systemctl' in command and '--no-pager' not in command:
            command = command.replace('systemctl ', 'systemctl --no-pager ', 1)
            args["command"] = command  # Update args so CMD_CARD gets the fixed command
            
        # Auto-fix: Add --no-pager to journalctl commands
        if 'journalctl' in command and '--no-pager' not in command:
            command = command.replace('journalctl ', 'journalctl --no-pager ', 1)
            args["command"] = command

        # Detect OS type from server name or default to linux
        # Simple heuristic: if server contains 'win' or ends with Windows-like patterns
        os_type = "windows" if any(x in server.lower() for x in ['win', 'windows']) else "linux"
        
        # Validate command using CommandValidator
        validator = CommandValidator()
        validation = validator.validate_command(command, os_type)
        
        # Handle validation result
        if validation.result == ValidationResult.BLOCKED:
            return (
                f"⛔ COMMAND BLOCKED\n\n"
                f"The command you attempted to suggest has been blocked by the safety filter.\n\n"
                f"**Reason:** {validation.reason}\n"
                f"**Risk Level:** {validation.risk_level.upper()}\n"
                f"**Pattern Matched:** `{validation.matched_pattern}`\n\n"
                f"⚠️ INSTRUCTION: You MUST suggest a safer alternative command.\n"
                f"Do NOT attempt to bypass this filter. Think of another approach to accomplish the goal safely."
            )
        
        # Build response based on validation result
        safety_indicator = ""
        if validation.result == ValidationResult.SUSPICIOUS:
            safety_indicator = (
                f"\n\n⚠️ **Warning:** {validation.reason}\n"
                f"This command requires elevated privileges or modifies system state. "
                f"Proceed with caution."
            )
        else:
            safety_indicator = "\n\n✅ **Safe** (read-only or low-risk command)"

        # Return a response that FORCES the Agent to understand:
        # 1. A command has been suggested
        # 2. It MUST wait for output
        # 3. It should NOT suggest more commands
        
        return (
            f"✓ Command suggestion recorded.\n"
            f"Server: {server}\n"
            f"Command: {command}\n"
            f"Explanation: {explanation}\n"
            f"{safety_indicator}\n\n"
            f"⚠️ CRITICAL INSTRUCTION: You have suggested ONE command. You MUST now:\n"
            f"1. Display the command to the user in a markdown code block\n"
            f"2. Include the safety indicator (✅ Safe or ⚠️ Warning)\n"
            f"3. STOP your response immediately after displaying the command\n"
            f"4. DO NOT suggest additional commands\n"
            f"5. DO NOT write 'Once you run that...' or 'After that...'\n"
            f"6. WAIT for the user to provide the command output\n\n"
            f"Status: ⏳ Waiting for user execution and output..."
        )

    async def _get_proven_solutions(self, args: Dict[str, Any]) -> str:
        """Find solutions that worked for similar problems in the past."""
        problem_description = args.get("problem_description", "").strip()
        limit = args.get("limit", 5)

        if not problem_description:
            return "Error: problem_description is required"

        try:
            from app.models import SolutionOutcome
            from sqlalchemy import func
            
            # Query for successful solutions
            results = (
                self.db.query(
                    SolutionOutcome.solution_type,
                    SolutionOutcome.solution_reference,
                    SolutionOutcome.solution_summary,
                    SolutionOutcome.problem_description,
                    func.count().label('total_uses'),
                    func.sum(func.cast(SolutionOutcome.success == True, type_=sa.Integer)).label('success_count')
                )
                .filter(SolutionOutcome.success == True)
                .group_by(
                    SolutionOutcome.solution_type,
                    SolutionOutcome.solution_reference,
                    SolutionOutcome.solution_summary,
                    SolutionOutcome.problem_description
                )
                .order_by(func.count().desc())
                .limit(limit)
                .all()
            )

            if not results:
                return "No proven solutions found in the learning database yet. This is a new problem - proceed with your own analysis."

            output_parts = ["**Proven Solutions from Past Success:**\n"]
            for i, r in enumerate(results, 1):
                success_rate = 100  # We filtered for success=True
                output_parts.append(
                    f"{i}. **{r.solution_type.title()}**: `{r.solution_reference[:100] if r.solution_reference else 'N/A'}`\n"
                    f"   - Original problem: {r.problem_description[:100] if r.problem_description else 'N/A'}...\n"
                    f"   - Used {r.total_uses} time(s), all successful\n"
                )

            output_parts.append("\n*These solutions worked before - consider trying them first.*")
            return "\n".join(output_parts)

        except Exception as e:
            logger.error(f"Error in get_proven_solutions: {e}")
            return f"Error searching proven solutions: {str(e)}"

