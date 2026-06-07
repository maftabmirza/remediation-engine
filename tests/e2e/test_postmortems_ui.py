import json

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


POSTMORTEM_LIST = {
    "items": [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "title": "Database failover review",
            "status": "draft",
            "severity": "critical",
            "incident_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "impact_summary": "Primary database failover introduced a 14 minute write outage.",
            "generated_by": "ai",
            "created_at": "2026-03-06T10:15:00Z",
            "updated_at": "2026-03-06T10:35:00Z",
            "incident_start": "2026-03-06T09:58:00Z",
            "incident_end": "2026-03-06T10:12:00Z",
            "metrics": {"mttr_minutes": 14, "mtta_minutes": 3},
            "timeline": [{"timestamp": "2026-03-06T10:00:00Z", "event": "Database saturation", "source": "alert"}],
            "action_items": [{"description": "Tune failover timeout", "status": "open"}],
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "title": "Queue latency retrospective",
            "status": "published",
            "severity": "warning",
            "alert_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "impact_summary": "Message queue latency increased after a batch deployment.",
            "generated_by": "manual",
            "created_at": "2026-03-05T13:05:00Z",
            "updated_at": "2026-03-05T14:05:00Z",
            "incident_start": "2026-03-05T12:15:00Z",
            "incident_end": "2026-03-05T12:39:00Z",
            "metrics": {"mttr_minutes": 24},
            "timeline": [],
            "action_items": [],
        },
    ],
    "total": 2,
    "page": 1,
    "page_size": 50,
}

INCIDENT_LIST = {
    "items": [
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "title": "Ingress saturation on prod-eu",
            "severity": "critical",
            "started_at": "2026-03-06T08:00:00Z",
            "resolved_at": "2026-03-06T08:18:00Z",
            "affected_services": ["edge-api", "auth-service"],
        }
    ],
    "total": 1,
    "page": 1,
    "page_size": 50,
}

INCIDENT_EVIDENCE = {
    "incident": {
        "id": "33333333-3333-3333-3333-333333333333",
        "title": "Ingress saturation on prod-eu",
        "severity": "critical",
        "started_at": "2026-03-06T08:00:00Z",
        "resolved_at": "2026-03-06T08:18:00Z",
    },
    "alert_count": 4,
    "timeline": [
        {"timestamp": "2026-03-06T08:01:00Z", "event": "Ingress CPU alert triggered", "source": "alert"},
        {"timestamp": "2026-03-06T08:07:00Z", "event": "Runbook execution started", "source": "runbook"},
    ],
    "runbook_executions": [
        {
            "id": "44444444-4444-4444-4444-444444444444",
            "runbook_id": "55555555-5555-5555-5555-555555555555",
            "status": "completed",
            "started_at": "2026-03-06T08:07:00Z",
            "completed_at": "2026-03-06T08:11:00Z",
            "duration_minutes": 4,
        }
    ],
    "change_events": [
        {
            "timestamp": "2026-03-06T07:55:00Z",
            "change_type": "deployment",
            "service_name": "edge-api",
            "description": "Ingress configuration rollout",
        }
    ],
    "affected_services": ["edge-api", "auth-service"],
    "mttr_minutes": 18,
}

ALERT_LIST = {
    "alerts": [
        {
            "id": "66666666-6666-6666-6666-666666666666",
            "alert_name": "ApacheDown",
            "status": "resolved",
        },
        {
            "id": "77777777-7777-7777-7777-777777777777",
            "alert_name": "ApacheExporterDown74_208_225_85",
            "status": "resolved",
        },
    ],
    "total": 2,
    "page": 1,
    "page_size": 100,
    "total_pages": 1,
}


def _mock_postmortem_routes(page: Page) -> None:
    def handler(route):
        url = route.request.url
        method = route.request.method

        if "/api/alerts" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(ALERT_LIST))
            return

        if "/api/postmortems/incidents/33333333-3333-3333-3333-333333333333/evidence" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(INCIDENT_EVIDENCE))
            return

        if "/api/postmortems/incidents" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(INCIDENT_LIST))
            return

        if "/api/postmortems/" in url and "page_size=100" in url and method == "GET":
            route.fulfill(status=200, content_type="application/json", body=json.dumps(POSTMORTEM_LIST))
            return

        route.continue_()

    page.route("**/api/**", handler)


def test_postmortems_page_renders_themed_summary_and_cards(authenticated_page: Page):
    _mock_postmortem_routes(authenticated_page)

    authenticated_page.goto("/postmortems")

    expect(authenticated_page).to_have_title("Post-Mortems - AIOps Platform")
    expect(authenticated_page.locator("h1.page-heading", has_text="Post-Incident Postmortems")).to_be_visible()
    expect(authenticated_page.locator("#summaryMeta .summary-pill")).to_have_count(5)
    # Table rows (2 data rows rendered in tbody)
    expect(authenticated_page.locator("#pmTableBody tr")).to_have_count(2)
    expect(authenticated_page.locator("#resultsMeta")).to_contain_text("2 reports")
    expect(authenticated_page.locator("#pmTableBody")).to_contain_text("Database failover review")


def test_postmortems_filters_by_status_and_search(authenticated_page: Page):
    _mock_postmortem_routes(authenticated_page)

    authenticated_page.goto("/postmortems")

    authenticated_page.locator("#statusFilters button", has_text="Published").click()
    expect(authenticated_page.locator("#pmTableBody")).to_contain_text("Queue latency retrospective")
    expect(authenticated_page.locator("#pmTableBody")).not_to_contain_text("Database failover review")

    authenticated_page.locator("#searchInput").fill("nonexistent report")
    expect(authenticated_page.locator(".empty-state-title")).to_have_text("No postmortems match the current view.")


def test_incident_picker_modal_shows_evidence_preview(authenticated_page: Page):
    _mock_postmortem_routes(authenticated_page)

    authenticated_page.goto("/postmortems")
    authenticated_page.locator("#btn-generate-incident").click()

    expect(authenticated_page.locator("#incidentPickerModal")).to_be_visible()
    expect(authenticated_page.locator("#incidentList")).to_contain_text("Ingress saturation on prod-eu")

    authenticated_page.locator("#incidentList .incident-item").first.click()

    expect(authenticated_page.locator("#evidencePreview")).to_be_visible()
    expect(authenticated_page.locator("#evidenceContent")).to_contain_text("Evidence Summary")
    expect(authenticated_page.locator("#evidenceContent")).to_contain_text("Runbook Executions")
    expect(authenticated_page.locator("#generateIncidentBtn")).to_be_enabled()


def test_legacy_alert_modal_loads_alert_options(authenticated_page: Page):
    _mock_postmortem_routes(authenticated_page)

    authenticated_page.goto("/postmortems")
    authenticated_page.locator("#btn-generate-alert").click()

    expect(authenticated_page.locator("#alertGenerateModal")).to_be_visible()
    expect(authenticated_page.locator("#genAlertId option")).to_have_count(3)
    expect(authenticated_page.locator("#genAlertId")).to_contain_text("ApacheDown")
