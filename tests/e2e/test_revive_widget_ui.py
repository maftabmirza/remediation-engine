"""
E2E tests for RE-VIVE AI Assistant Widget

Tests cover the RE-VIVE widget functionality on Prometheus view and Grafana Advanced pages,
including button visibility, toggle functionality, DOM injection, container resizing,
message input, and keyboard shortcuts.
"""
import re
from playwright.sync_api import Page, expect


def test_revive_button_exists_prometheus(authenticated_page: Page):
    """
    TC-REVIVE-01: Verify RE-VIVE toggle button exists on Prometheus view
    """
    authenticated_page.goto("/prometheus-view")
    
    # Wait for page to load
    authenticated_page.wait_for_selector("#prometheus-iframe", state="visible", timeout=10000)
    
    # Check that RE-VIVE button exists in header
    revive_button = authenticated_page.locator("#ai-helper-toggle")
    expect(revive_button).to_be_visible()
    expect(revive_button).to_have_text(re.compile(r"RE-VIVE", re.IGNORECASE))


def test_revive_button_exists_grafana(authenticated_page: Page):
    """
    TC-REVIVE-02: Verify RE-VIVE toggle button exists on Grafana Advanced view
    """
    authenticated_page.goto("/grafana-advanced")
    
    # Wait for page to load
    authenticated_page.wait_for_selector("#grafana-iframe", state="visible", timeout=10000)
    
    # Check that RE-VIVE button exists in header
    revive_button = authenticated_page.locator("#ai-helper-toggle")
    expect(revive_button).to_be_visible()
    expect(revive_button).to_have_text(re.compile(r"RE-VIVE", re.IGNORECASE))


def test_widget_opens_on_button_click_prometheus(authenticated_page: Page):
    """
    TC-REVIVE-03: Verify widget opens when RE-VIVE button is clicked on Prometheus view
    """
    authenticated_page.goto("/prometheus-view")
    authenticated_page.wait_for_selector("#prometheus-iframe", state="visible", timeout=10000)
    
    # Verify widget is initially hidden
    widget = authenticated_page.locator("#agent-widget")
    agent_window = authenticated_page.locator("#agent-window")
    
    # Widget should exist but window should not be visible
    expect(widget).to_be_attached()
    expect(agent_window).not_to_have_class(re.compile(r"visible"))
    
    # Click RE-VIVE button
    authenticated_page.click("#ai-helper-toggle")
    
    # Wait for animation and verify widget is now visible
    authenticated_page.wait_for_timeout(500)  # Allow for CSS transition
    expect(agent_window).to_have_class(re.compile(r"visible"))


def test_widget_opens_on_button_click_grafana(authenticated_page: Page):
    """
    TC-REVIVE-04: Verify widget opens when RE-VIVE button is clicked on Grafana Advanced
    """
    authenticated_page.goto("/grafana-advanced")
    authenticated_page.wait_for_selector("#grafana-iframe", state="visible", timeout=10000)
    
    # Verify widget is initially hidden
    widget = authenticated_page.locator("#agent-widget")
    agent_window = authenticated_page.locator("#agent-window")
    
    expect(widget).to_be_attached()
    expect(agent_window).not_to_have_class(re.compile(r"visible"))
    
    # Click RE-VIVE button
    authenticated_page.click("#ai-helper-toggle")
    
    # Verify widget is now visible
    authenticated_page.wait_for_timeout(500)
    expect(agent_window).to_have_class(re.compile(r"visible"))


def test_widget_closes_on_close_button_prometheus(authenticated_page: Page):
    """
    TC-REVIVE-05: Verify widget closes when close button is clicked on Prometheus view
    """
    authenticated_page.goto("/prometheus-view")
    authenticated_page.wait_for_selector("#prometheus-iframe", state="visible", timeout=10000)
    
    # Open widget
    authenticated_page.click("#ai-helper-toggle")
    authenticated_page.wait_for_timeout(500)
    
    agent_window = authenticated_page.locator("#agent-window")
    expect(agent_window).to_have_class(re.compile(r"visible"))
    
    # Click close button
    close_button = authenticated_page.locator("#agent-close")
    expect(close_button).to_be_visible()
    close_button.click()
    
    # Verify widget is now hidden
    authenticated_page.wait_for_timeout(500)
    expect(agent_window).not_to_have_class(re.compile(r"visible"))


def test_widget_dom_structure_prometheus(authenticated_page: Page):
    """
    TC-REVIVE-06: Verify widget DOM structure is correctly injected on Prometheus view
    """
    authenticated_page.goto("/prometheus-view")
    authenticated_page.wait_for_selector("#prometheus-iframe", state="visible", timeout=10000)
    
    # Verify widget container exists
    expect(authenticated_page.locator("#agent-widget")).to_be_attached()
    
    # Verify key elements exist
    expect(authenticated_page.locator("#agent-window")).to_be_attached()
    expect(authenticated_page.locator("#agent-messages")).to_be_attached()
    expect(authenticated_page.locator("#agent-input")).to_be_attached()
    expect(authenticated_page.locator("#agent-send")).to_be_attached()
    expect(authenticated_page.locator("#agent-close")).to_be_attached()
    expect(authenticated_page.locator("#agent-resize-handle")).to_be_attached()


def test_container_resizes_on_widget_open_prometheus(authenticated_page: Page):
    """
    TC-REVIVE-07: Verify Prometheus container resizes when widget opens
    """
    authenticated_page.goto("/prometheus-view")
    authenticated_page.wait_for_selector("#prometheus-iframe", state="visible", timeout=10000)
    
    container = authenticated_page.locator(".prometheus-container")
    
    # Get initial width (should span full right side)
    initial_right = container.evaluate("el => window.getComputedStyle(el).right")
    
    # Open widget
    authenticated_page.click("#ai-helper-toggle")
    authenticated_page.wait_for_timeout(500)
    
    # Container should now have reduced width to make room for widget
    # The container's 'right' property should increase to make space for the 380px widget
    new_right = container.evaluate("el => window.getComputedStyle(el).right")
    
    # Verify that the right offset has increased (container shrunk from right)
    assert new_right != initial_right, "Container should resize when widget opens"


def test_container_resizes_on_widget_open_grafana(authenticated_page: Page):
    """
    TC-REVIVE-08: Verify Grafana container resizes when widget opens
    """
    authenticated_page.goto("/grafana-advanced")
    authenticated_page.wait_for_selector("#grafana-iframe", state="visible", timeout=10000)
    
    container = authenticated_page.locator(".grafana-container")
    
    # Get initial right offset
    initial_right = container.evaluate("el => window.getComputedStyle(el).right")
    
    # Open widget
    authenticated_page.click("#ai-helper-toggle")
    authenticated_page.wait_for_timeout(500)
    
    # Verify container resized
    new_right = container.evaluate("el => window.getComputedStyle(el).right")
    assert new_right != initial_right, "Container should resize when widget opens"


def test_widget_input_field_functional_prometheus(authenticated_page: Page):
    """
    TC-REVIVE-09: Verify message input field is functional on Prometheus view
    """
    authenticated_page.goto("/prometheus-view")
    authenticated_page.wait_for_selector("#prometheus-iframe", state="visible", timeout=10000)
    
    # Open widget
    authenticated_page.click("#ai-helper-toggle")
    authenticated_page.wait_for_timeout(500)
    
    # Verify input field exists and is editable
    input_field = authenticated_page.locator("#agent-input")
    expect(input_field).to_be_visible()
    expect(input_field).to_be_editable()
    
    # Type test message
    test_message = "Test query for RE-VIVE"
    input_field.fill(test_message)
    
    # Verify input contains the typed message
    expect(input_field).to_have_value(test_message)


def test_widget_send_button_visible_prometheus(authenticated_page: Page):
    """
    TC-REVIVE-10: Verify send button is visible and clickable on Prometheus view
    """
    authenticated_page.goto("/prometheus-view")
    authenticated_page.wait_for_selector("#prometheus-iframe", state="visible", timeout=10000)
    
    # Open widget
    authenticated_page.click("#ai-helper-toggle")
    authenticated_page.wait_for_timeout(500)
    
    # Verify send button exists and is visible
    send_button = authenticated_page.locator("#agent-send")
    expect(send_button).to_be_visible()
    expect(send_button).to_be_enabled()


def test_widget_keyboard_shortcut_prometheus(authenticated_page: Page):
    """
    TC-REVIVE-11: Verify Ctrl+Shift+A keyboard shortcut toggles widget on Prometheus view
    """
    authenticated_page.goto("/prometheus-view")
    authenticated_page.wait_for_selector("#prometheus-iframe", state="visible", timeout=10000)
    
    agent_window = authenticated_page.locator("#agent-window")
    
    # Verify widget is initially hidden
    expect(agent_window).not_to_have_class(re.compile(r"visible"))
    
    # Press Ctrl+Shift+A to open
    authenticated_page.keyboard.press("Control+Shift+A")
    authenticated_page.wait_for_timeout(500)
    
    # Verify widget opened
    expect(agent_window).to_have_class(re.compile(r"visible"))
    
    # Press Ctrl+Shift+A again to close
    authenticated_page.keyboard.press("Control+Shift+A")
    authenticated_page.wait_for_timeout(500)
    
    # Verify widget closed
    expect(agent_window).not_to_have_class(re.compile(r"visible"))


def test_widget_keyboard_shortcut_grafana(authenticated_page: Page):
    """
    TC-REVIVE-12: Verify Ctrl+Shift+A keyboard shortcut toggles widget on Grafana Advanced
    """
    authenticated_page.goto("/grafana-advanced")
    authenticated_page.wait_for_selector("#grafana-iframe", state="visible", timeout=10000)
    
    agent_window = authenticated_page.locator("#agent-window")
    
    # Verify widget is initially hidden
    expect(agent_window).not_to_have_class(re.compile(r"visible"))
    
    # Press Ctrl+Shift+A to open
    authenticated_page.keyboard.press("Control+Shift+A")
    authenticated_page.wait_for_timeout(500)
    
    # Verify widget opened
    expect(agent_window).to_have_class(re.compile(r"visible"))
    
    # Press Ctrl+Shift+A again to close
    authenticated_page.keyboard.press("Control+Shift+A")
    authenticated_page.wait_for_timeout(500)
    
    # Verify widget closed
    expect(agent_window).not_to_have_class(re.compile(r"visible"))


def test_widget_maintains_state_across_toggle_prometheus(authenticated_page: Page):
    """
    TC-REVIVE-13: Verify widget maintains conversation state across open/close cycles
    """
    authenticated_page.goto("/prometheus-view")
    authenticated_page.wait_for_selector("#prometheus-iframe", state="visible", timeout=10000)
    
    # Open widget
    authenticated_page.click("#ai-helper-toggle")
    authenticated_page.wait_for_timeout(500)
    
    # Type a message (don't send)
    test_message = "Persistent test message"
    input_field = authenticated_page.locator("#agent-input")
    input_field.fill(test_message)
    
    # Close widget
    authenticated_page.click("#agent-close")
    authenticated_page.wait_for_timeout(500)
    
    # Reopen widget
    authenticated_page.click("#ai-helper-toggle")
    authenticated_page.wait_for_timeout(500)
    
    # Verify messages container still exists (conversation is preserved)
    messages_container = authenticated_page.locator("#agent-messages")
    expect(messages_container).to_be_visible()
    
    # Verify initial greeting message still exists
    expect(messages_container.locator(".agent-message.ai").first).to_be_visible()


def test_no_duplicate_widgets_prometheus(authenticated_page: Page):
    """
    TC-REVIVE-14: Verify no duplicate widgets are created on Prometheus view
    """
    authenticated_page.goto("/prometheus-view")
    authenticated_page.wait_for_selector("#prometheus-iframe", state="visible", timeout=10000)
    
    # Count widget instances
    widget_count = authenticated_page.locator("#agent-widget").count()
    
    # Should only have exactly one widget
    assert widget_count == 1, f"Expected 1 widget, found {widget_count}"
    
    # Toggle widget multiple times
    for _ in range(3):
        authenticated_page.click("#ai-helper-toggle")
        authenticated_page.wait_for_timeout(300)
    
    # Verify still only one widget exists
    widget_count_after = authenticated_page.locator("#agent-widget").count()
    assert widget_count_after == 1, f"Expected 1 widget after toggles, found {widget_count_after}"


def test_no_duplicate_buttons_prometheus(authenticated_page: Page):
    """
    TC-REVIVE-15: Verify no duplicate RE-VIVE buttons exist on Prometheus view
    """
    authenticated_page.goto("/prometheus-view")
    authenticated_page.wait_for_selector("#prometheus-iframe", state="visible", timeout=10000)
    
    # Count toggle buttons
    header_button_count = authenticated_page.locator("#ai-helper-toggle").count()
    floating_button_count = authenticated_page.locator("#grafana-ai-toggle").count()
    
    # Should have exactly one header button and zero floating buttons (since we're in parent wrapper)
    assert header_button_count == 1, f"Expected 1 header button, found {header_button_count}"
    assert floating_button_count == 0, f"Expected 0 floating buttons in wrapper, found {floating_button_count}"
