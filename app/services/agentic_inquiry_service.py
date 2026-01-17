"""
Agentic Inquiry Service

Handles natural language observability queries using a tool-calling LLM agent.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import User, LLMProvider
from app.services.agentic.native_agent import NativeToolAgent
from app.services.agentic.tools.registry import create_inquiry_registry
from app.services.llm_service import get_default_provider

logger = logging.getLogger(__name__)


class AgenticInquiryService:
    """
    Service that uses an agentic approach to satisfy observability inquiries.
    """

    def __init__(self, db: Session):
        self.db = db

    async def query(self, query: str, user: User) -> Dict[str, Any]:
        """
        Process a natural language query using the NativeToolAgent.
        """
        logger.info(f"Processing agentic inquiry: {query}")

        # Get default LLM provider
        provider = get_default_provider(self.db)
        if not provider:
            return {
                "summary": "Error: No LLM provider configured.",
                "insights": [],
                "recommendations": ["Configure an LLM provider (OpenAI, Anthropic, or Google) in Settings."]
            }

        # Create agent with inquiry registry (knowledge + observability)
        agent = NativeToolAgent(
            db=self.db,
            provider=provider
        )
        
        # Override the tool registry to only include inquiry tools
        agent.tool_registry = create_inquiry_registry(self.db)

        # Update system prompt for Inquiry Mode
        agent.messages = [{
            "role": "system",
            "content": self._get_inquiry_system_prompt()
        }]

        try:
            # Run the agent
            # We use a lower max_iterations for inquiry (usually 5 is enough)
            agent.max_iterations = 8
            response = await agent.run(query)

            # Format the output to match the existing FormattedResponse schema
            # if possible, or just return the agent's content as a summary.
            return {
                "summary": response.content,
                "intent_type": "agentic_inquiry",
                "insights": self._extract_insights_from_agent(agent),
                "recommendations": self._extract_recommendations(response.content),
                "stats": {
                    "iterations": response.iterations,
                    "tools_used": response.tool_calls_made
                },
                "has_alerts": "get_active_alerts" in response.tool_calls_made,
                "has_logs": "query_grafana_logs" in response.tool_calls_made,
                "has_metrics": "query_grafana_metrics" in response.tool_calls_made,
                "has_knowledge": "search_knowledge" in response.tool_calls_made
            }

        except Exception as e:
            logger.error(f"Agentic inquiry error: {e}", exc_info=True)
            return {
                "summary": f"I encountered an error while processing your request: {str(e)}",
                "insights": [],
                "recommendations": ["Try rephrasing your query.", "Check system logs for details."]
            }

    def _extract_insights_from_agent(self, agent: NativeToolAgent) -> list:
        """Extract structured insights from the agent's tool results."""
        insights = []
        
        # Iterate through messages to find tool results
        for msg in agent.messages:
            if msg.get("role") == "tool":
                tool_name = msg.get("name")
                content = msg.get("content")
                
                # Check for error strings in content
                if isinstance(content, str) and content.startswith("Error"):
                    continue

                if tool_name == "get_active_alerts" and isinstance(content, list):
                    for alert in content:
                        insights.append({
                            "title": f"Alert: {alert.get('name', 'Unknown')}",
                            "summary": f"[{alert.get('severity', 'UNKNOWN').upper()}] {alert.get('status', 'firing').upper()} on {alert.get('instance', 'unknown')}",
                            "details": [
                                f"Severity: {alert.get('severity')}",
                                f"Instance: {alert.get('instance')}",
                                f"Status: {alert.get('status')}",
                                f"Time: {alert.get('timestamp')}"
                            ],
                            "severity": "critical" if alert.get('severity', '').lower() in ('critical', 'error') else "warning"
                        })
                
                elif tool_name == "query_grafana_logs" and isinstance(content, list):
                    if content:
                        sample_logs = content[:5]
                        insights.append({
                            "title": "Log Samples",
                            "summary": f"Found {len(content)} matching log entries.",
                            "details": [f"[{l.get('timestamp')}] {l.get('line', '')[:100]}" for l in sample_logs],
                            "severity": "info"
                        })
                
                elif tool_name == "query_grafana_metrics" and isinstance(content, list):
                    for metric in content:
                        title = metric.get("metric_name", "Metric").replace('_', ' ').title()
                        value = metric.get("value")
                        if value is not None:
                            insights.append({
                                "title": title,
                                "summary": f"Current value: {value:.4f}",
                                "metric_value": float(value),
                                "severity": "info"
                            })
                
                elif tool_name == "search_knowledge" and isinstance(content, str):
                    if content and not content.startswith("No information found"):
                        insights.append({
                            "title": "Knowledge Base Insight",
                            "summary": "Relevant information discovered in runbooks/documentation.",
                            "details": [line.strip() for line in content.split('\n') if line.strip()][:5],
                            "severity": "info"
                        })
        
        return insights

    def _extract_recommendations(self, content: str) -> list:
        """Extract recommendation list from agent's response text."""
        recommendations = []
        lines = content.split('\n')
        in_recs = False
        
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue

            # Look for a recommendations section header
            if "recommend" in line_clean.lower() or "action" in line_clean.lower() or "suggest" in line_clean.lower():
                in_recs = True
                if line_clean.endswith(':'):
                    continue
            
            # Look for list items
            if in_recs:
                if line_clean.startswith('- ') or line_clean.startswith('* ') or (line_clean[0:1].isdigit() and line_clean[1:2] == "."):
                    recommendations.append(line_clean.lstrip('-* 0123456789.').strip())
                elif not any(x in line_clean.lower() for x in ["recommend", "action", "suggest"]) and len(line_clean) > 50:
                    # If we follow a header with a long line that's not a list, maybe it's a single recommendation
                    if len(recommendations) == 0:
                         recommendations.append(line_clean)
                    in_recs = False

        # Fallback: if no list items found but summary mentions "recommend", take the sentence
        if not recommendations:
            for line in lines:
                if "recommend" in line.lower() and len(line) > 20:
                    recommendations.append(line.strip())
                    break
        
        return recommendations[:5]

    def _get_inquiry_system_prompt(self) -> str:
        """System prompt specialized for observability inquiry"""
        return """You are RE-VIVE Inquiry Agent, an expert SRE assistant.
Your goal is to answer questions about the system's current state, health, and history using observability tools.

## CAPABILITIES
- **Knowledge**: Search runbooks, SOPs, and documentation.
- **Metrics**: Query Prometheus for real-time performance data (CPU, memory, latency).
- **Logs**: Search Loki logs for errors and patterns.
- **Alerts**: Query the database for firing or recently resolved alerts.

## GUIDELINES
1. **Be Precise**: If a user asks for "last 24 hours", use that time range in your tools.
2. **Multi-Source**: Often, a good answer combines alerts + logs + metrics.
3. **Fuzzy Matching**: If a user mentions an app with spaces (e.g., "api gateway"), try matching it as "api-gateway" or similar in labels.
4. **No Pre-emptive Summary**: Never claim "there were X alerts" or "everything is fine" BEFORE you have called the tools and received the results. 
5. **No Hallucination**: Only report what you find in the tools. If no data is found, say so.
6. **Parameter Handling**: If the user does not specify an application or service name, OMIT the 'application' parameter in tool calls (do not pass "None" or null).

## EXECUTION
- You can call multiple tools in sequence.
- Once you have enough information, provide a final comprehensive answer.
- You do NOT suggest SSH commands in Inquiry mode (that is for Troubleshooting mode).

## OUTPUT
Start with a clear summary ONLY AFTER you have gathered data. If you have no data yet, your first action must be calling a tool.
"""
