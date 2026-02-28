import os
import pytest
from playwright.sync_api import Page, expect


def test_login_page_loads(unauthenticated_page: Page, base_url: str):
    """
    Verify the login page loads correctly with all necessary elements.
    Uses an unauthenticated browser context so we actually see the login form.
    """
    unauthenticated_page.goto(f"{base_url}/login")

    # Check title
    expect(unauthenticated_page).to_have_title("Sign In - Remediation Engine")

    # Check form elements
    expect(unauthenticated_page.locator('input[name="username"]')).to_be_visible()
    expect(unauthenticated_page.locator('input[name="password"]')).to_be_visible()
    expect(unauthenticated_page.locator('button[type="submit"]')).to_be_visible()


def test_login_success(unauthenticated_page: Page, base_url: str):
    """
    Verify successful login redirects to the homepage/dashboard.
    """
    admin_pass = os.getenv("ADMIN_PASSWORD")
    if not admin_pass:
        pytest.skip("ADMIN_PASSWORD env var not set")

    unauthenticated_page.goto(f"{base_url}/login")

    unauthenticated_page.fill('input[name="username"]', os.getenv("ADMIN_USERNAME", "admin"))
    unauthenticated_page.fill('input[name="password"]', admin_pass)

    unauthenticated_page.click('button[type="submit"]')

    # Check if error message appears (rate limit or bad creds)
    error_msg = unauthenticated_page.locator("#errorMessage")
    if error_msg.is_visible():
        error_text = error_msg.text_content()
        print(f"Login failed with: {error_text}")
        if "rate" in error_text.lower() or "429" in error_text:
            pytest.skip("Rate limited - skipping test")

    # Wait flexibly for redirect away from login
    unauthenticated_page.wait_for_url(lambda url: "login" not in url, timeout=45000)


def test_login_failure(unauthenticated_page: Page, base_url: str):
    """
    Verify invalid credentials show an error message.
    """
    unauthenticated_page.goto(f"{base_url}/login")

    unauthenticated_page.fill('input[name="username"]', "wronguser")
    unauthenticated_page.fill('input[name="password"]', "wrongpass")
    unauthenticated_page.click('button[type="submit"]')

    # Expect to stay on login page
    expect(unauthenticated_page).to_have_url(f"{base_url}/login")

    # Expect error message
    error_message = unauthenticated_page.locator('#errorMessage')
    expect(error_message).to_be_visible()
    expect(error_message).not_to_be_empty()
