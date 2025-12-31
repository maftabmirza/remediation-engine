"""
Integration tests for Application Profiles API.

Tests cover:
- Creating application profiles
- Listing profiles with pagination and filtering
- Getting profiles by ID and application ID
- Updating profiles
- Deleting profiles
- Health check validation
- Error handling and validation
"""

import pytest
from uuid import uuid4
from datetime import datetime


# ============================================================================
# Test POST /api/application-profiles - Create Profile
# ============================================================================

@pytest.mark.asyncio
async def test_create_application_profile_success(authenticated_client, test_db_session):
    """Test creating a new application profile."""
    from app.models_application import Application

    # Create an application first
    app = Application(
        id=uuid4(),
        name="test-app",
        description="Test application"
    )
    test_db_session.add(app)
    test_db_session.commit()

    # Create profile
    profile_data = {
        "app_id": str(app.id),
        "architecture_type": "microservices",
        "framework": "FastAPI",
        "language": "Python",
        "architecture_info": {
            "description": "REST API microservice"
        },
        "service_mappings": {
            "api-service": {
                "metrics_prefix": "http_",
                "log_labels": {"app": "api-service"}
            }
        },
        "default_metrics": [
            "http_requests_total",
            "http_request_duration_seconds",
            "http_errors_total"
        ],
        "slos": {
            "availability": {"target": 99.9},
            "latency_p95": {"target": 500, "unit": "ms"}
        },
        "default_time_range": "1h",
        "log_patterns": {
            "error": "ERROR|Exception|Failed",
            "warning": "WARN|Warning"
        }
    }

    response = await authenticated_client.post(
        "/api/application-profiles",
        json=profile_data
    )

    assert response.status_code == 201
    data = response.json()
    assert data["app_id"] == str(app.id)
    assert data["architecture_type"] == "microservices"
    assert data["framework"] == "FastAPI"
    assert data["language"] == "Python"
    assert data["default_metrics"] == profile_data["default_metrics"]
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_profile_application_not_found(authenticated_client):
    """Test creating profile for non-existent application."""
    profile_data = {
        "app_id": str(uuid4()),  # Non-existent app
        "architecture_type": "monolith"
    }

    response = await authenticated_client.post(
        "/api/application-profiles",
        json=profile_data
    )

    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_profile_duplicate(authenticated_client, test_db_session):
    """Test creating duplicate profile for same application."""
    from app.models_application import Application, ApplicationProfile

    # Create application and profile
    app = Application(
        id=uuid4(),
        name="test-app",
        description="Test application"
    )
    test_db_session.add(app)
    test_db_session.commit()

    existing_profile = ApplicationProfile(
        id=uuid4(),
        app_id=app.id,
        architecture_type="monolith"
    )
    test_db_session.add(existing_profile)
    test_db_session.commit()

    # Try to create another profile for same app
    profile_data = {
        "app_id": str(app.id),
        "architecture_type": "microservices"
    }

    response = await authenticated_client.post(
        "/api/application-profiles",
        json=profile_data
    )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


# ============================================================================
# Test GET /api/application-profiles - List Profiles
# ============================================================================

@pytest.mark.asyncio
async def test_list_application_profiles(authenticated_client, test_db_session):
    """Test listing application profiles with pagination."""
    from app.models_application import Application, ApplicationProfile

    # Create test data
    for i in range(5):
        app = Application(
            id=uuid4(),
            name=f"app-{i}",
            description=f"Application {i}"
        )
        test_db_session.add(app)
        test_db_session.commit()

        profile = ApplicationProfile(
            id=uuid4(),
            app_id=app.id,
            architecture_type="microservices" if i % 2 == 0 else "monolith",
            language="Python" if i < 3 else "Go"
        )
        test_db_session.add(profile)

    test_db_session.commit()

    # List all profiles
    response = await authenticated_client.get("/api/application-profiles")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert data["total"] == 5
    assert len(data["items"]) == 5
    assert data["page"] == 1
    assert data["page_size"] == 50


@pytest.mark.asyncio
async def test_list_profiles_with_pagination(authenticated_client, test_db_session):
    """Test listing profiles with pagination parameters."""
    from app.models_application import Application, ApplicationProfile

    # Create 10 profiles
    for i in range(10):
        app = Application(id=uuid4(), name=f"app-{i}")
        test_db_session.add(app)
        test_db_session.commit()

        profile = ApplicationProfile(
            id=uuid4(),
            app_id=app.id,
            architecture_type="microservices"
        )
        test_db_session.add(profile)

    test_db_session.commit()

    # Get page 2 with 3 items per page
    response = await authenticated_client.get(
        "/api/application-profiles?page=2&page_size=3"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["items"]) == 3
    assert data["page"] == 2
    assert data["page_size"] == 3


@pytest.mark.asyncio
async def test_list_profiles_filter_by_architecture(authenticated_client, test_db_session):
    """Test filtering profiles by architecture type."""
    from app.models_application import Application, ApplicationProfile

    # Create profiles with different architectures
    for arch_type in ["microservices", "microservices", "monolith"]:
        app = Application(id=uuid4(), name=f"app-{arch_type}-{uuid4()}")
        test_db_session.add(app)
        test_db_session.commit()

        profile = ApplicationProfile(
            id=uuid4(),
            app_id=app.id,
            architecture_type=arch_type
        )
        test_db_session.add(profile)

    test_db_session.commit()

    # Filter by microservices
    response = await authenticated_client.get(
        "/api/application-profiles?architecture_type=microservices"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(item["architecture_type"] == "microservices" for item in data["items"])


@pytest.mark.asyncio
async def test_list_profiles_filter_by_language(authenticated_client, test_db_session):
    """Test filtering profiles by programming language."""
    from app.models_application import Application, ApplicationProfile

    # Create profiles with different languages
    for lang in ["Python", "Python", "Go", "Java"]:
        app = Application(id=uuid4(), name=f"app-{lang}-{uuid4()}")
        test_db_session.add(app)
        test_db_session.commit()

        profile = ApplicationProfile(
            id=uuid4(),
            app_id=app.id,
            architecture_type="microservices",
            language=lang
        )
        test_db_session.add(profile)

    test_db_session.commit()

    # Filter by Python (case-insensitive)
    response = await authenticated_client.get(
        "/api/application-profiles?language=python"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


# ============================================================================
# Test GET /api/application-profiles/by-app/{app_id} - Get by Application
# ============================================================================

@pytest.mark.asyncio
async def test_get_profile_by_application(authenticated_client, test_db_session):
    """Test getting profile by application ID."""
    from app.models_application import Application, ApplicationProfile

    app = Application(id=uuid4(), name="test-app")
    test_db_session.add(app)
    test_db_session.commit()

    profile = ApplicationProfile(
        id=uuid4(),
        app_id=app.id,
        architecture_type="microservices",
        language="Python"
    )
    test_db_session.add(profile)
    test_db_session.commit()

    response = await authenticated_client.get(
        f"/api/application-profiles/by-app/{app.id}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["app_id"] == str(app.id)
    assert data["architecture_type"] == "microservices"


@pytest.mark.asyncio
async def test_get_profile_by_application_not_found(authenticated_client):
    """Test getting profile for application without profile."""
    non_existent_app_id = uuid4()

    response = await authenticated_client.get(
        f"/api/application-profiles/by-app/{non_existent_app_id}"
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ============================================================================
# Test GET /api/application-profiles/{profile_id} - Get Profile
# ============================================================================

@pytest.mark.asyncio
async def test_get_application_profile(authenticated_client, test_db_session):
    """Test getting profile by ID with application details."""
    from app.models_application import Application, ApplicationProfile

    app = Application(
        id=uuid4(),
        name="my-app",
        description="My application"
    )
    test_db_session.add(app)
    test_db_session.commit()

    profile = ApplicationProfile(
        id=uuid4(),
        app_id=app.id,
        architecture_type="serverless",
        framework="AWS Lambda"
    )
    test_db_session.add(profile)
    test_db_session.commit()

    response = await authenticated_client.get(
        f"/api/application-profiles/{profile.id}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(profile.id)
    assert data["architecture_type"] == "serverless"
    # Should include application details (relationship)
    assert "application" in data or data["app_id"] == str(app.id)


@pytest.mark.asyncio
async def test_get_profile_not_found(authenticated_client):
    """Test getting non-existent profile."""
    non_existent_id = uuid4()

    response = await authenticated_client.get(
        f"/api/application-profiles/{non_existent_id}"
    )

    assert response.status_code == 404


# ============================================================================
# Test PUT /api/application-profiles/{profile_id} - Update Profile
# ============================================================================

@pytest.mark.asyncio
async def test_update_application_profile(authenticated_client, test_db_session):
    """Test updating an application profile."""
    from app.models_application import Application, ApplicationProfile

    app = Application(id=uuid4(), name="test-app")
    test_db_session.add(app)
    test_db_session.commit()

    profile = ApplicationProfile(
        id=uuid4(),
        app_id=app.id,
        architecture_type="monolith",
        language="Python",
        default_metrics=[]
    )
    test_db_session.add(profile)
    test_db_session.commit()

    # Update profile
    update_data = {
        "architecture_type": "microservices",
        "framework": "FastAPI",
        "default_metrics": ["http_requests_total", "cpu_usage"]
    }

    response = await authenticated_client.put(
        f"/api/application-profiles/{profile.id}",
        json=update_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["architecture_type"] == "microservices"
    assert data["framework"] == "FastAPI"
    assert len(data["default_metrics"]) == 2
    # Language should remain unchanged
    assert data["language"] == "Python"


@pytest.mark.asyncio
async def test_update_profile_not_found(authenticated_client):
    """Test updating non-existent profile."""
    non_existent_id = uuid4()

    response = await authenticated_client.put(
        f"/api/application-profiles/{non_existent_id}",
        json={"architecture_type": "monolith"}
    )

    assert response.status_code == 404


# ============================================================================
# Test DELETE /api/application-profiles/{profile_id} - Delete Profile
# ============================================================================

@pytest.mark.asyncio
async def test_delete_application_profile(authenticated_client, test_db_session):
    """Test deleting an application profile."""
    from app.models_application import Application, ApplicationProfile

    app = Application(id=uuid4(), name="test-app")
    test_db_session.add(app)
    test_db_session.commit()

    profile = ApplicationProfile(
        id=uuid4(),
        app_id=app.id,
        architecture_type="monolith"
    )
    test_db_session.add(profile)
    test_db_session.commit()
    profile_id = profile.id

    # Delete profile
    response = await authenticated_client.delete(
        f"/api/application-profiles/{profile_id}"
    )

    assert response.status_code == 204

    # Verify deletion
    response = await authenticated_client.get(
        f"/api/application-profiles/{profile_id}"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_profile_not_found(authenticated_client):
    """Test deleting non-existent profile."""
    non_existent_id = uuid4()

    response = await authenticated_client.delete(
        f"/api/application-profiles/{non_existent_id}"
    )

    assert response.status_code == 404


# ============================================================================
# Test GET /api/application-profiles/{profile_id}/health-check
# ============================================================================

@pytest.mark.asyncio
async def test_profile_health_check_complete(authenticated_client, test_db_session):
    """Test health check for complete profile."""
    from app.models_application import Application, ApplicationProfile

    app = Application(id=uuid4(), name="complete-app")
    test_db_session.add(app)
    test_db_session.commit()

    profile = ApplicationProfile(
        id=uuid4(),
        app_id=app.id,
        architecture_type="microservices",
        slos={"availability": {"target": 99.9}},
        default_metrics=["http_requests_total"],
        service_mappings={"api": {"metrics_prefix": "http_"}}
    )
    test_db_session.add(profile)
    test_db_session.commit()

    response = await authenticated_client.get(
        f"/api/application-profiles/{profile.id}/health-check"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_complete"] is True
    assert data["has_slos"] is True
    assert data["has_metrics"] is True
    assert data["has_service_mappings"] is True
    assert data["has_architecture"] is True
    assert len(data["recommendations"]) == 0
    assert data["profile_id"] == str(profile.id)


@pytest.mark.asyncio
async def test_profile_health_check_incomplete(authenticated_client, test_db_session):
    """Test health check for incomplete profile."""
    from app.models_application import Application, ApplicationProfile

    app = Application(id=uuid4(), name="incomplete-app")
    test_db_session.add(app)
    test_db_session.commit()

    profile = ApplicationProfile(
        id=uuid4(),
        app_id=app.id,
        # Missing architecture_type, slos, metrics, service_mappings
    )
    test_db_session.add(profile)
    test_db_session.commit()

    response = await authenticated_client.get(
        f"/api/application-profiles/{profile.id}/health-check"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_complete"] is False
    assert data["has_slos"] is False
    assert data["has_metrics"] is False
    assert data["has_service_mappings"] is False
    assert data["has_architecture"] is False
    assert len(data["recommendations"]) > 0
    # Should have recommendations for missing components
    assert any("SLOs" in rec for rec in data["recommendations"])
    assert any("metrics" in rec for rec in data["recommendations"])
    assert any("service mappings" in rec for rec in data["recommendations"])
    assert any("architecture" in rec for rec in data["recommendations"])


@pytest.mark.asyncio
async def test_health_check_profile_not_found(authenticated_client):
    """Test health check for non-existent profile."""
    non_existent_id = uuid4()

    response = await authenticated_client.get(
        f"/api/application-profiles/{non_existent_id}/health-check"
    )

    assert response.status_code == 404


# ============================================================================
# Test Authentication and Authorization
# ============================================================================

@pytest.mark.asyncio
async def test_create_profile_unauthenticated(async_client, test_db_session):
    """Test creating profile without authentication."""
    from app.models_application import Application

    app = Application(id=uuid4(), name="test-app")
    test_db_session.add(app)
    test_db_session.commit()

    profile_data = {
        "app_id": str(app.id),
        "architecture_type": "monolith"
    }

    # Request without auth headers
    response = await async_client.post(
        "/api/application-profiles",
        json=profile_data
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_profiles_unauthenticated(async_client):
    """Test listing profiles without authentication."""
    response = await async_client.get("/api/application-profiles")

    assert response.status_code == 401
