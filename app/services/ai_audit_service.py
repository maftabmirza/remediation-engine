"""
AI Audit Service
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)

class AIAuditService:
    """
    Logs AI interactions for compliance and debugging.
    """
    
    def log_interaction(
        self, 
        session_id: UUID, 
        user_id: UUID, 
        query: str, 
        response: str, 
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log a complete interaction cycle.
        In a real implementation, this might write to a structured log file or database table.
        """
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "ai_interaction",
            "session_id": str(session_id) if session_id else None,
            "user_id": str(user_id) if user_id else None,
            "query": query,
            "response_summary": response[:100] + "..." if len(response) > 100 else response,
            "metadata": metadata or {}
        }
        
        # for now just log to application log
        logger.info(f"AI_AUDIT: {audit_entry}")

    def log_action(
        self,
        session_id: UUID,
        user_id: UUID,
        action_type: str,
        action_details: Dict[str, Any]
    ):
        """
        Log a specific validatable action proposed or taken by the AI.
        """
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "ai_action",
            "session_id": str(session_id) if session_id else None,
            "user_id": str(user_id) if user_id else None,
            "action_type": action_type,
            "details": action_details
        }
        logger.info(f"AI_AUDIT_ACTION: {audit_entry}")

_audit_service = AIAuditService()

def get_ai_audit_service():
    return _audit_service
