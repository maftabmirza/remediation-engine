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

    # Fill credentials — defaults from docker-compose ADMIN_PASSWORD env
    page.fill('input[name="username"]', os.getenv("ADMIN_USERNAME", "admin"))
    page.fill('input[name="password"]', os.getenv("ADMIN_PASSWORD", "admin123"))

    # Click login — the form uses a JS fetch then window.location.href = '/'
    with page.expect_navigation(timeout=20000):
        page.click('button[type="submit"]')

    # Extra guard: if somehow still on login (bad creds etc.) raise clearly
    if "login" in page.url:
        raise RuntimeError(f"E2E login failed — still on {page.url}")
    
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
