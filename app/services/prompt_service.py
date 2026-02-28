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

            # Expose Active Query (PromQL/LogQL/TraceQL)
            if context.get('query'):
                context_str += f"- **Active Query:** `{context.get('query')}`\n"
            
            # Expose Dashboard Structure
            if context.get('dashboard'):
                dash = context.get('dashboard')
                context_str += f"- **Dashboard Name:** {dash.get('name', 'Unknown')}\n"
                if dash.get('panels'):
                    # Limit panels to avoid token overflow
                    panels_list = dash.get('panels', [])[:20]
                    context_str += f"- **Visible Panels:** {', '.join(panels_list)}\n"
            
            # Add Grafana expertise if on Grafana page (Broadened check)
            if context.get('is_grafana') or context.get('is_native_grafana') or 'grafana' in page_type or 'prometheus' in page_type:
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
## CRITICAL RESPONSE RULES
1. **DIRECTLY ANSWER** the user's question first, before any explanations.
2. If they ask for a query, provide the EXACT working query in a code block immediately.
3. Do NOT describe the page unless they specifically ask about the page.
4. Be concise - aim for 2-4 paragraphs max.

## Query Examples to Use
When asked about alerts, provide these PromQL queries:
```promql
# All firing alerts
ALERTS{alertstate="firing"}

# Count of alerts over time
count(ALERTS{alertstate="firing"})

# Alerts from specific job
ALERTS{alertstate="firing", job="prometheus"}
```

When asked about metrics:
```promql
# CPU usage
100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory usage
100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))
```

## Format
- Start with the **answer** (query, command, or explanation)
- Then provide brief context if needed
- Use `code blocks` for all queries
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
You are the semantic intent classifier for an AIOps Assistant. Your goal is to route the user's request to the correct subsystem based on their **TRUE GOAL**.

Do NOT rely on specific keywords. Analyze what the user wants to ACHIEVE.

## Subsystems (Intents):

### 1. **general** (Goal: KNOWLEDGE, EXPLANATION, or SYNTAX HELP)
Route here if the user wants to **LEARN** something, **UNDERSTAND** a concept, or **GET HELP WRITING** a query.
*   **The Output:** The user expects text, code snippets, or an explanation.
*   **Key Distinction:** They do NOT expect to see live data from the system yet. They are preparing to run something, or asking "how to".
*   *Examples:* "How do I check CPU?", "Give me a query for alerts", "Explain this error", "What syntax do I use?"

### 2. **observability** (Goal: LIVE DATA, METRICS, LOGS)
Route here if the user wants to **SEE** the actual state of the system RIGHT NOW.
*   **The Output:** The user expects a table of numbers, a graph, a list of log entries, or a count.
*   **Key Distinction:** They are asking for the **RESULT** of a query, not the query itself.
*   *Examples:* "Show me the CPU usage", "List the errors from last hour", "Count the number of alerts", "Is the db down?"

### 3. **remediation** (Goal: ACTION, CHANGE, or PROCEDURE)
Route here if the user wants to **CHANGE** the system state or find a formal **PROCEDURE**.
*   **The Output:** The user expects an action to be taken (restart, scale) or a link to a runbook.
*   *Examples:* "Restart the pod", "Fix the high cpu", "Run the disk cleaner", "Find the playbook for database failure"

## Current User Query:
"{query}"

## Analysis Steps:
1.  **Identify the entity:** What is the user talking about? (e.g., "alerts", "CPU", "query")
2.  **Identify the desired outcome:**
    *   Do they want to *know how* to get it? -> **general**
    *   Do they want to *have* the data right now? -> **observability**
    *   Do they want to *fix* it? -> **remediation**

## Output JSON ONLY:
{{
  "intent": "observability" | "remediation" | "general",
  "reasoning": "Brief explanation of why this falls into the chosen category based on the user's goal.",
  "confidence": 0.0 to 1.0
}}
"""


