"""
Post-Incident Postmortem Service

Generates, edits, and publishes AI-powered post-incident review documents.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Alert
from app.models_learning import AnalysisFeedback, ExecutionOutcome
from app.models_postmortem import PostmortemReport
from app.models_remediation import RunbookExecution, StepExecution
from app.schemas_postmortem import OutOfBandContextAdd, PostmortemReportUpdate

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(obj: Any) -> Any:
    """JSON-serialise datetime / UUID objects for the LLM prompt."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class PostmortemService:
    """
    Service for generating and managing post-incident postmortem reports.

    Typical workflow:
        1. ``generate(alert_id, created_by)`` — AI builds draft from incident data.
        2. Engineer reviews/edits via ``update()``.
        3. Add context via ``add_out_of_band_context()``.
        4. ``publish(postmortem_id, reviewed_by)`` — marks report as published.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        alert_id: UUID,
        created_by: UUID,
        app_id: Optional[UUID] = None,
    ) -> PostmortemReport:
        """
        Generate a draft postmortem from incident data for *alert_id*.

        Args:
            alert_id: UUID of the triggering alert.
            created_by: UUID of the requesting user.
            app_id: Optional UUID of the related application.

        Returns:
            The newly created PostmortemReport (status="draft").

        Raises:
            HTTPException 404 if the alert is not found.
            HTTPException 502 if the LLM call fails.
        """
        # 1. Load alert
        alert_result = await self.db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = alert_result.scalar_one_or_none()
        if alert is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert {alert_id} not found",
            )

        # 2. Gather incident data
        gathered = await self._gather_incident_data(alert)

        # 3. Call LLM
        llm_output = await self._call_llm(gathered)

        # 4. Build and persist the report
        report = PostmortemReport(
            title=f"Post-Incident Review: {alert.alert_name}",
            alert_id=alert_id,
            app_id=app_id,
            status="draft",
            generated_by="ai",
            severity=getattr(alert, "severity", None),
            incident_start=gathered.get("incident_start"),
            incident_end=gathered.get("incident_end"),
            timeline=gathered.get("timeline", []),
            metrics=gathered.get("metrics", {}),
            impact_summary=llm_output.get("impact_summary", ""),
            root_cause=llm_output.get("root_cause", ""),
            contributing_factors=llm_output.get("contributing_factors", []),
            remediation_actions=gathered.get("remediation_actions", []),
            action_items=llm_output.get("action_items", []),
            lessons_learned=llm_output.get("lessons_learned", ""),
            out_of_band_context=[],
            created_by=created_by,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def get(self, postmortem_id: UUID) -> PostmortemReport:
        """Return a postmortem by ID or raise 404."""
        result = await self.db.execute(
            select(PostmortemReport).where(PostmortemReport.id == postmortem_id)
        )
        report = result.scalar_one_or_none()
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Postmortem {postmortem_id} not found",
            )
        return report

    async def list_reports(
        self,
        app_id: Optional[UUID] = None,
        report_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple:
        """
        Return a paginated list of postmortem reports.

        Returns:
            Tuple of (items, total_count).
        """
        query = select(PostmortemReport)
        conditions = []
        if app_id:
            conditions.append(PostmortemReport.app_id == app_id)
        if report_status:
            conditions.append(PostmortemReport.status == report_status)
        if conditions:
            from sqlalchemy import and_  # noqa: PLC0415
            query = query.where(and_(*conditions))

        total_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = total_result.scalar_one()

        query = (
            query.order_by(PostmortemReport.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        items = result.scalars().all()
        return items, total

    async def update(
        self,
        postmortem_id: UUID,
        data: PostmortemReportUpdate,
    ) -> PostmortemReport:
        """Apply partial updates to a postmortem report."""
        report = await self.get(postmortem_id)

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            # Serialise nested Pydantic models to plain dicts/lists for JSONB storage
            if isinstance(value, list):
                value = [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in value
                ]
            elif hasattr(value, "model_dump"):
                value = value.model_dump()
            setattr(report, field, value)

        report.updated_at = _utc_now()
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def regenerate(self, postmortem_id: UUID) -> PostmortemReport:
        """
        Re-run AI generation preserving manual out-of-band context entries
        and any manually added timeline events.
        """
        report = await self.get(postmortem_id)

        # Load the alert
        if report.alert_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot regenerate postmortem without a linked alert",
            )

        alert_result = await self.db.execute(
            select(Alert).where(Alert.id == report.alert_id)
        )
        alert = alert_result.scalar_one_or_none()
        if alert is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert {report.alert_id} not found",
            )

        # Preserve manually added entries
        preserved_oob = [
            entry for entry in (report.out_of_band_context or [])
        ]
        manual_timeline = [
            entry for entry in (report.timeline or [])
            if entry.get("manual", False)
        ]

        gathered = await self._gather_incident_data(alert)
        llm_output = await self._call_llm(gathered)

        # Merge manual timeline events back in
        merged_timeline = gathered.get("timeline", []) + manual_timeline
        merged_timeline.sort(key=lambda e: e.get("timestamp", ""))

        report.impact_summary = llm_output.get("impact_summary", "")
        report.root_cause = llm_output.get("root_cause", "")
        report.contributing_factors = llm_output.get("contributing_factors", [])
        report.action_items = llm_output.get("action_items", [])
        report.lessons_learned = llm_output.get("lessons_learned", "")
        report.timeline = merged_timeline
        report.out_of_band_context = preserved_oob
        report.updated_at = _utc_now()

        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def add_out_of_band_context(
        self,
        postmortem_id: UUID,
        entry: OutOfBandContextAdd,
    ) -> PostmortemReport:
        """Append a manual context entry to the postmortem."""
        report = await self.get(postmortem_id)

        new_entry = {
            "source": entry.source,
            "content": entry.content,
            "timestamp": entry.timestamp.isoformat() if entry.timestamp else _utc_now().isoformat(),
        }

        current = list(report.out_of_band_context or [])
        current.append(new_entry)
        report.out_of_band_context = current
        report.updated_at = _utc_now()

        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def publish(
        self,
        postmortem_id: UUID,
        reviewed_by: UUID,
    ) -> PostmortemReport:
        """Mark a postmortem as published after review."""
        report = await self.get(postmortem_id)
        report.status = "published"
        report.reviewed_by = reviewed_by
        report.updated_at = _utc_now()
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def delete(self, postmortem_id: UUID) -> None:
        """Delete a draft postmortem.  Only drafts may be deleted."""
        report = await self.get(postmortem_id)
        if report.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft postmortems can be deleted",
            )
        await self.db.delete(report)
        await self.db.commit()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _gather_incident_data(self, alert: Alert) -> Dict[str, Any]:
        """
        Collect alert, execution, step, and feedback data for the LLM prompt.

        Returns a dict with keys: timeline, remediation_actions, metrics,
        incident_start, incident_end, and a snapshot dict for the LLM.
        """
        timeline: List[Dict[str, Any]] = []
        remediation_actions: List[Dict[str, Any]] = []

        fired_at = getattr(alert, "timestamp", None)
        if fired_at:
            timeline.append(
                {
                    "timestamp": fired_at.isoformat() if isinstance(fired_at, datetime) else str(fired_at),
                    "event": f"Alert fired: {alert.alert_name}",
                    "source": "alert",
                    "manual": False,
                }
            )

        incident_start = fired_at
        incident_end: Optional[datetime] = None

        # Load runbook executions
        exec_result = await self.db.execute(
            select(RunbookExecution)
            .options(selectinload(RunbookExecution.step_executions))
            .where(RunbookExecution.alert_id == alert.id)
            .order_by(RunbookExecution.started_at)
        )
        executions = exec_result.scalars().all()

        for ex in executions:
            if ex.started_at:
                timeline.append(
                    {
                        "timestamp": ex.started_at.isoformat(),
                        "event": f"Runbook execution started (id={ex.id})",
                        "source": "runbook_execution",
                        "manual": False,
                    }
                )
            for step in ex.step_executions or []:
                if step.started_at:
                    summary = (step.stdout or "")[:200] if step.stdout else ""
                    timeline.append(
                        {
                            "timestamp": step.started_at.isoformat(),
                            "event": f"Step '{step.step_name}': {step.status}. {summary}",
                            "source": "step_execution",
                            "manual": False,
                        }
                    )
            if ex.completed_at:
                timeline.append(
                    {
                        "timestamp": ex.completed_at.isoformat(),
                        "event": f"Runbook execution completed with status '{ex.status}'",
                        "source": "runbook_execution",
                        "manual": False,
                    }
                )
                if incident_end is None or ex.completed_at > incident_end:
                    incident_end = ex.completed_at

            # Remediation actions
            action_entry: Dict[str, Any] = {
                "action": f"Executed runbook (id={ex.runbook_id})",
                "runbook_id": str(ex.runbook_id) if ex.runbook_id else None,
                "outcome": ex.status,
                "duration_minutes": None,
            }
            if ex.started_at and ex.completed_at:
                delta = ex.completed_at - ex.started_at
                action_entry["duration_minutes"] = round(delta.total_seconds() / 60, 2)
            remediation_actions.append(action_entry)

        # Sort timeline chronologically
        timeline.sort(key=lambda e: e.get("timestamp", ""))

        # Compute basic metrics
        mttd: Optional[float] = None
        mttr: Optional[float] = None
        if incident_start and incident_end:
            mttr = round((incident_end - incident_start).total_seconds() / 60, 2)

        metrics: Dict[str, Any] = {
            "mttd_minutes": mttd,
            "mtta_minutes": None,
            "mtte_minutes": None,
            "mttr_minutes": mttr,
        }

        # Snapshot for LLM
        snapshot: Dict[str, Any] = {
            "alert_name": alert.alert_name,
            "severity": getattr(alert, "severity", None),
            "instance": getattr(alert, "instance", None),
            "fired_at": fired_at.isoformat() if isinstance(fired_at, datetime) else str(fired_at) if fired_at else None,
            "annotations": getattr(alert, "annotations_json", {}) or {},
            "labels": getattr(alert, "labels_json", {}) or {},
            "timeline": timeline,
            "remediation_actions": remediation_actions,
            "metrics": metrics,
            "executions_count": len(executions),
        }

        return {
            "snapshot": snapshot,
            "timeline": timeline,
            "remediation_actions": remediation_actions,
            "metrics": metrics,
            "incident_start": incident_start,
            "incident_end": incident_end,
        }

    async def _call_llm(self, gathered: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the LLM to generate postmortem narrative sections.

        Returns a dict with keys: impact_summary, root_cause,
        contributing_factors, lessons_learned, action_items.

        Raises:
            HTTPException 502 on LLM failure.
        """
        from app.database import SessionLocal  # noqa: PLC0415
        import asyncio  # noqa: PLC0415
        from app.services.llm_service import generate_completion  # noqa: PLC0415

        snapshot_json = json.dumps(gathered.get("snapshot", {}), indent=2, default=_serialize)

        system_prompt = "You are an SRE expert generating a structured post-incident review."
        user_prompt = (
            "Given the following incident data, generate:\n"
            "1. A concise impact summary (2-3 sentences, include affected services and user impact)\n"
            "2. Root cause analysis (what actually failed and why)\n"
            "3. Contributing factors (list of 3-5 items, return as JSON array of strings)\n"
            "4. Lessons learned (what should change)\n"
            "5. 3-5 concrete action items with suggested owners "
            "(return as JSON array of objects with keys: description, owner, due_date, status)\n\n"
            "Return your answer as a JSON object with keys: impact_summary, root_cause, "
            "contributing_factors, lessons_learned, action_items.\n\n"
            f"Incident data:\n{snapshot_json}"
        )

        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        try:
            def _sync_call():
                import asyncio as _asyncio  # noqa: PLC0415
                loop = _asyncio.new_event_loop()
                try:
                    with SessionLocal() as sync_db:
                        result = loop.run_until_complete(
                            generate_completion(sync_db, full_prompt, json_mode=True)
                        )
                    return result
                finally:
                    loop.close()

            analysis, _provider = await asyncio.get_event_loop().run_in_executor(
                None, _sync_call
            )
        except Exception as exc:
            logger.error("LLM call failed for postmortem generation: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM generation failed: {exc}",
            )

        # Parse JSON response
        try:
            # Strip markdown code fences if present
            cleaned = analysis.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```", 2)[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            if cleaned.endswith("```"):
                cleaned = cleaned[: cleaned.rfind("```")]
            parsed = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("LLM response was not valid JSON, using raw text: %s", exc)
            parsed = {
                "impact_summary": analysis,
                "root_cause": "",
                "contributing_factors": [],
                "lessons_learned": "",
                "action_items": [],
            }

        # Normalise types
        if isinstance(parsed.get("contributing_factors"), str):
            parsed["contributing_factors"] = [parsed["contributing_factors"]]
        if not isinstance(parsed.get("action_items"), list):
            parsed["action_items"] = []

        return parsed
