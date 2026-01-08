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
        feedback_history: List[AnalysisFeedback] = [],
        ranked_solutions: Optional[Dict[str, Any]] = None,
        server_os: str = 'linux'  # NEW: 'linux' or 'windows'
    ) -> str:
        """
        Generate the system prompt for the chat assistant.
        """
        # Select command language based on OS
        cmd_lang = "PowerShell" if server_os.lower() == 'windows' else "bash"
        os_name = "Windows" if server_os.lower() == 'windows' else "Linux"

        base_prompt = f"""You are Antigravity, an advanced SRE AI Agent.
You are pair-programming with the user to resolve a production incident on a {os_name} server.

## Your Operating Mode:
1.  **Iterative Troubleshooting**: Do not dump a wall of text. Propose **one** step at a time.
2.  **Command Execution**: When you need information, provide the exact `{cmd_lang}` command to run.
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

        # NEW: Solution formatting instructions
        if ranked_solutions:
            solutions = ranked_solutions.get('solutions', [])
            strategy = ranked_solutions.get('presentation_strategy', 'single_solution')
            
            context_sections.append(f"""
## KNOWLEDGE BASE:

Our organization has {len(solutions)} documented runbook(s) that match this query.
These runbooks represent **tested, approved procedures** from our knowledge base.

**Decision Framework:**
1. If a runbook directly answers the user's question → Reference it and explain why it applies
2. If the runbook is related but not exact → Mention it as additional context
3. If the runbook is not relevant → Use your own expertise

When referencing a runbook, include the link so the user can execute it.
The runbook details will be provided below.
""")

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
    def get_investigation_plan_prompt(alert: Alert, server_os: str = 'linux') -> str:
        """
        Generate prompt for Investigation Path.
        """
        cmd_lang = "PowerShell" if server_os.lower() == 'windows' else "bash"
        os_name = "Windows" if server_os.lower() == 'windows' else "Linux"

        return f"""
Create a step-by-step investigation plan for this alert:
Alert: {alert.alert_name}
Instance: {alert.instance}
Description: {alert.annotations_json.get('description', '')}

INSTRUCTIONS:
1. Provide 3-5 logical steps to diagnose the issue on this {os_name} server.
2. For each step, provide a specific `{cmd_lang}` command to run.
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
