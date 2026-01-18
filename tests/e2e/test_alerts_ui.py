
import pytest
from playwright.sync_api import Page, expect
import uuid
from datetime import datetime
import time

def create_test_alert(page: Page, alert_name: str, severity: str = "critical"):
    """Helper to create an alert via webhook"""
    webhook_url = "/webhook/alerts"
    payload = {
        "version": "4",
        "groupKey": "{}:{alertname=\"" + alert_name + "\"}",
        "truncatedAlerts": 0,
        "status": "firing",
        "receiver": "webhook",
        "groupLabels": {"alertname": alert_name},
        "commonLabels": {"alertname": alert_name, "severity": severity},
        "commonAnnotations": {},
        "externalURL": "http://localhost:9093",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": alert_name,
                    "severity": severity,
                    "instance": "test-instance",
                    "job": "e2e-test"
                },
                "annotations": {
                    "summary": f"Test summary for {alert_name}",
                    "description": "Created by E2E test automation"
                },
                "startsAt": datetime.utcnow().isoformat() + "Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://localhost:9090",
                "fingerprint": str(uuid.uuid4())
            }
        ]
    }
    
    response = page.request.post(webhook_url, data=payload)
    expect(response).to_be_ok()
    return response

def test_alerts_list_and_filter(authenticated_page: Page):
    """
    TC-AL-01: List & Filter
    """
    # Create unique alert
    unique_id = str(uuid.uuid4())[:8]
    alert_name = f"E2E_Alert_{unique_id}"
    create_test_alert(authenticated_page, alert_name, "critical")
    
    # Go to alerts page
    authenticated_page.goto("/alerts")
    
    # Verify page title
    expect(authenticated_page).to_have_title("Alerts - AIOps Platform")
    
    # Verify alert is visible
    # We might need to reload or wait for polling if list doesn't auto-refresh instant
    # The alerts page seems to load data on mount.
    
    row = authenticated_page.locator(f"tr:has-text('{alert_name}')")
    expect(row).to_be_visible(timeout=10000)
    
    # Test Filter
    # Filter by 'Warning' -> Should NOT see our critical alert
    authenticated_page.select_option("#filterSeverity", "warning")
    # Wait for list update (check api call or wait for spinner)
    authenticated_page.wait_for_timeout(1000) # simple wait for debounce
    expect(row).not_to_be_visible()
    
    # Filter by 'Critical' -> Should see it
    authenticated_page.select_option("#filterSeverity", "critical")
    authenticated_page.wait_for_timeout(1000)
    expect(row).to_be_visible()

def test_alert_details_view(authenticated_page: Page):
    """
    TC-AL-02: Alert Details
    """
    authenticated_page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))
    authenticated_page.on("pageerror", lambda exc: print(f"BROWSER ERROR: {exc}"))

    unique_id = str(uuid.uuid4())[:8]
    alert_name = f"E2E_Detail_{unique_id}"
    create_test_alert(authenticated_page, alert_name, "info")
    
    authenticated_page.goto("/alerts")
    row = authenticated_page.locator(f"tr:has-text('{alert_name}')")
    expect(row).to_be_visible()
    
    # Click details (the link with external-link icon)
    # The link selector in alerts.html is: <a href="/alerts/${alert.id}" ...>
    # We can find it inside the row
    details_link = row.locator("a[title='Details']")
    details_link.click()
    
    # Verify URL pattern
    expect(authenticated_page).to_have_url(re.compile(r".*/alerts/[a-f0-9-]+$"))
    
    # Verify Header
    expect(authenticated_page.locator("#header_alert_name")).to_contain_text(alert_name)
    
    # Verify tabs exist
    expect(authenticated_page.locator("#btn-tab-live")).to_be_visible()
    expect(authenticated_page.locator("#btn-tab-analysis")).to_be_visible()

import re
