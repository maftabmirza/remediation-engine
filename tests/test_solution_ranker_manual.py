import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.runbook_search_service import RankedRunbook
from app.services.solution_ranker import SolutionRanker, Solution
from app.models_remediation import Runbook
from uuid import uuid4

def test_ranking_logic():
    print("Testing Solution Ranking Logic...")
    
    # Mock data
    rb1 = Runbook(id=uuid4(), name="Restart Apache", description="Restarts apache service", enabled=True)
    rb2 = Runbook(id=uuid4(), name="Check Disk Space", description="Checks disk usage", enabled=True)
    
    ranked_rb1 = RankedRunbook(runbook=rb1, score=0.8, permission_status="can_execute")
    ranked_rb2 = RankedRunbook(runbook=rb2, score=0.4, permission_status="view_only")
    
    ranker = SolutionRanker(None) # Mock DB
    
    results = ranker.rank_and_combine_solutions(
        runbooks=[ranked_rb1, ranked_rb2],
        manual_solutions=[],
        knowledge_refs=[],
        user_context={}
    )
    
    print(f"Presentation Strategy: {results.presentation_strategy}")
    print(f"Number of solutions: {len(results.solutions)}")
    
    for sol in results.solutions:
        print(f"Solution: {sol.title}, Confidence: {sol.confidence:.2f}, Type: {sol.type}")
        
    # Verify ranking
    assert results.solutions[0].title == "Restart Apache"
    assert results.presentation_strategy in ["primary_with_alternatives", "primary_plus_one"]
    print("✅ Logic Verified")

if __name__ == "__main__":
    test_ranking_logic()
