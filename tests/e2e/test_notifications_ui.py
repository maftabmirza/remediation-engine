"""
E2E tests for the Notifications section inside the Settings page.

Notifications was moved from a standalone ``/notifications`` page into
the Settings page as ``/settings#section-notifications``.

Uses the Playwright ``authenticated_page`` fixture which navigates as an
authenticated admin user.
"""
import pytest
from playwright.sync_api import Page, expect

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOTIFICATIONS_URL = "/settings#section-notifications"


def _go_to_notifications(page: Page) -> None:
    """Navigate to the Notifications section inside Settings."""
    page.goto(NOTIFICATIONS_URL)
    page.wait_for_timeout(800)  # allow section JS to initialise


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_notifications_section_loads(authenticated_page: Page):
    """TC-NT-01: Settings page loads and Notifications section is visible."""
    _go_to_notifications(authenticated_page)
    expect(authenticated_page).to_have_title("Settings - AIOps Platform")
    expect(authenticated_page.locator("#section-notifications")).to_be_visible()


def test_channels_tab_visible(authenticated_page: Page):
    """TC-NT-02: Channels tab is the default active tab."""
    _go_to_notifications(authenticated_page)

    # Default tab content should be visible
    expect(authenticated_page.locator("#notif-tab-channels")).to_be_visible()


def test_policies_tab_navigation(authenticated_page: Page):
    """TC-NT-03: Clicking Policies tab shows policies panel."""
    _go_to_notifications(authenticated_page)

    # Click Policies tab button
    authenticated_page.locator(".notif-tab-btn:has-text('Policies')").click()
    authenticated_page.wait_for_timeout(300)

    expect(authenticated_page.locator("#notif-tab-policies")).to_be_visible()


def test_log_tab_navigation(authenticated_page: Page):
    """TC-NT-04: Clicking Log tab shows delivery log panel."""
    _go_to_notifications(authenticated_page)

    # Click Delivery Log tab button
    authenticated_page.locator(".notif-tab-btn:has-text('Delivery Log')").click()
    authenticated_page.wait_for_timeout(300)

    expect(authenticated_page.locator("#notif-tab-log")).to_be_visible()


def test_add_channel_button_visible(authenticated_page: Page):
    """TC-NT-05: Add Channel button is present on channels tab."""
    _go_to_notifications(authenticated_page)

    expect(authenticated_page.locator("#btn-add-channel")).to_be_visible()


def test_add_channel_modal_opens(authenticated_page: Page):
    """TC-NT-06: Clicking Add Channel opens the channel modal."""
    _go_to_notifications(authenticated_page)

    authenticated_page.locator("#btn-add-channel").click()
    authenticated_page.wait_for_timeout(300)

    # Modal should be visible
    expect(authenticated_page.locator("#channel-modal")).to_be_visible()


def test_channel_modal_type_selector(authenticated_page: Page):
    """TC-NT-07: Channel modal shows all 4 channel type options."""
    _go_to_notifications(authenticated_page)

    authenticated_page.locator("#btn-add-channel").click()
    authenticated_page.wait_for_timeout(300)

    # Check for channel type select element
    type_select = authenticated_page.locator("#channel-type-select")
    expect(type_select).to_be_visible()

    options = type_select.locator("option").all()
    labels = [opt.inner_text() for opt in options]
    assert any("Slack" in lbl for lbl in labels)
    assert any("Teams" in lbl or "Microsoft" in lbl for lbl in labels)
    assert any("Email" in lbl for lbl in labels)
    assert any("Webhook" in lbl for lbl in labels)


def test_channel_modal_closes_on_cancel(authenticated_page: Page):
    """TC-NT-08: Cancel button closes the channel modal."""
    _go_to_notifications(authenticated_page)

    authenticated_page.locator("#btn-add-channel").click()
    authenticated_page.wait_for_timeout(300)

    # Close via cancel / close button
    authenticated_page.locator(
        "#channel-modal .modal-close, #channel-modal [data-dismiss]"
    ).first.click()
    authenticated_page.wait_for_timeout(300)

    expect(authenticated_page.locator("#channel-modal")).not_to_be_visible()


def test_log_stats_section_visible(authenticated_page: Page):
    """TC-NT-09: Log tab shows stats section."""
    _go_to_notifications(authenticated_page)

    authenticated_page.locator(".notif-tab-btn:has-text('Delivery Log')").click()
    authenticated_page.wait_for_timeout(500)

    # Stats cards should be present
    expect(authenticated_page.locator("#notif-tab-log")).to_be_visible()
    # Stats region — we just verify the tab content is rendered
    tab_html = authenticated_page.locator("#notif-tab-log").inner_html()
    assert len(tab_html) > 50  # sanity-check: content was rendered


def test_test_channel_sends_post(authenticated_page: Page):
    """TC-NT-10: Test Channel button fires a POST request, not GET.

    Regression guard for the apiCall signature mismatch bug where the
    settings.html local ``apiCall(url, options={})`` shadowed the
    base.html ``apiCall(url, method, data)`` causing all non-GET
    notification requests to fall back to GET.
    """
    _go_to_notifications(authenticated_page)

    # Only run if a Test button exists (i.e. at least one channel is configured)
    test_btn = authenticated_page.locator("button:has-text('Test')").first
    if not test_btn.is_visible():
        pytest.skip("No channels configured — cannot test the Test button")

    # Intercept the /test request to verify the method
    request_methods: list[str] = []

    def capture_request(route):
        request_methods.append(route.request.method)
        # Fulfill with a mock response so we don't hit the real server
        route.fulfill(
            status=200,
            content_type="application/json",
            body='{"success": true, "message": "mock"}',
        )

    authenticated_page.route("**/api/notifications/channels/*/test", capture_request)

    test_btn.click()
    authenticated_page.wait_for_timeout(1000)

    assert len(request_methods) >= 1, "Expected at least one request to /test endpoint"
    assert request_methods[0] == "POST", (
        f"Test channel button should send POST but sent {request_methods[0]}"
    )
