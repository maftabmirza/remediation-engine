"""
AI Audit Service - Comprehensive logging for all AI helper interactions
CRITICAL: Logs everything - user queries, LLM requests/responses, actions, approvals
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import logging

from app.models_ai_helper import AIHelperAuditLog, AIHelperSession
from app.schemas_ai_helper import (
    AIAuditLogCreate,
    AIAuditLogUpdate,
    AIAuditLogResponse,
    AIHelperAnalytics,
    UserAIHelperStats
)

logger = logging.getLogger(__name__)


class AIAuditService:
    """
    Comprehensive audit logging service for AI Helper
    Tracks every interaction from query to execution
    """

    def __init__(self, db: Session):
        self.db = db

    async def log_ai_interaction(
        self,
        user_id: UUID,
        username: str,
        user_query: str,
        session_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
        page_context: Optional[Dict[str, Any]] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_request: Optional[Dict[str, Any]] = None,
        llm_response: Optional[Dict[str, Any]] = None,
        llm_tokens_input: Optional[int] = None,
        llm_tokens_output: Optional[int] = None,
        llm_latency_ms: Optional[int] = None,
        llm_cost_usd: Optional[float] = None,
        knowledge_sources_used: Optional[List[UUID]] = None,
        knowledge_chunks_used: Optional[int] = None,
        rag_search_time_ms: Optional[int] = None,
        code_files_referenced: Optional[List[str]] = None,
        code_functions_referenced: Optional[List[str]] = None,
        ai_suggested_action: Optional[str] = None,
        ai_action_details: Optional[Dict[str, Any]] = None,
        ai_confidence_score: Optional[float] = None,
        ai_reasoning: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        context_assembly_ms: Optional[int] = None,
        is_error: bool = False,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        error_stack_trace: Optional[str] = None,
        **kwargs
    ) -> UUID:
        """
        Log AI interaction with full context
        Returns: audit_log_id for correlation
        """
        try:
            # Calculate total tokens
            llm_tokens_total = None
            if llm_tokens_input is not None and llm_tokens_output is not None:
                llm_tokens_total = llm_tokens_input + llm_tokens_output

            # Create audit log entry
            audit_log = AIHelperAuditLog(
                user_id=user_id,
                username=username,
                session_id=session_id,
                correlation_id=correlation_id,
                user_query=user_query,
                page_context=page_context,
                llm_provider=llm_provider,
                llm_model=llm_model,
                llm_request=llm_request,  # FULL REQUEST
                llm_response=llm_response,  # FULL RESPONSE
                llm_tokens_input=llm_tokens_input,
                llm_tokens_output=llm_tokens_output,
                llm_tokens_total=llm_tokens_total,
                llm_latency_ms=llm_latency_ms,
                llm_cost_usd=llm_cost_usd,
                knowledge_sources_used=knowledge_sources_used,
                knowledge_chunks_used=knowledge_chunks_used,
                rag_search_time_ms=rag_search_time_ms,
                code_files_referenced=code_files_referenced,
                code_functions_referenced=code_functions_referenced,
                ai_suggested_action=ai_suggested_action,
                ai_action_details=ai_action_details,
                ai_confidence_score=ai_confidence_score,
                ai_reasoning=ai_reasoning,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                context_assembly_ms=context_assembly_ms,
                is_error=is_error,
                error_type=error_type,
                error_message=error_message,
                error_stack_trace=error_stack_trace,
                timestamp=datetime.utcnow()
            )

            self.db.add(audit_log)
            self.db.commit()
            self.db.refresh(audit_log)

            logger.info(
                f"AI interaction logged: user={username}, session={session_id}, "
                f"action={ai_suggested_action}, query_length={len(user_query)}"
            )

            return audit_log.id

        except Exception as e:
            logger.error(f"Failed to log AI interaction: {str(e)}", exc_info=True)
            self.db.rollback()
            raise

    async def log_user_response(
        self,
        audit_log_id: UUID,
        user_action: str,
        modifications: Optional[Dict[str, Any]] = None,
        feedback: Optional[str] = None,
        feedback_comment: Optional[str] = None
    ):
        """
        Log user's response to AI suggestion
        """
        try:
            audit_log = self.db.query(AIHelperAuditLog).filter(
                AIHelperAuditLog.id == audit_log_id
            ).first()

            if not audit_log:
                logger.warning(f"Audit log not found: {audit_log_id}")
                return

            audit_log.user_action = user_action
            audit_log.user_action_timestamp = datetime.utcnow()
            audit_log.user_modifications = modifications
            audit_log.user_feedback = feedback
            audit_log.user_feedback_comment = feedback_comment

            self.db.commit()

            logger.info(
                f"User response logged: audit_log={audit_log_id}, "
                f"action={user_action}, feedback={feedback}"
            )

        except Exception as e:
            logger.error(f"Failed to log user response: {str(e)}", exc_info=True)
            self.db.rollback()
            raise

    async def log_execution_result(
        self,
        audit_log_id: UUID,
        executed: bool,
        result: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        affected_resources: Optional[Dict[str, Any]] = None,
        action_blocked: bool = False,
        block_reason: Optional[str] = None,
        permissions_required: Optional[List[str]] = None,
        permissions_granted: Optional[List[str]] = None
    ):
        """
        Log execution outcome
        """
        try:
            audit_log = self.db.query(AIHelperAuditLog).filter(
                AIHelperAuditLog.id == audit_log_id
            ).first()

            if not audit_log:
                logger.warning(f"Audit log not found: {audit_log_id}")
                return

            audit_log.executed = executed
            audit_log.execution_timestamp = datetime.utcnow()
            audit_log.execution_result = result
            audit_log.execution_details = details
            audit_log.affected_resources = affected_resources
            audit_log.action_blocked = action_blocked
            audit_log.block_reason = block_reason
            audit_log.permissions_required = permissions_required
            audit_log.permissions_granted = permissions_granted

            # Calculate total duration
            if audit_log.timestamp:
                duration = (datetime.utcnow() - audit_log.timestamp.replace(tzinfo=None)).total_seconds() * 1000
                audit_log.total_duration_ms = int(duration)

            self.db.commit()

            logger.info(
                f"Execution result logged: audit_log={audit_log_id}, "
                f"executed={executed}, result={result}, blocked={action_blocked}"
            )

        except Exception as e:
            logger.error(f"Failed to log execution result: {str(e)}", exc_info=True)
            self.db.rollback()
            raise

    async def get_user_history(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
        session_id: Optional[UUID] = None
    ) -> List[AIAuditLogResponse]:
        """
        Get user's AI interaction history
        """
        try:
            query = self.db.query(AIHelperAuditLog).filter(
                AIHelperAuditLog.user_id == user_id
            )

            if session_id:
                query = query.filter(AIHelperAuditLog.session_id == session_id)

            logs = query.order_by(
                AIHelperAuditLog.timestamp.desc()
            ).offset(offset).limit(limit).all()

            return [AIAuditLogResponse.from_orm(log) for log in logs]

        except Exception as e:
            logger.error(f"Failed to get user history: {str(e)}", exc_info=True)
            raise

    async def get_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[UUID] = None
    ) -> AIHelperAnalytics:
        """
        Generate analytics for AI helper usage
        """
        try:
            # Default to last 30 days
            if not start_date:
                start_date = datetime.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = datetime.utcnow()

            query = self.db.query(AIHelperAuditLog).filter(
                and_(
                    AIHelperAuditLog.timestamp >= start_date,
                    AIHelperAuditLog.timestamp <= end_date
                )
            )

            if user_id:
                query = query.filter(AIHelperAuditLog.user_id == user_id)

            logs = query.all()

            # Calculate metrics
            total_queries = len(logs)
            total_sessions = len(set(log.session_id for log in logs if log.session_id))
            total_tokens = sum(log.llm_tokens_total or 0 for log in logs)
            total_cost = sum(float(log.llm_cost_usd or 0) for log in logs)

            # Response time
            response_times = [log.llm_latency_ms for log in logs if log.llm_latency_ms]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0

            # User actions
            total_with_action = len([log for log in logs if log.user_action])
            approved = len([log for log in logs if log.user_action == 'approved'])
            rejected = len([log for log in logs if log.user_action == 'rejected'])
            modified = len([log for log in logs if log.user_action == 'modified'])

            approval_rate = (approved / total_with_action * 100) if total_with_action > 0 else 0
            rejection_rate = (rejected / total_with_action * 100) if total_with_action > 0 else 0
            modification_rate = (modified / total_with_action * 100) if total_with_action > 0 else 0

            # Most common actions
            action_counts = {}
            for log in logs:
                if log.ai_suggested_action:
                    action_counts[log.ai_suggested_action] = action_counts.get(log.ai_suggested_action, 0) + 1

            most_common_actions = [
                {"action": action, "count": count}
                for action, count in sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]

            # Error rate
            errors = len([log for log in logs if log.is_error])
            error_rate = (errors / total_queries * 100) if total_queries > 0 else 0

            # Blocked actions
            blocked_actions_count = len([log for log in logs if log.action_blocked])

            return AIHelperAnalytics(
                total_queries=total_queries,
                total_sessions=total_sessions,
                total_tokens_used=total_tokens,
                total_cost_usd=total_cost,
                avg_response_time_ms=avg_response_time,
                approval_rate=approval_rate,
                rejection_rate=rejection_rate,
                modification_rate=modification_rate,
                most_common_actions=most_common_actions,
                top_users=[],  # TODO: Implement top users
                error_rate=error_rate,
                blocked_actions_count=blocked_actions_count
            )

        except Exception as e:
            logger.error(f"Failed to generate analytics: {str(e)}", exc_info=True)
            raise

    async def generate_audit_report(
        self,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate compliance audit report
        """
        try:
            query = self.db.query(AIHelperAuditLog).filter(
                and_(
                    AIHelperAuditLog.timestamp >= start_date,
                    AIHelperAuditLog.timestamp <= end_date
                )
            )

            # Apply filters
            if filters:
                if filters.get('user_id'):
                    query = query.filter(AIHelperAuditLog.user_id == filters['user_id'])
                if filters.get('action'):
                    query = query.filter(AIHelperAuditLog.ai_suggested_action == filters['action'])
                if filters.get('executed'):
                    query = query.filter(AIHelperAuditLog.executed == filters['executed'])
                if filters.get('action_blocked'):
                    query = query.filter(AIHelperAuditLog.action_blocked == filters['action_blocked'])

            logs = query.order_by(AIHelperAuditLog.timestamp.desc()).all()

            # Format for export
            report = []
            for log in logs:
                report.append({
                    "timestamp": log.timestamp.isoformat(),
                    "user": log.username,
                    "query": log.user_query,
                    "suggested_action": log.ai_suggested_action,
                    "user_action": log.user_action,
                    "executed": log.executed,
                    "execution_result": log.execution_result,
                    "blocked": log.action_blocked,
                    "block_reason": log.block_reason,
                    "llm_provider": log.llm_provider,
                    "llm_model": log.llm_model,
                    "tokens_used": log.llm_tokens_total,
                    "cost_usd": float(log.llm_cost_usd) if log.llm_cost_usd else 0,
                    "ip_address": str(log.ip_address) if log.ip_address else None,
                    "request_id": log.request_id
                })

            return report

        except Exception as e:
            logger.error(f"Failed to generate audit report: {str(e)}", exc_info=True)
            raise

    async def get_blocked_actions(
        self,
        start_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AIAuditLogResponse]:
        """
        Get list of blocked actions (security monitoring)
        """
        try:
            query = self.db.query(AIHelperAuditLog).filter(
                AIHelperAuditLog.action_blocked == True
            )

            if start_date:
                query = query.filter(AIHelperAuditLog.timestamp >= start_date)

            logs = query.order_by(
                AIHelperAuditLog.timestamp.desc()
            ).limit(limit).all()

            return [AIAuditLogResponse.from_orm(log) for log in logs]

        except Exception as e:
            logger.error(f"Failed to get blocked actions: {str(e)}", exc_info=True)
            raise

    async def get_user_stats(self, user_id: UUID) -> UserAIHelperStats:
        """
        Get user-specific statistics
        """
        try:
            logs = self.db.query(AIHelperAuditLog).filter(
                AIHelperAuditLog.user_id == user_id
            ).all()

            if not logs:
                return None

            total_queries = len(logs)
            sessions = set(log.session_id for log in logs if log.session_id)
            total_sessions = len(sessions)
            avg_session_queries = total_queries / total_sessions if total_sessions > 0 else 0

            total_tokens = sum(log.llm_tokens_total or 0 for log in logs)
            total_cost = sum(float(log.llm_cost_usd or 0) for log in logs)

            # Approval rate
            with_action = [log for log in logs if log.user_action]
            approved = len([log for log in with_action if log.user_action == 'approved'])
            approval_rate = (approved / len(with_action) * 100) if with_action else 0

            # Most used actions
            action_counts = {}
            for log in logs:
                if log.ai_suggested_action:
                    action_counts[log.ai_suggested_action] = action_counts.get(log.ai_suggested_action, 0) + 1

            most_used_actions = [
                action for action, count in sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            ]

            last_activity = max(log.timestamp for log in logs) if logs else None

            return UserAIHelperStats(
                user_id=user_id,
                username=logs[0].username,
                total_queries=total_queries,
                total_sessions=total_sessions,
                avg_session_queries=avg_session_queries,
                total_tokens_used=total_tokens,
                total_cost_usd=total_cost,
                approval_rate=approval_rate,
                most_used_actions=most_used_actions,
                last_activity_at=last_activity
            )

        except Exception as e:
            logger.error(f"Failed to get user stats: {str(e)}", exc_info=True)
            raise
