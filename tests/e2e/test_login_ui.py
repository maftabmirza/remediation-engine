from playwright.sync_api import Page, expect

def test_login_page_loads(page: Page, base_url: str):
    """
    Verify the login page loads correctly with all necessary elements.
    """
    page.goto(f"{base_url}/login")
    
    # Check title
    expect(page).to_have_title("Login - AIOps Platform")
    
    # Check form elements
    expect(page.locator('input[name="username"]')).to_be_visible()
    expect(page.locator('input[name="password"]')).to_be_visible()
    expect(page.locator('button[type="submit"]')).to_be_visible()

def test_login_success(page: Page, base_url: str):
    """
    Verify successful login redirects to the homepage/dashboard.
    """
    page.goto(f"{base_url}/login")
    
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.click('button[type="submit"]')
    
    # Check if error message appears (debugging step)
    error_msg = page.locator("#errorMessage")
    if error_msg.is_visible():
        print(f"Login failed with: {error_msg.text_content()}")
    
    # Expect redirect to root or dashboard
    # The JS redirects to '/', checking for that or dashboard
    # allow both for robustness
    expect(page).to_have_url(f"{base_url}/")

def test_login_failure(page: Page, base_url: str):
    """
    Verify invalid credentials show an error message.
    """
    page.goto(f"{base_url}/login")
    
    page.fill('input[name="username"]', "wronguser")
    page.fill('input[name="password"]', "wrongpass")
    page.click('button[type="submit"]')
    
    # Expect to stay on login page
    expect(page).to_have_url(f"{base_url}/login")
    
    # Expect error message
    error_message = page.locator('#errorMessage')
    expect(error_message).to_be_visible()
    expect(error_message).not_to_be_empty()
