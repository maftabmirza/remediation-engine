import re
import uuid
from playwright.sync_api import Page, expect

def test_runbook_list_loads(authenticated_page: Page):
    """
    TC-RB-01: Verify runbook list renders with expected elements.
    """
    # Navigate to runbooks page
    authenticated_page.goto("/runbooks")
    
    # Verify page title/header
    expect(authenticated_page.locator("h1, h2").first).to_have_text(re.compile(r"Runbook", re.IGNORECASE))
    
    # Check for "Create Runbook" button - it is an anchor tag
    expect(authenticated_page.locator("a[href='/runbooks/new']")).to_be_visible()
    
    # Check for list headers - div based layout
    # Using specific text locators for headers we know exist
    expect(authenticated_page.locator("div").filter(has_text="Name").first).to_be_visible()
    expect(authenticated_page.locator("div").filter(has_text="Status").first).to_be_visible()
    expect(authenticated_page.locator("div").filter(has_text="Actions").first).to_be_visible()

def test_create_new_runbook(authenticated_page: Page):
    """
    TC-RB-02: Create New Runbook.
    """
    authenticated_page.goto("/runbooks")
    
    # Click Create Runbook
    authenticated_page.click("a[href='/runbooks/new']")
    
    # Verify we are on create page
    expect(authenticated_page).to_have_url(re.compile(r".*/runbooks/new"))
    
    # Basic form fill
    # Use unique name to avoid conflicts with previous test runs
    unique_id = str(uuid.uuid4())[:8]
    runbook_name = f"E2E Test Runbook {unique_id}"
    authenticated_page.fill('#runbookName', runbook_name)
    authenticated_page.fill('#runbookDescription', "Created by E2E automation")
    
    # Select a category if needed (default might be fine, but good to be explicit if validation requires it)
    # authenticated_page.select_option('#runbookCategory', 'Operations') 
    
    # Add a step (Required)
    authenticated_page.click("button:has-text('Add Step')")
    
    # Wait for step card to appear
    expect(authenticated_page.locator("#step-1")).to_be_visible()
    
    # Fill step name
    authenticated_page.fill("#step-1 .step-name", "Echo Test")
    
    # Set command in CodeMirror (Linux tab is default)
    # Click inside the CodeMirror editor and type
    authenticated_page.click("#step-1-linux-content .CodeMirror")
    authenticated_page.keyboard.type('echo "Hello World"')

    # Save
    authenticated_page.click("button:has-text('Save Runbook')")
    
    # Verify success - should redirect to runbooks list
    expect(authenticated_page).to_have_url(re.compile(r".*/runbooks$"))
    
    # Verify the new runbook appears in the list
    # The list is div-based, so we check for text visibility in the container
    expect(authenticated_page.locator("div").filter(has_text=runbook_name).first).to_be_visible()


def test_execute_runbook(authenticated_page: Page):
    """
    TC-RB-03: Execute Runbook.
    """
    # 1. Create a runbook first (Prerequisite)
    authenticated_page.goto("/runbooks/new")
    
    unique_id = str(uuid.uuid4())[:8]
    runbook_name = f"E2E Exec Test {unique_id}"
    authenticated_page.fill('#runbookName', runbook_name)
    authenticated_page.fill('#runbookDescription', "For execution test")
    
    # Add step
    authenticated_page.click("button:has-text('Add Step')")
    expect(authenticated_page.locator("#step-1")).to_be_visible()
    authenticated_page.fill("#step-1 .step-name", "Echo Step")
    authenticated_page.click("#step-1-linux-content .CodeMirror")
    authenticated_page.keyboard.type('echo "Executing..."')
    
    # Save
    authenticated_page.click("button:has-text('Save Runbook')")
    expect(authenticated_page).to_have_url(re.compile(r".*/runbooks$"))
    
    # 2. Find and Execute
    # We need to find the specific row or card. The list view seems to be a table row in `templates/runbooks.html`
    # The row contains the name. We look for the "Run" button in that row.
    # Row locator: tr that contains the runbook name
    row = authenticated_page.locator("tr").filter(has_text=runbook_name)
    expect(row).to_be_visible()
    
    # Click Run button (title="Run")
    row.get_by_title("Run").click()
    
    # 3. Handle Execute Modal
    modal = authenticated_page.locator("#executeModal")
    expect(modal).to_be_visible()
    
    # Optional: Select server if needed. Default is usually "Use runbook default..."
    # We can just click Execute.
    # Button is type="submit" inside the modal form
    modal.locator("button[type='submit']").click()
    
    # 4. Verify Redirection to Executions
    # "window.location.href = '/executions';" on success
    expect(authenticated_page).to_have_url(re.compile(r".*/executions$"))



