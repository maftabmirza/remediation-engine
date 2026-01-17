"""
Integration tests for runbook view pages (HTML rendering).
Tests that templates render correctly and return proper content.
"""
import pytest
from uuid import uuid4


@pytest.mark.integration
class TestRunbookViewPages:
    """Test runbook view pages render correctly."""
    
    def test_runbook_view_requires_authentication(self, test_client, test_runbook):
        """Test that runbook view page requires authentication."""
        response = test_client.get(f"/runbooks/{test_runbook.id}/view")
        
        # Should redirect to login or return 401
        assert response.status_code in [302, 401]
    
    def test_runbook_view_renders_with_auth(self, test_client, auth_headers, test_runbook):
        """Test that authenticated user can view runbook page."""
        response = test_client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_runbook_view_contains_runbook_name(self, test_client, auth_headers, test_runbook):
        """Test that runbook view page contains the runbook name."""
        response = test_client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text
        assert test_runbook.name in html
    
    def test_runbook_view_contains_essential_sections(self, test_client, auth_headers, test_runbook):
        """Test that runbook view page has all essential sections."""
        response = test_client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text
        
        # Check for essential content
        assert len(html) > 1000, "Page content is suspiciously short"
        
        # Check for key sections
        assert "Runbook Steps" in html or "Steps" in html
        assert "Execute" in html or "Run" in html
        
        # Should have some form of navigation (sidebar or header)
        assert "nav" in html.lower() or "sidebar" in html.lower() or "menu" in html.lower()
    
    def test_runbook_view_has_correct_css_framework(self, test_client, auth_headers, test_runbook):
        """Test that runbook view uses Tailwind CSS, not Bootstrap."""
        response = test_client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text.lower()
        
        # Should use Tailwind classes
        tailwind_indicators = ["card", "flex", "grid", "px-", "py-", "rounded"]
        has_tailwind = any(indicator in html for indicator in tailwind_indicators)
        assert has_tailwind, "Page should use Tailwind CSS classes"
        
        # Should NOT have Bootstrap-specific classes
        bootstrap_classes = ["col-md-", "btn-primary", "container-fluid", "row mb-"]
        has_bootstrap = any(cls in html for cls in bootstrap_classes)
        assert not has_bootstrap, "Page should not use Bootstrap classes"
    
    def test_runbook_view_with_steps(self, test_client, auth_headers, test_runbook_with_steps):
        """Test that runbook view displays steps."""
        response = test_client.get(
            f"/runbooks/{test_runbook_with_steps.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text
        
        # Should show step information
        for step in test_runbook_with_steps.steps:
            assert step.name in html
    
    def test_runbook_view_nonexistent_returns_404(self, test_client, auth_headers):
        """Test that non-existent runbook returns 404."""
        fake_id = uuid4()
        response = test_client.get(
            f"/runbooks/{fake_id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_runbook_view_has_execute_modal(self, test_client, auth_headers, test_runbook):
        """Test that page includes execute modal functionality."""
        response = test_client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text.lower()
        
        # Should have execute modal
        assert "modal" in html or "execute" in html
        
        # Should have form or button to execute
        assert "button" in html or "form" in html
    
    def test_runbook_view_shows_metadata(self, test_client, auth_headers, test_runbook):
        """Test that runbook view shows metadata like category and status."""
        response = test_client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text
        
        # Should show metadata
        if test_runbook.category:
            assert test_runbook.category in html or test_runbook.category.title() in html
        
        # Should show status indicators
        assert "active" in html.lower() or "enabled" in html.lower() or "draft" in html.lower()
    
    def test_runbook_view_has_proper_html_structure(self, test_client, auth_headers, test_runbook):
        """Test that page has proper HTML structure."""
        response = test_client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text.lower()
        
        # Basic HTML structure
        assert "<!doctype html>" in html or "<html" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "</html>" in html
        
        # Should have title
        assert "<title>" in html
    
    def test_runbook_view_includes_scripts(self, test_client, auth_headers, test_runbook):
        """Test that page includes necessary JavaScript."""
        response = test_client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text.lower()
        
        # Should have script tags for interactivity
        assert "<script>" in html or "<script " in html


@pytest.mark.integration
class TestRunbookListView:
    """Test runbook list page."""
    
    def test_runbooks_list_page_loads(self, test_client, auth_headers):
        """Test that runbooks list page loads."""
        response = test_client.get("/runbooks", headers=auth_headers)
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_runbooks_list_has_content(self, test_client, auth_headers):
        """Test that runbooks list page has content."""
        response = test_client.get("/runbooks", headers=auth_headers)
        
        assert response.status_code == 200
        html = response.text
        
        assert len(html) > 1000
        assert "Runbook" in html or "runbook" in html
    
    def test_runbooks_list_requires_auth(self, test_client):
        """Test that runbooks list requires authentication."""
        response = test_client.get("/runbooks")
        
        # Should redirect to login or return 401
        assert response.status_code in [302, 401]


@pytest.mark.integration  
class TestRunbookEditView:
    """Test runbook edit page."""
    
    def test_runbook_edit_page_loads(self, test_client, auth_headers, test_runbook):
        """Test that runbook edit page loads."""
        response = test_client.get(
            f"/runbooks/{test_runbook.id}/edit",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_runbook_edit_has_form(self, test_client, auth_headers, test_runbook):
        """Test that edit page has form elements."""
        response = test_client.get(
            f"/runbooks/{test_runbook.id}/edit",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text.lower()
        
        # Should have form
        assert "<form" in html
        assert "<input" in html or "<textarea" in html
        assert "button" in html or "submit" in html


@pytest.mark.integration
class TestOtherViewPages:
    """Test other important view pages."""
    
    @pytest.mark.parametrize("path,should_contain", [
        ("/", ["Dashboard", "Alert"]),
        ("/alerts", ["Alert", "Severity"]),
        ("/executions", ["Execution", "Runbook"]),
    ])
    def test_important_pages_render(self, test_client, auth_headers, path, should_contain):
        """Test that important pages render with expected content."""
        response = test_client.get(path, headers=auth_headers)
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        
        html = response.text
        assert len(html) > 500, f"Page {path} content is too short"
        
        # Check for expected content
        for expected in should_contain:
            assert expected in html, f"Expected '{expected}' in {path}"
        
        # Should redirect to login or return 401
        assert response.status_code in [302, 401]
    
    def test_runbook_view_renders_with_auth(self, client: TestClient, auth_headers, test_runbook):
        """Test that authenticated user can view runbook page."""
        response = client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_runbook_view_contains_runbook_name(self, client: TestClient, auth_headers, test_runbook):
        """Test that runbook view page contains the runbook name."""
        response = client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text
        assert test_runbook.name in html
    
    def test_runbook_view_contains_essential_sections(self, client: TestClient, auth_headers, test_runbook):
        """Test that runbook view page has all essential sections."""
        response = client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text
        
        # Check for essential content
        assert len(html) > 1000, "Page content is suspiciously short"
        
        # Check for key sections
        assert "Runbook Steps" in html or "Steps" in html
        assert "Execute" in html or "Run" in html
        
        # Should have some form of navigation (sidebar or header)
        assert "nav" in html.lower() or "sidebar" in html.lower() or "menu" in html.lower()
    
    def test_runbook_view_has_correct_css_framework(self, client: TestClient, auth_headers, test_runbook):
        """Test that runbook view uses Tailwind CSS, not Bootstrap."""
        response = client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text.lower()
        
        # Should use Tailwind classes
        tailwind_indicators = ["card", "flex", "grid", "px-", "py-", "rounded"]
        has_tailwind = any(indicator in html for indicator in tailwind_indicators)
        assert has_tailwind, "Page should use Tailwind CSS classes"
        
        # Should NOT have Bootstrap-specific classes
        bootstrap_classes = ["col-md-", "btn-primary", "container-fluid", "row mb-"]
        has_bootstrap = any(cls in html for cls in bootstrap_classes)
        assert not has_bootstrap, "Page should not use Bootstrap classes"
    
    def test_runbook_view_with_steps(self, client: TestClient, auth_headers, test_runbook_with_steps):
        """Test that runbook view displays steps."""
        response = client.get(
            f"/runbooks/{test_runbook_with_steps.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text
        
        # Should show step information
        for step in test_runbook_with_steps.steps:
            assert step.name in html
    
    def test_runbook_view_nonexistent_returns_404(self, client: TestClient, auth_headers):
        """Test that non-existent runbook returns 404."""
        fake_id = uuid4()
        response = client.get(
            f"/runbooks/{fake_id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_runbook_view_has_execute_modal(self, client: TestClient, auth_headers, test_runbook):
        """Test that page includes execute modal functionality."""
        response = client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text.lower()
        
        # Should have execute modal
        assert "modal" in html or "execute" in html
        
        # Should have form or button to execute
        assert "button" in html or "form" in html
    
    def test_runbook_view_shows_metadata(self, client: TestClient, auth_headers, test_runbook):
        """Test that runbook view shows metadata like category and status."""
        response = client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text
        
        # Should show metadata
        if test_runbook.category:
            assert test_runbook.category in html or test_runbook.category.title() in html
        
        # Should show status indicators
        assert "active" in html.lower() or "enabled" in html.lower() or "draft" in html.lower()
    
    def test_runbook_view_has_proper_html_structure(self, client: TestClient, auth_headers, test_runbook):
        """Test that page has proper HTML structure."""
        response = client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text.lower()
        
        # Basic HTML structure
        assert "<!doctype html>" in html or "<html" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "</html>" in html
        
        # Should have title
        assert "<title>" in html
    
    def test_runbook_view_includes_scripts(self, client: TestClient, auth_headers, test_runbook):
        """Test that page includes necessary JavaScript."""
        response = client.get(
            f"/runbooks/{test_runbook.id}/view",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text.lower()
        
        # Should have script tags for interactivity
        assert "<script>" in html or "<script " in html


@pytest.mark.integration
class TestRunbookListView:
    """Test runbook list page."""
    
    def test_runbooks_list_page_loads(self, client: TestClient, auth_headers):
        """Test that runbooks list page loads."""
        response = client.get("/runbooks", headers=auth_headers)
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_runbooks_list_has_content(self, client: TestClient, auth_headers):
        """Test that runbooks list page has content."""
        response = client.get("/runbooks", headers=auth_headers)
        
        assert response.status_code == 200
        html = response.text
        
        assert len(html) > 1000
        assert "Runbook" in html or "runbook" in html
    
    def test_runbooks_list_requires_auth(self, client: TestClient):
        """Test that runbooks list requires authentication."""
        response = client.get("/runbooks")
        
        # Should redirect to login or return 401
        assert response.status_code in [302, 401]


@pytest.mark.integration  
class TestRunbookEditView:
    """Test runbook edit page."""
    
    def test_runbook_edit_page_loads(self, client: TestClient, auth_headers, test_runbook):
        """Test that runbook edit page loads."""
        response = client.get(
            f"/runbooks/{test_runbook.id}/edit",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_runbook_edit_has_form(self, client: TestClient, auth_headers, test_runbook):
        """Test that edit page has form elements."""
        response = client.get(
            f"/runbooks/{test_runbook.id}/edit",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text.lower()
        
        # Should have form
        assert "<form" in html
        assert "<input" in html or "<textarea" in html
        assert "button" in html or "submit" in html


@pytest.mark.integration
class TestOtherViewPages:
    """Test other important view pages."""
    
    @pytest.mark.parametrize("path,should_contain", [
        ("/", ["Dashboard", "Alert"]),
        ("/alerts", ["Alert", "Severity"]),
        ("/executions", ["Execution", "Runbook"]),
    ])
    def test_important_pages_render(self, client: TestClient, auth_headers, path, should_contain):
        """Test that important pages render with expected content."""
        response = client.get(path, headers=auth_headers)
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        
        html = response.text
        assert len(html) > 500, f"Page {path} content is too short"
        
        # Check for expected content
        for expected in should_contain:
            assert expected in html, f"Expected '{expected}' in {path}"
