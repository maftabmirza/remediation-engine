import pytest
import os
from playwright.sync_api import Page, expect

# Default to running against the local docker-compose environment
DEFAULT_BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")

@pytest.fixture(scope="session")
def base_url():
    return DEFAULT_BASE_URL


@pytest.fixture(scope="session")
def _auth_storage_state(browser, base_url):
    """
    Log in ONCE per test session and capture the auth cookies/localStorage.
    Uses the pytest-playwright session-scoped `browser` fixture directly so
    we never call sync_playwright() inside an asyncio loop (which is forbidden
    when asyncio_mode=auto is active).
    """
    admin_pass = os.getenv("ADMIN_PASSWORD")
    if not admin_pass:
        return None  # individual tests will skip when they detect no auth state

    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    page = ctx.new_page()
    try:
        page.goto(f"{base_url}/login")
        page.fill('input[name="username"]', os.getenv("ADMIN_USERNAME", "admin"))
        page.fill('input[name="password"]', admin_pass)
        page.click('button[type="submit"]')
        page.wait_for_url(lambda u: "login" not in u, timeout=45000)
        return ctx.storage_state()
    finally:
        page.close()
        ctx.close()


@pytest.fixture(scope="function")
def browser_context_args(browser_context_args, _auth_storage_state):
    """
    Inject session-scoped auth cookies into every new browser context so that
    each test page starts already authenticated — no per-test login needed.
    """
    base_args = {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
    }
    if _auth_storage_state:
        base_args["storage_state"] = _auth_storage_state
    return base_args


@pytest.fixture(scope="function")
def unauthenticated_page(browser, base_url: str) -> Page:
    """
    Return a page with NO auth cookies so login-page tests work.
    Uses a fresh, isolated browser context.
    """
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    page = ctx.new_page()
    yield page
    page.close()
    ctx.close()


@pytest.fixture(scope="function")
def authenticated_page(page: Page, base_url: str, _auth_storage_state) -> Page:
    """
    Return an authenticated page. Authentication is handled once per session
    by _auth_storage_state and injected into the context via browser_context_args.
    """
    if not _auth_storage_state:
        pytest.skip("ADMIN_PASSWORD env var not set — skipping E2E login tests")

    # Navigate to home; if cookies are valid we won't be redirected to /login
    page.goto(f"{base_url}/")
    if "login" in page.url:
        raise RuntimeError(f"E2E auth failed — still on {page.url}")

    return page
