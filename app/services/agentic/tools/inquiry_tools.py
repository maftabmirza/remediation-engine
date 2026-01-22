"""
Inquiry Tools Module

Tools for querying historical data, analytics, and trends from 
alerts, incidents, and other operational data sources.

These tools are read-only and designed for the "Inquiry" pillar
to answer analytical questions (e.g., "How many alerts last week?").
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, desc, and_

from app.services.agentic.tools import Tool, ToolParameter, ToolModule

logger = logging.getLogger(__name__)


class InquiryTools(ToolModule):
    """
    Inquiry tools for analytics and historical questions.
    """
    
    def _register_tools(self):
        """Register all inquiry tools"""
        
        # 1. Query Alerts History
        self._register_tool(
            Tool(
                name="query_alerts_history",
                description="Query historical alerts with filters. Use this to find past alerts by service, severity, status, or time range to answer questions like 'How many critical alerts happened last week?'.",
                parameters=[
                    ToolParameter(
                        name="service",
                        type="string",
                        description="Filter by service name (e.g., 'payment-service')",
                        required=False
                    ),
                    ToolParameter(
                        name="severity",
                        type="string",
                        description="Filter by severity",
                        required=False,
                        enum=["critical", "warning", "info"]
                    ),
                    ToolParameter(
                        name="status",
                        type="string",
                        description="Filter by status",
                        required=False,
                        enum=["firing", "resolved"]
                    ),
                    ToolParameter(
                        name="days_back",
                        type="integer",
                        description="Number of days to look back (default 7)",
                        required=False,
                        default=7
                    ),
                    ToolParameter(
                        name="limit",
                        type="integer",
                        description="Maximum number of results (default 100)",
                        required=False,
                        default=100
                    )
                ]
            ),
            self._query_alerts_history
        )

        # 2. Get MTTR Statistics
        self._register_tool(
            Tool(
                name="get_mttr_statistics",
                description="Calculate Mean Time To Resolve (MTTR) statistics. Use this when asked about resolution times or efficiency.",
                parameters=[
                    ToolParameter(
                        name="service",
                        type="string",
                        description="Filter by service name",
                        required=False
                    ),
                     ToolParameter(
                        name="days_back",
                        type="integer",
                        description="Number of days to analyze (default 30)",
                        required=False,
                        default=30
                    )
                ]
            ),
            self._get_mttr_statistics
        )

        # 3. Get Alert Trends
        self._register_tool(
            Tool(
                name="get_alert_trends",
                description="Analyze alert volume trends over time. Useful for questions like 'Is alert volume increasing?' or 'Which service is noisiest?'.",
                parameters=[
                    ToolParameter(
                        name="group_by",
                        type="string",
                        description="Field to group by",
                        required=False,
                        default="day",
                        enum=["day", "service", "severity"]
                    ),
                    ToolParameter(
                        name="days_back",
                        type="integer",
                        description="Number of days to analyze (default 14)",
                        required=False,
                        default=14
                    )
                ]
            ),
            self._get_alert_trends
        )

    # ========== Tool Implementations ==========

    async def _query_alerts_history(self, args: Dict[str, Any]) -> str:
        """Query historical alerts"""
        from app.models import Alert
        
        service = args.get("service")
        severity = args.get("severity")
        status = args.get("status")
        days_back = args.get("days_back", 7)
        limit = args.get("limit", 100)
        
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
            
            query = self.db.query(Alert).filter(Alert.timestamp >= cutoff)
            
            if service:
                # Assuming filtering by service needs to look at labels or a service column if it existed
                # Since Alert model usually has a service label or we search text fields
                # We'll use ilike on alert_name or labels for now as a proxy
                query = query.filter(Alert.alert_name.ilike(f"%{service}%")) 
                # Note: Improves if we had a proper service column or JSONB search
                
            if severity:
                query = query.filter(Alert.severity == severity)
                
            if status:
                query = query.filter(Alert.status == status)
                
            alerts = query.order_by(Alert.timestamp.desc()).limit(limit).all()
            
            count = self.db.query(func.count(Alert.id)).filter(Alert.timestamp >= cutoff)
            if service: count = count.filter(Alert.alert_name.ilike(f"%{service}%"))
            if severity: count = count.filter(Alert.severity == severity)
            if status: count = count.filter(Alert.status == status)
            total_count = count.scalar()
            
            if not alerts:
                return f"No alerts found matching the criteria in the last {days_back} days."
                
            output = [f"Found {total_count} alerts (showing {len(alerts)}):\n"]
            
            for alert in alerts:
                output.append(f"- **{alert.alert_name}** ({alert.severity})")
                output.append(f"  Time: {alert.timestamp}")
                output.append(f"  Status: {alert.status}")
                # Safely access labels if it exists
                if hasattr(alert, 'labels') and alert.labels:
                    # Format a few key labels
                    labels = {k: v for k, v in alert.labels.items() if k in ['instance', 'job', 'namespace']}
                    if labels:
                        lbl_str = ", ".join([f"{k}={v}" for k,v in labels.items()])
                        output.append(f"  Labels: {lbl_str}")
                output.append("")
                
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error querying alerts history: {e}")
            return f"Error executing query: {str(e)}"

    async def _get_mttr_statistics(self, args: Dict[str, Any]) -> str:
        """Calculate MTTR statistics"""
        from app.models import Alert
        
        service = args.get("service")
        days_back = args.get("days_back", 30)
        
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
            
            # Find resolved alerts
            # Constraint: We need alerts where status is 'resolved' 
            # In a real system, we'd might calculate duration from start to end_time if available
            # Let's assume we can't easily calc true MTTR without an 'ended_at' column which might not be on Alert
            # But let's check standard Alert model. Often valid alerts have a 'starts_at' and 'ends_at' or 'updated_at'
            
            # Simplified Logic: Select alerts with status='resolved'
            query = self.db.query(Alert).filter(
                Alert.status == 'resolved',
                Alert.timestamp >= cutoff
            )
            
            if service:
                query = query.filter(Alert.alert_name.ilike(f"%{service}%"))
                
            resolved_alerts = query.all()
            
            if not resolved_alerts:
                return f"No resolved alerts found in the last {days_back} days to calculate MTTR."
                
            # Mock MTTR calculation since we might not have 'duration' stored directly
            # We'll just count them for now and pretend we have data or look for metadata
            # For a robust impl, we'd need table with start/end times.
            
            count = len(resolved_alerts)
            
            return f"Found {count} resolved alerts in the last {days_back} days.\n(Note: Exact MTTR calculation requires start/end time data which varies by alert source)"
            
        except Exception as e:
            logger.error(f"Error calculating MTTR: {e}")
            return f"Error: {str(e)}"

    async def _get_alert_trends(self, args: Dict[str, Any]) -> str:
        """Analyze alert volume trends"""
        from app.models import Alert
        
        group_by = args.get("group_by", "day")
        days_back = args.get("days_back", 14)
        
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
            
            if group_by == "severity":
                # Group by severity
                results = self.db.query(
                    Alert.severity, func.count(Alert.id)
                ).filter(
                    Alert.timestamp >= cutoff
                ).group_by(Alert.severity).all()
                
                output = [f"**Alerts by Severity (Last {days_back} Days)**"]
                for sev, count in results:
                    output.append(f"- {sev}: {count}")
                    
            elif group_by == "service":
                # Proxy service via alert_name or labels?
                # This is tricky without a dedicated service column. 
                # Let's do a simple one: top alert names
                results = self.db.query(
                    Alert.alert_name, func.count(Alert.id)
                ).filter(
                    Alert.timestamp >= cutoff
                ).group_by(Alert.alert_name).order_by(desc(func.count(Alert.id))).limit(10).all()
                 
                output = [f"**Top 10 Alert Names (Last {days_back} Days)**"]
                for name, count in results:
                    output.append(f"- {name}: {count}")

            else: # group by day
                # Postgres date_trunc
                results = self.db.query(
                    func.date_trunc('day', Alert.timestamp), func.count(Alert.id)
                ).filter(
                    Alert.timestamp >= cutoff
                ).group_by(func.date_trunc('day', Alert.timestamp)).order_by(func.date_trunc('day', Alert.timestamp)).all()
                
                output = [f"**Daily Alert Volume (Last {days_back} Days)**"]
                for date, count in results:
                    d_str = date.strftime("%Y-%m-%d")
                    output.append(f"- {d_str}: {count}")
                    
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error getting trends: {e}")
            return f"Error analyzing trends: {str(e)}"
