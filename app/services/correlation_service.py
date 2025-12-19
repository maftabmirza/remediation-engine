"""
Correlation Service
Detects alert storms and groups related alerts.
"""
import logging
from typing import List, Optional, Dict
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime, timedelta
import json

from app.models import Alert
from app.models_troubleshooting import AlertCorrelation
from app.services.prompt_service import PromptService
from app.services.llm_service import generate_completion

logger = logging.getLogger(__name__)


class CorrelationService:
    """Service for correlating alerts into groups."""
    
    # Time window to consider alerts related (e.g., 15 minutes)
    CORRELATION_WINDOW_MINUTES = 15
    
    def __init__(self, db: Session):
        self.db = db

    def find_or_create_correlation(self, alert: Alert) -> Optional[AlertCorrelation]:
        """
        Find an existing active correlation for this alert or create a new one.
        Logic:
        1. Check if alert already has a correlation.
        2. Look for other active correlations with alerts from the same application 
           within the time window.
        3. Look for correlations with alerts on the same instance/host.
        4. If match found, add to it.
        5. If no match, create new correlation.
        """
        if alert.correlation_id:
            return self.db.query(AlertCorrelation).filter(AlertCorrelation.id == alert.correlation_id).first()

        # Look for recent active correlations
        time_threshold = datetime.utcnow() - timedelta(minutes=self.CORRELATION_WINDOW_MINUTES)
        
        # Candidate correlations based on shared attributes (App ID or Instance)
        # This is a simplified heuristic. In a real system, we'd use topology.
        query = (
            self.db.query(AlertCorrelation)
            .join(Alert, AlertCorrelation.id == Alert.correlation_id)
            .filter(
                AlertCorrelation.status == 'active',
                AlertCorrelation.updated_at >= time_threshold
            )
        )
        
        # Build filter conditions
        conditions = []
        if alert.app_id:
            conditions.append(Alert.app_id == alert.app_id)
        if alert.instance:
            conditions.append(Alert.instance == alert.instance)
            
        if not conditions:
            # If no detailed metadata, just create new correlation
            return self._create_new_correlation(alert)
            
        # Apply OR condition to find any matching correlation
        matching_correlation = query.filter(or_(*conditions)).first()
        
        if matching_correlation:
            self._add_to_correlation(matching_correlation, alert)
            return matching_correlation
        else:
            return self._create_new_correlation(alert)

    def _create_new_correlation(self, alert: Alert) -> AlertCorrelation:
        """Create a new correlation group starting with this alert."""
        summary = f"Issue on {alert.instance or 'unknown'} - {alert.alert_name}"
        if alert.application:
            summary = f"{alert.application.name}: {summary}"
            
        correlation = AlertCorrelation(
            summary=summary,
            status='active',
            confidence_score=1.0 # Initial confidence
        )
        self.db.add(correlation)
        self.db.commit()
        self.db.refresh(correlation)
        
        # Link alert
        alert.correlation_id = correlation.id
        self.db.commit()
        
        logger.info(f"Created new correlation {correlation.id} for alert {alert.id}")
        return correlation

    def _add_to_correlation(self, correlation: AlertCorrelation, alert: Alert):
        """Add alert to existing correlation and update summary."""
        alert.correlation_id = correlation.id
        correlation.updated_at = datetime.utcnow()
        
        # Update summary if needed (simple logic for now)
        # If multiple alerts, maybe generalize summary?
        # For now, keep original summary but maybe append count if we tracked it?
        
        self.db.commit()
        logger.info(f"Added alert {alert.id} to correlation {correlation.id}")

    async def analyze_root_cause(self, correlation_id: UUID) -> Dict:
        """
        Analyze the alerts in a correlation to determine root cause using LLM.
        Returns dictionary with analysis results.
        """
        correlation = self.db.query(AlertCorrelation).filter(AlertCorrelation.id == correlation_id).first()
        if not correlation:
            return {"root_cause": "Correlation not found", "reasoning": [], "confidence": 0.0}

        alerts = correlation.alerts
        if not alerts:
            return {"root_cause": "No alerts in correlation", "reasoning": [], "confidence": 0.0}

        # Generate prompt
        prompt = PromptService.get_rca_prompt(correlation, alerts)
        
        try:
            # Call LLM
            # We assume generate_completion handles the lookup of default provider
            analysis_text, _ = await generate_completion(self.db, prompt, json_mode=True)
            
            # Parse JSON
            # LLM might return Markdown code block ```json ... ```
            cleaned_text = analysis_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text.split("```json")[1]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text.rsplit("```", 1)[0]
                
            result = json.loads(cleaned_text.strip())
            
            # Format for storage (Legacy String Format for frontend compatibility)
            # Likely Root Cause: <Cause>
            # Reasoning: <Text>
            root_cause = result.get("root_cause", "Unknown")
            reasoning_list = result.get("reasoning", [])
            confidence = result.get("confidence", 0.5)
            
            reasoning_text = " ".join(reasoning_list)
            
            stored_string = (
                f"Likely Root Cause: {root_cause}\n"
                f"Reasoning: {reasoning_text}\n"
                f"Confidence: {confidence}"
            )
            
            correlation.root_cause_analysis = stored_string
            correlation.confidence_score = confidence
            self.db.commit()
            
            return result
            
        except Exception as e:
            logger.error(f"Error in LLM RCA: {e}")
            # Fallback to simple update
            correlation.root_cause_analysis = f"Likely Root Cause: Analysis Failed\nReasoning: {str(e)}"
            self.db.commit()
            return {"root_cause": "Analysis Failed", "reasoning": [str(e)], "confidence": 0.0}
