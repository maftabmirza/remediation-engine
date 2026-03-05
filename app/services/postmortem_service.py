"""
Postmortem Service
Generates, manages and publishes AI-assisted post-incident review reports.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Alert, IncidentMetrics
from app.models_learning import AnalysisFeedback, ExecutionOutcome
from app.models_postmortem import PostmortemReport
from app.models_remediation import RunbookExecution, StepExecution
from app.models_troubleshooting import AlertCorrelation
from app.schemas_postmortem import (
    OutOfBandContextAdd,
    PostmortemReportUpdate,
)

logger = logging.getLogger(__name__)

# Maximum characters to retain from a raw LLM response when JSON parsing fails.
# Keeps the fallback impact_summary reasonably sized without truncating structured data.
_MAX_FALLBACK_TEXT_LENGTH = 1000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _seconds_to_minutes(seconds: Optional[int]) -> Optional[float]:
    if seconds is None:
        return None
    return round(seconds / 60.0, 2)


class PostmortemService:
    """
    Service for generating and managing post-incident review reports.

    Gathers incident data (alerts, executions, metrics, feedback) and
    uses the LLM to generate structured postmortem content.
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
    ) -> PostmortemReport:
        """
        Generate a postmortem report for the given alert.

        Args:
            alert_id: UUID of the primary alert.
            created_by: UUID of the user triggering generation.

        Returns:
            A newly created PostmortemReport with status='draft'.

        Raises:
            HTTPException 404 if alert not found.
            HTTPException 502 if LLM call fails.
        """
        alert = await self._load_alert(alert_id)

        # Gather incident data
        gathered = await self._gather_incident_data(alert)

        # Build sorted timeline
        timeline = self._build_timeline(gathered)

        # Compute metrics
        metrics = self._compute_metrics(gathered, timeline)

        # LLM generation
        llm_sections = await self._call_llm(gathered)

        # Build action items from LLM output
        action_items = self._extract_action_items(llm_sections.get("action_items", []))

        # Determine incident bounds
        incident_start, incident_end = self._determine_incident_bounds(timeline, gathered)

        title = f"Post-Incident Review: {alert.alert_name} ({_utc_now().strftime('%Y-%m-%d')})"

        report = PostmortemReport(
            title=title,
            alert_id=alert_id,
            app_id=alert.app_id,
            status="draft",
            incident_start=incident_start,
            incident_end=incident_end,
            severity=alert.severity,
            timeline=[entry for entry in timeline],
            impact_summary=llm_sections.get("impact_summary"),
            root_cause=llm_sections.get("root_cause"),
            contributing_factors=llm_sections.get("contributing_factors", []),
            remediation_actions=gathered.get("remediation_actions", []),
            action_items=action_items,
            lessons_learned=llm_sections.get("lessons_learned"),
            metrics=metrics,
            generated_by="ai",
            out_of_band_context=[],
            created_by=created_by,
        )

        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def regenerate(self, postmortem_id: UUID) -> PostmortemReport:
        """
        Re-run AI generation while preserving manually-added context.

        Args:
            postmortem_id: UUID of the existing postmortem.

        Returns:
            Updated PostmortemReport.

        Raises:
            HTTPException 404 if not found.
        """
        report = await self._get_or_404(postmortem_id)

        # Preserve manual entries
        manual_timeline = [e for e in (report.timeline or []) if e.get("manual")]
        manual_oob = [e for e in (report.out_of_band_context or []) if e.get("source")]

        if report.alert_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot regenerate a postmortem without a linked alert",
            )

        alert = await self._load_alert(report.alert_id)
        gathered = await self._gather_incident_data(alert)
        timeline = self._build_timeline(gathered)

        # Re-inject manual timeline entries
        all_entries = timeline + manual_timeline
        all_entries.sort(key=lambda e: e.get("timestamp", ""))

        metrics = self._compute_metrics(gathered, all_entries)
        llm_sections = await self._call_llm(gathered)
        action_items = self._extract_action_items(llm_sections.get("action_items", []))
        incident_start, incident_end = self._determine_incident_bounds(all_entries, gathered)

        report.impact_summary = llm_sections.get("impact_summary")
        report.root_cause = llm_sections.get("root_cause")
        report.contributing_factors = llm_sections.get("contributing_factors", [])
        report.action_items = action_items
        report.lessons_learned = llm_sections.get("lessons_learned")
        report.timeline = all_entries
        report.out_of_band_context = manual_oob
        report.metrics = metrics
        report.incident_start = incident_start
        report.incident_end = incident_end
        report.updated_at = _utc_now()

        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def add_out_of_band_context(
        self,
        postmortem_id: UUID,
        entry: OutOfBandContextAdd,
    ) -> PostmortemReport:
        """
        Append a manual context entry to out_of_band_context.

        Args:
            postmortem_id: UUID of the postmortem.
            entry: OutOfBandContextAdd payload.

        Returns:
            Updated PostmortemReport.
        """
        report = await self._get_or_404(postmortem_id)

        new_entry: Dict[str, Any] = {
            "source": entry.source,
            "content": entry.content,
            "timestamp": (entry.timestamp or _utc_now()).isoformat(),
        }

        existing: List[Dict[str, Any]] = list(report.out_of_band_context or [])
        existing.append(new_entry)
        report.out_of_band_context = existing
        report.updated_at = _utc_now()

        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def publish(
        self,
        postmortem_id: UUID,
        reviewed_by: UUID,
    ) -> PostmortemReport:
        """
        Publish the postmortem (status='published') with reviewer attribution.

        Args:
            postmortem_id: UUID of the postmortem.
            reviewed_by: UUID of the reviewing user.

        Returns:
            Updated PostmortemReport.
        """
        report = await self._get_or_404(postmortem_id)

        report.status = "published"
        report.reviewed_by = reviewed_by
        report.updated_at = _utc_now()

        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def update(
        self,
        postmortem_id: UUID,
        data: PostmortemReportUpdate,
    ) -> PostmortemReport:
        """
        Apply manual edits to the postmortem.

        Args:
            postmortem_id: UUID of the postmortem.
            data: PostmortemReportUpdate payload.

        Returns:
            Updated PostmortemReport.
        """
        report = await self._get_or_404(postmortem_id)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(report, field, value)

        report.updated_at = _utc_now()
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def get_by_id(self, postmortem_id: UUID) -> PostmortemReport:
        """Retrieve a single postmortem by ID or raise 404."""
        return await self._get_or_404(postmortem_id)

    async def list_reports(
        self,
        app_id: Optional[UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[PostmortemReport], int]:
        """
        List postmortem reports with optional filters.

        Returns:
            Tuple of (items, total_count).
        """
        query = select(PostmortemReport)
        count_query = select(func.count()).select_from(PostmortemReport)

        conditions = []
        if app_id is not None:
            conditions.append(PostmortemReport.app_id == app_id)
        if status is not None:
            conditions.append(PostmortemReport.status == status)

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        # Total
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Page
        offset = (page - 1) * page_size
        query = query.order_by(PostmortemReport.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def delete(self, postmortem_id: UUID) -> None:
        """Delete a draft postmortem report."""
        report = await self._get_or_404(postmortem_id)
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

    async def _get_or_404(self, postmortem_id: UUID) -> PostmortemReport:
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

    async def _load_alert(self, alert_id: UUID) -> Alert:
        result = await self.db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if alert is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert {alert_id} not found",
            )
        return alert

    async def _gather_incident_data(self, alert: Alert) -> Dict[str, Any]:
        """Gather all incident data for LLM prompt and timeline construction."""
        data: Dict[str, Any] = {
            "alert": {
                "id": str(alert.id),
                "name": alert.alert_name,
                "severity": alert.severity,
                "instance": alert.instance,
                "status": alert.status,
                "fired_at": alert.timestamp.isoformat() if alert.timestamp else None,
                "labels": alert.labels_json or {},
                "annotations": alert.annotations_json or {},
            },
            "correlated_alerts": [],
            "executions": [],
            "metrics": None,
            "feedback": [],
            "remediation_actions": [],
        }

        # Correlated alerts
        if alert.correlation_id:
            corr_result = await self.db.execute(
                select(Alert).where(
                    and_(
                        Alert.correlation_id == alert.correlation_id,
                        Alert.id != alert.id,
                    )
                )
            )
            correlated = corr_result.scalars().all()
            data["correlated_alerts"] = [
                {
                    "id": str(a.id),
                    "name": a.alert_name,
                    "severity": a.severity,
                    "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                }
                for a in correlated
            ]

        # Runbook executions
        exec_result = await self.db.execute(
            select(RunbookExecution)
            .options(selectinload(RunbookExecution.step_executions))
            .where(RunbookExecution.alert_id == alert.id)
            .order_by(RunbookExecution.started_at)
        )
        executions = exec_result.scalars().all()
        exec_data = []
        remediation_actions = []
        for exe in executions:
            duration: Optional[float] = None
            if exe.started_at and exe.completed_at:
                duration = round(
                    (exe.completed_at - exe.started_at).total_seconds() / 60.0, 2
                )

            steps = [
                {
                    "step_name": s.step_name,
                    "status": s.status,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "output_summary": (s.stdout or "")[:200] if s.stdout else None,
                }
                for s in (exe.step_executions or [])
            ]

            exec_data.append(
                {
                    "runbook_id": str(exe.runbook_id),
                    "status": exe.status,
                    "started_at": exe.started_at.isoformat() if exe.started_at else None,
                    "completed_at": exe.completed_at.isoformat() if exe.completed_at else None,
                    "duration_minutes": duration,
                    "result_summary": exe.result_summary,
                    "steps": steps,
                }
            )

            remediation_actions.append(
                {
                    "action": f"Executed runbook {exe.runbook_id}",
                    "runbook_id": str(exe.runbook_id),
                    "outcome": exe.status,
                    "duration_minutes": duration,
                }
            )

        data["executions"] = exec_data
        data["remediation_actions"] = remediation_actions

        # Incident metrics
        metrics_result = await self.db.execute(
            select(IncidentMetrics).where(IncidentMetrics.alert_id == alert.id)
        )
        metrics = metrics_result.scalar_one_or_none()
        if metrics:
            data["metrics"] = {
                "mttd_minutes": _seconds_to_minutes(metrics.time_to_detect),
                "mtta_minutes": _seconds_to_minutes(metrics.time_to_acknowledge),
                "mtte_minutes": _seconds_to_minutes(metrics.time_to_engage),
                "mttr_minutes": _seconds_to_minutes(metrics.time_to_resolve),
                "incident_started": (
                    metrics.incident_started.isoformat()
                    if metrics.incident_started
                    else None
                ),
                "incident_resolved": (
                    metrics.incident_resolved.isoformat()
                    if metrics.incident_resolved
                    else None
                ),
            }

        # Analysis feedback
        feedback_result = await self.db.execute(
            select(AnalysisFeedback).where(AnalysisFeedback.alert_id == alert.id)
        )
        feedback_rows = feedback_result.scalars().all()
        data["feedback"] = [
            {
                "rating": fb.rating,
                "helpful": fb.helpful,
                "what_worked": fb.what_actually_worked,
                "what_was_missing": fb.what_was_missing,
            }
            for fb in feedback_rows
        ]

        return data

    def _build_timeline(self, gathered: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Construct a chronologically sorted timeline from gathered data."""
        entries: List[Dict[str, Any]] = []

        alert = gathered.get("alert", {})
        if alert.get("fired_at"):
            entries.append(
                {
                    "timestamp": alert["fired_at"],
                    "event": f"Alert '{alert.get('name')}' fired (severity: {alert.get('severity')})",
                    "source": "alert",
                    "manual": False,
                }
            )

        for ca in gathered.get("correlated_alerts", []):
            if ca.get("timestamp"):
                entries.append(
                    {
                        "timestamp": ca["timestamp"],
                        "event": f"Correlated alert '{ca.get('name')}' fired",
                        "source": "correlated_alert",
                        "manual": False,
                    }
                )

        for exe in gathered.get("executions", []):
            if exe.get("started_at"):
                entries.append(
                    {
                        "timestamp": exe["started_at"],
                        "event": f"Runbook execution started (runbook: {exe.get('runbook_id')})",
                        "source": "runbook_execution",
                        "manual": False,
                    }
                )
            for step in exe.get("steps", []):
                if step.get("started_at"):
                    entries.append(
                        {
                            "timestamp": step["started_at"],
                            "event": f"Step '{step.get('step_name')}' executed (status: {step.get('status')})",
                            "source": "step_execution",
                            "manual": False,
                        }
                    )
            if exe.get("completed_at"):
                entries.append(
                    {
                        "timestamp": exe["completed_at"],
                        "event": (
                            f"Runbook execution completed with status: {exe.get('status')}"
                        ),
                        "source": "runbook_execution",
                        "manual": False,
                    }
                )

        metrics = gathered.get("metrics") or {}
        if metrics.get("incident_resolved"):
            entries.append(
                {
                    "timestamp": metrics["incident_resolved"],
                    "event": "Incident resolved",
                    "source": "incident_metrics",
                    "manual": False,
                }
            )

        # Sort chronologically
        entries.sort(key=lambda e: e.get("timestamp") or "")
        return entries

    def _compute_metrics(
        self,
        gathered: Dict[str, Any],
        timeline: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute MTTD/MTTA/MTTE/MTTR from gathered data."""
        raw = gathered.get("metrics")
        if raw:
            return {
                "mttd_minutes": raw.get("mttd_minutes"),
                "mtta_minutes": raw.get("mtta_minutes"),
                "mtte_minutes": raw.get("mtte_minutes"),
                "mttr_minutes": raw.get("mttr_minutes"),
            }

        # Approximate MTTR from timeline if metrics table is unavailable
        timestamps = [e["timestamp"] for e in timeline if e.get("timestamp")]
        if len(timestamps) >= 2:
            try:

                def _parse_ts(ts: str) -> datetime:
                    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    return parsed

                first = _parse_ts(timestamps[0])
                last = _parse_ts(timestamps[-1])
                mttr = round((last - first).total_seconds() / 60.0, 2)
                return {"mttd_minutes": None, "mtta_minutes": None, "mtte_minutes": None, "mttr_minutes": mttr}
            except (ValueError, AttributeError):
                pass

        return {}

    def _determine_incident_bounds(
        self,
        timeline: List[Dict[str, Any]],
        gathered: Dict[str, Any],
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Determine incident start and end datetimes."""
        incident_start: Optional[datetime] = None
        incident_end: Optional[datetime] = None

        alert = gathered.get("alert", {})
        if alert.get("fired_at"):
            try:
                incident_start = datetime.fromisoformat(
                    alert["fired_at"].replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        metrics = gathered.get("metrics") or {}
        if metrics.get("incident_resolved"):
            try:
                incident_end = datetime.fromisoformat(
                    metrics["incident_resolved"].replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        # Fall back to last timeline entry
        if incident_end is None and timeline:
            last_ts = timeline[-1].get("timestamp")
            if last_ts:
                try:
                    incident_end = datetime.fromisoformat(
                        last_ts.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass

        return incident_start, incident_end

    async def _call_llm(self, gathered: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the LLM to generate postmortem sections.

        Returns:
            Dict with keys: impact_summary, root_cause, contributing_factors,
            lessons_learned, action_items.

        Raises:
            HTTPException 502 on LLM failure.
        """
        from app.services.llm_service import generate_completion
        from app.database import async_session_factory

        system_prompt = "You are an SRE expert generating a structured post-incident review."
        user_prompt = (
            "Given the following incident data, generate a JSON response with exactly "
            "these keys:\n"
            "1. impact_summary: A concise impact summary (2-3 sentences, include affected "
            "services and user impact)\n"
            "2. root_cause: Root cause analysis (what actually failed and why)\n"
            "3. contributing_factors: List of 3-5 contributing factor strings\n"
            "4. lessons_learned: What should change (paragraph)\n"
            "5. action_items: List of 3-5 objects with keys: description, owner (string or null), "
            "due_date (ISO date string or null), status (always 'open')\n\n"
            "Respond with ONLY a valid JSON object.\n\n"
            f"Incident data:\n{json.dumps(gathered, indent=2, default=str)}"
        )

        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        try:
            # generate_completion uses a sync Session internally
            async with async_session_factory() as llm_db:
                text, _ = await generate_completion(llm_db, full_prompt, json_mode=True)
        except Exception as exc:
            logger.error("LLM call failed during postmortem generation: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM call failed: {exc}",
            ) from exc

        return self._parse_llm_response(text)

    @staticmethod
    def _parse_llm_response(text: str) -> Dict[str, Any]:
        """Parse the LLM JSON response, falling back gracefully on errors."""
        # Strip markdown code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned

        try:
            data = json.loads(cleaned)
            return {
                "impact_summary": data.get("impact_summary", ""),
                "root_cause": data.get("root_cause", ""),
                "contributing_factors": data.get("contributing_factors", []),
                "lessons_learned": data.get("lessons_learned", ""),
                "action_items": data.get("action_items", []),
            }
        except (json.JSONDecodeError, ValueError):
            logger.warning("Could not parse LLM JSON response; returning raw text as impact_summary")
            return {
                "impact_summary": text[:_MAX_FALLBACK_TEXT_LENGTH],
                "root_cause": "",
                "contributing_factors": [],
                "lessons_learned": "",
                "action_items": [],
            }

    @staticmethod
    def _extract_action_items(raw_items: List[Any]) -> List[Dict[str, Any]]:
        """Normalise action items from LLM output."""
        result = []
        for item in raw_items:
            if isinstance(item, dict):
                result.append(
                    {
                        "description": item.get("description", ""),
                        "owner": item.get("owner"),
                        "due_date": item.get("due_date"),
                        "status": item.get("status", "open"),
                    }
                )
            elif isinstance(item, str):
                result.append(
                    {"description": item, "owner": None, "due_date": None, "status": "open"}
                )
        return result
