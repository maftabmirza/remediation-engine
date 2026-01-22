"""
AI Audit Service

Comprehensive audit logging for all AI-initiated actions across the Three-Pillar LLM system.
Tracks sessions, tool executions, permissions, and user confirmations.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from app.models import User
from app.models_ai import (
    AISession,
    AIMessage,
    AIToolExecution,
    AIActionConfirmation
)

logger = logging.getLogger(__name__)


@dataclass
class AIActivitySummary:
    """Summary of user's AI activity."""
    user_id: UUID
    pillar: str
    session_count: int
    message_count: int
    tool_execution_count: int
    confirmation_count: int
    total_execution_time_ms: int
    first_activity: datetime
    last_activity: datetime


@dataclass
class ToolUsageStats:
    """Aggregated tool usage statistics."""
    total_executions: int
    unique_tools: int
    success_rate: float
    avg_execution_time_ms: float
    top_tools: List[Dict[str, Any]]
    by_pillar: Dict[str, int]
    by_status: Dict[str, int]


class AIAuditService:
    """
    Service for logging and querying all AI-initiated actions.
    
    Provides comprehensive audit trail for:
    - AI session lifecycle
    - Tool executions with timing
    - Permission checks and denials
    - Action confirmations
    - User activity patterns
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_session_start(
        self,
        user: User,
        pillar: str,
        revive_mode: Optional[str] = None,
        context_type: Optional[str] = None,
        context_id: Optional[UUID] = None
    ) -> AISession:
        """
        Create and log new AI session start.
        
        Args:
            user: User starting the session
            pillar: 'inquiry', 'troubleshooting', or 'revive'
            revive_mode: For RE-VIVE: 'grafana' or 'aiops'
            context_type: Optional context (e.g., 'alert', 'dashboard')
            context_id: Optional ID of contextual entity
        
        Returns:
            Created AISession instance
        """
        session = AISession(
            user_id=user.id,
            pillar=pillar,
            revive_mode=revive_mode,
            context_type=context_type,
            context_id=context_id,
            started_at=datetime.now(timezone.utc),
            message_count=0
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(
            f"AI session started: session_id={session.id}, user={user.username}, "
            f"pillar={pillar}, mode={revive_mode}"
        )
        
        return session
    
    def log_session_end(self, session: AISession) -> None:
        """
        Mark session as ended.
        
        Args:
            session: AISession to end
        """
        session.ended_at = datetime.now(timezone.utc)
        self.db.commit()
        
        duration = (session.ended_at - session.started_at).total_seconds()
        logger.info(
            f"AI session ended: session_id={session.id}, "
            f"duration={duration:.2f}s, messages={session.message_count}"
        )
    
    def increment_message_count(self, session: AISession) -> None:
        """Increment message count for session."""
        session.message_count += 1
        self.db.commit()

    def log_interaction(
        self,
        session_id: Optional[UUID],
        user_id: UUID,
        query: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Simple interaction logging for RE-VIVE and other services.
        
        Args:
            session_id: Associated session ID (can be None for temporary sessions)
            user_id: User who made the query
            query: User's query text
            response: AI's response text
            metadata: Additional metadata (intent, confidence, etc.)
        """
        try:
            logger.info(
                f"AI Interaction - User: {user_id}, "
                f"Session: {session_id}, "
                f"Intent: {metadata.get('intent', 'unknown') if metadata else 'unknown'}"
            )
            # Could persist to a separate audit table in the future
        except Exception as e:
            logger.error(f"Failed to log interaction: {e}")

    
    def log_tool_execution(
        self,
        session: AISession,
        tool_name: str,
        tool_category: str,
        arguments: Dict[str, Any],
        result: str,
        status: str,
        execution_time_ms: int,
        permission_required: Optional[str] = None,
        permission_granted: bool = True
    ) -> AIToolExecution:
        """
        Log individual tool execution with full context.
        
        Args:
            session: Associated AI session
            tool_name: Name of executed tool
            tool_category: Category (e.g., 'inquiry', 'grafana', 'aiops')
            arguments: Tool arguments used
            result: Execution result or error message
            status: 'success', 'error', or 'denied'
            execution_time_ms: Execution duration in milliseconds
            permission_required: Required permission level
            permission_granted: Whether permission was granted
        
        Returns:
            Created AIToolExecution instance
        """
        execution = AIToolExecution(
            session_id=session.id,
            user_id=session.user_id,
            tool_name=tool_name,
            tool_category=tool_category,
            arguments=arguments,
            result=result[:10000] if result else None,  # Limit result size
            result_status=status,
            permission_required=permission_required,
            permission_granted=permission_granted,
            execution_time_ms=execution_time_ms
        )
        
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        
        logger.info(
            f"Tool executed: tool={tool_name}, session={session.id}, "
            f"status={status}, time={execution_time_ms}ms, granted={permission_granted}"
        )
        
        return execution
    
    def log_action_confirmation(
        self,
        session: AISession,
        action_type: str,
        action_details: Dict[str, Any],
        risk_level: str,
        status: str = 'pending',
        user_decision: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> AIActionConfirmation:
        """
        Log user confirmation for risky actions.
        
        Args:
            session: Associated AI session
            action_type: Type of action (e.g., 'delete_dashboard', 'execute_runbook')
            action_details: Full action context
            risk_level: 'low', 'medium', or 'high'
            status: 'pending', 'approved', 'rejected', or 'expired'
            user_decision: User's decision if completed
            expires_at: When confirmation expires (default: 5 minutes)
        
        Returns:
            Created AIActionConfirmation instance
        """
        if expires_at is None:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        confirmation = AIActionConfirmation(
            session_id=session.id,
            user_id=session.user_id,
            action_type=action_type,
            action_details=action_details,
            risk_level=risk_level,
            status=status,
            user_decision=user_decision,
            expires_at=expires_at
        )
        
        self.db.add(confirmation)
        self.db.commit()
        self.db.refresh(confirmation)
        
        logger.info(
            f"Action confirmation logged: type={action_type}, risk={risk_level}, "
            f"status={status}, session={session.id}"
        )
        
        return confirmation
    
    def update_confirmation_decision(
        self,
        confirmation_id: UUID,
        decision: str
    ) -> AIActionConfirmation:
        """
        Update confirmation with user's decision.
        
        Args:
            confirmation_id: ID of confirmation to update
            decision: 'approved' or 'rejected'
        
        Returns:
            Updated AIActionConfirmation instance
        """
        confirmation = self.db.query(AIActionConfirmation).filter(
            AIActionConfirmation.id == confirmation_id
        ).first()
        
        if not confirmation:
            raise ValueError(f"Confirmation {confirmation_id} not found")
        
        confirmation.status = decision
        confirmation.user_decision = decision
        confirmation.decided_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(confirmation)
        
        logger.info(
            f"Confirmation updated: id={confirmation_id}, decision={decision}"
        )
        
        return confirmation
    
    def get_user_ai_activity(
        self,
        user_id: UUID,
        days: int = 30,
        pillar: Optional[str] = None
    ) -> List[AIActivitySummary]:
        """
        Get summary of user's AI activity over time period.
        
        Args:
            user_id: User to query
            days: Number of days to look back
            pillar: Optional filter by pillar
        
        Returns:
            List of activity summaries grouped by pillar
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Base query
        query = self.db.query(
            AISession.pillar,
            func.count(AISession.id).label('session_count'),
            func.sum(AISession.message_count).label('message_count'),
            func.min(AISession.started_at).label('first_activity'),
            func.max(AISession.started_at).label('last_activity')
        ).filter(
            and_(
                AISession.user_id == user_id,
                AISession.started_at >= since
            )
        )
        
        if pillar:
            query = query.filter(AISession.pillar == pillar)
        
        query = query.group_by(AISession.pillar)
        
        results = []
        for row in query.all():
            # Get tool execution stats for this pillar
            tool_stats = self.db.query(
                func.count(AIToolExecution.id).label('tool_count'),
                func.sum(AIToolExecution.execution_time_ms).label('total_time')
            ).join(AISession).filter(
                and_(
                    AISession.user_id == user_id,
                    AISession.pillar == row.pillar,
                    AISession.started_at >= since
                )
            ).first()
            
            # Get confirmation stats
            confirmation_count = self.db.query(
                func.count(AIActionConfirmation.id)
            ).join(AISession).filter(
                and_(
                    AISession.user_id == user_id,
                    AISession.pillar == row.pillar,
                    AISession.started_at >= since
                )
            ).scalar() or 0
            
            results.append(AIActivitySummary(
                user_id=user_id,
                pillar=row.pillar,
                session_count=row.session_count or 0,
                message_count=row.message_count or 0,
                tool_execution_count=tool_stats.tool_count or 0,
                confirmation_count=confirmation_count,
                total_execution_time_ms=tool_stats.total_time or 0,
                first_activity=row.first_activity,
                last_activity=row.last_activity
            ))
        
        return results
    
    def get_tool_usage_stats(
        self,
        pillar: Optional[str] = None,
        days: int = 30
    ) -> ToolUsageStats:
        """
        Get aggregated tool usage statistics.
        
        Args:
            pillar: Optional filter by pillar
            days: Number of days to look back
        
        Returns:
            ToolUsageStats with aggregated metrics
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Base query
        query = self.db.query(AIToolExecution).join(AISession).filter(
            AIToolExecution.created_at >= since
        )
        
        if pillar:
            query = query.filter(AISession.pillar == pillar)
        
        executions = query.all()
        
        if not executions:
            return ToolUsageStats(
                total_executions=0,
                unique_tools=0,
                success_rate=0.0,
                avg_execution_time_ms=0.0,
                top_tools=[],
                by_pillar={},
                by_status={}
            )
        
        # Calculate stats
        total = len(executions)
        unique_tools = len(set(e.tool_name for e in executions))
        success_count = sum(1 for e in executions if e.result_status == 'success')
        success_rate = (success_count / total) * 100 if total > 0 else 0.0
        avg_time = sum(e.execution_time_ms or 0 for e in executions) / total
        
        # Top tools
        tool_counts = {}
        for e in executions:
            tool_counts[e.tool_name] = tool_counts.get(e.tool_name, 0) + 1
        
        top_tools = [
            {'name': name, 'count': count}
            for name, count in sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        # By pillar
        by_pillar_query = self.db.query(
            AISession.pillar,
            func.count(AIToolExecution.id).label('count')
        ).join(AIToolExecution).filter(
            AIToolExecution.created_at >= since
        ).group_by(AISession.pillar)
        
        by_pillar = {row.pillar: row.count for row in by_pillar_query.all()}
        
        # By status
        by_status_query = self.db.query(
            AIToolExecution.result_status,
            func.count(AIToolExecution.id).label('count')
        ).filter(
            AIToolExecution.created_at >= since
        ).group_by(AIToolExecution.result_status)
        
        by_status = {row.result_status: row.count for row in by_status_query.all()}
        
        return ToolUsageStats(
            total_executions=total,
            unique_tools=unique_tools,
            success_rate=success_rate,
            avg_execution_time_ms=avg_time,
            top_tools=top_tools,
            by_pillar=by_pillar,
            by_status=by_status
        )
    
    def get_pending_confirmations(
        self,
        user_id: UUID
    ) -> List[AIActionConfirmation]:
        """
        Get all pending confirmations for a user.
        
        Args:
            user_id: User to query
        
        Returns:
            List of pending confirmations
        """
        now = datetime.now(timezone.utc)
        
        return self.db.query(AIActionConfirmation).filter(
            and_(
                AIActionConfirmation.user_id == user_id,
                AIActionConfirmation.status == 'pending',
                AIActionConfirmation.expires_at > now
            )
        ).order_by(desc(AIActionConfirmation.created_at)).all()
    
    def expire_old_confirmations(self) -> int:
        """
        Mark expired confirmations as 'expired'.
        
        Returns:
            Number of confirmations expired
        """
        now = datetime.now(timezone.utc)
        
        result = self.db.query(AIActionConfirmation).filter(
            and_(
                AIActionConfirmation.status == 'pending',
                AIActionConfirmation.expires_at <= now
            )
        ).update({
            'status': 'expired',
            'decided_at': now
        })
        
        self.db.commit()
        
        if result > 0:
            logger.info(f"Expired {result} old confirmations")
        
        return result


# Dependency injection function
def get_ai_audit_service():
    """
    Factory function to create AIAuditService instance.
    Used for dependency injection in routes.
    """
    from app.database import SessionLocal
    
    db = SessionLocal()
    try:
        return AIAuditService(db)
    finally:
        db.close()
