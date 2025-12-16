"""
Effectiveness Service
Calculates runbook effectiveness scores based on execution outcomes and feedback
"""
import logging
from typing import Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta

from app.models_remediation import Runbook, RunbookExecution
from app.models_learning import ExecutionOutcome, AnalysisFeedback
from app.schemas_learning import (
    RunbookEffectiveness,
    RunbookEffectivenessMetrics,
    AlertTypeBreakdown
)

logger = logging.getLogger(__name__)


class EffectivenessService:
    """Service for calculating runbook effectiveness scores."""
    
    # Score weights (from kb-ai-analysis.md)
    WEIGHT_SUCCESS_RATE = 0.4
    WEIGHT_FEEDBACK = 0.3
    WEIGHT_RESOLUTION_TIME = 0.2
    WEIGHT_RECOMMENDATION_FOLLOWED = 0.1
    
    MIN_EXECUTIONS_FOR_SCORE = 5  # Minimum executions before calculating score
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_runbook_effectiveness(
        self, 
        runbook_id: UUID,
        days_lookback: int = 90
    ) -> Optional[RunbookEffectiveness]:
        """
        Calculate effectiveness score for a runbook.
        
        Args:
            runbook_id: UUID of the runbook
            days_lookback: Number of days to look back for data
            
        Returns:
            RunbookEffectiveness or None if insufficient data
        """
        try:
            # Get runbook
            runbook = self.db.query(Runbook).filter(Runbook.id == runbook_id).first()
            if not runbook:
                logger.error(f"Runbook {runbook_id} not found")
                return None
            
            # Get date threshold
            since_date = datetime.utcnow() - timedelta(days=days_lookback)
            
            # Get all executions with outcomes
            executions_with_outcomes = (
                self.db.query(RunbookExecution, ExecutionOutcome)
                .join(ExecutionOutcome, ExecutionOutcome.execution_id == RunbookExecution.id)
                .filter(
                    RunbookExecution.runbook_id == runbook_id,
                    RunbookExecution.completed_at >= since_date
                )
                .all()
            )
            
            if len(executions_with_outcomes) < self.MIN_EXECUTIONS_FOR_SCORE:
                logger.info(
                    f"Insufficient data for runbook {runbook_id}: "
                    f"{len(executions_with_outcomes)} executions (need {self.MIN_EXECUTIONS_FOR_SCORE})"
                )
                return None
            
            # Calculate metrics
            metrics = self._calculate_metrics(executions_with_outcomes)
            
            # Get feedback data
            feedback_score = self._calculate_feedback_score(runbook_id, since_date)
            
            # Calculate overall effectiveness score
            overall_score = self._calculate_overall_score(metrics, feedback_score)
            
            # Get breakdown by alert type
            by_alert_type = self._calculate_alert_type_breakdown(executions_with_outcomes)
            
            # Get improvement suggestions
            improvement_suggestions = self._get_improvement_suggestions(runbook_id, since_date)
            
            return RunbookEffectiveness(
                runbook_id=runbook_id,
                runbook_name=runbook.name,
                overall_score=round(overall_score, 2),
                metrics=metrics,
                by_alert_type=by_alert_type,
                improvement_suggestions=improvement_suggestions,
                last_updated=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error calculating effectiveness for runbook {runbook_id}: {e}")
            return None
    
    def _calculate_metrics(
        self, 
        executions_with_outcomes: List
    ) -> RunbookEffectivenessMetrics:
        """Calculate core effectiveness metrics."""
        total = len(executions_with_outcomes)
        
        successful_count = sum(
            1 for _, outcome in executions_with_outcomes
            if outcome.resolved_issue and outcome.resolution_type == 'full'
        )
        
        resolution_times = [
            outcome.time_to_resolution_minutes
            for _, outcome in executions_with_outcomes
            if outcome.time_to_resolution_minutes is not None
        ]
        avg_resolution_minutes = (
            sum(resolution_times) / len(resolution_times)
            if resolution_times else 0
        )
        
        # Count positive feedback from execution outcomes
        positive_feedback_count = sum(
            1 for _, outcome in executions_with_outcomes
            if outcome.resolved_issue == True
        )
        
        recommendation_followed_count = sum(
            1 for _, outcome in executions_with_outcomes
            if outcome.recommendation_followed == True
        )
        
        return RunbookEffectivenessMetrics(
            success_rate=round((successful_count / total) * 100, 2),
            avg_resolution_minutes=round(avg_resolution_minutes, 2),
            total_executions=total,
            positive_feedback_rate=round((positive_feedback_count / total) * 100, 2),
            recommendation_followed_rate=round((recommendation_followed_count / total) * 100, 2)
        )
    
    def _calculate_feedback_score(self, runbook_id: UUID, since_date: datetime) -> float:
        """Calculate average feedback score from analysis feedback."""
        # Get all feedback for alerts that had this runbook executed
        feedback_data = (
            self.db.query(AnalysisFeedback)
            .join(RunbookExecution, AnalysisFeedback.alert_id == RunbookExecution.alert_id)
            .filter(
                RunbookExecution.runbook_id == runbook_id,
                AnalysisFeedback.created_at >= since_date,
                AnalysisFeedback.rating.isnot(None)
            )
            .all()
        )
        
        if not feedback_data:
            return 0.5  # Neutral score if no feedback
        
        # Average rating (1-5 scale, normalize to 0-1)
        avg_rating = sum(fb.rating for fb in feedback_data) / len(feedback_data)
        normalized_score = (avg_rating - 1) / 4  # Convert 1-5 to 0-1
        
        return normalized_score
    
    def _calculate_overall_score(
        self, 
        metrics: RunbookEffectivenessMetrics,
        feedback_score: float
    ) -> float:
        """Calculate weighted overall effectiveness score (0-100)."""
        # Normalize success rate to 0-1
        success_rate_normalized = metrics.success_rate / 100
        
        # Normalize recommendation followed rate to 0-1
        recommendation_followed_normalized = metrics.recommendation_followed_rate / 100
        
        # For resolution time, lower is better - use exponential decay
        # Assume target is 10 minutes - score higher for faster resolutions
        if metrics.avg_resolution_minutes > 0:
            import math
            resolution_time_score = math.exp(-metrics.avg_resolution_minutes / 10)
        else:
            resolution_time_score = 0.5
        
        # Calculate weighted score
        overall_score = (
            success_rate_normalized * self.WEIGHT_SUCCESS_RATE +
            feedback_score * self.WEIGHT_FEEDBACK +
            resolution_time_score * self.WEIGHT_RESOLUTION_TIME +
            recommendation_followed_normalized * self.WEIGHT_RECOMMENDATION_FOLLOWED
        ) * 100
        
        return max(0, min(100, overall_score))  # Clamp to 0-100
    
    def _calculate_alert_type_breakdown(
        self,
        executions_with_outcomes: List
    ) -> List[AlertTypeBreakdown]:
        """Calculate effectiveness breakdown by alert type."""
        from collections import defaultdict
        
        # Group by alert name
        by_alert_type = defaultdict(list)
        
        for execution, outcome in executions_with_outcomes:
            if execution.alert:
                alert_name = execution.alert.alert_name
                by_alert_type[alert_name].append((execution, outcome))
        
        breakdown = []
        for alert_type, data in by_alert_type.items():
            total = len(data)
            successful = sum(
                1 for _, outcome in data
                if outcome.resolved_issue and outcome.resolution_type == 'full'
            )
            
            resolution_times = [
                outcome.time_to_resolution_minutes
                for _, outcome in data
                if outcome.time_to_resolution_minutes is not None
            ]
            avg_resolution = (
                sum(resolution_times) / len(resolution_times)
                if resolution_times else None
            )
            
            breakdown.append(AlertTypeBreakdown(
                alert_type=alert_type,
                success_rate=round((successful / total) * 100, 2),
                count=total,
                avg_resolution_minutes=round(avg_resolution, 2) if avg_resolution else None
            ))
        
        # Sort by count descending
        breakdown.sort(key=lambda x: x.count, reverse=True)
        
        return breakdown
    
    def _get_improvement_suggestions(
        self, 
        runbook_id: UUID,
        since_date: datetime
    ) -> List[str]:
        """Get aggregated improvement suggestions from users."""
        suggestions = (
            self.db.query(ExecutionOutcome.improvement_suggestion)
            .join(RunbookExecution, ExecutionOutcome.execution_id == RunbookExecution.id)
            .filter(
                RunbookExecution.runbook_id == runbook_id,
                ExecutionOutcome.created_at >= since_date,
                ExecutionOutcome.improvement_suggestion.isnot(None),
                ExecutionOutcome.improvement_suggestion != ''
            )
            .all()
        )
        
        # Extract unique suggestions (limit to top 5 most recent)
        unique_suggestions = list(set(s[0] for s in suggestions if s[0]))
        return unique_suggestions[:5]
