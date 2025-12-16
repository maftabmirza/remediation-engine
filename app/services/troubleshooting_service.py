"""
Troubleshooting Service
Generates investigation paths and matches failure patterns.
"""
import logging
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models import Alert
from app.models_troubleshooting import FailurePattern
from app.schemas_troubleshooting import InvestigationPath, InvestigationStep
from app.services.prompt_service import PromptService
from app.services.llm_service import generate_completion
import json

logger = logging.getLogger(__name__)


class TroubleshootingService:
    """Service for generating troubleshooting guidance."""

    def __init__(self, db: Session):
        self.db = db

    async def generate_investigation_path(self, alert_id: UUID) -> Optional[InvestigationPath]:
        """
        Generate a step-by-step investigation path for an alert using LLM.
        """
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return None

        # Generate prompt
        prompt = PromptService.get_investigation_plan_prompt(alert)
        
        try:
            # Call LLM
            analysis_text, _ = await generate_completion(self.db, prompt, json_mode=True)
            
            # Parse JSON
            cleaned_text = analysis_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text.split("```json")[1]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text.rsplit("```", 1)[0]
                
            result = json.loads(cleaned_text.strip())
            
            steps_data = result.get("steps", [])
            steps = []
            
            for step in steps_data:
                steps.append(InvestigationStep(
                    step_number=step.get("step_number", len(steps) + 1),
                    action=step.get("action", "Unknown Action"),
                    description=step.get("description", ""),
                    component=step.get("component", alert.instance or "System"),
                    command_to_run=step.get("command_to_run", "")
                ))
                
            return InvestigationPath(
                alert_id=alert.id,
                steps=steps,
                estimated_time_minutes=result.get("estimated_time_minutes", len(steps) * 5)
            )
            
        except Exception as e:
            logger.error(f"Error in LLM Investigation Path: {e}")
            # Fallback to single step
            return InvestigationPath(
                alert_id=alert.id,
                steps=[
                    InvestigationStep(
                        step_number=1, 
                        action="Check Logs", 
                        description="LLM generation failed, check logs manually.", 
                        component=alert.instance, 
                        command_to_run="tail -n 50 /var/log/syslog"
                    )
                ],
                estimated_time_minutes=5
            )

    def find_matching_pattern(self, alert_text: str) -> Optional[FailurePattern]:
        """
        Find a matching failure pattern (simple keyword match for now).
        In a real system, this would use vector similarity on signatures.
        """
        # Placeholder logic
        return self.db.query(FailurePattern).filter(FailurePattern.description.ilike(f"%{alert_text}%")).first()
