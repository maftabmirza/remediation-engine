import pytest
import os
from playwright.sync_api import Page, expect

# Default to running against the local docker-compose environment
DEFAULT_BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")

@pytest.fixture(scope="session")
def base_url():
    return DEFAULT_BASE_URL

@pytest.fixture(scope="function")
def authenticated_page(page: Page, base_url: str) -> Page:
    """
    Login to the application and return the authenticated page.
    This fixture assumes the default admin credentials.
    """
    # Go to login page
    page.goto(f"{base_url}/login")
    
    # Check if we are already logged in (redirected to dashboard)
    if "login" not in page.url:
        return page

    # Fill credentials
    # Using the default from docker-compose.yml
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    
    # Click login
    page.click('button[type="submit"]')
    
    # Wait for navigation to dashboard - adjust logic to match actual app behavior
    # App redirects to root which might be dashboard or redirect to it
    # We'll wait for URL to NOT be login
    except_condition = lambda: "login" not in page.url
    # expect(page).not_to_have_url(re.compile(r".*/login")) # Simplified wait below
    page.wait_for_url(lambda u: "login" not in u, timeout=10000)
    
    return page

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """
    Override default browser context arguments.
    """
    return {
        **browser_context_args,
        "viewport": {
            "width": 1280,
            "height": 720,
        },
        # "record_video_dir": "test-results/videos",  # Enable if debugging needed
    }
