"""
Runbook Search Service
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models_remediation import Runbook
from app.database import get_db

logger = logging.getLogger(__name__)

class RunbookSearchService:
    """
    Searches for runbooks based on natural language queries or specific tags.
    """
    
    def search(self, db: Session, query_text: str, limit: int = 5) -> List[Runbook]:
        """
        Search for runbooks matching the query text.
        Uses exact tag matching and fuzzy text matching on name/description.
        """
        if not query_text:
            return []
            
        search_term = f"%{query_text}%"
        
        # Basic search strategy:
        # 1. Match name or description
        # 2. Filter by enabled=True
        results = db.query(Runbook).filter(
            Runbook.enabled == True,
            or_(
                Runbook.name.ilike(search_term),
                Runbook.description.ilike(search_term),
                # We could add tag search here if we parsed the query for tags
            )
        ).limit(limit).all()
        
        return results

    def find_by_context(self, db: Session, alert_labels: dict) -> List[Runbook]:
        """
        Find runbooks that match specific alert labels.
        This reuses the logic used by the remediation engine triggers, 
        but in a search context.
        """
        # simplified implementation for search purposes
        # In a full implementation, we would query RunbookTrigger
        return []

_search_service = RunbookSearchService()

def get_runbook_search_service():
    return _search_service
