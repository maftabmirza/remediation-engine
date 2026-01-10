"""
Troubleshooting Tools Module

Tools specifically for alert investigation and troubleshooting workflow.
Includes change correlation, alert details, service dependencies,
and command suggestion for interactive troubleshooting.
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.services.agentic.tools import Tool, ToolParameter, ToolModule

logger = logging.getLogger(__name__)


class TroubleshootingTools(ToolModule):
    """
    Troubleshooting-specific tools for alert investigation.
    
    These tools are primarily used in Troubleshooting mode and include
    alert-context-aware operations and command suggestions.
    """
    
    def _register_tools(self):
        """Register all troubleshooting tools"""
        
        # 1. Get Recent Changes
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

        # 2. Get Correlated Alerts
        self._register_tool(
            Tool(
                name="get_correlated_alerts",
                description="Get other alerts that are correlated with the current alert (same incident group). Returns related alerts and root cause analysis if available.",
                parameters=[]
            ),
            self._get_correlated_alerts
        )

        # 3. Get Service Dependencies
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

        # 4. Get User Feedback History
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

        # 5. Get Alert Details
        self._register_tool(
            Tool(
                name="get_alert_details",
                description="Get full details of the current alert including all labels, annotations, and metadata.",
                parameters=[]
            ),
            self._get_alert_details
        )

        # 6. Suggest Server Command
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

    # ========== Tool Implementations ==========

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

                output.append(f"\n**Previous AI Analysis:**")
                output.append(f"{alert.ai_analysis[:500]}...")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Alert details error: {e}")
            return f"Error fetching alert details: {str(e)}"

    async def _suggest_ssh_command(self, args: Dict[str, Any]) -> str:
        """Suggest a command for the user to run"""
        server = args.get("server", "").strip()
        command = args.get("command", "").strip()
        explanation = args.get("explanation", "").strip()

        if not server or not command:
            return "Error: server and command are required"

        # Return a response that FORCES the Agent to understand:
        # 1. A command has been suggested
        # 2. It MUST wait for output
        # 3. It should NOT suggest more commands
        
        return (
            f"✓ Command suggestion recorded.\n"
            f"Server: {server}\n"
            f"Command: {command}\n"
            f"Explanation: {explanation}\n\n"
            f"⚠️ CRITICAL INSTRUCTION: You have suggested ONE command. You MUST now:\n"
            f"1. Display the command to the user in a markdown code block\n"
            f"2. STOP your response immediately after displaying the command\n"
            f"3. DO NOT suggest additional commands\n"
            f"4. DO NOT write 'Once you run that...' or 'After that...'\n"
            f"5. WAIT for the user to provide the command output\n\n"
            f"Status: Waiting for user execution and output..."
        )
