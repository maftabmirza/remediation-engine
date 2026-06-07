import json

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


ALERTS_PAYLOAD = {
    "alerts": [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "alert_name": "ApacheDown",
            "annotations": {
                "summary": "Apache process stopped",
                "description": "Apache service on 74.208.225.85 is not responding",
            },
            "instance": "74.208.225.85:9117",
            "severity": "critical",
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "alert_name": "NodeExporterDown",
            "annotations": {
                "summary": "Exporter unavailable"
            },
            "instance": "74.208.225.85:9100",
            "severity": "warning",
        },
    ]
}

INCIDENTS_PAYLOAD = {
    "items": [
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "human_id": "INC-20260308-001",
            "title": "Apache outage on production edge",
            "description": "Customer-facing traffic failed after Apache restart",
            "severity": "critical",
        }
    ]
}

PROVIDERS_PAYLOAD = [
    {
        "id": "provider-1",
        "provider_name": "OpenAI",
        "name": "GPT",
        "is_default": True,
    }
]

SESSION_PAYLOAD = {
    "id": "44444444-4444-4444-4444-444444444444",
    "title": "Troubleshooting Session",
}


def _mock_troubleshoot_routes(page: Page) -> None:
    def handler(route):
        url = route.request.url
        method = route.request.method

        if "/api/troubleshoot/providers" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(PROVIDERS_PAYLOAD))
            return

        if "/api/troubleshoot/sessions/standalone" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(SESSION_PAYLOAD))
            return

        if "/api/troubleshoot/sessions/" in url and "/messages" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"messages": []}))
            return

        if "/api/troubleshoot/sessions" in url and method == "POST":
            route.fulfill(status=200, content_type="application/json", body=json.dumps(SESSION_PAYLOAD))
            return

        if "/api/troubleshoot/sessions" in url and method == "GET":
            route.fulfill(status=200, content_type="application/json", body=json.dumps([SESSION_PAYLOAD]))
            return

        if "/api/alerts?status=firing&page_size=50" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(ALERTS_PAYLOAD))
            return

        if "/api/incidents?status=open&page_size=50" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(INCIDENTS_PAYLOAD))
            return

        route.continue_()

    page.route("**/api/**", handler)


def test_context_selector_search_matches_title_description_and_ids(authenticated_page: Page):
    _mock_troubleshoot_routes(authenticated_page)

    authenticated_page.goto("/troubleshoot")

    authenticated_page.locator("#contextDropdownBtn").click()

    expect(authenticated_page.locator("#contextListContainer")).to_contain_text("ApacheDown")
    expect(authenticated_page.locator("#contextListContainer")).to_contain_text("Apache outage on production edge")

    search_input = authenticated_page.locator("#contextSearchInput")

    search_input.fill("customer-facing traffic")
    expect(authenticated_page.locator("#contextListContainer")).to_contain_text("Apache outage on production edge")
    expect(authenticated_page.locator("#contextListContainer")).not_to_contain_text("NodeExporterDown")

    search_input.fill("74.208.225.85")
    expect(authenticated_page.locator("#contextListContainer")).to_contain_text("ApacheDown")

    search_input.fill("33333333")
    expect(authenticated_page.locator("#contextListContainer")).to_contain_text("Apache outage on production edge")