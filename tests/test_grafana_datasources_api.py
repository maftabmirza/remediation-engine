"""
Integration tests for Grafana Datasources API.

Tests cover:
- Creating datasources
- Listing datasources with pagination and filtering
- Getting datasources by ID and type
- Updating datasources
- Deleting datasources
- Health check functionality
- Connection testing
- Error handling and validation
"""

import pytest
from uuid import uuid4
from datetime import datetime


# ============================================================================
# Test POST /api/grafana-datasources - Create Datasource
# ============================================================================

@pytest.mark.asyncio
async def test_create_datasource_loki_success(authenticated_client, test_db_session):
    """Test creating a Loki datasource."""
    datasource_data = {
        "name": "production-loki",
        "datasource_type": "loki",
        "url": "http://loki:3100",
        "description": "Production Loki instance for log aggregation",
        "auth_type": "none",
        "timeout": 30,
        "is_default": True,
        "is_enabled": True,
        "config_json": {"max_lines": 5000},
        "custom_headers": {}
    }

    response = await authenticated_client.post(
        "/api/grafana-datasources",
        json=datasource_data
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "production-loki"
    assert data["datasource_type"] == "loki"
    assert data["url"] == "http://loki:3100"
    assert data["is_default"] is True
    assert data["is_enabled"] is True
    assert data["config_json"]["max_lines"] == 5000
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_datasource_tempo_success(authenticated_client, test_db_session):
    """Test creating a Tempo datasource."""
    datasource_data = {
        "name": "production-tempo",
        "datasource_type": "tempo",
        "url": "http://tempo:3200",
        "description": "Production Tempo for distributed tracing",
        "timeout": 60,
        "is_default": True,
        "config_json": {"trace_query_type": "search"}
    }

    response = await authenticated_client.post(
        "/api/grafana-datasources",
        json=datasource_data
    )

    assert response.status_code == 201
    data = response.json()
    assert data["datasource_type"] == "tempo"
    assert data["timeout"] == 60


@pytest.mark.asyncio
async def test_create_datasource_duplicate_name(authenticated_client, test_db_session):
    """Test creating datasource with duplicate name fails."""
    from app.models_application import GrafanaDatasource

    # Create existing datasource
    existing = GrafanaDatasource(
        id=uuid4(),
        name="existing-loki",
        datasource_type="loki",
        url="http://loki:3100"
    )
    test_db_session.add(existing)
    test_db_session.commit()

    # Try to create another with same name
    datasource_data = {
        "name": "existing-loki",
        "datasource_type": "loki",
        "url": "http://other-loki:3100"
    }

    response = await authenticated_client.post(
        "/api/grafana-datasources",
        json=datasource_data
    )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_datasource_auto_unset_default(authenticated_client, test_db_session):
    """Test creating default datasource unsets previous default."""
    from app.models_application import GrafanaDatasource

    # Create existing default Loki datasource
    existing = GrafanaDatasource(
        id=uuid4(),
        name="old-default-loki",
        datasource_type="loki",
        url="http://old-loki:3100",
        is_default=True
    )
    test_db_session.add(existing)
    test_db_session.commit()

    # Create new default Loki datasource
    datasource_data = {
        "name": "new-default-loki",
        "datasource_type": "loki",
        "url": "http://new-loki:3100",
        "is_default": True
    }

    response = await authenticated_client.post(
        "/api/grafana-datasources",
        json=datasource_data
    )

    assert response.status_code == 201

    # Verify old default is no longer default
    test_db_session.refresh(existing)
    assert existing.is_default is False


# ============================================================================
# Test GET /api/grafana-datasources - List Datasources
# ============================================================================

@pytest.mark.asyncio
async def test_list_datasources(authenticated_client, test_db_session):
    """Test listing datasources with pagination."""
    from app.models_application import GrafanaDatasource

    # Create test datasources
    for i in range(5):
        ds = GrafanaDatasource(
            id=uuid4(),
            name=f"datasource-{i}",
            datasource_type="loki" if i % 2 == 0 else "tempo",
            url=f"http://ds-{i}:3100"
        )
        test_db_session.add(ds)

    test_db_session.commit()

    # List all datasources
    response = await authenticated_client.get("/api/grafana-datasources")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert data["total"] == 5
    assert len(data["items"]) == 5


@pytest.mark.asyncio
async def test_list_datasources_with_pagination(authenticated_client, test_db_session):
    """Test listing datasources with pagination parameters."""
    from app.models_application import GrafanaDatasource

    # Create 10 datasources
    for i in range(10):
        ds = GrafanaDatasource(
            id=uuid4(),
            name=f"ds-{i}",
            datasource_type="loki",
            url=f"http://loki-{i}:3100"
        )
        test_db_session.add(ds)

    test_db_session.commit()

    # Get page 2 with 3 items per page
    response = await authenticated_client.get(
        "/api/grafana-datasources?page=2&page_size=3"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["items"]) == 3
    assert data["page"] == 2
    assert data["page_size"] == 3


@pytest.mark.asyncio
async def test_list_datasources_filter_by_type(authenticated_client, test_db_session):
    """Test filtering datasources by type."""
    from app.models_application import GrafanaDatasource

    # Create datasources of different types
    for ds_type in ["loki", "loki", "tempo", "prometheus"]:
        ds = GrafanaDatasource(
            id=uuid4(),
            name=f"{ds_type}-ds",
            datasource_type=ds_type,
            url=f"http://{ds_type}:3100"
        )
        test_db_session.add(ds)

    test_db_session.commit()

    # Filter by loki
    response = await authenticated_client.get(
        "/api/grafana-datasources?datasource_type=loki"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(item["datasource_type"] == "loki" for item in data["items"])


@pytest.mark.asyncio
async def test_list_datasources_filter_by_enabled(authenticated_client, test_db_session):
    """Test filtering datasources by enabled status."""
    from app.models_application import GrafanaDatasource

    # Create enabled and disabled datasources
    for i in range(5):
        ds = GrafanaDatasource(
            id=uuid4(),
            name=f"ds-{i}",
            datasource_type="loki",
            url=f"http://loki-{i}:3100",
            is_enabled=(i % 2 == 0)
        )
        test_db_session.add(ds)

    test_db_session.commit()

    # Filter by enabled=true
    response = await authenticated_client.get(
        "/api/grafana-datasources?is_enabled=true"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert all(item["is_enabled"] is True for item in data["items"])


@pytest.mark.asyncio
async def test_list_datasources_search(authenticated_client, test_db_session):
    """Test searching datasources by name/description."""
    from app.models_application import GrafanaDatasource

    # Create datasources with different names
    datasources = [
        {"name": "production-loki", "description": "Production environment logs"},
        {"name": "staging-loki", "description": "Staging environment logs"},
        {"name": "production-tempo", "description": "Production traces"}
    ]

    for ds_data in datasources:
        ds = GrafanaDatasource(
            id=uuid4(),
            datasource_type="loki",
            url="http://loki:3100",
            **ds_data
        )
        test_db_session.add(ds)

    test_db_session.commit()

    # Search for "production"
    response = await authenticated_client.get(
        "/api/grafana-datasources?search=production"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


# ============================================================================
# Test GET /api/grafana-datasources/{id} - Get Datasource
# ============================================================================

@pytest.mark.asyncio
async def test_get_datasource(authenticated_client, test_db_session):
    """Test getting datasource by ID."""
    from app.models_application import GrafanaDatasource

    ds = GrafanaDatasource(
        id=uuid4(),
        name="test-loki",
        datasource_type="loki",
        url="http://loki:3100",
        description="Test Loki instance"
    )
    test_db_session.add(ds)
    test_db_session.commit()

    response = await authenticated_client.get(
        f"/api/grafana-datasources/{ds.id}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(ds.id)
    assert data["name"] == "test-loki"
    assert data["datasource_type"] == "loki"


@pytest.mark.asyncio
async def test_get_datasource_not_found(authenticated_client):
    """Test getting non-existent datasource."""
    non_existent_id = uuid4()

    response = await authenticated_client.get(
        f"/api/grafana-datasources/{non_existent_id}"
    )

    assert response.status_code == 404


# ============================================================================
# Test GET /api/grafana-datasources/type/{type}/default - Get Default
# ============================================================================

@pytest.mark.asyncio
async def test_get_default_datasource(authenticated_client, test_db_session):
    """Test getting default datasource for a type."""
    from app.models_application import GrafanaDatasource

    # Create non-default datasource
    ds1 = GrafanaDatasource(
        id=uuid4(),
        name="loki-1",
        datasource_type="loki",
        url="http://loki-1:3100",
        is_default=False
    )
    test_db_session.add(ds1)

    # Create default datasource
    ds2 = GrafanaDatasource(
        id=uuid4(),
        name="loki-default",
        datasource_type="loki",
        url="http://loki-2:3100",
        is_default=True
    )
    test_db_session.add(ds2)
    test_db_session.commit()

    response = await authenticated_client.get(
        "/api/grafana-datasources/type/loki/default"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "loki-default"
    assert data["is_default"] is True


@pytest.mark.asyncio
async def test_get_default_datasource_not_found(authenticated_client, test_db_session):
    """Test getting default datasource when none exists."""
    response = await authenticated_client.get(
        "/api/grafana-datasources/type/tempo/default"
    )

    assert response.status_code == 404
    assert "no default" in response.json()["detail"].lower()


# ============================================================================
# Test PUT /api/grafana-datasources/{id} - Update Datasource
# ============================================================================

@pytest.mark.asyncio
async def test_update_datasource(authenticated_client, test_db_session):
    """Test updating a datasource."""
    from app.models_application import GrafanaDatasource

    ds = GrafanaDatasource(
        id=uuid4(),
        name="old-name",
        datasource_type="loki",
        url="http://old-url:3100",
        timeout=30,
        is_enabled=True
    )
    test_db_session.add(ds)
    test_db_session.commit()

    # Update datasource
    update_data = {
        "name": "new-name",
        "url": "http://new-url:3100",
        "timeout": 60,
        "is_enabled": False
    }

    response = await authenticated_client.put(
        f"/api/grafana-datasources/{ds.id}",
        json=update_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "new-name"
    assert data["url"] == "http://new-url:3100"
    assert data["timeout"] == 60
    assert data["is_enabled"] is False


@pytest.mark.asyncio
async def test_update_datasource_set_default(authenticated_client, test_db_session):
    """Test updating datasource to be default."""
    from app.models_application import GrafanaDatasource

    # Create existing default
    ds1 = GrafanaDatasource(
        id=uuid4(),
        name="old-default",
        datasource_type="loki",
        url="http://loki-1:3100",
        is_default=True
    )
    test_db_session.add(ds1)

    # Create non-default
    ds2 = GrafanaDatasource(
        id=uuid4(),
        name="new-default",
        datasource_type="loki",
        url="http://loki-2:3100",
        is_default=False
    )
    test_db_session.add(ds2)
    test_db_session.commit()

    # Update ds2 to be default
    response = await authenticated_client.put(
        f"/api/grafana-datasources/{ds2.id}",
        json={"is_default": True}
    )

    assert response.status_code == 200

    # Verify old default is no longer default
    test_db_session.refresh(ds1)
    assert ds1.is_default is False


@pytest.mark.asyncio
async def test_update_datasource_name_conflict(authenticated_client, test_db_session):
    """Test updating datasource name to existing name fails."""
    from app.models_application import GrafanaDatasource

    ds1 = GrafanaDatasource(
        id=uuid4(),
        name="existing-name",
        datasource_type="loki",
        url="http://loki-1:3100"
    )
    test_db_session.add(ds1)

    ds2 = GrafanaDatasource(
        id=uuid4(),
        name="other-name",
        datasource_type="loki",
        url="http://loki-2:3100"
    )
    test_db_session.add(ds2)
    test_db_session.commit()

    # Try to rename ds2 to ds1's name
    response = await authenticated_client.put(
        f"/api/grafana-datasources/{ds2.id}",
        json={"name": "existing-name"}
    )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_datasource_not_found(authenticated_client):
    """Test updating non-existent datasource."""
    non_existent_id = uuid4()

    response = await authenticated_client.put(
        f"/api/grafana-datasources/{non_existent_id}",
        json={"timeout": 60}
    )

    assert response.status_code == 404


# ============================================================================
# Test DELETE /api/grafana-datasources/{id} - Delete Datasource
# ============================================================================

@pytest.mark.asyncio
async def test_delete_datasource(authenticated_client, test_db_session):
    """Test deleting a datasource."""
    from app.models_application import GrafanaDatasource

    ds = GrafanaDatasource(
        id=uuid4(),
        name="to-delete",
        datasource_type="loki",
        url="http://loki:3100"
    )
    test_db_session.add(ds)
    test_db_session.commit()
    ds_id = ds.id

    # Delete datasource
    response = await authenticated_client.delete(
        f"/api/grafana-datasources/{ds_id}"
    )

    assert response.status_code == 204

    # Verify deletion
    response = await authenticated_client.get(
        f"/api/grafana-datasources/{ds_id}"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_datasource_not_found(authenticated_client):
    """Test deleting non-existent datasource."""
    non_existent_id = uuid4()

    response = await authenticated_client.delete(
        f"/api/grafana-datasources/{non_existent_id}"
    )

    assert response.status_code == 404


# ============================================================================
# Test GET /api/grafana-datasources/{id}/health-check - Health Check
# ============================================================================

@pytest.mark.asyncio
async def test_health_check_datasource(authenticated_client, test_db_session):
    """Test health check on a datasource."""
    from app.models_application import GrafanaDatasource
    from unittest.mock import patch, AsyncMock

    ds = GrafanaDatasource(
        id=uuid4(),
        name="test-loki",
        datasource_type="loki",
        url="http://loki:3100"
    )
    test_db_session.add(ds)
    test_db_session.commit()

    # Mock the health check function
    with patch("app.routers.grafana_datasources_api.test_datasource_connection", new_callable=AsyncMock) as mock_test:
        mock_test.return_value = (True, "Loki connection successful", 45.3)

        response = await authenticated_client.get(
            f"/api/grafana-datasources/{ds.id}/health-check"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["datasource_id"] == str(ds.id)
        assert data["datasource_name"] == "test-loki"
        assert data["datasource_type"] == "loki"
        assert data["is_healthy"] is True
        assert data["response_time_ms"] == 45.3
        assert "checked_at" in data


@pytest.mark.asyncio
async def test_health_check_datasource_not_found(authenticated_client):
    """Test health check on non-existent datasource."""
    non_existent_id = uuid4()

    response = await authenticated_client.get(
        f"/api/grafana-datasources/{non_existent_id}/health-check"
    )

    assert response.status_code == 404


# ============================================================================
# Test POST /api/grafana-datasources/test-connection - Test Connection
# ============================================================================

@pytest.mark.asyncio
async def test_test_connection_success(authenticated_client):
    """Test connection testing before creating datasource."""
    from unittest.mock import patch, AsyncMock

    test_request = {
        "datasource_type": "loki",
        "url": "http://loki:3100",
        "auth_type": "none",
        "timeout": 30
    }

    # Mock the connection test
    with patch("app.routers.grafana_datasources_api.test_datasource_connection", new_callable=AsyncMock) as mock_test:
        mock_test.return_value = (True, "Connection successful", 52.1)

        response = await authenticated_client.post(
            "/api/grafana-datasources/test-connection",
            json=test_request
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Connection successful"
        assert data["response_time_ms"] == 52.1


@pytest.mark.asyncio
async def test_test_connection_failure(authenticated_client):
    """Test connection testing with failed connection."""
    from unittest.mock import patch, AsyncMock

    test_request = {
        "datasource_type": "loki",
        "url": "http://invalid:3100",
        "auth_type": "none",
        "timeout": 5
    }

    # Mock the connection test failure
    with patch("app.routers.grafana_datasources_api.test_datasource_connection", new_callable=AsyncMock) as mock_test:
        mock_test.return_value = (False, "Connection failed: Connection refused", 1000.0)

        response = await authenticated_client.post(
            "/api/grafana-datasources/test-connection",
            json=test_request
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Connection failed" in data["message"]


# ============================================================================
# Test Authentication and Authorization
# ============================================================================

@pytest.mark.asyncio
async def test_create_datasource_unauthenticated(async_client):
    """Test creating datasource without authentication."""
    datasource_data = {
        "name": "test-loki",
        "datasource_type": "loki",
        "url": "http://loki:3100"
    }

    response = await async_client.post(
        "/api/grafana-datasources",
        json=datasource_data
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_datasources_unauthenticated(async_client):
    """Test listing datasources without authentication."""
    response = await async_client.get("/api/grafana-datasources")

    assert response.status_code == 401
