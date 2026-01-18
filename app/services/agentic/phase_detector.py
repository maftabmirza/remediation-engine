"""
Phase Detector for AI Troubleshooting Agent

Detects which phase the AI is in based on its output text.
Used to emit progress events for the UI.
"""

import re
from typing import Optional
from app.services.agentic.progress_messages import TroubleshootingPhase


class PhaseDetector:
    """Detect which phase the AI is in based on its output"""
    
    # Pattern matching for each phase
    PHASE_PATTERNS = {
        TroubleshootingPhase.IDENTIFY: [
            r'\bidentify(ing)?\b',
            r'what\s+(we\'re|are)\s+troubleshooting',
            r'the\s+issue\s+is',
            r'problem\s+description',
            r'user\s+reports?',
            r'phase\s+1',
        ],
        TroubleshootingPhase.VERIFY: [
            r'\bverify(ing)?\b',
            r'\bconfirm(ed|ing)?\b',
            r'target\s+(server|system|environment)',
            r'os\s+type',
            r'phase\s+2',
        ],
        TroubleshootingPhase.INVESTIGATE: [
            r'\binvestigat(e|ing)\b',
            r'\bgather(ing)?\s+(evidence|data)',
            r'\bquer(y|ying)\b',
            r'\bcheck(ing)?\b',
            r'\blook(ing)?\s+at',
            r'calling\s+tool',
            r'phase\s+3',
        ],
        TroubleshootingPhase.PLAN: [
            r'\banalyz(e|ing)\b',
            r'\bhypothesis\b',
            r'likely\s+cause',
            r'based\s+on\s+(the\s+)?(evidence|data|findings)',
            r'root\s+cause',
            r'phase\s+4',
        ],
        TroubleshootingPhase.ACT: [
            r'\bsuggest(ing|ed)?\b',
            r'\brecommend(ing|ed)?\b',
            r'command\s+to\s+run',
            r'remediation\s+step',
            r'action\s+plan',
            r'phase\s+5',
        ],
    }
    
    @classmethod
    def detect_phase(cls, text: str) -> Optional[str]:
        """
        Detect the current phase from AI output text.
        
        Args:
            text: The AI's output text (thought or response)
            
        Returns:
            Phase name as string, or None if no phase detected
        """
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Check for explicit phase markers first (more reliable)
        for phase, patterns in cls.PHASE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return phase.value
        
        return None
    
    @classmethod
    def extract_thought(cls, text: str) -> Optional[str]:
        """
        Extract the thought portion from AI output.
        
        Args:
            text: The AI's output text
            
        Returns:
            The extracted thought, or None
        """
        # Look for "Thought:" prefix
        thought_match = re.search(r'thought:\s*(.+?)(?:\n|$)', text, re.IGNORECASE | re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
            # Truncate at "Action:" if present
            action_idx = thought.lower().find('action:')
            if action_idx > 0:
                thought = thought[:action_idx].strip()
            return thought
        
        return None
    
    @classmethod
    def detect_phase_from_tool(cls, tool_name: str) -> Optional[str]:
        """
        Detect phase based on the tool being called.
        
        Args:
            tool_name: Name of the tool being executed
            
        Returns:
            Phase name as string
        """
        # Most tool calls happen in INVESTIGATE phase
        investigation_tools = [
            'query_grafana_metrics',
            'query_grafana_logs',
            'get_recent_changes',
            'get_correlated_alerts',
            'get_service_dependencies',
            'get_similar_incidents',
            'get_proven_solutions',
            'search_knowledge',
            'get_runbook',
            'get_feedback_history',
            'get_alert_details',
        ]
        
        if tool_name in investigation_tools:
            return TroubleshootingPhase.INVESTIGATE.value
        
        # Command suggestion is ACT phase
        if tool_name == 'suggest_ssh_command':
            return TroubleshootingPhase.ACT.value
        
        return None
