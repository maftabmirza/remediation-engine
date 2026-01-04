"""
Grafana Proxy Router

Proxies requests to Grafana with SSO authentication via X-WEBAUTH-USER header.
Enables transparent Grafana integration with automatic user provisioning.
"""

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
import httpx
import os
import re
from app.routers.auth import get_current_user
from app.models import User

router = APIRouter(
    prefix="/grafana",
    tags=["grafana"]
)

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def grafana_proxy(
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Proxy all Grafana requests with SSO authentication.

    This endpoint:
    1. Authenticates the user via AIOps auth (JWT)
    2. Passes X-WEBAUTH-USER header to Grafana for SSO
    3. Grafana auto-provisions the user on first access
    4. Proxies the request/response transparently

    Args:
        path: The Grafana path to proxy (e.g., "api/dashboards/home")
        request: The incoming FastAPI request
        current_user: The authenticated user (from JWT)

    Returns:
        Proxied response from Grafana
    """
    # Build target URL
    url = f"{GRAFANA_URL}/{path}"

    # Copy query parameters
    if request.url.query:
        url += f"?{request.url.query}"

    # Prepare headers for proxying
    headers = {}

    # Copy important headers
    for header_name, header_value in request.headers.items():
        # Skip headers that shouldn't be forwarded or might cause compression/encoding issues
        if header_name.lower() not in ['host', 'connection', 'content-length', 'accept-encoding']:
            headers[header_name] = header_value

    # Add SSO authentication header
    headers["X-WEBAUTH-USER"] = current_user.username

    # Set the correct host
    headers["Host"] = "grafana:3000"

    # Get request body if present
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        body = await request.body()

    # Proxy the request to Grafana
    # IMPORTANT: Do NOT follow redirects - let the browser handle them
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        try:
            response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body
            )

            # Prepare response headers
            response_headers = {}
            for header_name, header_value in response.headers.items():
                # Skip headers that cause issues with proxying or iframe embedding
                if header_name.lower() not in [
                    'content-encoding', # We want to serve decoded content if we modify it
                    'content-length',   # Length changes after modification
                    'transfer-encoding',
                    'x-frame-options',
                    'content-security-policy',
                    'x-content-security-policy',
                    'x-webkit-csp'
                ]:
                    # Rewrite Location headers to go through our proxy
                    if header_name.lower() == 'location':
                        if '/grafana' in header_value:
                            idx = header_value.find('/grafana')
                            header_value = header_value[idx:]
                        elif header_value.startswith(GRAFANA_URL):
                            header_value = header_value.replace(GRAFANA_URL, '/grafana')
                        elif header_value.startswith('/'):
                            header_value = f'/grafana{header_value}'
                    response_headers[header_name] = header_value

            # Process HTML responses for branding injection
            response_content = response.content
            
            # Check for HTML content type (case-insensitive)
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                try:
                    # httpx handles encoding if accessed via .text, but .content is raw bytes
                    # Since we stripped Accept-Encoding, it should be plain text (utf-8 usually)
                    html_content = response.content.decode('utf-8')
                    
                    # Inject inline CSS to hide Grafana branding
                    custom_css = '''<style>
                    /* Hide Grafana logo and branding */
                    .css-1drra8y, [href*="grafana.com"], img[src*="grafana_icon.svg"],
                    .css-yciab3-Logo, button[aria-label="Home"], a[aria-label="Go to home"],
                    .sidemenu__logo, header img[alt*="Grafana"], .navbar-logo,
                    [data-testid="grafana-logo"], [class*="GrafanaLogo"],
                    img[alt="Grafana"], a[href="/"] > img, .css-1mhnkuh {
                        display: none !important;
                        visibility: hidden !important;
                    }
                    /* Hide Grafana news panel and blog section */
                    [data-testid="news-panel"], .news-container,
                    [data-testid="homepage-news-feed"],
                    [data-testid="latest-from-blog"] {
                        display: none !important;
                    }
                    </style>
                    <script>
                    function hideGrafanaBranding() {
                        document.querySelectorAll('h1, h2, h3').forEach(el => {
                            const text = (el.textContent || '').trim();
                            if (text === 'Welcome to Grafana' || text === 'Welcome to AIOps' || 
                                text === 'Latest from the blog') {
                                el.style.display = 'none';
                            }
                        });
                        document.querySelectorAll('section, article, div').forEach(el => {
                            const heading = el.querySelector(':scope > h1, :scope > h2, :scope > h3, :scope > h4');
                            if (heading) {
                                const text = (heading.textContent || '').trim();
                                if (text === 'Latest from the blog') {
                                    el.style.display = 'none';
                                }
                            }
                        });
                    }
                    setTimeout(hideGrafanaBranding, 1000);
                    setTimeout(hideGrafanaBranding, 2500);
                    setTimeout(hideGrafanaBranding, 5000);
                    </script>'''
                    
                    if '</head>' in html_content:
                        html_content = html_content.replace('</head>', f'{custom_css}</head>')
                    
                    # Replace "Grafana" text with "AIOps"
                    html_content = re.sub(r'<title>([^<]*?)Grafana([^<]*?)</title>', 
                                         r'<title>\1AIOps\2</title>', 
                                         html_content, flags=re.IGNORECASE)
                    html_content = re.sub(r'>(\s*)Grafana(\s*)<', 
                                         r'>\1AIOps\2<', 
                                         html_content)

                    # INJECT AI AGENT WIDGET
                    ai_agent_injection = '''
                    <!-- AI Agent Widget Injection -->
                    <link href="/static/css/agent_widget.css" rel="stylesheet">
                    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
                    <script src="/static/js/agent_widget.js"></script>
                    <!-- End AI Agent Widget -->
                    '''
                    
                    # More robust injection: Try closing body tag, then case-insensitive regex, then append
                    if '</body>' in html_content:
                        html_content = html_content.replace('</body>', f'{ai_agent_injection}</body>')
                    else:
                        # Case insensitive regex replacement
                        html_content, count = re.subn(r'</body>', f'{ai_agent_injection}</body>', html_content, count=1, flags=re.IGNORECASE)
                        if count == 0:
                            # Fallback: Just append to end
                            html_content += ai_agent_injection
                    
                    response_content = html_content.encode('utf-8')
                except Exception as e:
                    print(f"Error injecting content into Grafana response: {e}")
                    # Fallback to original content
                    response_content = response.content

            # Return proxied response
            return Response(
                content=response_content,
                status_code=response.status_code,
                headers=response_headers
            )

        except httpx.RequestError as e:
            return Response(
                content=f"Error connecting to Grafana: {str(e)}",
                status_code=502,
                headers={"Content-Type": "text/plain"}
            )
