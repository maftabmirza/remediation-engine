"""
Post-Incident Postmortem Service

Generates, edits, and publishes AI-powered post-incident review documents.

Data sources gathered during generation:
  - Alert (name, severity, labels, annotations, ai_analysis, recommendations)
  - IncidentMetrics  (MTTD / MTTA / MTTE / MTTR with real timestamps)
  - AlertCorrelation (correlated sibling alerts in the same incident)
  - RunbookExecution + StepExecution (every step command + outcome)
  - ExecutionOutcome (post-execution resolution rating from user feedback)
  - AnalysisFeedback (helpfulness/accuracy rating + what-actually-worked text)
  - SolutionOutcome  (knowledge / command solutions that succeeded)
  - AgentSession + AgentStep (AI troubleshooting commands run during incident)

Incident-first generation:
  - Primary path: ``generate_by_incident(incident_id, created_by)``
    Gathers the full incident evidence bundle via IncidentService and drives
    a richer LLM prompt with multi-alert context, change events, and ITSM data.
  - Compatibility path: ``generate(alert_id, created_by)``
    Resolves or creates an Incident for the alert first, then falls through to
    ``generate_by_incident()``.
"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import SessionLocal
from app.models import Alert, IncidentMetrics, SolutionOutcome, TerminalSession
from app.models_agent import AgentSession, AgentStep
from app.models_learning import AnalysisFeedback, ExecutionOutcome
from app.models_postmortem import PostmortemReport
from app.models_remediation import RunbookExecution, StepExecution
from app.models_troubleshooting import AlertCorrelation
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


def _td_minutes(start: Optional[datetime], end: Optional[datetime]) -> Optional[float]:
    """Return elapsed minutes between two timestamps, or None if either is missing."""
    if start is None or end is None:
        return None
    return round((end - start).total_seconds() / 60, 2)


class PostmortemService:
    """
    Service for generating and managing post-incident postmortem reports.

    Typical workflow (incident-first):
        1. ``generate_by_incident(incident_id, created_by)`` — AI builds draft
           from the full incident evidence bundle.
        2. Engineer reviews/edits via ``update()``.
        3. Add context via ``add_out_of_band_context()``.
        4. ``publish(postmortem_id, reviewed_by)`` — marks report as published.

    Alert compatibility path:
        ``generate(alert_id, created_by)`` resolves or creates an Incident for
        the alert first, then delegates to ``generate_by_incident()``.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_by_incident(
        self,
        incident_id: UUID,
        created_by: UUID,
        app_id: Optional[UUID] = None,
        skip_eligibility_check: bool = False,
    ) -> PostmortemReport:
        """
        Generate a draft postmortem from the full incident evidence bundle.

        This is the primary (incident-first) generation path.  It gathers
        all available evidence — alerts, runbook executions, agent sessions,
        change events, ITSM data — and produces a structured postmortem.

        Args:
            incident_id: UUID of the resolved Incident to generate from.
            created_by: UUID of the requesting user.
            app_id: Optional UUID of the related application.

        Returns:
            The newly created PostmortemReport (status="draft").

        Raises:
            HTTPException 404 if the incident is not found.
            HTTPException 502 if the LLM call fails.
        """
        from app.services.incident_service import IncidentService  # noqa: PLC0415

        inc_svc = IncidentService(self.db)
        evidence = await inc_svc.get_evidence(incident_id)
        incident = evidence["incident"]

        if not skip_eligibility_check:
            self._ensure_incident_is_generatable(incident)
        await self._ensure_no_existing_incident_postmortem(incident_id)

        # Build the evidence snapshot for the LLM (also builds remediation_actions)
        gathered = self._build_gathered_from_evidence(evidence)

        llm_output = await self._call_llm(gathered)

        report = PostmortemReport(
            title=f"Post-Incident Review: {incident.title}",
            incident_id=incident_id,
            app_id=app_id,
            status="draft",
            generated_by="ai",
            severity=incident.severity,
            incident_start=incident.started_at,
            incident_end=incident.resolved_at,
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
        logger.info("Generated postmortem %s for incident %s", report.id, incident_id)
        return report

    async def generate(
        self,
        alert_id: UUID,
        created_by: UUID,
        app_id: Optional[UUID] = None,
    ) -> PostmortemReport:
        """
        Generate a draft postmortem from incident data for *alert_id*.

        Alert compatibility path: resolves or creates an Incident for the
        alert, then delegates to ``generate_by_incident()``.

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
        from app.services.incident_service import IncidentService  # noqa: PLC0415

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

        # 2. Find or create an Incident for this alert
        inc_svc = IncidentService(self.db)
        incident = await inc_svc.find_or_create_incident_for_alert(alert)

        # 3. Delegate to incident-first generation path, but also carry the
        #    alert_id for backward compatibility / lineage.
        report = await self.generate_by_incident(
            incident_id=incident.id,
            created_by=created_by,
            app_id=app_id,
            skip_eligibility_check=True,
        )

        # Preserve alert_id for lineage / backward compatibility
        report.alert_id = alert_id
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
        if "status" in update_dict:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Use the publish endpoint to change postmortem status",
            )

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
        # Prefer incident-first regeneration when incident_id is present
        if report.incident_id is not None:
            return await self._regenerate_by_incident(report)

        if report.alert_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot regenerate postmortem without a linked alert or incident",
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
        report.metrics = gathered.get("metrics", {})
        report.remediation_actions = gathered.get("remediation_actions", [])
        report.out_of_band_context = preserved_oob
        report.updated_at = _utc_now()

        await self.db.commit()
        await self.db.refresh(report)
        return report

    def _ensure_incident_is_generatable(self, incident: Any) -> None:
        """Reject postmortem generation for incidents that are not yet eligible."""
        grace_elapsed = (
            incident.grace_period_ends_at is not None
            and incident.grace_period_ends_at <= _utc_now()
        )
        is_eligible = bool(incident.is_eligible_for_postmortem or grace_elapsed)

        if incident.status != "resolved" or not is_eligible:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Incident is not yet eligible for postmortem generation",
            )

    async def _ensure_no_existing_incident_postmortem(self, incident_id: UUID) -> None:
        """Reject duplicate postmortem generation for the same incident."""
        result = await self.db.execute(
            select(PostmortemReport).where(PostmortemReport.incident_id == incident_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Incident {incident_id} already has a postmortem report",
            )

    async def _regenerate_by_incident(self, report: PostmortemReport) -> PostmortemReport:
        """
        Re-generate AI sections using the incident evidence bundle.

        Preserves manual out-of-band context and manually-added timeline events.
        """
        from app.services.incident_service import IncidentService  # noqa: PLC0415

        preserved_oob = list(report.out_of_band_context or [])
        manual_timeline = [
            entry for entry in (report.timeline or [])
            if entry.get("manual", False)
        ]

        inc_svc = IncidentService(self.db)
        evidence = await inc_svc.get_evidence(report.incident_id)
        gathered = self._build_gathered_from_evidence(evidence)
        llm_output = await self._call_llm(gathered)

        merged_timeline = gathered.get("timeline", []) + manual_timeline
        merged_timeline.sort(key=lambda e: e.get("timestamp", ""))

        report.impact_summary = llm_output.get("impact_summary", "")
        report.root_cause = llm_output.get("root_cause", "")
        report.contributing_factors = llm_output.get("contributing_factors", [])
        report.action_items = llm_output.get("action_items", [])
        report.lessons_learned = llm_output.get("lessons_learned", "")
        report.timeline = merged_timeline
        report.metrics = gathered.get("metrics", {})
        report.remediation_actions = gathered.get("remediation_actions", [])
        report.incident_start = evidence["incident"].started_at
        report.incident_end = evidence["incident"].resolved_at
        report.severity = evidence["incident"].severity
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
        """
        Delete a draft postmortem.  Only drafts may be deleted.

        Note: Role-based authorization (admin only) is enforced at the router
        layer via ``require_role(['admin'])``.  This service method enforces
        only the *status* constraint.
        """
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

    def _build_gathered_from_evidence(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build the ``gathered`` dict consumed by ``_call_llm`` from an
        incident evidence bundle returned by ``IncidentService.get_evidence()``.
        """
        incident = evidence["incident"]
        alerts = evidence.get("alerts", [])
        timeline = evidence.get("timeline", [])
        executions = evidence.get("runbook_executions", [])
        change_events = evidence.get("change_events", [])
        agent_sessions = evidence.get("agent_sessions", [])
        terminal_sessions = evidence.get("terminal_sessions", [])
        # FK-linked sessions (directly associated with the alert)
        linked_agent_sessions = evidence.get("alert_linked_agent_sessions", agent_sessions)
        linked_terminal_sessions = evidence.get("alert_linked_terminal_sessions", terminal_sessions)
        itsm_event = evidence.get("itsm_event")

        # Add step execution events to the timeline
        for ex in executions:
            for step in getattr(ex, "step_executions", []) or []:
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

        # Add agent session summaries
        for session in agent_sessions:
            session_started_at = getattr(session, "created_at", None)
            if session_started_at:
                steps_summary = []
                for step in getattr(session, "steps", []) or []:
                    step_label = getattr(step, "step_type", None) or "step"
                    step_content = getattr(step, "content", None) or ""
                    if step_content:
                        steps_summary.append(f"{step_label}:{step_content[:40]}")
                    else:
                        steps_summary.append(step_label)
                tool_str = ", ".join(steps_summary[:5])
                timeline.append(
                    {
                        "timestamp": session_started_at.isoformat(),
                        "event": f"AI troubleshooting session (tools: {tool_str or 'none'})",
                        "source": "agent_session",
                        "manual": False,
                    }
                )

        for terminal_session in terminal_sessions:
            terminal_started_at = getattr(terminal_session, "started_at", None)
            if terminal_started_at:
                commands = _extract_terminal_commands_from_recording(
                    getattr(terminal_session, "recording_path", None),
                    limit=3,
                )
                server_name = _terminal_session_server_name(terminal_session)
                command_str = "; ".join(commands) if commands else "interactive terminal activity recorded"
                timeline.append(
                    {
                        "timestamp": terminal_started_at.isoformat(),
                        "event": f"Terminal session on {server_name}: {command_str}",
                        "source": "terminal_session",
                        "manual": False,
                    }
                )

        timeline.sort(key=lambda e: e.get("timestamp", ""))

        remediation_actions = _build_remediation_actions(
            executions,
            agent_sessions=linked_agent_sessions,
            terminal_sessions=linked_terminal_sessions,
            change_events=change_events,
            incident=incident,
        )

        # Build LLM snapshot
        change_summaries = [
            {
                "change_id": ce.change_id,
                "type": ce.change_type,
                "service": ce.service_name,
                "description": (ce.description or "")[:200],
                "timestamp": ce.timestamp.isoformat() if ce.timestamp else None,
                "impact_level": ce.impact_level,
            }
            for ce in change_events
        ]

        alert_snapshots = [
            {
                "alert_name": a.alert_name,
                "severity": a.severity,
                "instance": a.instance,
                "fired_at": a.timestamp.isoformat() if a.timestamp else None,
                "annotations": getattr(a, "annotations_json", {}) or {},
                "labels": getattr(a, "labels_json", {}) or {},
            }
            for a in alerts
        ]

        itsm_summary = None
        if itsm_event:
            itsm_summary = {
                "title": itsm_event.title,
                "status": itsm_event.status,
                "severity": itsm_event.severity,
                "service": itsm_event.service_name,
            }

        # Build detailed remediation evidence for the LLM
        # Use only FK-linked sessions — directly associated with the alert
        remediation_evidence: List[Dict[str, Any]] = []
        for session in linked_agent_sessions:
            steps_detail = []
            for step in getattr(session, "steps", []) or []:
                step_entry: Dict[str, Any] = {
                    "step_type": getattr(step, "step_type", None),
                    "command": (getattr(step, "content", None) or "")[:300],
                    "status": getattr(step, "status", None),
                }
                output = getattr(step, "output", None)
                if output:
                    step_entry["output"] = output[:500]
                exit_code = getattr(step, "exit_code", None)
                if exit_code is not None:
                    step_entry["exit_code"] = exit_code
                steps_detail.append(step_entry)
            remediation_evidence.append({
                "source": "agent_session",
                "goal": getattr(session, "goal", None),
                "summary": getattr(session, "summary", None),
                "status": getattr(session, "status", None),
                "steps": steps_detail[:20],
            })

        for ts in linked_terminal_sessions:
            commands = _extract_terminal_commands_from_recording(
                getattr(ts, "recording_path", None), limit=10,
            )
            server_name = _terminal_session_server_name(ts)
            if commands:
                remediation_evidence.append({
                    "source": "terminal_session",
                    "server": server_name,
                    "commands": commands,
                })

        snapshot: Dict[str, Any] = {
            "incident_title": incident.title,
            "incident_status": incident.status,
            "severity": incident.severity,
            "started_at": incident.started_at.isoformat() if incident.started_at else None,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "affected_services": incident.affected_services or [],
            "alert_count": len(alerts),
            "alerts": alert_snapshots,
            "timeline": timeline,
            "remediation_actions": remediation_actions,
            "remediation_evidence": remediation_evidence,
            "change_events": change_summaries,
            "terminal_sessions_count": len(terminal_sessions),
            "itsm_event": itsm_summary,
            "mttr_minutes": evidence.get("mttr_minutes"),
        }

        return {
            "snapshot": snapshot,
            "timeline": timeline,
            "remediation_actions": remediation_actions,
            "metrics": {
                "mttd_minutes": None,
                "mtta_minutes": None,
                "mtte_minutes": None,
                "mttr_minutes": evidence.get("mttr_minutes"),
            },
            "incident_start": incident.started_at,
            "incident_end": incident.resolved_at,
        }

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
                loop = asyncio.new_event_loop()
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


# ------------------------------------------------------------------
# Module-level helpers (pure functions — no DB access)
# ------------------------------------------------------------------

def _build_remediation_actions(
    executions: list,
    agent_sessions: Optional[list] = None,
    terminal_sessions: Optional[list] = None,
    change_events: Optional[list] = None,
    incident: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Build remediation_actions from runbooks, agent sessions, and fallback incident evidence."""
    actions: List[Dict[str, Any]] = []

    for ex in executions:
        entry: Dict[str, Any] = {
            "action": f"Executed runbook (id={ex.runbook_id})",
            "runbook_id": str(ex.runbook_id) if ex.runbook_id else None,
            "outcome": ex.status,
            "duration_minutes": None,
        }
        if ex.started_at and ex.completed_at:
            delta = ex.completed_at - ex.started_at
            entry["duration_minutes"] = round(delta.total_seconds() / 60, 2)
        actions.append(entry)

    for session in agent_sessions or []:
        session_summary = getattr(session, "summary", None)
        if not isinstance(session_summary, str) or not session_summary.strip():
            session_summary = None

        session_goal = getattr(session, "goal", None)
        if not isinstance(session_goal, str) or not session_goal.strip():
            session_goal = None

        command_steps = []
        for step in getattr(session, "steps", []) or []:
            step_type = getattr(step, "step_type", None) or "step"
            step_content = (getattr(step, "content", None) or "").strip()
            if step_content:
                command_steps.append(f"{step_type}: {step_content}")
            else:
                command_steps.append(step_type)

        action_text = (
            session_summary
            or "; ".join(command_steps[:3])
            or session_goal
            or "AI troubleshooting session executed"
        )

        duration_minutes = None
        created_at = getattr(session, "created_at", None)
        completed_at = getattr(session, "completed_at", None)
        if created_at and completed_at:
            duration_minutes = round((completed_at - created_at).total_seconds() / 60, 2)

        actions.append(
            {
                "action": action_text[:240],
                "runbook_id": None,
                "outcome": getattr(session, "status", None),
                "duration_minutes": duration_minutes,
            }
        )

    for terminal_session in terminal_sessions or []:
        commands = _extract_terminal_commands_from_recording(
            getattr(terminal_session, "recording_path", None),
            limit=3,
        )
        server_name = _terminal_session_server_name(terminal_session)
        action_text = "; ".join(commands)
        if not action_text:
            action_text = f"Interactive terminal session recorded on {server_name}"

        actions.append(
            {
                "action": action_text[:240],
                "runbook_id": None,
                "outcome": "recorded",
                "duration_minutes": _td_minutes(
                    getattr(terminal_session, "started_at", None),
                    getattr(terminal_session, "ended_at", None),
                ),
            }
        )

    if not actions and change_events:
        latest_change = max(
            change_events,
            key=lambda change: getattr(change, "timestamp", None) or datetime.min.replace(tzinfo=timezone.utc),
        )
        duration_minutes = None
        change_timestamp = getattr(latest_change, "timestamp", None)
        resolved_at = getattr(incident, "resolved_at", None) if incident is not None else None
        if change_timestamp and resolved_at:
            duration_minutes = round((resolved_at - change_timestamp).total_seconds() / 60, 2)

        change_label = getattr(latest_change, "change_id", None) or "recorded change"
        change_description = (getattr(latest_change, "description", None) or "").strip()
        action_text = f"Manual recovery following {change_label}"
        if change_description:
            action_text = f"{action_text}: {change_description}"

        actions.append(
            {
                "action": action_text[:240],
                "runbook_id": None,
                "outcome": "resolved" if getattr(incident, "status", None) == "resolved" else "recorded",
                "duration_minutes": duration_minutes,
            }
        )

    if not actions and getattr(incident, "status", None) == "resolved":
        actions.append(
            {
                "action": "Incident resolved through manual operator intervention; no tracked runbook or agent session was recorded.",
                "runbook_id": None,
                "outcome": "resolved",
                "duration_minutes": None,
            }
        )

    return actions


def _terminal_session_server_name(session: Any) -> str:
    """Return a human-friendly server label for a terminal session."""
    server = getattr(session, "server", None)
    if server is None:
        return str(getattr(session, "server_credential_id", "server"))
    return (
        getattr(server, "hostname", None)
        or getattr(server, "name", None)
        or str(getattr(session, "server_credential_id", "server"))
    )


def _read_terminal_recording(recording_path: Optional[str], max_bytes: int = 50_000) -> str:
    """Safely read terminal transcript content from the configured recording directory."""
    if not recording_path:
        return ""

    recording_dir = os.path.abspath(get_settings().recording_dir)
    path = os.path.abspath(recording_path)
    if not path.startswith(recording_dir + os.sep) and path != recording_dir:
        return ""
    if not os.path.exists(path):
        return ""

    try:
        with open(path, "rb") as handle:
            return handle.read(max_bytes).decode("utf-8", errors="replace")
    except OSError:
        return ""


def _extract_terminal_commands_from_recording(
    recording_path: Optional[str],
    limit: int = 5,
) -> List[str]:
    """Extract shell command lines from a terminal transcript."""
    content = _read_terminal_recording(recording_path)
    if not content:
        return []

    ansi_re = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    commands: List[str] = []
    seen: set[str] = set()

    for raw_line in content.splitlines():
        line = ansi_re.sub("", raw_line).strip()
        command = None
        if line.startswith("> "):
            command = line[2:].strip()
        elif line.startswith("$ "):
            command = line[2:].strip()
        elif line.startswith("# "):
            command = line[2:].strip()

        if not command or command in seen:
            continue

        seen.add(command)
        commands.append(command)
        if len(commands) >= limit:
            break

    return commands
