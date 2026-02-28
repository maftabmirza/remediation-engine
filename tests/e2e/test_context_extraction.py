
import pytest
from playwright.sync_api import Page, expect

def test_runbook_view_context_extraction(authenticated_page: Page):
    """
    Verify that getPageContext() correctly extracts step information from the Runbook View page.
    This ensures the generic fallback logic in revive_widget.js works as expected.
    """
    # 1. Navigate to a runbook view page
    # We can use an existing runbook or just check if we can land on one.
    # Ideally we'd create one, but for now let's assume at least one exists or we can mock the page structure.
    # To be safe and robust, let's inject a mock runbook view structure into a blank page if we can't rely on data.
    # However, since this is a "live" app test, we should try to use real pages.
    
    # Navigate to runbooks list
    authenticated_page.goto("/runbooks")
    
    # Wait for runbook list validation
    # If no runbooks, we can't test "View" page. 
    # Let's create a temporary runbook to be sure.
    
    # Click "Create" (Header Action)
    authenticated_page.click("a[href='/runbooks/new']")
    authenticated_page.wait_for_url("**/runbooks/new")
    
    # Fill form
    runbook_name = "Context Extraction Test"
    authenticated_page.fill("#runbookName", runbook_name)
    authenticated_page.fill("#runbookDescription", "Testing context extraction")
    
    # Add a step
    authenticated_page.click("text=Add Step")
    
    # Wait for step card
    step_card = authenticated_page.locator(".step-card").first
    expect(step_card).to_be_visible()
    
    # Fill step details
    step_card.locator(".step-name").fill("Verify System")
    step_card.locator(".CodeMirror").first.click()
    authenticated_page.keyboard.type("echo 'System OK'")
    
    # Save Runbook
    authenticated_page.click("text=Save Runbook")
    
    # Wait for redirect to list (or stay on edit?)
    # Usually redirects to list. Let's wait for list.
    authenticated_page.wait_for_url("**/runbooks")
    
    # Find the new runbook and click View
    # Assuming list has links. 
    # We need to find the row with "Context Extraction Test"
    row = authenticated_page.locator(f"tr:has-text('{runbook_name}')")
    expect(row).to_be_visible()
    
    # Click the "View" button/icon (usually eye icon or just the name)
    # Let's try clicking the name or the view action
    row.click() 
    # Wait, usually clicking row or name goes to view.
    
    # Wait for view page
    authenticated_page.wait_for_selector("text=Runbook Steps")
    
    # Now verify the context extraction
    # Execute getPageContext() in the browser context
    context = authenticated_page.evaluate("window.getPageContext()")
    
    # Assertions
    assert context['page_type'] == 'runbooks'
    
    # key part: check if runbook_steps_summary is populated
    assert 'runbook_steps_summary' in context['form_data']
    summary = context['form_data']['runbook_steps_summary']
    
    print(f"Extracted Summary:\n{summary}")
    
    assert "Runbook Steps (View Mode):" in summary
    assert "Verify System" in summary
    assert "echo 'System OK'" in summary
    
    # Cleanup (Optional, but good practice)
    # navigate back to list and delete?
    # For now, let's just leave it or rely on test DB reset.
