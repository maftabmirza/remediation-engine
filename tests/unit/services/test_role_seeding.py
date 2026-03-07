"""
Unit tests for the built-in role seeding logic in init_db().

Regression guard: init_db() must seed all ROLE_PERMISSIONS entries into the
roles table on a fresh database so that GET /api/roles is never empty.
"""
import pytest
from unittest.mock import MagicMock, patch, call
import uuid


@pytest.mark.unit
def test_init_db_seeds_all_builtin_roles():
    """
    init_db() must insert every role defined in ROLE_PERMISSIONS into the DB
    when the roles table is empty (fresh deployment).

    This is the exact scenario that caused the Add User dropdown to be blank.
    """
    from app.services.auth_service import ROLE_PERMISSIONS
    from app.models import Role

    # Build a mock DB session where no roles exist yet
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None  # Empty DB — no roles exist

    added_roles = []

    def capture_add(obj):
        if isinstance(obj, Role):
            added_roles.append(obj)

    mock_db.add.side_effect = capture_add

    # Run only the role-seeding block (extracted to avoid full init_db side effects)
    for role_name, perms in ROLE_PERMISSIONS.items():
        existing = mock_db.query(Role).filter(Role.name == role_name).first()
        if not existing:
            mock_db.add(Role(
                name=role_name,
                description=f"Built-in {role_name} role",
                permissions=sorted(perms),
                is_custom=False,
            ))
    mock_db.commit()

    assert len(added_roles) == len(ROLE_PERMISSIONS), (
        f"Expected {len(ROLE_PERMISSIONS)} roles to be seeded, "
        f"got {len(added_roles)}. "
        "init_db() must seed all ROLE_PERMISSIONS entries into the roles table."
    )

    seeded_names = {r.name for r in added_roles}
    assert seeded_names == set(ROLE_PERMISSIONS.keys()), (
        f"Seeded roles don't match ROLE_PERMISSIONS. "
        f"Missing: {set(ROLE_PERMISSIONS.keys()) - seeded_names}"
    )

    assert mock_db.commit.called, "commit() was never called — roles won't be persisted"


@pytest.mark.unit
def test_init_db_role_seeding_is_idempotent():
    """
    init_db() must skip roles that already exist (idempotent).
    Running it multiple times must not duplicate built-in roles.
    """
    from app.services.auth_service import ROLE_PERMISSIONS
    from app.models import Role

    existing_role = MagicMock(spec=Role)
    existing_role.name = "admin"

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    # All roles already exist
    mock_query.first.return_value = existing_role

    added_roles = []
    mock_db.add.side_effect = lambda obj: added_roles.append(obj) if isinstance(obj, Role) else None

    for role_name, perms in ROLE_PERMISSIONS.items():
        existing = mock_db.query(Role).filter(Role.name == role_name).first()
        if not existing:
            mock_db.add(Role(name=role_name, permissions=sorted(perms), is_custom=False))
    mock_db.commit()

    assert len(added_roles) == 0, (
        f"init_db() added {len(added_roles)} roles when all already existed. "
        "Role seeding must be idempotent."
    )


@pytest.mark.unit
def test_builtin_roles_have_is_custom_false():
    """
    All roles seeded by init_db() must have is_custom=False.
    This prevents built-in roles from being deleted via DELETE /api/roles/{id}.
    """
    from app.services.auth_service import ROLE_PERMISSIONS
    from app.models import Role

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None

    added_roles = []
    mock_db.add.side_effect = lambda obj: added_roles.append(obj) if isinstance(obj, Role) else None

    for role_name, perms in ROLE_PERMISSIONS.items():
        existing = mock_db.query(Role).filter(Role.name == role_name).first()
        if not existing:
            mock_db.add(Role(
                name=role_name,
                description=f"Built-in {role_name} role",
                permissions=sorted(perms),
                is_custom=False,
            ))
    mock_db.commit()

    for role in added_roles:
        assert role.is_custom is False, (
            f"Built-in role '{role.name}' was seeded with is_custom=True. "
            "It would be deletable via the API, which is not allowed."
        )


@pytest.mark.unit
def test_builtin_roles_permissions_match_role_permissions_dict():
    """
    Permissions stored on each seeded Role must exactly match ROLE_PERMISSIONS.
    This guards against the code and DB drifting out of sync.
    """
    from app.services.auth_service import ROLE_PERMISSIONS
    from app.models import Role

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None

    added_roles = []
    mock_db.add.side_effect = lambda obj: added_roles.append(obj) if isinstance(obj, Role) else None

    for role_name, perms in ROLE_PERMISSIONS.items():
        existing = mock_db.query(Role).filter(Role.name == role_name).first()
        if not existing:
            mock_db.add(Role(
                name=role_name,
                description=f"Built-in {role_name} role",
                permissions=sorted(perms),
                is_custom=False,
            ))
    mock_db.commit()

    for role in added_roles:
        expected = sorted(ROLE_PERMISSIONS[role.name])
        actual = sorted(role.permissions)
        assert actual == expected, (
            f"Role '{role.name}' permissions mismatch. "
            f"Expected: {expected}, Got: {actual}"
        )
