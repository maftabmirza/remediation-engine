"""
Grafana Proxy Router

Proxies requests to Grafana with SSO authentication via X-WEBAUTH-USER header.
Enables transparent Grafana integration with automatic user provisioning.
"""

from fastapi import APIRouter, Depends, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import httpx
import os
import re
from app.routers.auth import get_current_user
from app.services.auth_service import get_current_user_optional
from app.models import User

router = APIRouter(
    prefix="/grafana",
    tags=["grafana"]
)

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")


# WebSocket endpoint to gracefully handle Grafana live connections
@router.websocket("/api/live/ws")
async def grafana_websocket(websocket: WebSocket):
    """
    Handle Grafana WebSocket connections.
    
    Grafana's live update feature requires WebSocket support which is not
    implemented in this proxy. Close connections gracefully.
    """
    await websocket.close(code=1000, reason="WebSocket not supported through proxy")


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def grafana_proxy(
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional)
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
    # Handle WebSocket connections - they fail auth so reject them gracefully
    if "websocket" in request.headers.get("upgrade", "").lower() or path.startswith("api/live/ws"):
        return Response(
            content="WebSocket live updates not supported through proxy",
            status_code=404,
            headers={"Content-Type": "text/plain"}
        )
    
    # Require authentication for non-WebSocket requests
    if not current_user:
        return Response(
            content="Authentication required",
            status_code=401,
            headers={"Content-Type": "text/plain"}
        )
    # Build target URL
    url = f"{GRAFANA_URL}/{path}"

    # Copy query parameters
    if request.url.query:
        url += f"?{request.url.query}"

    # Prepare headers for proxying
    headers = {}

    # Copy important headers
    for header_name, header_value in request.headers.items():
        # Skip headers that shouldn't be forwarded
        if header_name.lower() not in ['host', 'connection', 'content-length']:
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
    # This preserves authentication when Grafana redirects (e.g., / -> /login)
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
                    'content-encoding',
                    'content-length',
                    'transfer-encoding',
                    'x-frame-options',  # Remove frame-busting header
                    'content-security-policy',  # Remove CSP that restricts iframes
                    'x-content-security-policy',  # Legacy CSP header
                    'x-webkit-csp'  # WebKit CSP header
                ]:
                    # Rewrite Location headers to go through our proxy
                    if header_name.lower() == 'location':
                        # Grafana returns URLs with its configured root URL
                        # e.g., http://localhost:8080/grafana/ or http://grafana:3000/...
                        # We need to extract just the path and keep it relative to /grafana
                        
                        # Check if URL contains /grafana (Grafana's external URL pattern)
                        if '/grafana' in header_value:
                            # Extract everything after /grafana
                            idx = header_value.find('/grafana')
                            header_value = header_value[idx:]  # Keeps /grafana/...
                        elif header_value.startswith(GRAFANA_URL):
                            # Internal Grafana URL - rewrite to external
                            header_value = header_value.replace(GRAFANA_URL, '/grafana')
                        elif header_value.startswith('/'):
                            # Relative redirect - prefix with /grafana
                            header_value = f'/grafana{header_value}'
                    response_headers[header_name] = header_value

            # Process HTML responses for branding injection
            response_content = response.content
            if 'text/html' in response.headers.get('content-type', ''):
                try:
                    html_content = response.content.decode('utf-8')
                    
                    # Inject inline CSS to hide Grafana branding and logo
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
                    // Hide Grafana branding elements by exact text content
                    function hideGrafanaBranding() {
                        // Only target specific heading elements with exact text match
                        document.querySelectorAll('h1, h2, h3').forEach(el => {
                            const text = (el.textContent || '').trim();
                            if (text === 'Welcome to Grafana' || text === 'Welcome to AIOps' || 
                                text === 'Latest from the blog') {
                                el.style.display = 'none';
                            }
                        });
                        // Hide the news/blog section container - look for specific patterns
                        document.querySelectorAll('section, article, div').forEach(el => {
                            // Check direct children for blog heading
                            const heading = el.querySelector(':scope > h1, :scope > h2, :scope > h3, :scope > h4');
                            if (heading) {
                                const text = (heading.textContent || '').trim();
                                if (text === 'Latest from the blog') {
                                    el.style.display = 'none';
                                }
                            }
                        });
                    }
                    // Run after content loads - careful timing
                    setTimeout(hideGrafanaBranding, 1000);
                    setTimeout(hideGrafanaBranding, 2500);
                    setTimeout(hideGrafanaBranding, 5000);
                    </script>'''
                    if '</head>' in html_content:
                        html_content = html_content.replace('</head>', f'{custom_css}</head>')
                    
                    # Replace "Grafana" text with "AIOps" in specific contexts only
                    # Target title tags specifically to avoid unintended replacements
                    # Replace in title tags
                    html_content = re.sub(r'<title>([^<]*?)Grafana([^<]*?)</title>', 
                                         r'<title>\1AIOps\2</title>', 
                                         html_content, flags=re.IGNORECASE)
                    # Replace in visible text (between tags) but not in attributes or scripts
                    html_content = re.sub(r'>([^<]*?)Grafana([^<]*?)<', 
                                         r'>\1AIOps\2<', 
                                         html_content)
                    
                    response_content = html_content.encode('utf-8')
                except (UnicodeDecodeError, AttributeError):
                    # If decoding fails, use original content
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
