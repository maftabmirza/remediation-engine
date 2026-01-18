import re
from playwright.sync_api import Page, expect

def test_dashboard_elements(authenticated_page: Page):
    """
    Verify key elements on the dashboard are visible.
    """
    # The authenticated_page fixture ensures we are on the dashboard
    
    # Check for sidebar navigation (use .first since there may be multiple nav elements)
    expect(authenticated_page.locator('#sidebar nav').first).to_be_visible()
    
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
    # The sidebar is collapsed by default, so we need to hover on the parent nav item
    # to trigger the flyout menu, then click the Runbooks link in the flyout
    
    # Find the Remediation nav group (parent of Runbooks)
    remediation_nav = authenticated_page.locator('.nav-group').filter(
        has=authenticated_page.locator('[data-tooltip="Remediation"]')
    )
    
    # Hover to trigger the flyout menu
    remediation_nav.hover()
    
    # Wait for flyout to appear and click Runbooks link in the flyout
    runbooks_link = authenticated_page.locator('#remediationFlyout a[href="/runbooks"]')
    runbooks_link.click()
    
    # Verify we navigated to the runbooks page
    expect(authenticated_page).to_have_url(re.compile(r'.*/runbooks'))
    
    # Verify the page content shows Runbooks
    expect(authenticated_page.locator('h1, h2').first).to_have_text(
        re.compile(r'Runbook', re.IGNORECASE)
    )
