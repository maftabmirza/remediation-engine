"""
Grafana Proxy Router

Proxies requests to Grafana with SSO authentication via X-WEBAUTH-USER header.
Enables transparent Grafana integration with automatic user provisioning.
"""

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
import httpx
import os
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
                # Skip headers that cause issues with proxying
                if header_name.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']:
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

            # Return proxied response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers
            )

        except httpx.RequestError as e:
            return Response(
                content=f"Error connecting to Grafana: {str(e)}",
                status_code=502,
                headers={"Content-Type": "text/plain"}
            )
