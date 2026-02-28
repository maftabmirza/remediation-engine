import re
from playwright.sync_api import Page, expect

def test_dashboard_elements(authenticated_page: Page):
    """
    Verify key elements on the dashboard are visible.
    """
    # The authenticated_page fixture ensures we are on the dashboard
    
    # Check for sidebar navigation — #sidebar IS the <nav> element
    expect(authenticated_page.locator('nav#sidebar')).to_be_visible()
    
    # Check for main content area
    expect(authenticated_page.locator('main')).to_be_visible()
    
    # The dashboard has no <h1>/<h2>; section cards use <h3> headings.
    # Verify one of the known dashboard card headings is present.
    expect(authenticated_page.locator('h3').first).to_have_text(
        re.compile(r'(Service Health|Active Incidents|MTTR|Alert Volume|Dashboard|Overview)', re.IGNORECASE)
    )

def test_navigation_to_runbooks(authenticated_page: Page):
    """
    Verify navigation from Dashboard to Runbooks page.
    """
    # The sidebar uses expandable nav-groups with submenu items.
    # Click the Remediation group header to expand it, then click the Runbooks item.

    # Find the Remediation nav group by its data-nav-group attribute
    remediation_nav = authenticated_page.locator('.nav-group[data-nav-group="remediation"]')

    # Click the group header to expand the submenu
    remediation_nav.locator('.has-submenu').click()

    # Click the Runbooks submenu item (uses onclick=window.location.href navigation)
    runbooks_item = remediation_nav.locator('.submenu-item', has_text='Runbooks')
    runbooks_item.click()

    # Wait for full page navigation triggered by window.location.href
    authenticated_page.wait_for_url('**/runbooks', timeout=15000)

    # Verify the page title confirms we're on the Runbooks page
    expect(authenticated_page).to_have_title(re.compile(r'Runbook', re.IGNORECASE))
