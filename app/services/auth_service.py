"""
Authentication service - JWT tokens, password hashing
"""
from datetime import datetime, timedelta
from typing import Optional, Set, List
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.database import get_db
from app.models import User, Role
from app.models_group import Group, GroupMember
from app.models_runbook_acl import RunbookACL

settings = get_settings()

# ---- Role & Permission model ----

# Normalize legacy roles to the richer RBAC set
ROLE_ALIASES = {"user": "operator"}

ROLE_PERMISSIONS = {
    "owner": {
        "manage_users",
        "manage_servers",
        "manage_server_groups",
        "manage_providers",
        "execute",
        "update",
        "read",
        "view_audit",
        "view_knowledge",
        "upload_documents",
        "manage_knowledge",
    },
    "admin": {
        "manage_users",
        "manage_servers",
        "manage_server_groups",
        "manage_providers",
        "execute",
        "update",
        "read",
        "view_audit",
        "view_knowledge",
        "upload_documents",
        "manage_knowledge",
    },
    "maintainer": {
        "manage_servers",
        "manage_server_groups",
        "manage_providers",
        "update",
        "execute",
        "read",
        "view_knowledge",
        "upload_documents",
        "manage_knowledge",
    },
    "operator": {
        "execute",
        "read",
        "view_knowledge",
        "upload_documents",
    },
    "viewer": {
        "read",
        "view_knowledge",
    },
    "auditor": {
        "read",
        "view_audit",
        "view_knowledge",
    },
}

DEFAULT_ROLE = "operator"
ADMIN_ROLES = {"owner", "admin"}
VALID_ROLES = set(ROLE_PERMISSIONS.keys())

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer scheme
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    # bcrypt has a 72-byte limit for passwords
    truncated_password = plain_password[:72] if plain_password else plain_password
    try:
        return pwd_context.verify(truncated_password, hashed_password)
    except ValueError:
        # Handle invalid hash format or other bcrypt errors
        return False


def get_password_hash(password: str) -> str:
    """Hash a password"""
    # bcrypt has a 72-byte limit for passwords
    truncated_password = password[:72] if password else password
    return pwd_context.hash(truncated_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiry_hours)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username"""
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password"""
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def normalize_role(role: str) -> str:
    """Map legacy or alias roles to the canonical role name."""
    return ROLE_ALIASES.get(role, role)


def get_permissions_for_role(db: Session, role: str) -> Set[str]:
    """Return the permission set for a given role string from DB."""
    normalized = normalize_role(role)
    # Query DB
    role_obj = db.query(Role).filter(Role.name == normalized).first()
    if role_obj:
        return set(role_obj.permissions)
    
    # Fallback to defaults (useful during migration or if DB is empty)
    return ROLE_PERMISSIONS.get(normalized, set())


def get_permissions_for_user(db: Session, user: User) -> Set[str]:
    """
    Get all permissions for a user: direct role + all group roles.
    
    Permission calculation: user_perms = direct_role_perms ∪ group1_role_perms ∪ group2_role_perms ...
    """
    perms = set()
    
    # 1. Direct user role permissions
    direct_perms = get_permissions_for_role(db, user.role)
    perms.update(direct_perms)
    
    # 2. Group role permissions
    memberships = db.query(GroupMember).filter(
        GroupMember.user_id == user.id
    ).all()
    
    for membership in memberships:
        group = db.query(Group).filter(
            Group.id == membership.group_id,
            Group.is_active == True
        ).first()
        
        if group and group.role:
            group_perms = set(group.role.permissions or [])
            perms.update(group_perms)
    
    return perms


def has_permission(db: Session, user: User, permission: str) -> bool:
    """Check if a user has a specific permission (from direct role or groups)."""
    return permission in get_permissions_for_user(db, user)


def can_access_runbook(db: Session, user: User, runbook_id: str, action: str) -> bool:
    """
    Check if user can perform action on runbook (ADDITIVE model).
    
    action: 'view', 'edit', 'execute'
    
    Returns True if:
    - User has global permission (edit_runbooks, execute_runbooks, view_runbooks)
    - OR User belongs to a group with matching ACL on this runbook
    """
    # Map action to global permission
    global_perm_map = {
        'view': 'read',  # Any read permission allows viewing
        'edit': 'edit_runbooks',
        'execute': 'execute_runbooks'
    }
    
    global_perm = global_perm_map.get(action)
    if not global_perm:
        return False
    
    # Check global permission first
    user_perms = get_permissions_for_user(db, user)
    if global_perm in user_perms:
        return True
    
    # For view, also check 'execute_runbooks' and 'edit_runbooks' (they imply view)
    if action == 'view' and ('execute_runbooks' in user_perms or 'edit_runbooks' in user_perms):
        return True
    
    # Check ACL: get user's group IDs
    memberships = db.query(GroupMember).filter(GroupMember.user_id == user.id).all()
    group_ids = [m.group_id for m in memberships]
    
    if not group_ids:
        return False
    
    # Find ACL entry for this runbook and any of user's groups
    acl_column = {
        'view': RunbookACL.can_view,
        'edit': RunbookACL.can_edit,
        'execute': RunbookACL.can_execute
    }[action]
    
    acl_entry = db.query(RunbookACL).filter(
        RunbookACL.runbook_id == runbook_id,
        RunbookACL.group_id.in_(group_ids),
        acl_column == True
    ).first()
    
    return acl_entry is not None

def create_user(db: Session, username: str, password: str, role: str = DEFAULT_ROLE) -> User:
    """Create a new user"""
    normalized_role = normalize_role(role)
    if normalized_role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        password_hash=hashed_password,
        role=normalized_role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from JWT token.
    Checks both Authorization header and cookie.
    """
    token = None
    
    # Try Authorization header first
    if credentials:
        token = credentials.credentials
    
    # Try cookie if no header
    if not token:
        token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    
    return user


async def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.
    Useful for endpoints that work with or without authentication.
    """
    try:
        return await get_current_user(request, credentials, db)
    except HTTPException:
        return None


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that requires an administrative role."""
    role = normalize_role(user.role)
    if role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


def require_role(allowed_roles: list):
    """
    Dependency factory that requires specific roles.
    
    Usage:
        @router.get("/endpoint")
        async def endpoint(user: User = Depends(require_role(["admin", "engineer"]))):
            ...
    """
    def role_checker(user: User = Depends(get_current_user)) -> User:
        normalized = normalize_role(user.role)
        normalized_allowed = {normalize_role(r) for r in allowed_roles}
        if normalized not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(normalized_allowed)}"
            )
        return user
    return role_checker


def require_permission(required: List[str]):
    """Dependency factory that enforces the presence of permissions (from direct role or groups)."""

    def permission_checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        user_perms = get_permissions_for_user(db, user)
        if not set(required).issubset(user_perms):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Missing required permissions"
            )
        return user

    return permission_checker


async def get_current_user_ws(token: str, db: Session) -> Optional[User]:
    """
    Authenticate WebSocket connection using JWT token.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
        
    user = get_user_by_id(db, user_id=user_id)
    if user is None:
        return None
        
    return user
