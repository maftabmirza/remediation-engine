"""
Alerts API Router - Integration with Prometheus AlertManager

Fetches and displays alerts from Prometheus AlertManager.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import httpx
from app.database import get_db
from app.models_dashboards import PrometheusDatasource

router = APIRouter(
    prefix="/api/alerts",
    tags=["alerts"]
)


async def fetch_alertmanager_alerts(alertmanager_url: str) -> Dict[str, Any]:
    """
    Fetch alerts from Prometheus AlertManager API.

    Args:
        alertmanager_url: Base URL of AlertManager (e.g., http://localhost:9093)

    Returns:
        Dictionary containing alerts data
    """
    try:
        async with httpx.AsyncClient() as client:
            # Fetch alerts from AlertManager API
            response = await client.get(
                f"{alertmanager_url}/api/v2/alerts",
                timeout=10.0
            )
            response.raise_for_status()
            return {"alerts": response.json()}
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Failed to fetch alerts from AlertManager: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching alerts: {str(e)}")


@router.get("")
async def get_alerts(db: Session = Depends(get_db)):
    """
    Get all alerts from Prometheus AlertManager.

    This endpoint fetches alerts from the first available Prometheus datasource
    that has an AlertManager URL configured.

    Returns:
        {
            "alerts": [
                {
                    "labels": {...},
                    "annotations": {...},
                    "status": {
                        "state": "firing|pending",
                        "silencedBy": [...],
                        "inhibitedBy": [...]
                    },
                    "fingerprint": "...",
                    "startsAt": "...",
                    "endsAt": "..."
                }
            ]
        }
    """
    # Find a Prometheus datasource with AlertManager configured
    # For now, we'll try to infer the AlertManager URL from Prometheus URL
    datasource = db.query(PrometheusDatasource).first()

    if not datasource:
        raise HTTPException(status_code=404, detail="No Prometheus datasource configured")

    # Try to infer AlertManager URL from Prometheus URL
    # Typically AlertManager runs on port 9093, Prometheus on 9090
    prometheus_url = datasource.url.rstrip('/')

    # Try common AlertManager URLs
    alertmanager_urls = []

    # If Prometheus is on port 9090, try 9093
    if ':9090' in prometheus_url:
        alertmanager_urls.append(prometheus_url.replace(':9090', ':9093'))

    # Try same host with port 9093
    if '://' in prometheus_url:
        protocol, rest = prometheus_url.split('://', 1)
        host = rest.split(':')[0].split('/')[0]
        alertmanager_urls.append(f"{protocol}://{host}:9093")

    # Try the Prometheus URL itself (some setups proxy AlertManager through Prometheus)
    alertmanager_urls.append(prometheus_url)

    # Try each URL until one works
    last_error = None
    for url in alertmanager_urls:
        try:
            return await fetch_alertmanager_alerts(url)
        except HTTPException as e:
            last_error = e
            continue

    # If all failed, return empty alerts instead of error (AlertManager might not be configured)
    return {"alerts": []}


@router.get("/config")
async def get_alertmanager_config(db: Session = Depends(get_db)):
    """
    Get AlertManager configuration.

    Returns information about the configured AlertManager URL.
    """
    datasource = db.query(PrometheusDatasource).first()

    if not datasource:
        raise HTTPException(status_code=404, detail="No Prometheus datasource configured")

    prometheus_url = datasource.url.rstrip('/')

    # Infer AlertManager URL
    alertmanager_url = prometheus_url.replace(':9090', ':9093') if ':9090' in prometheus_url else prometheus_url

    return {
        "prometheus_url": prometheus_url,
        "alertmanager_url": alertmanager_url,
        "datasource_name": datasource.name
    }
