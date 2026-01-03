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
import asyncio
import websockets
from app.routers.auth import get_current_user
from app.models import User

router = APIRouter(
    prefix="/grafana",
    tags=["grafana"]
)

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")
GRAFANA_WS_URL = GRAFANA_URL.replace("http://", "ws://").replace("https://", "wss://")


@router.websocket("/api/live/ws")
async def grafana_websocket_proxy(websocket: WebSocket):
    """
    Proxy WebSocket connections for Grafana Live.
    This enables real-time dashboard updates.
    """
    await websocket.accept()
    
    # Get username from cookie/token for SSO
    username = "admin"  # Default fallback
    try:
        # Try to extract username from cookies
        cookies = websocket.cookies
        # You may need to decode JWT from access_token cookie
        # For now, use a simple approach
        if "access_token" in cookies:
            import jwt
            token = cookies.get("access_token")
            try:
                payload = jwt.decode(token, options={"verify_signature": False})
                username = payload.get("sub", "admin")
            except:
                pass
    except:
        pass
    
    # Connect to Grafana WebSocket
    grafana_ws_url = f"{GRAFANA_WS_URL}/api/live/ws"
    headers = {
        "X-WEBAUTH-USER": username,
        "Host": "grafana:3000"
    }
    
    try:
        async with websockets.connect(
            grafana_ws_url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=20
        ) as grafana_ws:
            # Create tasks for bidirectional message passing
            async def forward_to_grafana():
                try:
                    while True:
                        data = await websocket.receive_text()
                        await grafana_ws.send(data)
                except WebSocketDisconnect:
                    pass
                except Exception:
                    pass
            
            async def forward_to_client():
                try:
                    async for message in grafana_ws:
                        await websocket.send_text(message)
                except Exception:
                    pass
            
            # Run both directions concurrently
            await asyncio.gather(
                forward_to_grafana(),
                forward_to_client(),
                return_exceptions=True
            )
    except Exception as e:
        # Close client WebSocket on error
        try:
            await websocket.close(code=1011, reason=str(e)[:100])
        except:
            pass


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
                    html_content = re.sub(r'>(\s*)Grafana(\s*)<', 
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
