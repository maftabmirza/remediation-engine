import pytest
import asyncio
from unittest.mock import MagicMock
from uuid import uuid4
import sys

sys.path.append('/app')

try:
    from app.models import User, Role
    import app.models_remediation
    from app.models_remediation import Runbook, RunbookExecution
    from app.models_runbook_acl import RunbookACL
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
    import app.models_scheduler
    import app.models_observability
except ImportError as e:
    print(f"Import warning: {e}")
    pass

from app.services.runbook_search_service import RunbookSearchService

@pytest.mark.asyncio
async def test_search_runbooks_ranking():
    """Test that search service returns ranked runbooks based on semantic distance."""
    mock_db = MagicMock()
    user = User(id=uuid4(), username='test_user')
    
    service = RunbookSearchService(mock_db)
    service.embedding_service = MagicMock()
    service.embedding_service.is_configured.return_value = True
    service.embedding_service.generate_embedding.return_value = [0.1] * 1536
    service.check_runbook_acl = MagicMock(return_value=True)

    # Mock DB returns
    rb1 = Runbook(id=uuid4(), name="Match 1", enabled=True)
    rb2 = Runbook(id=uuid4(), name="Match 2", enabled=True)
    
    # Search query mock
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    # Return runbooks with distance (smaller distance = better match)
    mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        (rb1, 0.1),
        (rb2, 0.5)
    ]
    
    # Mock executions query (return empty list to avoid ZeroDivisionError check)
    # We rely on the complex side_effect logic or just ensure it returns something iterable if called
    # But since we just mocked the main query chain, subsequent queries for executions need to handle the new call
    # Simpler approach: mock calculate_runbook_score to avoid DB calls inside it, 
    # OR better: let's trust our manual verification for integration and keep this unit test focused on the search flow.
    # We will mock calculate_runbook_score to keep this a true unit test of the search method.
    service.calculate_runbook_score = MagicMock(side_effect=[0.9, 0.5])

    results = await service.search_runbooks("query", {}, user)
    
    assert len(results) == 2
    assert results[0].runbook.name == "Match 1"
    assert results[0].score == 0.9

def test_calculate_score_no_history():
    """Test scoring logic handles missing history gracefully (ZeroDivisionError fix verification)."""
    service = RunbookSearchService(MagicMock())
    rb = Runbook(id=uuid4(), name="New Runbook")
    
    # We need to mock the executions query to return empty list
    mock_query = service.db.query.return_value
    mock_query.filter.return_value.limit.return_value.all.return_value = []
    
    score = service.calculate_runbook_score(rb, 0.5, {}, User(id=uuid4()))
    
    # Base score: semantic(0.5) * 0.5 + success(0.5 default) * 0.3 + context(0) * 0.2
    # = 0.25 + 0.15 + 0 = 0.4
    assert 0.39 < score < 0.41
