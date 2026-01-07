import sys
import os
import asyncio
from unittest.mock import MagicMock, Mock
from uuid import uuid4

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.runbook_search_service import RunbookSearchService, RankedRunbook
from app.models_remediation import Runbook
from app.models import User, Role

async def test_runbook_search():
    print("Testing Runbook Search Logic (Mocked)...")
    
    # Mock DB
    mock_db = MagicMock()
    
    # Mock User
    user = User(id=uuid4(), username="test_user")
    role = Role(name="operator")
    user.roles = [role]
    
    # Mock Service
    service = RunbookSearchService(mock_db)
    service.embedding_service = MagicMock()
    service.embedding_service.is_configured.return_value = True
    service.embedding_service.generate_embedding.return_value = [0.1] * 1536
    
    # Mock DB Query Results
    # Result tuple: (Runbook, distance)
    rb1 = Runbook(id=uuid4(), name="R1", enabled=True, approval_required=False)
    rb2 = Runbook(id=uuid4(), name="R2", enabled=True, approval_required=True, approval_roles=["admin"])
    
    # complex chain of mock calls for db.query(...).filter(...)...
    mock_filter = mock_db.query.return_value
    mock_filter.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        (rb1, 0.1), # High similarity (low distance)
        (rb2, 0.2)
    ]
    
    # Mock ACL check to simple logic for test
    # We want to verify that search_runbooks calls calculate_score and returns ranked list
    service.check_runbook_acl = MagicMock(return_value=True)
    
    results = await service.search_runbooks("fix cpu", {}, user)
    
    print(f"Found {len(results)} runbooks")
    assert len(results) == 2
    assert results[0].runbook.name == "R1"
    
    # Verify score ordering (R1 has better distance 0.1 vs 0.2)
    print(f"R1 Score: {results[0].score}")
    print(f"R2 Score: {results[1].score}")
    assert results[0].score > results[1].score
    
    print("✅ Search Logic Verified")

if __name__ == "__main__":
    asyncio.run(test_runbook_search())
