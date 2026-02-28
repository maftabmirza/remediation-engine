
import re
from playwright.sync_api import Page, expect

def test_chat_initialization_success(authenticated_page: Page):
    """
    TC-AI-Init-01: Verify Chat Session Initialization
    Ensures that navigating to /ai successfully initializes a chat session
    without any 500 errors or failure toasts.
    """
    # Setup request interception to verify API calls
    with authenticated_page.expect_response(
        lambda response: "/api/chat/sessions" in response.url and response.status in [200, 201]
    ) as response_info:
        authenticated_page.goto("/ai")
    
    # Wait for page to settle
    authenticated_page.wait_for_load_state("networkidle")
    
    # Verify the API call was successful
    response = response_info.value
    assert response.ok
    
    # Check that no error toast appeared
    # Assuming toast has a specific class or ID, usually .toast or text content
    expect(authenticated_page.locator("text=Chat init failed")).not_to_be_visible()
    
    # Verify the chat input is ready and visible
    expect(authenticated_page.locator("#chatInput")).to_be_visible()
    expect(authenticated_page.locator("#chatInput")).to_be_enabled()
    
    # Verify session ID is present in JS
    # We can evaluate JS to check the global currentSessionId
    session_id = authenticated_page.evaluate("window.currentSessionId")
    assert session_id is not None
    assert len(session_id) > 0

def test_chat_session_persistence(authenticated_page: Page):
    """
    TC-AI-Init-02: Verify Session Persistence
    Ensures that reloading the page maintains or correctly re-initializes functionality.
    """
    authenticated_page.goto("/ai")
    authenticated_page.wait_for_load_state("networkidle")
    
    initial_id = authenticated_page.evaluate("window.currentSessionId")
    assert initial_id
    
    # Reload
    authenticated_page.reload()
    authenticated_page.wait_for_load_state("networkidle")
    
    new_id = authenticated_page.evaluate("window.currentSessionId")
    assert new_id
    
    # Note: Depending on implementation, it might reuse the session or create a new one.
    # For standalone chat, it typically reuses 'session-{user_id}' if implemented that way,
    # or creates new one if using UUIDs.
    # We just ensure it works.
    expect(authenticated_page.locator("#chatInput")).to_be_visible()
