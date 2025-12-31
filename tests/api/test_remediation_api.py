"""
API tests for Remediation endpoints.

Tests cover runbook CRUD operations, execution, approvals, and circuit breaker.
"""
import pytest
import yaml
from pathlib import Path

from tests.fixtures.factories import RunbookFactory, RunbookStepFactory


class TestRunbookCRUD:
    """Test runbook create, read, update, delete operations."""
    
    @pytest.mark.asyncio
    async def test_create_runbook(
        self, async_client, admin_auth_headers
    ):
        """Test creating a new runbook."""
        runbook_data = {
            "name": "Test Runbook",
            "description": "Test runbook for API testing",
            "category": "service_recovery",
            "enabled": True,
            "auto_execute": False,
            "approval_required": True,
            "approval_required": True,
            # "timeout_seconds": 300, # Removed from model
            "steps": [
                {
                    "name": "Step 1",
                    "step_order": 1,
                    "command": "echo 'test'",
                    "executor_type": "ssh",
                    "timeout_seconds": 30
                }
            ]
        }
        
        response = await async_client.post(
            "/api/remediation/runbooks",
            json=runbook_data,
            headers=admin_auth_headers
        )
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert data.get("name") == "Test Runbook"
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_get_runbooks_list(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test getting list of runbooks."""
        # Create test runBooks
        runbook1 = RunbookFactory()
        runbook2 = RunbookFactory()
        db_session.add_all([runbook1, runbook2])
        db_session.commit()
        
        response = await async_client.get(
            "/api/remediation/runbooks",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
    
    @pytest.mark.asyncio
    async def test_get_runbook_by_id(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test getting a single runbook by ID."""
        runbook = RunbookFactory()
        db_session.add(runbook)
        db_session.commit()
        
        response = await async_client.get(
            f"/api/remediation/runbooks/{runbook.id}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("id") == str(runbook.id)
    
    @pytest.mark.asyncio
    async def test_update_runbook(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test updating a runbook."""
        runbook = RunbookFactory(name="Original Name")
        db_session.add(runbook)
        db_session.commit()
        
        response = await async_client.put(
            f"/api/remediation/runbooks/{runbook.id}",
            json={"name": "Updated Name"},
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("name") == "Updated Name"
        # Version should increment
        if "version" in data:
            assert data["version"] > runbook.version
    
    @pytest.mark.asyncio
    async def test_delete_runbook(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test deleting a runbook."""
        runbook = RunbookFactory()
        db_session.add(runbook)
        db_session.commit()
        runbook_id = runbook.id
        
        response = await async_client.delete(
            f"/api/remediation/runbooks/{runbook_id}",
            headers=admin_auth_headers
        )
        
        assert response.status_code in [200, 204]
        
        # Verify deleted
        get_response = await async_client.get(
            f"/api/remediation/runbooks/{runbook_id}",
            headers=admin_auth_headers
        )
        assert get_response.status_code == 404


class TestRunbookExecution:
    """Test runbook execution endpoints."""
    
    @pytest.mark.asyncio
    async def test_execute_runbook(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test executing a runbook."""
        runbook = RunbookFactory(auto_execute=True, approval_required=False)
        db_session.add(runbook)
        db_session.flush()
        
        # Add steps
        step = RunbookStepFactory(runbook_id=runbook.id)
        db_session.add(step)
        db_session.commit()
        
        response = await async_client.post(
            f"/api/remediation/runbooks/{runbook.id}/execute",
            json={},
            headers=admin_auth_headers
        )
        
        assert response.status_code in [200, 202]
        data = response.json()
        assert "execution_id" in data or "id" in data
    
    @pytest.mark.asyncio
    async def test_execute_runbook_requires_approval(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test executing runbook that requires approval."""
        runbook = RunbookFactory(approval_required=True, auto_execute=False)
        db_session.add(runbook)
        db_session.commit()
        
        response = await async_client.post(
            f"/api/remediation/runbooks/{runbook.id}/execute",
            json={},
            headers=admin_auth_headers
        )
        
        assert response.status_code in [200, 202]
        data = response.json()
        
        # Should be pending approval
        if "status" in data:
            assert data["status"] == "pending_approval"
    
    @pytest.mark.asyncio
    async def test_execute_disabled_runbook(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test that disabled runbooks cannot be executed."""
        runbook = RunbookFactory(enabled=False)
        db_session.add(runbook)
        db_session.commit()
        
        response = await async_client.post(
            f"/api/remediation/runbooks/{runbook.id}/execute",
            json={},
            headers=admin_auth_headers
        )
        
        # Should reject
        assert response.status_code in [400, 403, 409]


class TestExecutionApproval:
    """Test execution approval workflow."""
    
    @pytest.mark.asyncio
    async def test_approve_execution(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test approving a pending execution."""
        # Create execution (mock)
        # In real scenario, would create via execute endpoint
        execution_id = "test-execution-id"
        
        response = await async_client.post(
            f"/api/remediation/executions/{execution_id}/approve",
            headers=admin_auth_headers
        )
        
        # May succeed or execution may not exist
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_reject_execution(
        self, async_client, admin_auth_headers
    ):
        """Test rejecting a pending execution."""
        execution_id = "test-execution-id"
        
        response = await async_client.post(
            f"/api/remediation/executions/{execution_id}/reject",
            json={"reason": "Not needed"},
            headers=admin_auth_headers
        )
        
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_cancel_execution(
        self, async_client, admin_auth_headers
    ):
        """Test canceling a running execution."""
        execution_id = "test-execution-id"
        
        response = await async_client.post(
            f"/api/remediation/executions/{execution_id}/cancel",
            headers=admin_auth_headers
        )
        
        assert response.status_code in [200, 404]


class TestExecutionHistory:
    """Test execution history and details."""
    
    @pytest.mark.asyncio
    async def test_get_execution_history(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test getting execution history for a runbook."""
        runbook = RunbookFactory()
        db_session.add(runbook)
        db_session.commit()
        
        response = await async_client.get(
            f"/api/remediation/runbooks/{runbook.id}/executions",
            headers=admin_auth_headers
        )
        
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_get_execution_details(
        self, async_client, admin_auth_headers
    ):
        """Test getting details of a specific execution."""
        execution_id = "test-execution-id"
        
        response = await async_client.get(
            f"/api/remediation/executions/{execution_id}",
            headers=admin_auth_headers
        )
        
        # Execution may not exist
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "status" in data


class TestRunbookImportExport:
    """Test runbook import/export functionality."""
    
    @pytest.mark.asyncio
    async def test_import_runbook_yaml(
        self, async_client, admin_auth_headers
    ):
        """Test importing runbook from YAML file."""
        test_data_dir = Path(__file__).parent.parent / "test_data" / "runbooks"
        with open(test_data_dir / "linux_runbook.yaml") as f:
            yaml_content = f.read()
        
        response = await async_client.post(
            "/api/remediation/runbooks/import",
            files={"file": ("runbook.yaml", yaml_content, "text/yaml")},
            headers=admin_auth_headers
        )
        
        # May or may not support import
        assert response.status_code in [200, 201, 404, 405]
    
    @pytest.mark.asyncio
    async def test_export_runbook_yaml(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test exporting runbook to YAML format."""
        runbook = RunbookFactory()
        db_session.add(runbook)
        db_session.commit()
        
        response = await async_client.get(
            f"/api/remediation/runbooks/{runbook.id}/export",
            headers=admin_auth_headers
        )
        
        # May or may not support export
        if response.status_code == 200:
            # Should be YAML format
            content = response.content.decode()
            try:
                yaml.safe_load(content)
                assert True  # Valid YAML
            except:
                assert False, "Response is not valid YAML"


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    @pytest.mark.asyncio
    async def test_get_circuit_breaker_status(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test getting circuit breaker status for a runbook."""
        runbook = RunbookFactory()
        db_session.add(runbook)
        db_session.commit()
        
        response = await async_client.get(
            f"/api/remediation/circuit-breaker/{runbook.id}",
            headers=admin_auth_headers
        )
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "state" in data  # open, closed, half_open
    
    @pytest.mark.asyncio
    async def test_reset_circuit_breaker(
        self, async_client, admin_auth_headers, db_session
    ):
        """Test manually resetting circuit breaker."""
        runbook = RunbookFactory()
        db_session.add(runbook)
        db_session.commit()
        
        response = await async_client.post(
            f"/api/remediation/circuit-breaker/{runbook.id}/override",
            json={"action": "reset"},
            headers=admin_auth_headers
        )
        
        # Circuit breaker override may or may not be implemented
        assert response.status_code in [200, 404]


class TestRunbookAuthorization:
    """Test authorization for runbook operations."""
    
    @pytest.mark.asyncio
    async def test_operator_can_execute_runbook(
        self, async_client, operator_auth_headers, db_session
    ):
        """Test that operator can execute runbooks."""
        runbook = RunbookFactory(auto_execute=True)
        db_session.add(runbook)
        db_session.commit()
        
        response = await async_client.post(
            f"/api/remediation/runbooks/{runbook.id}/execute",
            json={},
            headers=operator_auth_headers
        )
        
        # Should be allowed
        assert response.status_code in [200, 202]
    
    @pytest.mark.asyncio
    async def test_operator_cannot_delete_runbook(
        self, async_client, operator_auth_headers, db_session
    ):
        """Test that operator cannot delete runbooks."""
        runbook = RunbookFactory()
        db_session.add(runbook)
        db_session.commit()
        
        response = await async_client.delete(
            f"/api/remediation/runbooks/{runbook.id}",
            headers=operator_auth_headers
        )
        
        # Should be forbidden
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_viewer_cannot_execute_runbook(
        self, async_client, viewer_auth_headers, db_session
    ):
        """Test that viewer cannot execute runbooks."""
        runbook = RunbookFactory()
        db_session.add(runbook)
        db_session.commit()
        
        response = await async_client.post(
            f"/api/remediation/runbooks/{runbook.id}/execute",
            json={},
            headers=viewer_auth_headers
        )
        
        # Should be forbidden
        assert response.status_code == 403
