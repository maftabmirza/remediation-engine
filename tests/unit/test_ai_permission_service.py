import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4

from app.models import User, Role
from app.models_ai import AIPermission
from app.services.ai_permission_service import AIPermissionService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    return db

@pytest.fixture
def permission_service(mock_db):
    return AIPermissionService(mock_db)

@pytest.fixture
def user():
    return User(id=uuid4(), username="testuser", role="admin")

@pytest.mark.asyncio
async def test_check_permission_role_not_found(permission_service, mock_db, user):
    # Mock _get_role_id to return None (empty DB result)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    result = await permission_service.check_permission(user, "inquiry")
    assert result == "deny"

@pytest.mark.asyncio
async def test_check_permission_default_deny(permission_service, mock_db, user):
    # Mock Role ID found
    role_id = uuid4()
    mock_role_result = MagicMock()
    mock_role_result.scalar_one_or_none.return_value = role_id
    
    # Mock No Permissions found
    mock_perms_result = MagicMock()
    mock_perms_result.scalars().all.return_value = []
    
    # Configure side effects for sequential calls
    mock_db.execute.side_effect = [mock_role_result, mock_perms_result]

    result = await permission_service.check_permission(user, "inquiry")
    assert result == "deny"

@pytest.mark.asyncio
async def test_check_permission_specificity(permission_service, mock_db, user):
    role_id = uuid4()
    
    # Define various levels of permissions
    perm_pillar = AIPermission(role_id=role_id, pillar="revive", permission="deny")
    perm_category = AIPermission(role_id=role_id, pillar="revive", tool_category="grafana", permission="confirm")
    perm_tool = AIPermission(role_id=role_id, pillar="revive", tool_category="grafana", tool_name="create_dashboard", permission="allow")

    # 1. Test exact tool match
    mock_db.execute.side_effect = None # Reset
    mock_role_res = MagicMock()
    mock_role_res.scalar_one_or_none.return_value = role_id
    
    mock_perms_res = MagicMock()
    # Return all 3, logic should pick specifics
    mock_perms_res.scalars().all.return_value = [perm_pillar, perm_category, perm_tool]
    
    mock_db.execute.side_effect = [mock_role_res, mock_perms_res]
    
    result = await permission_service.check_permission(user, "revive", "grafana", "create_dashboard")
    assert result == "allow"

    # 2. Test Category Match (tool name mismatch/missing logic handled by query, checking resolution logic here)
    # The service query logic filters what comes back. 
    # check_permission logic: 
    # If we ask for "delete_dashboard" (not in list), but we get back [perm_pillar, perm_category] 
    # (assuming query returns partial matches as programmed)
    # The actual code query `or_` conditions imply we get relevant rules.
    
    # Let's simulate we query for "delete_dashboard" and DB returns pillar and category rules
    mock_db.execute.side_effect = None
    mock_role_res = MagicMock()
    mock_role_res.scalar_one_or_none.return_value = role_id
    
    mock_perms_res = MagicMock()
    mock_perms_res.scalars().all.return_value = [perm_pillar, perm_category]
    
    mock_db.execute.side_effect = [mock_role_res, mock_perms_res]
    
    result = await permission_service.check_permission(user, "revive", "grafana", "delete_dashboard")
    assert result == "confirm" # Category level wins over pillar

    # 3. Test Pillar Match
    mock_db.execute.side_effect = None
    mock_role_res = MagicMock()
    mock_role_res.scalar_one_or_none.return_value = role_id
    
    mock_perms_res = MagicMock()
    mock_perms_res.scalars().all.return_value = [perm_pillar]
    
    mock_db.execute.side_effect = [mock_role_res, mock_perms_res]
    
    result = await permission_service.check_permission(user, "revive", "aiops", "reboot_server")
    assert result == "deny" # Pillar level

@pytest.mark.asyncio
async def test_get_user_capabilities(permission_service, mock_db, user):
    role_id = uuid4()
    perm1 = AIPermission(role_id=role_id, pillar="inquiry", permission="allow")
    perm2 = AIPermission(role_id=role_id, pillar="revive", tool_category="grafana", permission="confirm")
    
    # Mock calls
    mock_role_res = MagicMock()
    mock_role_res.scalar_one_or_none.return_value = role_id
    
    mock_perms_res = MagicMock()
    mock_perms_res.scalars().all.return_value = [perm1, perm2]
    
    mock_db.execute.side_effect = [mock_role_res, mock_perms_res]
    
    caps = await permission_service.get_user_capabilities(user)
    
    assert caps["user_role"] == "admin"
    assert len(caps["permissions"]["inquiry"]) == 1
    assert caps["permissions"]["inquiry"][0]["permission"] == "allow"
    assert caps["permissions"]["revive"][0]["tool_category"] == "grafana"
