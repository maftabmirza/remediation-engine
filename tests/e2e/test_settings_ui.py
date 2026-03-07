
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
    # Use specific locators for stat cards in overview
    expect(authenticated_page.locator("#section-overview .settings-stat-card", has_text="LLM Providers")).to_be_visible()
    expect(authenticated_page.locator("#section-overview .settings-stat-card", has_text="Servers")).to_be_visible()

def test_llm_providers_section(authenticated_page: Page):
    """
    TC-ST-02: LLM Providers List (Agent Pool equivalent)
    """
    # Navigate directly with hash — JS on DOMContentLoaded reads the hash and
    # calls setActiveSection(), so the section is active after page load.
    authenticated_page.goto("/settings#section-providers")
    authenticated_page.wait_for_timeout(500)  # Allow JS section activation

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
    # Navigate directly with hash — same hash-routing as providers section
    authenticated_page.goto("/settings#section-servers")
    authenticated_page.wait_for_timeout(500)  # Allow JS section activation

    # Verify section active
    expect(authenticated_page.locator("#section-servers")).to_be_visible()
    
    # Verify Header
    expect(authenticated_page.locator("h1:has-text('Server Inventory')")).to_be_visible()
    
    # Verify Table Container
    expect(authenticated_page.locator("#serversTableContainer")).to_be_visible()
    
    # Check for Import button
    expect(authenticated_page.locator("text=Bulk import servers")).to_be_visible()


def test_users_section_visible(authenticated_page: Page):
    """
    TC-ST-04: Users section renders correctly (admin user).
    """
    authenticated_page.goto("/settings#section-users")
    authenticated_page.wait_for_timeout(500)

    expect(authenticated_page.locator("#section-users")).to_be_visible()
    expect(authenticated_page.locator("h1:has-text('User Management')")).to_be_visible()
    expect(authenticated_page.locator("#usersTableContainer")).to_be_visible()
    expect(authenticated_page.locator("button:has-text('Add User')")).to_be_visible()


def test_add_user_modal_role_dropdown_is_populated(authenticated_page: Page):
    """
    TC-ST-05: Add User modal — role dropdown must contain options.

    Regression guard: previously the roles table was empty on a fresh deployment,
    causing the <select id="userRole"> to show nothing. The user could not
    create any new users.

    This test fails if:
    - The roles table was never seeded (init_db() doesn't seed ROLE_PERMISSIONS)
    - GET /api/roles returns an empty list
    - The JS populateUserRoleDropdown() fails silently
    """
    authenticated_page.goto("/settings#section-users")
    authenticated_page.wait_for_timeout(500)

    # Open the Add User modal
    authenticated_page.click("button:has-text('Add User')")

    # Wait for the modal to appear
    expect(authenticated_page.locator("#userModal")).to_be_visible(timeout=5000)

    # Wait for the dropdown to finish loading (JS fetches /api/roles async)
    authenticated_page.wait_for_function(
        "document.querySelectorAll('#userRole option').length > 0",
        timeout=8000,
    )

    options = authenticated_page.locator("#userRole option").all()
    assert len(options) > 0, (
        "The role dropdown (#userRole) has no options. "
        "This means GET /api/roles returned [] — the roles table is empty. "
        "Ensure init_db() seeds ROLE_PERMISSIONS into the roles table at startup."
    )

    # Verify core roles are present
    option_values = [o.get_attribute("value") for o in options]
    for expected_role in ("admin", "operator", "viewer"):
        assert expected_role in option_values, (
            f"Role '{expected_role}' missing from Add User dropdown. "
            f"Available: {option_values}"
        )


def test_add_user_modal_no_loading_placeholder_stuck(authenticated_page: Page):
    """
    TC-ST-06: Add User modal — role dropdown must not be stuck on 'Loading...'

    Guards against the JS populateUserRoleDropdown() silently failing
    (e.g. network error, 401) and leaving 'Loading...' as the only option.
    """
    authenticated_page.goto("/settings#section-users")
    authenticated_page.wait_for_timeout(500)

    authenticated_page.click("button:has-text('Add User')")
    expect(authenticated_page.locator("#userModal")).to_be_visible(timeout=5000)

    # Give the async fetch time to complete
    authenticated_page.wait_for_timeout(3000)

    options = authenticated_page.locator("#userRole option").all()
    option_texts = [o.inner_text().strip() for o in options]

    assert option_texts != ["Loading..."], (
        "Role dropdown is stuck on 'Loading...' — the /api/roles fetch failed. "
        "Check network errors or auth cookie issues."
    )
    assert "Loading..." not in option_texts, (
        f"'Loading...' still present among options: {option_texts}"
    )
