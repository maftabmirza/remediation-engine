"""
Solution Ranker Service
"""
from typing import List, Dict, Any

class SolutionRanker:
    """
    Ranks potential solutions (runbooks, documentation, etc.) based on relevance and confidence.
    """
    
    def rank_solutions(self, query: str, solutions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort a list of solution objects by their confidence score.
        """
        # Simple sorting for now
        # In the future, this could use an LLM or specific heuristics
        return sorted(solutions, key=lambda x: x.get('confidence', 0), reverse=True)

_ranker = SolutionRanker()

def get_solution_ranker():
    return _ranker
