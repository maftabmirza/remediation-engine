"""
Agent Runbook Integration
Enables AI agent to search, propose, and integrate runbook execution
"""
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session

from app.models import Alert
from app.models_remediation import Runbook
from app.services.runbook_knowledge_service import RunbookKnowledgeService
from app.services.knowledge_search_service import KnowledgeSearchService

logger = logging.getLogger(__name__)


class AgentRunbookIntegration:
    """
    Provides runbook intelligence for the AI agent.
    Searches relevant runbooks and generates proposals.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.runbook_search = RunbookKnowledgeService(db)
        self.knowledge_search = KnowledgeSearchService(db)
    
    def find_relevant_runbooks_for_alert(
        self,
        alert: Alert,
        additional_context: Optional[str] = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find runbooks relevant to an alert.
        
        Args:
            alert: The alert to find runbooks for
            additional_context: Additional problem description
            limit: Max runbooks to return
            
        Returns:
            List of relevant runbooks with metadata
        """
        # Build query from alert
        query_parts = []
        
        if alert.alert_name:
            query_parts.append(alert.alert_name)
        if alert.description:
            query_parts.append(alert.description)
        if additional_context:
            query_parts.append(additional_context)
        
        query = " ".join(query_parts) if query_parts else "troubleshooting remediation"
        
        # Build alert context
        alert_context = {
            "alert_name": alert.alert_name,
            "severity": alert.severity,
            "instance": alert.instance,
            "description": alert.description,
            "job": alert.job
        }
        
        return self.runbook_search.search_relevant_runbooks(
            query=query,
            alert_context=alert_context,
            limit=limit,
            min_similarity=0.4
        )
    
    def find_relevant_runbooks_for_query(
        self,
        query: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find runbooks relevant to a natural language query.
        
        Args:
            query: Problem description or question
            limit: Max runbooks to return
            
        Returns:
            List of relevant runbooks
        """
        return self.runbook_search.search_relevant_runbooks(
            query=query,
            limit=limit,
            min_similarity=0.4
        )
    
    def generate_runbook_proposal(
        self,
        runbook: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        Generate a proposal for running a specific runbook.
        
        Returns structured data for the AI to present to user.
        """
        return {
            "type": "runbook_proposal",
            "runbook_id": runbook["runbook_id"],
            "runbook_name": runbook["runbook_name"],
            "description": runbook.get("description", ""),
            "relevance_score": runbook.get("similarity", 0),
            "category": runbook.get("category", ""),
            "steps_count": runbook.get("steps_count", 0),
            "approval_required": runbook.get("approval_required", True),
            "view_url": runbook.get("view_url"),
            "message": self._format_proposal_message(runbook, context),
            "actions": [
                {
                    "label": "View Runbook Details",
                    "action": "view",
                    "url": runbook.get("view_url")
                },
                {
                    "label": "Run This Runbook",
                    "action": "execute",
                    "runbook_id": runbook["runbook_id"]
                }
            ]
        }
    
    def _format_proposal_message(self, runbook: Dict, context: str) -> str:
        """Format a human-readable proposal message."""
        return f"""
I found a relevant runbook that might help with this issue:

**{runbook['runbook_name']}**
{runbook.get('description', 'No description available')}

- Category: {runbook.get('category', 'Uncategorized')}
- Steps: {runbook.get('steps_count', 0)}
- Relevance: {runbook.get('similarity', 0):.1%}

Would you like to view the runbook details or run it?
[View Runbook]({runbook.get('view_url')}) | [Execute Runbook]
""".strip()
    
    def search_knowledge_for_context(
        self,
        query: str,
        app_id: Optional[UUID] = None,
        include_runbooks: bool = True
    ) -> Dict[str, Any]:
        """
        Search entire knowledge base for context.
        Combines documents, runbooks, and historical data.
        
        Returns:
            Combined search results from all sources
        """
        results = {
            "documents": [],
            "runbooks": [],
            "combined_context": ""
        }
        
        # Search documents
        doc_results = self.knowledge_search.search_similar(
            query=query,
            app_id=app_id,
            limit=5,
            min_similarity=0.3
        )
        results["documents"] = doc_results
        
        # Search runbooks
        if include_runbooks:
            runbook_results = self.runbook_search.search_relevant_runbooks(
                query=query,
                limit=3,
                min_similarity=0.4
            )
            results["runbooks"] = runbook_results
        
        # Build combined context for LLM
        context_parts = []
        
        if doc_results:
            context_parts.append("=== Relevant Documentation ===")
            for doc in doc_results[:3]:
                context_parts.append(f"- {doc.get('source_title', 'Document')}: {doc.get('content', '')[:500]}")
        
        if results["runbooks"]:
            context_parts.append("\n=== Available Runbooks ===")
            for rb in results["runbooks"]:
                context_parts.append(f"- {rb['runbook_name']}: {rb.get('description', '')[:200]}")
                context_parts.append(f"  View: {rb.get('view_url')}")
        
        results["combined_context"] = "\n".join(context_parts)
        
        return results
