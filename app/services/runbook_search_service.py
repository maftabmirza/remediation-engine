"""
Runbook Search Service
Semantic search across runbooks using pgvector.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.models_remediation import Runbook, RunbookExecution
from app.models_runbook_acl import RunbookACL
from app.models import User
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

class RankedRunbook:
    def __init__(self, runbook: Runbook, score: float, permission_status: str = 'unknown'):
        self.runbook = runbook
        self.score = score
        self.permission_status = permission_status

class RunbookSearchService:
    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService()

    async def search_runbooks(
        self,
        query: str,
        context: Dict[str, Any],
        user: User,
        limit: int = 3
    ) -> List[RankedRunbook]:
        """
        Semantic search for runbooks matching query and context.
        """
        if not self.embedding_service.is_configured():
            logger.warning("Embedding service not configured")
            return []

        # Generate embedding (synchronous in this service implementation)
        embedding = self.embedding_service.generate_embedding(query)
        if not embedding:
            logger.warning("Failed to generate embedding for query")
            return []

        # Vector search
        try:
            # Query for runbooks sorted by similarity (cosine distance)
            # 1 - distance = similarity
            results = self.db.query(
                Runbook,
                Runbook.embedding.cosine_distance(embedding).label('distance')
            ).filter(
                Runbook.enabled == True,
                Runbook.embedding.is_not(None)
            ).order_by(
                'distance'
            ).limit(limit * 3).all()
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

        # Apply RBAC filter
        accessible_results = []
        for runbook, distance in results:
            if self.check_runbook_acl(user, runbook, permission='view'):
                accessible_results.append((runbook, distance))

        # Rank and score
        ranked = []
        for runbook, distance in accessible_results:
            # Determine permission status
            perm_status = "no_access"
            if self.check_runbook_acl(user, runbook, permission='execute'):
                perm_status = "can_execute"
            elif self.check_runbook_acl(user, runbook, permission='view'):
                perm_status = "view_only"

            score = self.calculate_runbook_score(
                runbook=runbook,
                distance=distance,
                context=context,
                user=user
            )
            print(f"DEBUG: Runbook '{runbook.name}' - distance={distance:.4f}, score={score:.4f}", flush=True)
            ranked.append(RankedRunbook(runbook=runbook, score=score, permission_status=perm_status))

        # Sort by score and return top
        ranked.sort(key=lambda x: x.score, reverse=True)
        return ranked[:limit]

    def check_runbook_acl(self, user: User, runbook: Runbook, permission: str = 'view') -> bool:
        """
        Check if user has permission to view/execute runbook.
        """
        if not runbook.enabled:
            return False

        # Superusers bypass ACLs (if applicable, but here we stick to explicit rules)
        
        # 1. Check Role-Based Access (Simplification for now)
        # If user has an admin-like role, grant access
        if user.role in ['owner', 'admin', 'maintainer', 'operator']:
            return True

        # TODO: Implement proper Group-based ACL check once GroupMember model is verified
        # For now, default to False for viewers unless public (not implemented yet)
        return False
        
        # BROKEN ACL CHECK REMOVED
        # acl_entry = self.db.query(RunbookACL).filter(
        #     RunbookACL.runbook_id == runbook.id,
        #     RunbookACL.user_id == user.id
        # ).first()
        #
        # if acl_entry:
        #     if permission == 'view':
        #         return acl_entry.can_view or acl_entry.can_execute
        #     elif permission == 'execute':
        #         return acl_entry.can_execute

        # Check approval_roles for execute permission
        if permission == 'execute' and runbook.approval_required:
            if user.roles:
                user_roles = [r.name for r in user.roles]
                return any(role in runbook.approval_roles for role in user_roles)
            return False

        # Default view permission: everyone can view enabled runbooks
        if permission == 'view':
            return True
            
        return False

    def calculate_runbook_score(self, runbook: Runbook, distance: float, context: Dict[str, Any], user: User) -> float:
        """Calculate weighted confidence score."""
        # Semantic similarity (0-1, 50% weight)
        # Cosine distance is 0 to 2 (for normalized vectors, 0 to 1 usually implies 1-cos(theta))
        # Usually dist=0 means identical. similarity = 1 - distance
        semantic_sim = max(0, 1 - distance)

        # Success rate (0-1, 30% weight)
        success_rate = 0.5 # Default
        executions = self.db.query(RunbookExecution).filter(
            RunbookExecution.runbook_id == runbook.id,
            RunbookExecution.dry_run == False
        ).limit(20).all() # Last 20 executions

        if executions:
            success_count = len([e for e in executions if e.status == 'success'])
            success_rate = success_count / len(executions)
        else:
            success_rate = 0.5  # Neutral score if no history

        # Context match (0-1, 20% weight)
        context_match = 0.0
        if context:
            if context.get('server_type') and runbook.tags and context.get('server_type') in runbook.tags:
                context_match += 0.5
            if context.get('os') and runbook.target_os_filter and context.get('os') in runbook.target_os_filter:
                context_match += 0.5
        
        context_match = min(context_match, 1.0)

        # Weighted final score
        final_score = (
            semantic_sim * 0.5 +
            success_rate * 0.3 +
            context_match * 0.2
        )

        return min(max(final_score, 0.0), 1.0)

    async def get_permission_status(self, user: User, runbook: Runbook) -> str:
        """Get human-readable permission status."""
        if self.check_runbook_acl(user, runbook, permission='execute'):
            return "can_execute"
        elif self.check_runbook_acl(user, runbook, permission='view'):
            return "view_only"
        else:
            return "no_access"
