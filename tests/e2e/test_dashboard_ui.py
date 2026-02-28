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
    
    # Check for dashboard-related headers - the dashboard shows Alert Clustering as the main widget
    # Use regex for flexibility to match various dashboard section headings
    expect(authenticated_page.locator('h1, h2').first).to_have_text(
        re.compile(r'(Alert Clustering|Dashboard|Overview)', re.IGNORECASE)
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

    # Click the Runbooks submenu item (uses onclick navigation, not <a> tags)
    runbooks_item = remediation_nav.locator('.submenu-item', has_text='Runbooks')
    runbooks_item.click()
    
    # Verify we navigated to the runbooks page
    expect(authenticated_page).to_have_url(re.compile(r'.*/runbooks'))
    
    # Verify the page content shows Runbooks
    expect(authenticated_page.locator('h1, h2').first).to_have_text(
        re.compile(r'Runbook', re.IGNORECASE)
    )
