"""
Grafana Proxy Router

Proxies requests to Grafana with SSO authentication via X-WEBAUTH-USER header.
Enables transparent Grafana integration with automatic user provisioning.
"""

from fastapi import APIRouter, Depends, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
import asyncio
import httpx
import os
from urllib.parse import urlparse
import re
import logging
import websockets
from websockets.exceptions import ConnectionClosed
from app.database import get_db
from app.services.auth_service import get_current_user_optional, get_current_user_ws
from app.models import User

router = APIRouter(
    prefix="/grafana",
    tags=["grafana"]
)

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")
GRAFANA_SUB_PATH = os.getenv("GRAFANA_SUB_PATH", "/grafana")
logger = logging.getLogger(__name__)


def _get_grafana_base_url() -> str:
    parsed = urlparse(GRAFANA_URL)
    base_path = (parsed.path or "").rstrip("/")
    if base_path in ["", "/"]:
        base_path = GRAFANA_SUB_PATH.rstrip("/") if GRAFANA_SUB_PATH else ""
    return f"{parsed.scheme}://{parsed.netloc}{base_path}"


def _join_grafana_url(path: str) -> str:
    base = _get_grafana_base_url().rstrip("/")
    return f"{base}/{path.lstrip('/')}"


async def _proxy_grafana_websocket(websocket: WebSocket, db: Session, path: str) -> None:
    token = websocket.cookies.get("access_token")
    if not token:
        token = websocket.query_params.get("access_token")

    user = await get_current_user_ws(token, db) if token else None
    if not user:
        logger.info("Grafana WS rejected (no auth): path=%s client=%s", websocket.url.path, websocket.client)
        await websocket.close(code=4401, reason="Authentication required")
        return

    requested_protocols_header = websocket.headers.get("sec-websocket-protocol")
    requested_protocols = []
    if requested_protocols_header:
        requested_protocols = [p.strip() for p in requested_protocols_header.split(",") if p.strip()]

    # Accept with the first requested subprotocol (Grafana commonly uses one).
    await websocket.accept(subprotocol=requested_protocols[0] if requested_protocols else None)

    upstream_base = _get_grafana_base_url()
    if upstream_base.startswith("https://"):
        upstream_base = "wss://" + upstream_base[len("https://"):]
    elif upstream_base.startswith("http://"):
        upstream_base = "ws://" + upstream_base[len("http://"):]

    upstream_url = f"{upstream_base}/{path.lstrip('/')}"
    if websocket.url.query:
        upstream_url += f"?{websocket.url.query}"

    origin = websocket.headers.get("origin")
    extra_headers = {
        "X-WEBAUTH-USER": user.username,
    }
    # Forward the browser's Origin when present.
    if origin:
        extra_headers["Origin"] = origin

    try:
        async with websockets.connect(
            upstream_url,
            extra_headers=extra_headers,
            subprotocols=requested_protocols or None,
        ) as upstream_ws:

            async def client_to_upstream() -> None:
                try:
                    while True:
                        message = await websocket.receive()
                        if message.get("type") == "websocket.disconnect":
                            break
                        if message.get("text") is not None:
                            await upstream_ws.send(message["text"])
                        elif message.get("bytes") is not None:
                            await upstream_ws.send(message["bytes"])
                finally:
                    try:
                        await upstream_ws.close()
                    except Exception:
                        pass

            async def upstream_to_client() -> None:
                try:
                    async for message in upstream_ws:
                        if isinstance(message, (bytes, bytearray)):
                            await websocket.send_bytes(bytes(message))
                        else:
                            await websocket.send_text(str(message))
                finally:
                    try:
                        await websocket.close(code=1000)
                    except Exception:
                        pass

            await asyncio.gather(client_to_upstream(), upstream_to_client())

    except (WebSocketDisconnect, ConnectionClosed):
        # Normal disconnection flow (client closed tab or upstream closed connection)
        logger.debug("Grafana WS disconnected normally")
    except Exception as e:
        logger.exception(
            "Grafana WS proxy failed: upstream=%s user=%s origin=%s err=%s",
            upstream_url,
            getattr(user, "username", None),
            origin,
            repr(e),
        )
        try:
            await websocket.close(code=1011, reason="Grafana WebSocket proxy failed")
        except Exception:
            pass


# Generic WebSocket proxy for Grafana (covers /api/live/ws and datasource proxy WS).
@router.websocket("/{path:path}")
async def grafana_websocket_any(websocket: WebSocket, path: str, db: Session = Depends(get_db)):
    await _proxy_grafana_websocket(websocket, db, path)


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
    
    # Allow public static assets without authentication
    # Grafana CSS, JS, fonts, images are public and must load for the iframe to render
    # Normalize path to remove leading slashes for consistent checking
    clean_path = path.lstrip('/')
    
    is_public_asset = (
        clean_path.startswith("public/") or
        clean_path.startswith("favicon") or
        clean_path == "robots.txt"
    )
    
    # Debug logging for public asset detection
    if "runtime" in path or "mnb" in path: # mnb is random pattern just in case
        logger.info(f"Grafana Proxy Analysis: Path='{path}' | Clean='{clean_path}' | IsPublic={is_public_asset} | User={current_user}")

    # Require authentication for non-public, non-WebSocket requests
    if not current_user and not is_public_asset:
        return Response(
            content="Authentication required",
            status_code=401,
            headers={"Content-Type": "text/plain"}
        )
    # Build target URL
    url = _join_grafana_url(path)

    # Copy query parameters
    if request.url.query:
        url += f"?{request.url.query}"

    # Prepare headers for proxying
    headers = {}

    # Copy important headers
    for header_name, header_value in request.headers.items():
        # Skip headers that shouldn't be forwarded
        if header_name.lower() not in ['host', 'connection', 'content-length', 'accept-encoding']:
            headers[header_name] = header_value
    
    # Force no compression to ensure we can modify content
    headers['Accept-Encoding'] = 'identity'

    # Add SSO authentication header (only when user is authenticated)
    if current_user:
        headers["X-WEBAUTH-USER"] = current_user.username
    elif is_public_asset:
        # Force "admin" user for public assets to bypass login redirects
        headers["X-WEBAUTH-USER"] = "admin"
        if "runtime" in path:
            logger.info("Injecting Admin Header for Public Asset: %s", path)
    
    # Debug logging for troubleshooting
    if 'runtime' in path:
         logger.debug(f"Proxying Grafana request: {path} | UserHeader: {headers.get('X-WEBAUTH-USER')} | Public: {is_public_asset}")

    # Set the correct host
    parsed_grafana = urlparse(GRAFANA_URL)
    if parsed_grafana.netloc:
        headers["Host"] = parsed_grafana.netloc

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

            # Fallback for static assets when Grafana subpath config mismatches
            # If Grafana is not actually serving from /grafana internally, try root.
            if response.status_code == 404 and path.startswith("public/"):
                parsed = urlparse(GRAFANA_URL)
                root_base = f"{parsed.scheme}://{parsed.netloc}"
                fallback_url = f"{root_base}/{path.lstrip('/')}"
                try:
                    response = await client.request(
                        method=request.method,
                        url=fallback_url,
                        headers=headers,
                        content=body
                    )
                except httpx.RequestError:
                    pass

            # Prepare response headers
            response_headers = {}
            for header_name, header_value in response.headers.items():
                # Skip headers that cause issues with proxying or iframe embedding
                if header_name.lower() not in [
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
                        elif header_value.startswith(_get_grafana_base_url()):
                            # Internal Grafana URL - rewrite to external
                            header_value = header_value.replace(_get_grafana_base_url(), '/grafana')
                        elif header_value.startswith('/'):
                            # Relative redirect - prefix with /grafana
                            header_value = f'/grafana{header_value}'
                    response_headers[header_name] = header_value

            # Process manifest.json (skip rewrite as file likely doesn't exist in recent Grafana versions)
            
            # Process HTML responses for branding injection
            response_content = response.content
            if 'text/html' in response.headers.get('content-type', ''):
                try:
                    # Log modification attempt for debugging
                    # logger.info("Modifying HTML content for path: %s", path)
                    
                    html_content = response.content.decode('utf-8')
                    
                    # Ensure base tag points to /grafana/ so relative asset paths resolve correctly
                    if '<base ' in html_content:
                        html_content = re.sub(
                            r'<base\s+href=["\'][^"\']*["\']\s*/?>', 
                            '<base href="/grafana/">', 
                            html_content, 
                            flags=re.IGNORECASE
                        )
                    elif '<head>' in html_content:
                        html_content = html_content.replace('<head>', '<head><base href="/grafana/">')

                    # Rewrite absolute asset paths to include /grafana prefix
                    html_content = re.sub(
                        r'(["\'])/public/',
                        r'\1/grafana/public/',
                        html_content
                    )
                    html_content = re.sub(
                        r'(["\'])/build/',
                        r'\1/grafana/build/',
                        html_content
                    )
                    
                    # Rewrite relative paths used by dynamic script/module loaders
                    html_content = re.sub(
                        r'(["\'])public/build/',
                        r'\1/grafana/public/build/',
                        html_content
                    )
                    
                    # -------------------------------------------------------------------
                    # Inject frame-containment script to prevent Grafana JS from
                    # navigating or overwriting the parent page when embedded in
                    # a same-origin iframe.  The snippet runs before any other
                    # script and makes `window.top` resolve to the iframe's own
                    # window so that any `top.location = ...` becomes a no-op.
                    frame_guard = (
                        '<script>'
                        '(function(){'
                        'if(window.self!==window.top){'
                        'try{'
                        'Object.defineProperty(window,"top",{get:function(){return window.self},configurable:false});'
                        'Object.defineProperty(window,"parent",{get:function(){return window.self},configurable:false});'
                        '}catch(e){}'
                        '}'
                        '})();'
                        '</script>'
                    )
                    # Insert right after <head> (or after <base> if present)
                    if '<base href="/grafana/">' in html_content:
                        html_content = html_content.replace(
                            '<base href="/grafana/">',
                            '<base href="/grafana/">' + frame_guard,
                            1
                        )
                    elif '<head>' in html_content:
                        html_content = html_content.replace(
                            '<head>',
                            '<head>' + frame_guard,
                            1
                        )
                    
                    response_content = html_content.encode('utf-8')
                    
                    # We modified the body (or decoded/encoded), so ensure content-encoding/length are not misleading
                    response_headers.pop('content-encoding', None)
                    response_headers.pop('content-length', None)
                except (UnicodeDecodeError, AttributeError):
                    # Replace in title tags
                    html_content = re.sub(r'<title>([^<]*?)Grafana([^<]*?)</title>', 
                                         r'<title>\1AIOps\2</title>', 
                                         html_content, flags=re.IGNORECASE)
                    # Replace in visible text (between tags) but not in attributes or scripts
                    html_content = re.sub(r'>([^<]*?)Grafana([^<]*?)<', 
                                         r'>\1AIOps\2<', 
                                         html_content)
                    
                    response_content = html_content.encode('utf-8')
                    # We modified the body, so ensure content-encoding/length are not misleading
                    response_headers.pop('content-encoding', None)
                    response_headers.pop('content-length', None)
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
