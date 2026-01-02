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
        observability_context: Optional[Any] = None
    ) -> str:
        """
        Generate the system prompt for the chat assistant.
        """
        base_prompt = """You are Antigravity, an advanced SRE AI Agent.
You are pair-programming with the user to resolve a production incident.

## Your Operating Mode:
1.  **Iterative Troubleshooting**: Do not dump a wall of text. Propose **one** step at a time.
2.  **Command Execution**: When you need information, provide the exact `bash` command to run.
3.  **Output Analysis**: The user will paste the command output. You must analyze it deeply.
    - If the output confirms your hypothesis -> Propose the fix (e.g., `systemctl restart` or `Start-Service`).
    - If the output disproves it -> Propose a new hypothesis and a new command.
    - If a service is found STOPPED, immediately suggest starting it.
4.  **Tone**: Professional, concise, confidence-inspiring.

## Format:
- Use **bold** for key concepts.
- Use `code blocks` for all commands/file paths.
- **Windows Context**: If the user is on Windows (PowerShell), provide `PowerShell` commands.
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

        if observability_context:
            obs_text = []
            
            # Format Logs
            if hasattr(observability_context, 'logs_results') and observability_context.logs_results:
                logs_count = observability_context.total_logs
                logs = []
                for res in observability_context.logs_results:
                    for entry in res.entries[:5]:  # Limit to 5 logs to avoid token overflow
                        logs.append(f"[{entry.timestamp}] {entry.line[:200]}")
                
                if logs:
                    obs_text.append(f"Recent Logs ({logs_count} found):\n" + "\n".join(logs))

            # Format Metrics
            if hasattr(observability_context, 'metrics_results') and observability_context.metrics_results:
                metrics = []
                for res in observability_context.metrics_results:
                    if res.value is not None:
                        metrics.append(f"{res.metric_name}: {res.value}")
                
                if metrics:
                    obs_text.append("Key Metrics:\n" + "\n".join(metrics))

            # Format Traces
            if hasattr(observability_context, 'traces_results') and observability_context.traces_results:
                failed_traces = 0
                slow_traces = 0
                # Simple heuristic analysis of traces
                for res in observability_context.traces_results:
                    for trace in res.traces:
                        if trace.duration_ms > 1000: # Slow
                            slow_traces += 1
                        # If we had error info in trace summary we would use it

                if slow_traces > 0:
                     obs_text.append(f"Traces: Found {slow_traces} slow traces (>1s).")

            if obs_text:
                context_sections.append(f"""
LIVE OBSERVABILITY DATA (Auto-fetched from Grafana Stack):
{chr(10).join(obs_text)}
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
