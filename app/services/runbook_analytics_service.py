"""
Runbook Analytics Service
Analyzes click patterns to determine runbook popularity and user preferences.
Used by SolutionRanker to boost confidence scores for popular runbooks.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.models_learning import RunbookClick, AIFeedback
from app.models_remediation import Runbook

logger = logging.getLogger(__name__)


class RunbookAnalyticsService:
    """Service for analyzing runbook click patterns and user preferences."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_most_clicked_runbooks(
        self, 
        limit: int = 10, 
        days: int = 30
    ) -> List[Dict]:
        """
        Get the most clicked runbooks in the specified time period.
        
        Returns list of dicts with: runbook_id, title, click_count, unique_users
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        results = self.db.query(
            RunbookClick.runbook_id,
            Runbook.name.label('title'),
            func.count(RunbookClick.id).label('click_count'),
            func.count(func.distinct(RunbookClick.user_id)).label('unique_users')
        ).join(
            Runbook, Runbook.id == RunbookClick.runbook_id
        ).filter(
            RunbookClick.clicked_at >= cutoff
        ).group_by(
            RunbookClick.runbook_id, Runbook.name
        ).order_by(
            desc('click_count')
        ).limit(limit).all()
        
        return [
            {
                'runbook_id': str(r.runbook_id),
                'title': r.title,
                'click_count': r.click_count,
                'unique_users': r.unique_users
            }
            for r in results
        ]
    
    def get_user_preferences(self, user_id: UUID) -> Dict:
        """
        Get click preferences for a specific user.
        
        Returns dict with: total_clicks, favorite_runbooks, recent_clicks
        """
        # Total clicks by this user
        total_clicks = self.db.query(func.count(RunbookClick.id)).filter(
            RunbookClick.user_id == user_id
        ).scalar() or 0
        
        # Most clicked runbooks by this user
        favorites = self.db.query(
            RunbookClick.runbook_id,
            Runbook.name.label('title'),
            func.count(RunbookClick.id).label('click_count')
        ).join(
            Runbook, Runbook.id == RunbookClick.runbook_id
        ).filter(
            RunbookClick.user_id == user_id
        ).group_by(
            RunbookClick.runbook_id, Runbook.name
        ).order_by(
            desc('click_count')
        ).limit(5).all()
        
        # Recent clicks (last 7 days)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        recent = self.db.query(
            RunbookClick.runbook_id,
            Runbook.name.label('title'),
            RunbookClick.clicked_at
        ).join(
            Runbook, Runbook.id == RunbookClick.runbook_id
        ).filter(
            RunbookClick.user_id == user_id,
            RunbookClick.clicked_at >= recent_cutoff
        ).order_by(
            desc(RunbookClick.clicked_at)
        ).limit(10).all()
        
        return {
            'user_id': str(user_id),
            'total_clicks': total_clicks,
            'favorite_runbooks': [
                {'runbook_id': str(f.runbook_id), 'title': f.title, 'click_count': f.click_count}
                for f in favorites
            ],
            'recent_clicks': [
                {'runbook_id': str(r.runbook_id), 'title': r.title, 'clicked_at': r.clicked_at.isoformat()}
                for r in recent
            ]
        }
    
    def get_popularity_score(self, runbook_id: UUID, days: int = 30) -> float:
        """
        Calculate a popularity score for a runbook (0.0 to 1.0).
        
        Based on click count relative to the most clicked runbook.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Get click count for this runbook
        runbook_clicks = self.db.query(func.count(RunbookClick.id)).filter(
            RunbookClick.runbook_id == runbook_id,
            RunbookClick.clicked_at >= cutoff
        ).scalar() or 0
        
        if runbook_clicks == 0:
            return 0.0
        
        # Get max clicks for any runbook
        max_clicks = self.db.query(func.count(RunbookClick.id)).filter(
            RunbookClick.clicked_at >= cutoff
        ).group_by(
            RunbookClick.runbook_id
        ).order_by(
            desc(func.count(RunbookClick.id))
        ).first()
        
        if not max_clicks or max_clicks[0] == 0:
            return 0.0
        
        # Return normalized score (0 to 1)
        return min(1.0, runbook_clicks / max_clicks[0])
    
    def get_popularity_scores_batch(self, runbook_ids: List[UUID], days: int = 30) -> Dict[str, float]:
        """
        Get popularity scores for multiple runbooks efficiently (single query).
        
        Returns dict mapping runbook_id -> popularity_score
        """
        if not runbook_ids:
            return {}
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Get click counts for all requested runbooks in one query
        results = self.db.query(
            RunbookClick.runbook_id,
            func.count(RunbookClick.id).label('click_count')
        ).filter(
            RunbookClick.runbook_id.in_(runbook_ids),
            RunbookClick.clicked_at >= cutoff
        ).group_by(
            RunbookClick.runbook_id
        ).all()
        
        # Build click count map
        click_counts = {str(r.runbook_id): r.click_count for r in results}
        
        # Find max for normalization
        max_clicks = max(click_counts.values()) if click_counts else 0
        
        if max_clicks == 0:
            return {str(rid): 0.0 for rid in runbook_ids}
        
        # Calculate normalized scores
        return {
            str(rid): min(1.0, click_counts.get(str(rid), 0) / max_clicks)
            for rid in runbook_ids
        }
    
    def get_click_through_rate(self, runbook_id: UUID, days: int = 30) -> float:
        """
        Calculate click-through rate when runbook was presented.
        
        Note: This requires presented count which we don't track yet.
        For now, returns click count as a proxy metric.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        click_count = self.db.query(func.count(RunbookClick.id)).filter(
            RunbookClick.runbook_id == runbook_id,
            RunbookClick.clicked_at >= cutoff
        ).scalar() or 0
        
        # For now, return raw click count normalized
        return min(1.0, click_count / 100)  # Assume 100 is "high" CTR

    def get_feedback_score(self, runbook_id: UUID) -> float:
        """
        Calculate feedback score (-1.0 to +1.0).
        Positive = more thumbs up than down.
        """
        thumbs_up = self.db.query(func.count(AIFeedback.id)).filter(
            AIFeedback.runbook_id == runbook_id,
            AIFeedback.feedback_type == 'thumbs_up',
            AIFeedback.target_type == 'runbook'
        ).scalar() or 0
        
        thumbs_down = self.db.query(func.count(AIFeedback.id)).filter(
            AIFeedback.runbook_id == runbook_id,
            AIFeedback.feedback_type == 'thumbs_down',
            AIFeedback.target_type == 'runbook'
        ).scalar() or 0
        
        total = thumbs_up + thumbs_down
        
        if total == 0:
            return 0.0
        
        return (thumbs_up - thumbs_down) / total

    def get_feedback_scores_batch(self, runbook_ids: List[UUID]) -> Dict[str, float]:
        """
        Get feedback scores for multiple runbooks in batch.
        Returns dict mapping runbook_id -> score (-1.0 to +1.0)
        """
        if not runbook_ids:
            return {}

        results = self.db.query(
            AIFeedback.runbook_id,
            AIFeedback.feedback_type,
            func.count(AIFeedback.id).label('count')
        ).filter(
            AIFeedback.runbook_id.in_(runbook_ids),
            AIFeedback.target_type == 'runbook'
        ).group_by(
            AIFeedback.runbook_id,
            AIFeedback.feedback_type
        ).all()
        
        # Calculate scores
        scores = {}
        counts = {}  # runbook_id -> {'thumbs_up': 0, 'thumbs_down': 0}
        
        for r in results:
            rid = str(r.runbook_id)
            if rid not in counts:
                counts[rid] = {'thumbs_up': 0, 'thumbs_down': 0}
            counts[rid][r.feedback_type] = r.count
            
        for rid in [str(id) for id in runbook_ids]:
            data = counts.get(rid, {'thumbs_up': 0, 'thumbs_down': 0})
            up = data['thumbs_up']
            down = data['thumbs_down']
            total = up + down
            
            if total == 0:
                scores[rid] = 0.0
            else:
                scores[rid] = (up - down) / total
                
        return scores
