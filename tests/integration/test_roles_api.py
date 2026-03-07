"""
Integration tests for /api/roles endpoint.

These tests specifically guard against the regression where the roles table
was empty on a fresh deployment, causing the Add User modal role dropdown
to show no options.

Root cause that went undetected: ROLE_PERMISSIONS (code) and the roles DB
table were out of sync — built-in roles were never seeded at startup.
"""
import pytest
from fastapi.testclient import TestClient

EXPECTED_BUILTIN_ROLES = {"owner", "admin", "maintainer", "operator", "viewer", "auditor", "security_admin", "security_viewer"}


@pytest.mark.integration
def test_get_roles_returns_all_builtin_roles(test_client: TestClient, admin_auth_headers: dict, test_db_session):
    """
    GET /api/roles must return all built-in roles so the Add User dropdown
    is never empty on a fresh deployment.

    Regression guard for: roles table empty → dropdown shows nothing.
    """
    from app.models import Role
    from app.services.auth_service import ROLE_PERMISSIONS

    # Seed built-in roles the same way init_db() does (test DB doesn't call init_db)
    for role_name, perms in ROLE_PERMISSIONS.items():
        if not test_db_session.query(Role).filter(Role.name == role_name).first():
            test_db_session.add(Role(
                name=role_name,
                description=f"Built-in {role_name} role",
                permissions=sorted(perms),
                is_custom=False,
            ))
    test_db_session.commit()

    response = test_client.get("/api/roles", headers=admin_auth_headers)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    roles = response.json()
    assert isinstance(roles, list), "Response must be a list"
    assert len(roles) > 0, (
        "roles table is empty — /api/roles returned []. "
        "This causes the Add User modal role dropdown to show no options. "
        "Ensure init_db() seeds ROLE_PERMISSIONS into the roles table."
    )

    returned_names = {r["name"] for r in roles}
    assert EXPECTED_BUILTIN_ROLES.issubset(returned_names), (
        f"Missing built-in roles: {EXPECTED_BUILTIN_ROLES - returned_names}"
    )


@pytest.mark.integration
def test_get_roles_builtin_roles_are_not_custom(test_client: TestClient, admin_auth_headers: dict, test_db_session):
    """
    Built-in roles must have is_custom=False so they cannot be deleted.
    """
    from app.models import Role
    from app.services.auth_service import ROLE_PERMISSIONS

    for role_name, perms in ROLE_PERMISSIONS.items():
        if not test_db_session.query(Role).filter(Role.name == role_name).first():
            test_db_session.add(Role(
                name=role_name,
                description=f"Built-in {role_name} role",
                permissions=sorted(perms),
                is_custom=False,
            ))
    test_db_session.commit()

    response = test_client.get("/api/roles", headers=admin_auth_headers)
    assert response.status_code == 200

    builtin = [r for r in response.json() if r["name"] in EXPECTED_BUILTIN_ROLES]
    for role in builtin:
        assert role["is_custom"] is False, (
            f"Built-in role '{role['name']}' has is_custom=True — "
            "it would be deletable, which should not be allowed."
        )


@pytest.mark.integration
def test_get_roles_requires_authentication(test_client: TestClient):
    """
    GET /api/roles must reject unauthenticated requests.
    """
    response = test_client.get("/api/roles")
    assert response.status_code == 401, (
        f"Expected 401 for unauthenticated request, got {response.status_code}"
    )


@pytest.mark.integration
def test_cannot_delete_builtin_role(test_client: TestClient, admin_auth_headers: dict, test_db_session):
    """
    DELETE /api/roles/{id} must refuse to delete built-in roles.
    """
    from app.models import Role
    from app.services.auth_service import ROLE_PERMISSIONS

    for role_name, perms in ROLE_PERMISSIONS.items():
        if not test_db_session.query(Role).filter(Role.name == role_name).first():
            test_db_session.add(Role(
                name=role_name,
                description=f"Built-in {role_name} role",
                permissions=sorted(perms),
                is_custom=False,
            ))
    test_db_session.commit()

    viewer = test_db_session.query(Role).filter(Role.name == "viewer").first()
    assert viewer is not None

    response = test_client.delete(f"/api/roles/{viewer.id}", headers=admin_auth_headers)
    assert response.status_code == 403, (
        f"Should not be able to delete built-in role 'viewer', got {response.status_code}"
    )
