"""Integration tests for postmortem API authorization and validation."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.models_postmortem import PostmortemReport


@pytest.mark.integration
class TestPostmortemApiAuth:
    """Postmortem mutating endpoints require elevated roles."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "path", "payload"),
        [
            ("post", "/api/postmortems/generate-by-incident", {"incident_id": None}),
            ("post", "/api/postmortems/generate", {"alert_id": None}),
            ("put", "/api/postmortems/{postmortem_id}", {"title": "Updated"}),
            ("post", "/api/postmortems/{postmortem_id}/regenerate", None),
            (
                "post",
                "/api/postmortems/{postmortem_id}/out-of-band",
                {
                    "source": "slack",
                    "content": "Customer escalation",
                    "timestamp": "2026-03-07T10:00:00Z",
                },
            ),
        ],
    )
    async def test_operator_cannot_mutate_postmortems(
        self,
        async_client,
        operator_auth_headers,
        method,
        path,
        payload,
    ):
        """Operator role is forbidden from mutating postmortems."""
        resource_id = uuid4()
        formatted_path = path.format(postmortem_id=resource_id)

        if payload and "incident_id" in payload:
            payload = {**payload, "incident_id": str(uuid4())}
        if payload and "alert_id" in payload:
            payload = {**payload, "alert_id": str(uuid4())}

        response = await getattr(async_client, method)(
            formatted_path,
            json=payload,
            headers=operator_auth_headers,
        )

        assert response.status_code == 403, response.text

    @pytest.mark.asyncio
    async def test_admin_can_generate_by_incident(self, async_client, admin_auth_headers):
        """Admin can access incident-first generation when the service succeeds."""
        incident_id = uuid4()
        created_by = uuid4()
        report = PostmortemReport(
            id=uuid4(),
            title="Post-Incident Review: High CPU",
            incident_id=incident_id,
            status="draft",
            generated_by="ai",
            severity="critical",
            incident_start=datetime(2026, 3, 7, 9, 0, tzinfo=timezone.utc),
            incident_end=datetime(2026, 3, 7, 10, 0, tzinfo=timezone.utc),
            timeline=[],
            metrics={"mttr_minutes": 60.0},
            impact_summary="Impact summary",
            root_cause="Root cause",
            contributing_factors=[],
            remediation_actions=[],
            action_items=[],
            lessons_learned="Lessons learned",
            out_of_band_context=[],
            created_by=created_by,
        )

        with patch(
            "app.routers.postmortem_api.PostmortemService.generate_by_incident",
            new=AsyncMock(return_value=report),
        ):
            response = await async_client.post(
                "/api/postmortems/generate-by-incident",
                json={"incident_id": str(incident_id)},
                headers=admin_auth_headers,
            )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["incident_id"] == str(incident_id)
        assert data["status"] == "draft"

    @pytest.mark.asyncio
    async def test_update_rejects_status_field(self, async_client, admin_auth_headers):
        """Generic update endpoint rejects status changes in the request body."""
        response = await async_client.put(
            f"/api/postmortems/{uuid4()}",
            json={"status": "published"},
            headers=admin_auth_headers,
        )

        assert response.status_code == 422, response.text