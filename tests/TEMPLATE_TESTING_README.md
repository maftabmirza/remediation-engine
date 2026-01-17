# Template and View Testing

This directory contains tests that validate HTML template rendering and view pages work correctly.

## Test Coverage Added

### 1. Integration Tests (`test_runbook_views.py`)
Tests that verify HTTP endpoints return properly rendered HTML:

- **Authentication**: Verifies pages require authentication
- **Content Rendering**: Checks pages contain expected content (not just 200 OK)
- **HTML Structure**: Validates proper HTML5 structure
- **CSS Framework**: Ensures correct CSS framework usage (Tailwind, not Bootstrap)
- **UI Elements**: Verifies presence of navigation, buttons, forms, modals
- **Data Display**: Confirms runbook names, steps, and metadata appear in HTML

### 2. Unit Tests (`test_templates.py`)
Tests that validate template files directly:

- **Template Structure**: Checks correct base template inheritance
- **Jinja2 Syntax**: Validates template syntax (matching tags)
- **CSS Classes**: Detects Bootstrap vs Tailwind class usage
- **Variable References**: Ensures templates use correct variable names
- **Accessibility**: Checks for lang attributes, viewport meta tags, semantic HTML
- **Security**: Validates proper escaping, checks for XSS risks
- **Code Quality**: Verifies consistent indentation

## Running the Tests

### Run All View Tests
```bash
pytest tests/integration/test_runbook_views.py tests/unit/test_templates.py -v
```

### Run Integration Tests Only
```bash
pytest tests/integration/test_runbook_views.py -v
```

### Run Template Unit Tests Only
```bash
pytest tests/unit/test_templates.py -v
```

### Run Specific Test Class
```bash
pytest tests/integration/test_runbook_views.py::TestRunbookViewPages -v
```

### Run Single Test
```bash
pytest tests/integration/test_runbook_views.py::TestRunbookViewPages::test_runbook_view_contains_runbook_name -v
```

## What These Tests Catch

These tests would have caught the runbook view page issues:

1. **❌ Wrong Base Template**
   - `test_templates_extend_correct_base` - Checks templates extend `layout.html`
   
2. **❌ Bootstrap Classes in Tailwind Environment**
   - `test_runbook_view_no_bootstrap_classes` - Detects Bootstrap classes in templates
   - `test_runbook_view_has_correct_css_framework` - Validates Tailwind usage
   
3. **❌ Blank Page Content**
   - `test_runbook_view_contains_essential_sections` - Checks page has content > 1000 chars
   - `test_runbook_view_contains_runbook_name` - Verifies actual data renders
   
4. **❌ Missing Navigation**
   - `test_runbook_view_contains_essential_sections` - Checks for sidebar/nav elements
   
5. **❌ AttributeError in Code**
   - Would cause 500 error, caught by `test_runbook_view_renders_with_auth` expecting 200

## Test Fixtures

### Available Fixtures (from `conftest.py`)

- `test_client` - FastAPI TestClient with test database
- `auth_headers` - Authentication headers for protected endpoints
- `test_runbook` - Basic runbook for testing
- `test_runbook_with_steps` - Runbook with 2 steps for testing
- `test_db_session` - Database session for data setup

## Adding More Tests

### Example: Test New View Page

```python
@pytest.mark.integration
def test_my_new_view_page(test_client, auth_headers):
    """Test my new view page renders correctly."""
    response = test_client.get("/my-page", headers=auth_headers)
    
    assert response.status_code == 200
    html = response.text
    
    # Check content
    assert "Expected Title" in html
    assert len(html) > 1000
    
    # Check structure
    assert "<nav" in html.lower()
    assert "sidebar" in html.lower()
```

### Example: Test Template Validation

```python
def test_my_template_structure(template_dir):
    """Test my template has correct structure."""
    template_path = template_dir / "my_template.html"
    content = template_path.read_text()
    
    # Should extend layout
    assert '{% extends "layout.html"' in content
    
    # Should have required blocks
    assert "{% block content %}" in content
    
    # Should not use Bootstrap
    assert 'class="row"' not in content
```

## Continuous Integration

Add to your CI/CD pipeline:

```yaml
# .github/workflows/tests.yml
- name: Run Template Tests
  run: |
    pytest tests/unit/test_templates.py -v
    pytest tests/integration/test_runbook_views.py -v
```

## Test Markers

Tests use pytest markers for categorization:

- `@pytest.mark.unit` - Fast, no external dependencies
- `@pytest.mark.integration` - Requires database, app setup

Run by marker:
```bash
pytest -m unit -v           # Unit tests only
pytest -m integration -v    # Integration tests only
```

## Coverage Goals

- **Template Files**: 100% of templates validated
- **View Routes**: All HTML-returning routes tested
- **Content Validation**: Every page checks content length + key elements
- **Framework Consistency**: No mixed CSS frameworks

## When to Update Tests

Update these tests when:

1. Adding new view pages
2. Changing base templates
3. Switching CSS frameworks
4. Adding new template blocks
5. Modifying page layouts
6. Changing authentication requirements

## Troubleshooting

### Test Fails: "Page content is too short"
- Template not rendering properly
- Check if correct base template is used
- Verify template variables are passed from view

### Test Fails: "Bootstrap classes found"
- Template uses old Bootstrap classes
- Update to Tailwind equivalents
- Check template inheritance chain

### Test Fails: "Authentication required"
- Ensure `auth_headers` fixture is used
- Check if test database has user seeded
- Verify JWT token generation works

## Next Steps: Browser Testing

These tests validate backend rendering. For full UI validation:

1. **Add Playwright/Selenium** - Test actual browser rendering
2. **Visual Regression** - Screenshot comparison
3. **Accessibility Testing** - WCAG compliance checks
4. **Performance Testing** - Page load times

See [TEST_COVERAGE_ANALYSIS.md](../TEST_COVERAGE_ANALYSIS.md) for roadmap.
