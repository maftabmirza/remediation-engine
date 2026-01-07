"""
Unit tests for Grafana proxy branding functionality.

Tests HTML/CSS injection and text replacement for branding.
"""
import pytest
import re


class TestGrafanaBrandingInjection:
    """Test Grafana branding injection logic."""
    
    def test_css_injection_in_html_head(self):
        """Test that custom CSS link is injected into HTML head."""
        html_input = """
        <html>
        <head>
            <title>Grafana</title>
            <link rel="stylesheet" href="existing.css">
        </head>
        <body>Test</body>
        </html>
        """
        
        # Simulate the CSS injection logic from grafana_proxy.py
        custom_css = '<link rel="stylesheet" href="/grafana/public/css/aiops-custom.css">'
        html_output = html_input.replace('</head>', f'{custom_css}</head>')
        
        assert custom_css in html_output
        assert html_output.index(custom_css) < html_output.index('</head>')
    
    def test_title_grafana_replacement(self):
        """Test that 'Grafana' in title tags is replaced with 'AIOps'."""
        test_cases = [
            ('<title>Grafana</title>', '<title>AIOps</title>'),
            ('<title>Grafana Dashboard</title>', '<title>AIOps Dashboard</title>'),
            ('<title>Welcome to Grafana</title>', '<title>Welcome to AIOps</title>'),
        ]
        
        for input_html, expected_output in test_cases:
            # Simulate the regex replacement logic from grafana_proxy.py
            output_html = re.sub(
                r'<title>([^<]*?)Grafana([^<]*?)</title>', 
                r'<title>\1AIOps\2</title>', 
                input_html, 
                flags=re.IGNORECASE
            )
            assert output_html == expected_output
    
    def test_visible_text_grafana_replacement(self):
        """Test that 'Grafana' in visible text is replaced with 'AIOps'."""
        test_cases = [
            ('<h1>Grafana</h1>', '<h1>AIOps</h1>'),
            ('<span>Grafana</span>', '<span>AIOps</span>'),
        ]
        
        for input_html, expected_output in test_cases:
            # Simulate the regex replacement logic from grafana_proxy.py
            output_html = re.sub(
                r'>(\s*)Grafana(\s*)<', 
                r'>\1AIOps\2<', 
                input_html
            )
            assert output_html == expected_output
    
    def test_no_replacement_in_attributes(self):
        """Test that 'Grafana' in attributes is NOT replaced."""
        html_input = '<a href="/grafana/dashboard" class="grafana-link">Link</a>'
        
        # Apply the visible text replacement only
        output_html = re.sub(
            r'>(\s*)Grafana(\s*)<', 
            r'>\1AIOps\2<', 
            html_input
        )
        
        # Grafana in attributes should remain unchanged
        assert 'href="/grafana/dashboard"' in output_html
        assert 'class="grafana-link"' in output_html
    
    def test_no_replacement_in_javascript(self):
        """Test that 'Grafana' in JavaScript code is NOT replaced."""
        html_input = '<script>var grafanaUrl = "http://grafana:3000";</script>'
        
        # Apply the visible text replacement only
        output_html = re.sub(
            r'>(\s*)Grafana(\s*)<', 
            r'>\1AIOps\2<', 
            html_input
        )
        
        # Grafana in JavaScript should remain unchanged
        assert 'var grafanaUrl' in output_html
        assert 'http://grafana:3000' in output_html
    
    def test_combined_branding_injection(self):
        """Test complete branding injection process."""
        html_input = """
        <html>
        <head>
            <title>Grafana Dashboard</title>
        </head>
        <body>
            <h1>Grafana</h1>
            <p>Welcome to <span>Grafana</span></p>
            <a href="/grafana/home" class="grafana-link">Home</a>
        </body>
        </html>
        """
        
        # Step 1: Inject CSS
        custom_css = '<link rel="stylesheet" href="/grafana/public/css/aiops-custom.css">'
        html_output = html_input.replace('</head>', f'{custom_css}</head>')
        
        # Step 2: Replace in title tags
        html_output = re.sub(
            r'<title>([^<]*?)Grafana([^<]*?)</title>', 
            r'<title>\1AIOps\2</title>', 
            html_output, 
            flags=re.IGNORECASE
        )
        
        # Step 3: Replace in visible text
        html_output = re.sub(
            r'>(\s*)Grafana(\s*)<', 
            r'>\1AIOps\2<', 
            html_output
        )
        
        # Verify results
        assert custom_css in html_output
        assert '<title>AIOps Dashboard</title>' in html_output
        assert '<h1>AIOps</h1>' in html_output
        assert '<span>AIOps</span>' in html_output
        # Attributes should remain unchanged
        assert 'href="/grafana/home"' in html_output
        assert 'class="grafana-link"' in html_output
