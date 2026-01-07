"""
Solution Ranker Service
Rank and combine different solution types (runbooks, manual solutions) for AI presentation.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from uuid import UUID

from app.services.runbook_search_service import RankedRunbook

@dataclass
class Solution:
    type: str # 'runbook', 'manual'
    id: str
    title: str
    description: str
    confidence: float
    success_rate: float
    estimated_time_minutes: int
    permission_status: Optional[str] = None
    metadata: Dict[str, Any] = None

@dataclass
class RankedSolutionList:
    solutions: List[Solution]
    presentation_strategy: str
    knowledge_refs: List[Dict[str, Any]]

    def to_dict(self):
        return {
            'solutions': [asdict(s) for s in self.solutions],
            'presentation_strategy': self.presentation_strategy,
            'knowledge_refs': self.knowledge_refs
        }

class SolutionRanker:
    def __init__(self, db):
        self.db = db

    def rank_and_combine_solutions(
        self,
        runbooks: List[RankedRunbook],
        manual_solutions: List[Any],
        knowledge_refs: List[Dict[str, Any]],
        user_context: Dict[str, Any]
    ) -> RankedSolutionList:
        """
        Combine and rank all solution types.
        """
        all_solutions = []

        # Convert runbooks to Solutions
        for rr in runbooks:
            # Automation bonus: slightly boost confidence for automated solutions
            confidence = rr.score + 0.15
            confidence = min(confidence, 1.0)
            
            sol = Solution(
                type='runbook',
                id=str(rr.runbook.id),
                title=rr.runbook.name,
                description=rr.runbook.description or "",
                confidence=confidence,
                success_rate=0.95, # Placeholder - should ideally come from rr calculation or stats service
                estimated_time_minutes=5, # Placeholder
                permission_status=rr.permission_status,
                metadata={
                    'runbook_id': str(rr.runbook.id),
                    'url': f'/runbooks/{rr.runbook.id}',
                    'automation_level': 'automated'
                }
            )
            all_solutions.append(sol)

        # Add manual solutions (future phase) - kept empty for now as per plan
        for manual in manual_solutions:
            pass

        # Sort by confidence (descending)
        all_solutions.sort(key=lambda s: s.confidence, reverse=True)
        
        # Apply decision matrix
        strategy = self.determine_presentation_strategy(all_solutions)
        
        return RankedSolutionList(
            solutions=all_solutions[:3],  # Top 3
            presentation_strategy=strategy,
            knowledge_refs=knowledge_refs
        )
        
    def determine_presentation_strategy(self, solutions: List[Solution]) -> str:
        """Apply decision matrix to determine how to present solutions."""
        if not solutions:
            return 'no_solutions'
            
        if len(solutions) == 1:
            return 'single_solution'
            
        top_confidence = solutions[0].confidence
        second_confidence = solutions[1].confidence if len(solutions) > 1 else 0
        
        confidence_diff = top_confidence - second_confidence
        
        # More aggressive: show single solution when top is clearly better
        if confidence_diff >= 0.15 or top_confidence > 0.85:
            return 'single_solution'  # Clear winner, don't show alternatives
        elif confidence_diff < 0.1:
            return 'multiple_options'  # Very similar, let user choose
        elif top_confidence > 0.9:
            return 'primary_with_alternatives'  # Very high confidence winner
        elif top_confidence < 0.6:
             return 'experimental_options'  # Low confidence, warn user
        else:
            return 'primary_plus_one'  # One clear winner, one backup
