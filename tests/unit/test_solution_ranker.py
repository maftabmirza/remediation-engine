import pytest
import sys
import os
from uuid import uuid4

# Ensure app is in path
sys.path.append('/app')

from app.services.runbook_search_service import RankedRunbook
from app.services.solution_ranker import SolutionRanker, Solution
# Import all models to populate registry
# Import all models to populate registry
try:
    from app.models import User
    import app.models_remediation
    import app.models_chat
    import app.models_knowledge
    import app.models_troubleshooting
    import app.models_agent
    import app.models_ai_helper
    import app.models_application
    import app.models_dashboards
    import app.models_group
    import app.models_itsm
    import app.models_learning
    import app.models_runbook_acl
    import app.models_scheduler
    import app.models_observability
except ImportError as e:
    print(f"Import warning: {e}")
    pass
from app.models_remediation import Runbook

def test_ranking_presentation_strategies():
    """Test that ranker selects correct presentation strategy based on confidence scores."""
    # Mock data
    rb1 = Runbook(id=uuid4(), name="Restart Apache", description="Restarts apache service", enabled=True)
    rb2 = Runbook(id=uuid4(), name="Check Disk Space", description="Checks disk usage", enabled=True)
    
    # Scenario 1: One high confidence, one low -> Primary with Alternatives
    ranked_rb1 = RankedRunbook(runbook=rb1, score=0.9, permission_status="can_execute")
    ranked_rb2 = RankedRunbook(runbook=rb2, score=0.4, permission_status="view_only")
    
    ranker = SolutionRanker(None)
    
    results = ranker.rank_and_combine_solutions(
        runbooks=[ranked_rb1, ranked_rb2],
        manual_solutions=[],
        knowledge_refs=[],
        user_context={}
    )
    
    assert results.presentation_strategy == "primary_with_alternatives"
    assert results.solutions[0].title == "Restart Apache"

def test_ranking_multiple_good_options():
    """Test strategy when multiple good options exist."""
    rb1 = Runbook(id=uuid4(), name="R1", enabled=True)
    rb2 = Runbook(id=uuid4(), name="R2", enabled=True)
    
    r1 = RankedRunbook(runbook=rb1, score=0.85, permission_status="can_execute")
    r2 = RankedRunbook(runbook=rb2, score=0.80, permission_status="can_execute")
    
    ranker = SolutionRanker(None)
    results = ranker.rank_and_combine_solutions([r1, r2], [], [], {})
    
    assert results.presentation_strategy == "multiple_options"
    assert len(results.solutions) == 2
