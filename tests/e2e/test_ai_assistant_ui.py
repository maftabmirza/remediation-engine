import re
from playwright.sync_api import Page, expect

def test_ai_page_visibility(authenticated_page: Page):
    """TC-AI-01: Chat Page Visibility"""
    authenticated_page.goto("/ai")
    expect(authenticated_page).to_have_title(re.compile("AI Assistant"))
    expect(authenticated_page.locator("#chatInput")).to_be_visible()
    expect(authenticated_page.locator("#modeGeneralBtn")).to_be_visible()

def test_basic_conversation(authenticated_page: Page):
    """TC-AI-02: Basic Conversation"""
    authenticated_page.goto("/ai")
    
    # Type message
    msg = "Hello AI"
    authenticated_page.fill("#chatInput", msg)
    authenticated_page.click("button[type='submit']")
    
    # Verify user message appears
    # The template appends user message to #chatMessages
    expect(authenticated_page.locator("#chatMessages")).to_contain_text(msg)
    
    # Verify input is cleared (standard chat behavior)
    expect(authenticated_page.locator("#chatInput")).to_be_empty()

def test_context_awareness_mode_switch(authenticated_page: Page):
    """TC-AI-03: Context Awareness (Mode Switching)"""
    authenticated_page.goto("/ai")
    
    # Default is Inquiry (General)
    # Class check: bg-blue-600 usually indicates active
    expect(authenticated_page.locator("#modeGeneralBtn")).to_have_class(re.compile("bg-blue-600"))
    
    # Switch to Troubleshoot
    authenticated_page.click("#modeTroubleshootBtn")
    
    # Verify switch
    expect(authenticated_page.locator("#modeTroubleshootBtn")).to_have_class(re.compile("bg-green-600"))
    expect(authenticated_page.locator("#modeGeneralBtn")).not_to_have_class(re.compile("bg-blue-600"))
