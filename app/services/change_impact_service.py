"""
Change Impact Service

Analyzes change events to detect correlation with incidents.
"""
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models import Alert
from app.models_itsm import ChangeEvent, ChangeImpactAnalysis


def utc_now():
    """Return current UTC datetime"""
    return datetime.now(timezone.utc)

logger = logging.getLogger(__name__)


class ChangeImpactService:
    """Service for analyzing change impact on incidents"""

    def __init__(self, db: Session):
        self.db = db

    def analyze_change_impact(
        self,
        change_event: ChangeEvent,
        time_window_hours: int = 4,
        service_weight: float = 2.0,
        severity_weights: Dict[str, float] = None
    ) -> ChangeImpactAnalysis:
        """
        Analyze the impact of a change event on incidents

        Args:
            change_event: The change event to analyze
            time_window_hours: Hours after change to look for incidents
            service_weight: Multiplier for same-service incidents
            severity_weights: Weights for different severity levels

        Returns:
            ChangeImpactAnalysis with correlation score and recommendation
        """
        if severity_weights is None:
            severity_weights = {
                'critical': 3.0,
                'warning': 1.5,
                'info': 0.5
            }

        # Define time window
        start_time = change_event.timestamp
        end_time = start_time + timedelta(hours=time_window_hours)

        # Query incidents in the time window
        incidents = self.db.query(Alert).filter(
            Alert.timestamp >= start_time,
            Alert.timestamp <= end_time
        ).all()

        # Calculate metrics
        incidents_after = len(incidents)
        critical_incidents = sum(1 for i in incidents if i.severity == 'critical')

        # Calculate correlation score
        score = 0.0
        for incident in incidents:
            # Base score from severity
            severity = incident.severity or 'info'
            base_score = severity_weights.get(severity, 1.0)

            # Time decay - incidents closer to change are more correlated
            time_diff = (incident.timestamp - start_time).total_seconds() / 3600  # hours
            time_factor = max(0.2, 1.0 - (time_diff / time_window_hours))

            # Service matching bonus
            service_match = 1.0
            if change_event.service_name and incident.job:
                # Check if service names match (partial match allowed)
                change_service = change_event.service_name.lower()
                incident_service = incident.job.lower()
                if change_service in incident_service or incident_service in change_service:
                    service_match = service_weight

            # Add to score
            incident_score = base_score * time_factor * service_match
            score += incident_score

        # Normalize score (0-100 scale)
        max_possible = incidents_after * 3.0 * service_weight  # Max if all critical + service match
        if max_possible > 0:
            normalized_score = min(100.0, (score / max_possible) * 100)
        else:
            normalized_score = 0.0

        # Determine impact level
        impact_level = self._calculate_impact_level(normalized_score, critical_incidents, incidents_after)

        # Generate recommendation
        recommendation = self._generate_recommendation(
            change_event, incidents_after, critical_incidents, impact_level
        )

        # Create or update analysis
        existing = self.db.query(ChangeImpactAnalysis).filter(
            ChangeImpactAnalysis.change_event_id == change_event.id
        ).first()

        if existing:
            existing.incidents_after = incidents_after
            existing.critical_incidents = critical_incidents
            existing.correlation_score = normalized_score
            existing.impact_level = impact_level
            existing.recommendation = recommendation
            existing.analyzed_at = utc_now()
            analysis = existing
        else:
            analysis = ChangeImpactAnalysis(
                change_event_id=change_event.id,
                incidents_after=incidents_after,
                critical_incidents=critical_incidents,
                correlation_score=normalized_score,
                impact_level=impact_level,
                recommendation=recommendation
            )
            self.db.add(analysis)

        # Update change event with correlation info
        change_event.correlation_score = normalized_score
        change_event.impact_level = impact_level

        self.db.commit()

        logger.info(
            f"Analyzed change {change_event.change_id}: "
            f"score={normalized_score:.1f}, impact={impact_level}, incidents={incidents_after}"
        )

        return analysis

    def _calculate_impact_level(
        self,
        score: float,
        critical_incidents: int,
        total_incidents: int
    ) -> str:
        """Calculate impact level from score and incident counts"""
        # High impact: high score OR any critical incidents
        if score >= 60 or critical_incidents >= 2:
            return 'high'
        elif score >= 30 or critical_incidents >= 1 or total_incidents >= 5:
            return 'medium'
        elif total_incidents > 0:
            return 'low'
        else:
            return 'none'

    def _generate_recommendation(
        self,
        change_event: ChangeEvent,
        incidents_after: int,
        critical_incidents: int,
        impact_level: str
    ) -> str:
        """Generate actionable recommendation based on analysis"""
        if impact_level == 'none':
            return "No incidents detected after this change. No action needed."

        recommendations = []

        if impact_level == 'high':
            recommendations.append("⚠️ HIGH RISK: This change is strongly correlated with incidents.")
            if critical_incidents > 0:
                recommendations.append(f"• {critical_incidents} critical incident(s) occurred after this change.")
            recommendations.append("• Consider rollback if issues persist.")
            recommendations.append("• Review change implementation and testing procedures.")

        elif impact_level == 'medium':
            recommendations.append("⚡ MODERATE RISK: This change may have contributed to incidents.")
            recommendations.append(f"• {incidents_after} incident(s) occurred in the time window.")
            recommendations.append("• Monitor closely and investigate root cause.")

        else:  # low
            recommendations.append("ℹ️ LOW RISK: Minor incident activity after change.")
            recommendations.append("• Continue monitoring but no immediate action required.")

        # Add service-specific note if available
        if change_event.service_name:
            recommendations.append(f"• Affected service: {change_event.service_name}")

        return "\n".join(recommendations)

    def get_correlated_incidents(
        self,
        change_event_id: UUID,
        time_window_hours: int = 4
    ) -> List[Alert]:
        """Get incidents that are correlated with a change event"""
        change_event = self.db.query(ChangeEvent).filter(
            ChangeEvent.id == change_event_id
        ).first()

        if not change_event:
            return []

        start_time = change_event.timestamp
        end_time = start_time + timedelta(hours=time_window_hours)

        incidents = self.db.query(Alert).filter(
            Alert.timestamp >= start_time,
            Alert.timestamp <= end_time
        ).order_by(Alert.timestamp.asc()).all()

        return incidents

    def get_high_impact_changes(
        self,
        days: int = 7,
        limit: int = 10
    ) -> List[ChangeEvent]:
        """Get high impact changes from recent period"""
        cutoff = utc_now() - timedelta(days=days)

        changes = self.db.query(ChangeEvent).filter(
            ChangeEvent.timestamp >= cutoff,
            ChangeEvent.impact_level.in_(['high', 'medium'])
        ).order_by(
            ChangeEvent.correlation_score.desc()
        ).limit(limit).all()

        return changes

    def get_change_timeline(
        self,
        start_date: datetime,
        end_date: datetime,
        service_name: Optional[str] = None
    ) -> List[Dict]:
        """Get timeline of changes with their impact"""
        query = self.db.query(ChangeEvent).filter(
            ChangeEvent.timestamp >= start_date,
            ChangeEvent.timestamp <= end_date
        )

        if service_name:
            query = query.filter(ChangeEvent.service_name == service_name)

        changes = query.order_by(ChangeEvent.timestamp.asc()).all()

        timeline = []
        for change in changes:
            timeline.append({
                'id': str(change.id),
                'change_id': change.change_id,
                'change_type': change.change_type,
                'service_name': change.service_name,
                'description': change.description,
                'timestamp': change.timestamp.isoformat(),
                'impact_level': change.impact_level,
                'correlation_score': change.correlation_score,
                'incidents_after': change.impact_analysis.incidents_after if change.impact_analysis else 0
            })

        return timeline

    def analyze_unprocessed_changes(self, max_age_hours: int = 24) -> int:
        """Analyze changes that haven't been analyzed yet"""
        cutoff = utc_now() - timedelta(hours=max_age_hours)

        # Get changes without analysis
        unanalyzed = self.db.query(ChangeEvent).outerjoin(
            ChangeImpactAnalysis
        ).filter(
            ChangeEvent.timestamp >= cutoff,
            ChangeImpactAnalysis.id.is_(None)
        ).all()

        count = 0
        for change in unanalyzed:
            try:
                self.analyze_change_impact(change)
                count += 1
            except Exception as e:
                logger.error(f"Error analyzing change {change.change_id}: {e}")

        logger.info(f"Analyzed {count} unprocessed changes")
        return count

    def get_impact_statistics(self, days: int = 30) -> Dict:
        """Get aggregate impact statistics"""
        cutoff = utc_now() - timedelta(days=days)

        total_changes = self.db.query(ChangeEvent).filter(
            ChangeEvent.timestamp >= cutoff
        ).count()

        impact_breakdown = dict(
            self.db.query(
                ChangeEvent.impact_level,
                func.count(ChangeEvent.id)
            ).filter(
                ChangeEvent.timestamp >= cutoff,
                ChangeEvent.impact_level.isnot(None)
            ).group_by(ChangeEvent.impact_level).all()
        )

        avg_score = self.db.query(func.avg(ChangeEvent.correlation_score)).filter(
            ChangeEvent.timestamp >= cutoff,
            ChangeEvent.correlation_score.isnot(None)
        ).scalar() or 0.0

        total_critical = self.db.query(func.sum(ChangeImpactAnalysis.critical_incidents)).join(
            ChangeEvent
        ).filter(
            ChangeEvent.timestamp >= cutoff
        ).scalar() or 0

        return {
            'total_changes': total_changes,
            'impact_breakdown': impact_breakdown,
            'average_correlation_score': round(avg_score, 2),
            'total_critical_incidents': total_critical,
            'high_impact_count': impact_breakdown.get('high', 0),
            'analysis_period_days': days
        }

    def get_changes_for_alert(
        self,
        alert: Alert,
        lookback_hours: int = 2
    ) -> List[ChangeEvent]:
        """
        Find changes that occurred before an alert.
        
        Useful for root cause analysis - shows what changed before an incident.
        
        Args:
            alert: The Alert to find changes for
            lookback_hours: Hours before alert to look for changes
            
        Returns:
            List of ChangeEvent objects ordered by timestamp descending
        """
        lookback_start = alert.timestamp - timedelta(hours=lookback_hours)

        changes = self.db.query(ChangeEvent).filter(
            ChangeEvent.timestamp.between(lookback_start, alert.timestamp)
        ).order_by(ChangeEvent.timestamp.desc()).all()

        return changes

    def detect_suspicious_changes(
        self,
        threshold_score: float = 70.0,
        days: int = 7
    ) -> List[ChangeEvent]:
        """
        Find changes with high correlation scores.
        
        Args:
            threshold_score: Minimum correlation score (0-100)
            days: Look back this many days
            
        Returns:
            List of suspicious changes (score >= threshold)
        """
        cutoff = utc_now() - timedelta(days=days)

        changes = self.db.query(ChangeEvent).filter(
            ChangeEvent.timestamp >= cutoff,
            ChangeEvent.correlation_score >= threshold_score
        ).order_by(ChangeEvent.correlation_score.desc()).all()

        return changes

