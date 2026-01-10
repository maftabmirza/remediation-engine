"""
Prompt Service
Centralizes management of LLM prompts and context injection.
"""
import logging
from typing import List, Optional, Dict, Any
from app.models import Alert
from app.models_troubleshooting import AlertCorrelation, FailurePattern
from app.models_learning import AnalysisFeedback, ExecutionOutcome

logger = logging.getLogger(__name__)

class PromptService:
    """Service for generating context-aware prompts for the LLM."""

    @staticmethod
    def get_system_prompt(
        alert: Optional[Alert] = None,
        correlation: Optional[AlertCorrelation] = None,
        similar_incidents: List[Dict[str, Any]] = [],
        feedback_history: List[AnalysisFeedback] = []
    ) -> str:
        """
        Generate the system prompt for the chat assistant.
        """
        base_prompt = """You are RE-VIVE, an advanced SRE AI Agent.
You are pair-programming with the user to resolve a production incident.

## Your Operating Mode:
1.  **Iterative Troubleshooting**: Do not dump a wall of text. Propose **one** step at a time.
2.  **Command Execution**: When you need information, provide the exact `bash` command to run.
3.  **Output Analysis**: The user will paste the command output. You must analyze it deeply.
    - If the output confirms your hypothesis -> Propose the fix.
    - If the output disproves it -> Propose a new hypothesis and a new command.
4.  **Tone**: Professional, concise, confidence-inspiring.

## Format:
- Use **bold** for key concepts.
- Use `code blocks` for all commands/file paths.
- Keep responses short (under 2 paragraphs) per turn unless explaining a complex solution.
"""
        
        context_sections = []

        if alert:
            context_sections.append(f"""
CURRENT ALERT CONTEXT:
- Name: {alert.alert_name}
- Severity: {alert.severity}
- Instance: {alert.instance}
- Status: {alert.status}
- Summary: {alert.annotations_json.get('summary', 'N/A')}
- Description: {alert.annotations_json.get('description', 'N/A')}
""")

        if correlation:
            summary = correlation.summary
            alert_count = len(correlation.alerts)
            context_sections.append(f"""
CORRELATION CONTEXT:
- Group ID: {correlation.id}
- Summary: {summary}
- Related Alerts Count: {alert_count}
- Root Cause Analysis: {correlation.root_cause_analysis or 'Pending'}
""")

        if similar_incidents:
            incidents_text = "\n".join([
                f"- {inc['alert_name']} (Resolution: {inc.get('resolution', 'Unknown')})"
                for inc in similar_incidents[:3]
            ])
            context_sections.append(f"""
SIMILAR PAST INCIDENTS:
{incidents_text}
""")

        if feedback_history:
            feedback_text = "\n".join([
                f"- User Feedback: {fb.feedback_text} (Score: {fb.effectiveness_score})"
                for fb in feedback_history[:3] if fb.feedback_text
            ])
            if feedback_text:
                context_sections.append(f"""
PAST FEEDBACK TO CONSIDER:
{feedback_text}
""")

        if context_sections:
            return base_prompt + "\n".join(context_sections)
        
        return base_prompt

    @staticmethod
    def get_rca_prompt(correlation: AlertCorrelation, alerts: List[Alert]) -> str:
        """
        Generate prompt for Root Cause Analysis.
        """
        alerts_desc = "\n".join([
            f"- [{a.timestamp}] {a.severity.upper()}: {a.alert_name} on {a.instance} ({a.job or 'unknown service'})" 
            for a in alerts
        ])

        return f"""
Analyze the following alert storm to determine the Root Cause.

ALERT STREAM:
{alerts_desc}

INSTRUCTIONS:
1. Identify the primary root cause alert (the "smoking gun").
2. Explain YOUR reasoning based on timestamp, severity, and dependencies (e.g. DB failure causes App failure).
3. Identify affected services.
4. Estimate confidence (0.0 to 1.0).

OUTPUT JSON FORMAT ONLY:
{{
  "root_cause": "Short title of root cause",
  "reasoning": ["point 1", "point 2"],
  "confidence": 0.95,
  "affected_services": ["service1", "service2"]
}}
"""

    @staticmethod
    def get_investigation_plan_prompt(alert: Alert) -> str:
        """
        Generate prompt for Investigation Path.
        """
        return f"""
Create a step-by-step investigation plan for this alert:
Alert: {alert.alert_name}
Instance: {alert.instance}
Description: {alert.annotations_json.get('description', '')}

INSTRUCTIONS:
1. Provide 3-5 logical steps to diagnose the issue.
2. For each step, provide a specific `bash` command to run on Linux.
3. Be concise.

OUTPUT JSON FORMAT ONLY:
{{
  "steps": [
    {{
      "step_number": 1,
      "action": "Title of step",
      "description": "Why we are doing this",
      "component": "Component name",
      "command_to_run": "exact command"
    }}
  ],
  "estimated_time_minutes": 10
}}
"""

    @staticmethod
    def get_ai_helper_prompt(query: str, context: Optional[dict] = None) -> str:
        """
        Generate a context-aware prompt for the AI Helper.
        """
        base_prompt = """You are RE-VIVE, an intelligent AIOps assistant embedded in an observability platform.
Your goal is to help the user understand the data they are resolving on the screen or answer general operations questions.

"""
        
        context_str = ""
        if context:
            # Extract useful parts from the context object (structure from revive_widget.js)
            # Note: Widget sends 'title', we also check 'page_title' for backwards compatibility
            page_title = context.get('title') or context.get('page_title', 'Unknown Page')
            page_type = context.get('page_type', 'unknown')
            url = context.get('url', '')
            
            context_str += f"\n## Current Page Context\n"
            context_str += f"- **Page Title:** {page_title}\n"
            context_str += f"- **Page Type:** {page_type}\n"
            context_str += f"- **URL:** {url}\n"
            
            # Add Grafana expertise if on Grafana page
            if context.get('is_grafana') or context.get('is_native_grafana'):
                context_str += "\n### Grafana Stack Expertise\n"
                context_str += "You are an expert in the Grafana observability stack:\n"
                context_str += "- **PromQL** (Prometheus/Mimir) for metrics\n"
                context_str += "- **LogQL** (Loki) for logs\n"
                context_str += "- **TraceQL** (Tempo) for traces\n"
                context_str += "Help the user write, debug, and optimize their queries.\n"
                
                # Add detected query language
                query_lang = context.get('form_data', {}).get('query_language')
                if query_lang:
                    context_str += f"\n**Detected Query Language:** {query_lang}\n"

            # Form Data (e.g., in Runbooks or scraped inputs)
            if context.get('form_data'):
                context_str += "\n### Form / Input Data:\n"
                for k, v in context.get('form_data').items():
                    context_str += f"- {k}: {v}\n"

            # Page Content (Text)
            if context.get('page_text'):
                # Truncate if too long to avoid token limits
                text = context.get('page_text', '')
                if len(text) > 2000:
                    text = text[:2000] + "...(truncated)"
                context_str += f"\n### Visible Page Content:\n```text\n{text}\n```\n"

        if context_str:
            base_prompt += context_str
            base_prompt += """
## Instructions
1. Use the "Current Page Context" above to answer the user's question explicitly.
2. If the user asks about specific values visible on the page, quote them.
3. If the user asks for help with a form, suggest specific values based on the context.
4. If the context is not relevant to the query, answer based on your general SRE knowledge.
5. Be concise and helpful.

## Formatting
- Use **Markdown** for all responses.
- Use **bold** for key terms and important values.
- Use `code blocks` for commands, queries, and technical values.
- Use bullet points for lists.
- Use headings (##) to organize longer responses.
"""
        else:
            base_prompt += """
## Instructions
1. Answer the user's SRE/DevOps question based on your general knowledge.
2. If you need more context, ask the user to provide it.

## Formatting
- Use **Markdown** for all responses.
- Use **bold** for key terms and important values.
- Use `code blocks` for commands, queries, and technical values.
- Use bullet points for lists.
"""

        return base_prompt

    @staticmethod
    def get_routing_prompt(query: str, context: Optional[dict] = None) -> str:
        """
        Generate a prompt for the LLM to decide which tool to use.
        """
        return f"""
You are the "Central Router" for an AIOps Assistant. Your job is to analyze the user's request and decide which subsystem should handle it.

## Available Tools:
1. **observability**: Use this for requests asking to SEE data, metric values, logs, traces, or specific infrastructure status.
   - Examples: "Show me CPU usage", "List error logs", "What is the memory usage of app-svr?"
   
2. **remediation**: Use this for requests asking to FIX something, RUN a process, or SEARCH for procedures.
   - Examples: "How do I restart nginx?", "Find runbook for disk cleanup", "Fix the 500 error", "Run the health check", "remediate high cpu", "solve connection issue"

3. **general**: Use this for "How-to" questions that need an EXPLANATION, or general chit-chat, or if the request implies READING the current screen content.
   - Examples: "How can I see cpu info?", "What does this error mean?", "Explain this page", "Help me understand this graph"

## Current User Query:
"{query}"

## Instructions:
- Analyze the intent. Is the user asking for DATA (observability), an ACTION/PROCEDURE (remediation), or an EXPLANATION (general)?
- "How can I see..." is usually an Explanation (general).
- "Show me..." is usually Data (observability).
- "Fix..." or "Run..." is usually Action (remediation).
- **CRITICAL**: If the user asks to "read", "check", "look at", or "explain" something **currently on the screen**, use **general**. Do NOT use observability unless they explicitly ask to query/fetch NEW data.

## Output JSON ONLY:
{{
  "intent": "observability" | "remediation" | "general",
  "reasoning": "brief explanation of why",
  "confidence": 0.0 to 1.0
}}
"""
