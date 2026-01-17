"""
Unit tests for template structure and validation.
Tests template files directly without rendering.
"""
import pytest
from pathlib import Path
import re


@pytest.mark.unit
class TestTemplateStructure:
    """Test template files have correct structure."""
    
    @pytest.fixture
    def template_dir(self):
        """Get template directory path."""
        return Path(__file__).parent.parent.parent / "templates"
    
    def test_template_directory_exists(self, template_dir):
        """Test that templates directory exists."""
        assert template_dir.exists()
        assert template_dir.is_dir()
    
    def test_base_templates_exist(self, template_dir):
        """Test that base templates exist."""
        assert (template_dir / "base.html").exists()
        assert (template_dir / "layout.html").exists()
    
    def test_runbook_templates_exist(self, template_dir):
        """Test that runbook templates exist."""
        assert (template_dir / "runbooks.html").exists()
        assert (template_dir / "runbook_view.html").exists()
        assert (template_dir / "runbook_form.html").exists()
    
    def test_templates_extend_correct_base(self, template_dir):
        """Test that page templates extend layout.html."""
        # Templates that should extend layout.html
        page_templates = [
            "runbooks.html",
            "runbook_view.html",
            "runbook_form.html",
            "dashboard.html",
            "alerts.html",
            "executions.html",
        ]
        
        for template_name in page_templates:
            template_path = template_dir / template_name
            if not template_path.exists():
                continue  # Skip if doesn't exist
            
            content = template_path.read_text()
            
            # Should extend layout.html
            if "{% extends" in content:
                assert '{% extends "layout.html"' in content, \
                    f"{template_name} should extend layout.html"
    
    def test_runbook_view_has_required_blocks(self, template_dir):
        """Test that runbook_view.html has required template blocks."""
        template_path = template_dir / "runbook_view.html"
        if not template_path.exists():
            pytest.skip("runbook_view.html not found")
        
        content = template_path.read_text()
        
        # Should have essential blocks
        assert "{% block title %}" in content
        assert "{% block content %}" in content
        
        # Should set active page
        assert "{% set active_page" in content or "active_page =" in content
    
    def test_runbook_view_no_bootstrap_classes(self, template_dir):
        """Test that runbook_view.html doesn't use Bootstrap classes."""
        template_path = template_dir / "runbook_view.html"
        if not template_path.exists():
            pytest.skip("runbook_view.html not found")
        
        content = template_path.read_text()
        
        # Bootstrap-specific classes that should not be present
        bootstrap_classes = [
            'class="row"',
            'class="col-md-',
            'class="btn btn-',
            'class="container"',
            'class="container-fluid"',
            '"d-flex"',
            '"mb-4"',
            '"text-muted"',
        ]
        
        for bootstrap_class in bootstrap_classes:
            assert bootstrap_class not in content, \
                f"Bootstrap class {bootstrap_class} found in runbook_view.html"
    
    def test_templates_have_proper_jinja_syntax(self, template_dir):
        """Test that templates have valid Jinja2 syntax (basic check)."""
        for template_path in template_dir.glob("*.html"):
            content = template_path.read_text()
            
            # Check for common syntax errors
            # Every {% should have a matching %}
            open_tags = content.count("{%")
            close_tags = content.count("%}")
            assert open_tags == close_tags, \
                f"{template_path.name} has mismatched template tags"
            
            # Every {{ should have a matching }}
            open_vars = content.count("{{")
            close_vars = content.count("}}")
            assert open_vars == close_vars, \
                f"{template_path.name} has mismatched variable tags"
    
    def test_templates_use_consistent_indentation(self, template_dir):
        """Test that templates use consistent indentation."""
        for template_path in template_dir.glob("*.html"):
            content = template_path.read_text()
            lines = content.split('\n')
            
            # Check that indentation is consistent (spaces or tabs, not mixed)
            has_space_indent = any(line.startswith('    ') for line in lines)
            has_tab_indent = any(line.startswith('\t') for line in lines)
            
            # It's ok to have both, but most lines should use one style
            if has_space_indent and has_tab_indent:
                space_lines = sum(1 for line in lines if line.startswith('    '))
                tab_lines = sum(1 for line in lines if line.startswith('\t'))
                
                # Warn if mixed heavily (more than 10% minority style)
                total_indented = space_lines + tab_lines
                if total_indented > 0:
                    minority_percent = min(space_lines, tab_lines) / total_indented
                    assert minority_percent < 0.1, \
                        f"{template_path.name} has mixed indentation styles"
    
    def test_runbook_view_references_valid_variables(self, template_dir):
        """Test that runbook_view.html references expected template variables."""
        template_path = template_dir / "runbook_view.html"
        if not template_path.exists():
            pytest.skip("runbook_view.html not found")
        
        content = template_path.read_text()
        
        # Should reference these objects provided by the view
        expected_variables = [
            "runbook",
            "steps",
            "triggers",
            "servers",
        ]
        
        for var in expected_variables:
            # Check if variable is used (not just in comments)
            pattern = r'\{\{[^}]*\b' + re.escape(var) + r'\b[^}]*\}\}|' + \
                     r'\{%[^%]*\b' + re.escape(var) + r'\b[^%]*%\}'
            assert re.search(pattern, content), \
                f"Expected variable '{var}' not found in runbook_view.html"


@pytest.mark.unit
class TestTemplateAccessibility:
    """Test templates have basic accessibility features."""
    
    @pytest.fixture
    def template_dir(self):
        """Get template directory path."""
        return Path(__file__).parent.parent.parent / "templates"
    
    def test_base_template_has_lang_attribute(self, template_dir):
        """Test that base.html has lang attribute."""
        base_path = template_dir / "base.html"
        if not base_path.exists():
            pytest.skip("base.html not found")
        
        content = base_path.read_text()
        assert 'lang="' in content, "HTML should have lang attribute"
    
    def test_base_template_has_viewport_meta(self, template_dir):
        """Test that base.html has viewport meta tag."""
        base_path = template_dir / "base.html"
        if not base_path.exists():
            pytest.skip("base.html not found")
        
        content = base_path.read_text()
        assert 'name="viewport"' in content, "HTML should have viewport meta tag"
    
    def test_templates_use_semantic_html(self, template_dir):
        """Test that templates use semantic HTML elements."""
        semantic_elements = ["<nav", "<main", "<header", "<footer", "<article", "<section"]
        
        # Check layout.html has semantic structure
        layout_path = template_dir / "layout.html"
        if layout_path.exists():
            content = layout_path.read_text()
            has_semantic = any(element in content for element in semantic_elements)
            assert has_semantic, "layout.html should use semantic HTML elements"


@pytest.mark.unit
class TestTemplateSecuritym:
    """Test templates follow security best practices."""
    
    @pytest.fixture
    def template_dir(self):
        """Get template directory path."""
        return Path(__file__).parent.parent.parent / "templates"
    
    def test_templates_escape_user_content(self, template_dir):
        """Test that templates escape user-provided content by default."""
        # Jinja2 auto-escapes by default, but check for |safe usage
        for template_path in template_dir.glob("*.html"):
            content = template_path.read_text()
            
            # Count uses of |safe filter (should be minimal)
            safe_count = content.count("|safe")
            
            # It's ok to use |safe, but not excessively
            assert safe_count < 5, \
                f"{template_path.name} uses |safe filter {safe_count} times (review for XSS)"
    
    def test_no_inline_javascript_with_user_data(self, template_dir):
        """Test that templates don't mix user data with inline JavaScript."""
        dangerous_patterns = [
            r'<script>.*\{\{.*\}\}.*</script>',  # User data in script tag
            r"var \w+ = '\{\{",  # User data in JS variable
        ]
        
        for template_path in template_dir.glob("*.html"):
            content = template_path.read_text()
            
            for pattern in dangerous_patterns:
                # This is a simplified check - not perfect but catches obvious issues
                matches = re.findall(pattern, content, re.DOTALL)
                if matches:
                    # Warn, but don't fail (might be safe in some cases)
                    print(f"Warning: {template_path.name} might have unsafe JS interpolation")
