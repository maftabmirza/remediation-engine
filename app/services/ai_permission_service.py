from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.models import User, Role
from app.models_ai import AIPermission

class AIPermissionService:
    """
    Service for handling AI-related RBAC permissions.
    """
    def __init__(self, db):
        self.db = db

    def can_access_pillar(self, user: User, pillar: str) -> bool:
        """
        Check if user can access a specific AI pillar.
        Returns True if user has any permissions for this pillar.
        Default: Allow access (permissions checked at tool level)
        """
        # For now, allow all authenticated users to access any pillar
        # Fine-grained permissions are checked at tool execution time
        return True

    def filter_tools_by_permission(self, user: User, pillar: str, tools: list) -> list:
        """
        Filter tools based on user permissions for a pillar.
        Returns list of tools the user is allowed to use.
        Default: Return all tools (permissions checked at execution time)
        """
        # For now, return all tools - permissions checked when tool is executed
        return tools

    async def check_permission(
        self, 
        user: User, 
        pillar: str, 
        tool_category: Optional[str] = None, 
        tool_name: Optional[str] = None
    ) -> str:
        """
        Check permission for a specific tool execution.
        Returns: 'allow', 'deny', or 'confirm'
        """
        # 1. Resolve User Role ID
        role_id = await self._get_role_id(user.role)
        if not role_id:
            # Fallback: If role definition doesn't exist in DB, default to DENY for safety
            return "deny"

        # 2. Query Permissions
        # specific tool > category > pillar
        # We can fetch all relevant permissions for this pillar and calculate in-memory 
        # or use a complex query. Fetching all for pillar/role is likely efficient enough.
        
        stmt = select(AIPermission).where(
            AIPermission.role_id == role_id,
            AIPermission.pillar == pillar,
            or_(
                # Exact tool match
                and_(
                    AIPermission.tool_category == tool_category,
                    AIPermission.tool_name == tool_name
                ),
                # Category match (all tools in category)
                and_(
                    AIPermission.tool_category == tool_category,
                    AIPermission.tool_name.is_(None)
                ),
                # Pillar match (all tools in pillar)
                and_(
                    AIPermission.tool_category.is_(None),
                    AIPermission.tool_name.is_(None)
                )
            )
        )
        
        result = await self.db.execute(stmt)
        permissions = result.scalars().all()
        
        # 3. Resolve most specific permission
        return self._resolve_permission(permissions, tool_category, tool_name)

    async def get_user_capabilities(self, user: User) -> Dict[str, Any]:
        """
        Get all AI capabilities for the user to populate UI state.
        """
        role_id = await self._get_role_id(user.role)
        if not role_id:
            return {}

        stmt = select(AIPermission).where(AIPermission.role_id == role_id)
        result = await self.db.execute(stmt)
        permissions = result.scalars().all()
        
        # Organize by pillar -> category -> tool
        capabilities = {}
        for p in permissions:
            if p.pillar not in capabilities:
                capabilities[p.pillar] = []
            
            capabilities[p.pillar].append({
                "tool_category": p.tool_category,
                "tool_name": p.tool_name,
                "permission": p.permission
            })
            
        return {
            "user_role": user.role,
            "permissions": capabilities
        }

    async def _get_role_id(self, role_name: str) -> Optional[UUID]:
        """Helper to get Role ID from name string"""
        stmt = select(Role.id).where(Role.name == role_name)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _resolve_permission(self, permissions: List[AIPermission], category: str, name: str) -> str:
        """
        Determine the effective permission from a list of matches.
        Priority:
        1. Exact Match (category + name)
        2. Category Match (category + NULL name)
        3. Pillar Match (NULL category + NULL name)
        
        Default: DENY
        """
        # Sort by specificity: 
        # (has_category, has_name) => (1, 1) > (1, 0) > (0, 0)
        
        def specificity_key(p):
            score = 0
            if p.tool_category: score += 1
            if p.tool_name: score += 1
            return score
            
        sorted_perms = sorted(permissions, key=specificity_key, reverse=True)
        
        if not sorted_perms:
            return "deny" # Default deny if no rules exist
            
        return sorted_perms[0].permission
