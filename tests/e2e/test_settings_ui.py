
import pytest
from playwright.sync_api import Page, expect
import time

def test_settings_overview_visibility(authenticated_page: Page):
    """
    TC-ST-01: Settings Overview & Navigation
    """
    authenticated_page.goto("/settings")
    expect(authenticated_page).to_have_title("Settings - AIOps Platform")
    
    # Check default active section (Overview)
    expect(authenticated_page.locator("#section-overview")).to_be_visible()
    
    # Verify Stats Cards existence
    # Use specific locators for cards in overview
    expect(authenticated_page.locator("#section-overview .card", has_text="LLM Providers")).to_be_visible()
    expect(authenticated_page.locator("#section-overview .card", has_text="Servers")).to_be_visible()

def test_llm_providers_section(authenticated_page: Page):
    """
    TC-ST-02: LLM Providers List (Agent Pool equivalent)
    """
    authenticated_page.goto("/settings")
    
    # Click Providers Nav
    authenticated_page.click("button[data-target='section-providers']")
    
    # Verify section active
    expect(authenticated_page.locator("#section-providers")).to_be_visible()
    expect(authenticated_page.locator("#section-overview")).not_to_be_visible()
    
    # Verify Header
    expect(authenticated_page.locator("h1:has-text('LLM Providers')")).to_be_visible()
    
    # Verify Table Container
    expect(authenticated_page.locator("#providersTableContainer")).to_be_visible()
    
    # Check for filters
    expect(authenticated_page.locator("#providerSearch")).to_be_visible()
    expect(authenticated_page.locator("#providerTypeFilter")).to_be_visible()

def test_servers_section(authenticated_page: Page):
    """
    TC-ST-03: Servers List (Target Nodes)
    """
    authenticated_page.goto("/settings")
    
    # Click Servers Nav
    authenticated_page.click("button[data-target='section-servers']")
    
    # Verify section active
    expect(authenticated_page.locator("#section-servers")).to_be_visible()
    
    # Verify Header
    expect(authenticated_page.locator("h1:has-text('Server Inventory')")).to_be_visible()
    
    # Verify Table Container
    expect(authenticated_page.locator("#serversTableContainer")).to_be_visible()
    
    # Check for Import button
    expect(authenticated_page.locator("text=Bulk import servers")).to_be_visible()
