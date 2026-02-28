from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.models import User, Role
from app.models_ai import AIPermission, AIActionConfirmation
from app.services.auth_service import normalize_role

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
        filtered = []
        for tool in tools:
            perm = self.get_tool_permission(user, pillar, tool.category, tool.name)
            if perm.permission in {"allow", "confirm"}:
                tool.requires_confirmation = perm.permission == "confirm"
                filtered.append(tool)

        return filtered

    def get_tool_permission(
        self,
        user: User,
        pillar: str,
        tool_category: Optional[str] = None,
        tool_name: Optional[str] = None
    ) -> "ToolPermission":
        """
        Synchronous permission check used by integration tests and sync services.
        Returns a ToolPermission object with permission, reason, and alternatives.
        """
        role_name = normalize_role(user.role)
        role_id = self._get_role_id_sync(role_name)

        if role_id:
            permissions = (
                self.db.query(AIPermission)
                .filter(
                    AIPermission.role_id == role_id,
                    AIPermission.pillar == pillar,
                    or_(
                        and_(
                            AIPermission.tool_category == tool_category,
                            AIPermission.tool_name == tool_name
                        ),
                        and_(
                            AIPermission.tool_category == tool_category,
                            AIPermission.tool_name == "*"
                        ),
                        and_(
                            AIPermission.tool_category == tool_category,
                            AIPermission.tool_name.is_(None)
                        ),
                        and_(
                            AIPermission.tool_category.is_(None),
                            AIPermission.tool_name.is_(None)
                        )
                    )
                )
                .all()
            )

            if permissions:
                permission = self._resolve_permission(permissions, tool_category, tool_name)
                return self._build_permission_response(role_name, tool_name, permission)

        return self._evaluate_default_policy(role_name, tool_name)

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
                # Wildcard tool match
                and_(
                    AIPermission.tool_category == tool_category,
                    AIPermission.tool_name == "*"
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

    def _get_role_id_sync(self, role_name: str) -> Optional[UUID]:
        """Sync helper to get Role ID from name string."""
        if not hasattr(self.db, "query"):
            return None
        role = self.db.query(Role).filter(Role.name == role_name).first()
        if role is None:
            role = Role(name=role_name, description=f"Auto-created role: {role_name}")
            self.db.add(role)
            self.db.flush()
        return role.id

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
            if p.tool_category:
                score += 2
            if p.tool_name:
                score += 1 if p.tool_name == "*" else 2
            return score
            
        sorted_perms = sorted(permissions, key=specificity_key, reverse=True)
        
        if not sorted_perms:
            return "deny" # Default deny if no rules exist
            
        return sorted_perms[0].permission

    def create_confirmation(
        self,
        session_id: UUID,
        user: User,
        action_type: str,
        action_details: Dict[str, Any],
        risk_level: str,
        expires_in_minutes: int = 5
    ) -> AIActionConfirmation:
        """
        Create and persist a pending confirmation for a risky action.
        """
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
        confirmation = AIActionConfirmation(
            session_id=session_id,
            user_id=user.id,
            action_type=action_type,
            action_details=action_details,
            risk_level=risk_level,
            status="pending",
            expires_at=expires_at
        )

        self.db.add(confirmation)
        self.db.commit()
        self.db.refresh(confirmation)

        return confirmation

    def _evaluate_default_policy(self, role_name: str, tool_name: Optional[str]) -> "ToolPermission":
        action_type = self._infer_action_type(tool_name or "")

        admin_roles = {"owner", "admin", "security_admin"}
        if role_name in admin_roles:
            return ToolPermission(permission="allow")

        if role_name == "operator":
            if action_type == "read":
                return ToolPermission(permission="allow")
            if action_type == "delete":
                return ToolPermission(
                    permission="deny",
                    reason="Delete actions are restricted for operators.",
                    alternative="Consider archive or disable instead of delete."
                )
            return ToolPermission(permission="confirm", reason="Operator actions require confirmation.")

        if role_name == "engineer":
            if action_type == "read":
                return ToolPermission(permission="allow")
            if action_type == "delete":
                return ToolPermission(
                    permission="deny",
                    reason="Delete actions are restricted for engineers.",
                    alternative="Consider archive or disable instead of delete."
                )
            return ToolPermission(permission="confirm", reason="Engineer actions require confirmation.")

        # Viewer or unknown roles default to read-only
        if action_type == "read":
            return ToolPermission(permission="allow")

        return ToolPermission(
            permission="deny",
            reason="Role is read-only and cannot perform this action."
        )

    def _infer_action_type(self, tool_name: str) -> str:
        name = tool_name.lower()

        delete_keywords = ("delete", "remove", "destroy", "drop", "purge")
        write_keywords = (
            "create",
            "update",
            "edit",
            "write",
            "execute",
            "run",
            "restart",
            "stop",
            "start",
            "deploy",
            "apply",
            "change",
            "approve"
        )
        read_keywords = (
            "search",
            "list",
            "get",
            "query",
            "read",
            "view",
            "describe",
            "fetch",
            "show",
            "status",
            "history",
            "metrics",
            "logs",
            "details"
        )

        if any(keyword in name for keyword in delete_keywords):
            return "delete"
        if any(keyword in name for keyword in read_keywords):
            return "read"
        if any(keyword in name for keyword in write_keywords):
            return "write"

        return "write"

    def _build_permission_response(
        self,
        role_name: str,
        tool_name: Optional[str],
        permission: str
    ) -> "ToolPermission":
        if permission == "deny":
            action_type = self._infer_action_type(tool_name or "")
            alternative = None
            if action_type == "delete":
                alternative = "Consider archive or disable instead of delete."
            return ToolPermission(
                permission="deny",
                reason="Action denied by policy.",
                alternative=alternative
            )

        if permission == "confirm":
            return ToolPermission(permission="confirm", reason="Action requires confirmation.")

        return ToolPermission(permission="allow")


@dataclass
class ToolPermission:
    permission: str
    reason: Optional[str] = None
    alternative: Optional[str] = None
