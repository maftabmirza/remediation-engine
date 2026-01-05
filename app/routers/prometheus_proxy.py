
from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
import httpx
import logging
from typing import Optional

from app.services.auth_service import get_current_user
from app.models import User
from app.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/prometheus",
    tags=["prometheus-proxy"]
)

settings = get_settings()
# Use internal docker networking if available, else localhost
PROMETHEUS_URL = "http://prometheus:9090"  # Docker service name

from starlette.background import BackgroundTask

# Use a single client or create per request? 
# Per request is safer for header/cookie isolation in robust proxies, though expensive.
# We will use per-request but managing the close.

@router.get("/{path:path}")
@router.post("/{path:path}")
async def proxy_prometheus(path: str, request: Request, current_user: User = Depends(get_current_user)):
    """
    Proxy all requests to Prometheus with support for Streaming and HTML Injection
    """
    target_path = f"/{path}" if path else "/"
    url = f"{PROMETHEUS_URL}{target_path}"
    
    # Filter headers
    headers = {}
    for key, value in request.headers.items():
        if key.lower() not in ['host', 'content-length', 'accept-encoding']:
            headers[key] = value
    # Force identity to allow us to read/modify content if needed (for HTML)
    # But for streaming (which might be compressed), we might want to respect it?
    # Actually, for SSE text/event-stream, it's usually identity.
    headers['Accept-Encoding'] = 'identity'

    # Read body for POST
    body = await request.body()
    
    client = httpx.AsyncClient(timeout=60.0) # Increased timeout, though streaming handles this differently
    req = client.build_request(
        method=request.method,
        url=url,
        headers=headers,
        params=request.query_params,
        content=body
    )

    try:
        response = await client.send(req, stream=True)
    except httpx.RequestError as exc:
        await client.aclose()
        logger.error(f"Prometheus proxy connection error: {exc}")
        return Response(content=f"Error connecting to Prometheus: {exc}", status_code=502)

    # Handle redirects
    if response.status_code in [301, 302, 307, 308] and 'location' in response.headers:
        await client.aclose() # Close immediately for simple redirect
        location = response.headers['location']
        if location.startswith(PROMETHEUS_URL):
            location = location.replace(PROMETHEUS_URL, "/prometheus")
        elif location.startswith("/"):
            location = f"/prometheus{location}"
        return Response(status_code=response.status_code, headers={"Location": location})

    content_type = response.headers.get('content-type', '')

    # CASE 1: HTML Injection
    if 'text/html' in content_type:
        try:
            # We must read the full content to inject
            content = await response.aread() 
            await client.aclose()
            
            html_content = content.decode('utf-8', errors='replace')
            
            # AI Agent & Theme Injection
            ai_agent_injection = '''
            <!-- AI Agent Widget & Theme Injection -->
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
            <link href="/static/css/agent_widget.css" rel="stylesheet">
            <link href="/static/css/prometheus_theme.css" rel="stylesheet">
            <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
            <script src="/static/js/agent_widget.js"></script>
            <!-- End AI Agent Widget -->
            '''
            
            if '</body>' in html_content:
                html_content = html_content.replace('</body>', f'{ai_agent_injection}</body>')
            else:
                html_content += ai_agent_injection

            return HTMLResponse(content=html_content, status_code=response.status_code)
            
        except Exception as e:
            await client.aclose()
            logger.error(f"Error injecting into Prometheus response: {e}")
            # Fallback to original content (if read happened? "content" variable might exist)
            # If fail, just return error
            return Response(content="Error processing response", status_code=500)

    # CASE 2: Streaming (SSE or otherwise)
    # If it's event-stream or we suspect a stream, we use StreamingResponse
    # For general API calls, StreamingResponse is also fine/better for large JSON.
    
    return StreamingResponse(
        response.aiter_raw(),
        status_code=response.status_code,
        headers=dict(response.headers), # Convert headers to dict
        background=BackgroundTask(client.aclose) # Close client when stream ends
    )
