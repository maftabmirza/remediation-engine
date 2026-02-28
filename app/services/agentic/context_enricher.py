from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
import asyncio
import logging

from sqlalchemy.orm import Session

from app.services.mcp.client import MCPClient
from app.services.agentic.tools.mcp_adapters import MCPToolAdapter, SiftAdapter, OnCallAdapter
from app.services.similarity_service import SimilarityService
from app.models import Alert
from app.models_remediation import Runbook

logger = logging.getLogger(__name__)

@dataclass
class EnrichedContext:
    sift_analysis: Optional[str]
    oncall_info: Optional[str]
    similar_incidents: List[str]
    runbook_recommendation: Optional[str]
    alert_summary: str

class TroubleshootingContextEnricher:
    """
    Automates context gathering for troubleshooting sessions.
    Fetches data from Sift, OnCall, and internal historical data.
    """

    def __init__(
        self,
        db: Session,
        mcp_client: Optional[MCPClient],
        alert_id: UUID
    ):
        self.db = db
        self.mcp_client = mcp_client
        self.alert_id = alert_id
        
        self.mcp_adapter = MCPToolAdapter(mcp_client) if mcp_client else None
        self.sift_adapter = SiftAdapter(self.mcp_adapter) if self.mcp_adapter else None
        self.oncall_adapter = OnCallAdapter(self.mcp_adapter) if self.mcp_adapter else None

    async def enrich(self) -> EnrichedContext:
        """
        Gather all context in parallel where possible.
        """
        alert = self.db.query(Alert).filter(Alert.id == self.alert_id).first()
        if not alert:
            raise ValueError(f"Alert {self.alert_id} not found")

        alert_summary = f"Alert: {alert.name} (Severity: {alert.severity}) on {alert.instance} at {alert.timestamp}"

        # Define tasks
        tasks = []
        
        # 1. Sift Analysis (if available)
        if self.sift_adapter:
            # We assume we can derivation app_name and timeframe from alert
            # This is a simplification for the prototype
            tasks.append(self._safely_get_sift(alert))
        else:
            tasks.append(asyncio.sleep(0, result=None)) # Placeholder

        # 2. OnCall Info (if available)
        if self.oncall_adapter:
            tasks.append(self._safely_get_oncall())
        else:
            tasks.append(asyncio.sleep(0, result=None))

        # 3. Similar Incidents (Internal)
        tasks.append(self._get_similar_incidents())

        # 4. Runbook Recommendation (Internal)
        tasks.append(self._find_runbook(alert))

        # Execute parallel
        results = await asyncio.gather(*tasks)
        
        return EnrichedContext(
            sift_analysis=results[0],
            oncall_info=results[1],
            similar_incidents=results[2] or [],
            runbook_recommendation=results[3],
            alert_summary=alert_summary
        )

    async def _safely_get_sift(self, alert: Alert) -> Optional[str]:
        try:
            # Heuristic: use service label as app_name
            app_name = alert.labels.get("service") or alert.labels.get("app") or "default"
            # For demo, using fixed window or deriving from alert timestamp
            return await self.sift_adapter.investigate_errors(
                app_name=app_name,
                start_time=str(alert.timestamp),
                end_time="now" 
            )
        except Exception as e:
            logger.warning(f"Failed to get Sift analysis: {e}")
            return None

    async def _safely_get_oncall(self) -> Optional[str]:
        try:
            return await self.oncall_adapter.get_schedule()
        except Exception as e:
            logger.warning(f"Failed to get OnCall info: {e}")
            return None

    async def _get_similar_incidents(self) -> List[str]:
        try:
            # Since SimilarityService is sync (based on previous usage), we wrap it or call it directly if it's fast
            # But wait, in tool_registry it was called synchronously. 
            # Ideally this should be async or run in executor. For now, assuming it's fast enough or effectively sync.
            service = SimilarityService(self.db)
            result = service.find_similar_alerts(self.alert_id, limit=3)
            
            incidents = []
            if result and result.similar_incidents:
                for inc in result.similar_incidents:
                    incidents.append(f"{inc.alert_name} (Sim: {inc.similarity_score:.2f})")
            return incidents
        except Exception as e:
            logger.warning(f"Failed to get similar incidents: {e}")
            return []

    async def _find_runbook(self, alert: Alert) -> Optional[str]:
        try:
            # Simple heuristic search
            service = alert.labels.get("service")
            query = self.db.query(Runbook).filter(Runbook.enabled == True)
            if service:
                query = query.filter(Runbook.name.ilike(f"%{service}%"))
            
            runbook = query.first()
            if runbook:
                return f"Recommended Runbook: {runbook.name} (ID: {runbook.id})"
            return None
        except Exception as e:
            logger.warning(f"Failed to find runbook: {e}")
            return None
