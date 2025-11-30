"""
Metrics endpoint for Prometheus
"""
from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

router = APIRouter(tags=["Metrics"])

ALERTS_RECEIVED = Counter('alerts_received_total', 'Total alerts received')
ANALYSIS_DURATION = Histogram('analysis_duration_seconds', 'Time spent on analysis')

@router.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
