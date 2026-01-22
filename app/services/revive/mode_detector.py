import logging
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ModeDetectionResult:
    mode: str  # 'grafana', 'aiops', or 'ambiguous'
    confidence: float
    detected_intent: str
    suggested_tools: List[str]

class ReviveModeDetector:
    """
    Detects whether the user's intent implies interacting with Grafana (dashboards, alerts, metrics)
    or AIOps Platform (runbooks, servers, settings).
    """

    GRAFANA_KEYWORDS = [
        "dashboard", "panel", "query", "promql", "logql", "alert rule",
        "datasource", "annotation", "grafana", "prometheus", "loki",
        "tempo", "oncall", "sift", "visualization", "chart", "metric"
    ]

    AIOPS_KEYWORDS = [
        "runbook", "server", "credential", "execute", "ssh", "terminal",
        "remediation", "auto-analyze", "rule", "setting", "configuration",
        "audit", "permission", "user", "role", "group"
    ]

    def __init__(self, llm_service: Optional[Any] = None):
        self.llm_service = llm_service

    def detect(
        self,
        message: str,
        current_page: Optional[str] = None,
        explicit_mode: Optional[str] = None
    ) -> ModeDetectionResult:
        """
        Detect mode based on keywords and context.
        """
        if explicit_mode and explicit_mode in ['grafana', 'aiops']:
            return ModeDetectionResult(
                mode=explicit_mode,
                confidence=1.0,
                detected_intent="explicit_selection",
                suggested_tools=[]
            )

        message_lower = message.lower()

        # Keyword matching
        grafana_score = sum(1 for kw in self.GRAFANA_KEYWORDS if kw in message_lower)
        aiops_score = sum(1 for kw in self.AIOPS_KEYWORDS if kw in message_lower)

        # Context boosting
        if current_page:
            if any(p in current_page for p in ['dashboard', 'explore', 'alert-rules']):
                grafana_score += 2
            elif any(p in current_page for p in ['runbooks', 'servers', 'settings', 'admin']):
                aiops_score += 2

        # Decision
        if grafana_score > aiops_score:
            return ModeDetectionResult(
                mode='grafana',
                confidence=0.8, # Simple heuristic
                detected_intent="grafana_interaction",
                suggested_tools=[]
            )
        elif aiops_score > grafana_score:
            return ModeDetectionResult(
                mode='aiops',
                confidence=0.8,
                detected_intent="aiops_interaction",
                suggested_tools=[]
            )
        else:
            # Default or Ambiguous
            # If completely ambiguous, default to the context if available, else 'grafana' (as it's the visual part)
            # or maybe 'auto' to let LLM decide later?
            # For now, let's say ambiguous
            return ModeDetectionResult(
                mode='ambiguous',
                confidence=0.0,
                detected_intent="unclear",
                suggested_tools=[]
            )

    async def detect_with_llm(self, message: str) -> ModeDetectionResult:
        """
        Use LLM for advanced intent detection (Placeholder for Phase 4.4).
        """
        # TODO: Implement LLM-based classification if keyword matching is insufficient
        return self.detect(message)
