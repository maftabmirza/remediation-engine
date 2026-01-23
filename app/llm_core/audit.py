"""
Shared LLM Audit Logging
"""
import logging
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models import AuditLog

logger = logging.getLogger(__name__)

def log_llm_action(
    db: Session,
    user_id: Optional[UUID],
    action: str,
    resource_type: str = "llm_flow",
    resource_id: Optional[UUID] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """Log an LLM-related action to the audit log."""
    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details_json=details,
        ip_address=ip_address,
        created_at=datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry
