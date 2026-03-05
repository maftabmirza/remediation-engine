"""
Runbook Auto-Generation Service (Feature B2).

Mines successful agent troubleshooting sessions to automatically generate
reusable runbook drafts.  No manual curation required — transforms tribal
knowledge into codified automation.
"""
import asyncio
import json
import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SolutionOutcome
from app.models_agent import AgentSession, AgentStep
from app.models_remediation import CommandBlocklist, Runbook, RunbookStep
from app.schemas_runbook_generation import (
    GeneratedStepPreview,
    GenerationCandidate,
    RunbookDraftResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Non-idempotent command patterns (regex fragments matched case-insensitively)
# ---------------------------------------------------------------------------
_DESTRUCTIVE_PATTERNS: List[str] = [
    r"\brm\b",
    r"\bdrop\b",
    r"\bdelete\b",
    r"\btruncate\b",
    r"\bkill\b",
    r"\bformat\b",
    r"\bmkfs\b",
]

_DESTRUCTIVE_RE = re.compile("|".join(_DESTRUCTIVE_PATTERNS), re.IGNORECASE)


def _serialize_dt(obj: Any) -> str:
    """JSON serialiser for datetime / UUID objects."""
    import uuid
    from datetime import datetime

    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _extract_variables(template: str) -> List[str]:
    """Return all unique Jinja2 ``{{ variable_name }}`` placeholders in *template*."""
    return list(dict.fromkeys(re.findall(r"\{\{\s*(\w+)\s*\}\}", template)))


def _is_non_idempotent(command: str) -> bool:
    """Return True when *command* looks potentially destructive / non-idempotent."""
    return bool(_DESTRUCTIVE_RE.search(command))


def _goal_similarity(goal_a: str, goal_b: str) -> float:
    """Quick text-similarity score between two goal strings (0–1)."""
    return SequenceMatcher(None, goal_a.lower(), goal_b.lower()).ratio()


class RunbookGenerationService:
    """
    Service for mining successful agent sessions and auto-generating runbooks.

    Typical workflow:
        1. ``find_generation_candidates()`` — discover clusters of similar sessions.
        2. ``generate_runbook()`` — LLM-powered generation from a set of sessions.
        3. ``approve_draft()`` — human approval activates the runbook.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def find_generation_candidates(
        self,
        min_success_count: int = 3,
    ) -> List[GenerationCandidate]:
        """
        Discover clusters of similar completed sessions that have enough
        successful outcomes to warrant runbook generation.

        Args:
            min_success_count: Minimum sessions required to surface a cluster.

        Returns:
            List of GenerationCandidate, sorted by session_count descending.
        """
        # 1. Load completed sessions that have resolved SolutionOutcomes
        sessions_result = await self.db.execute(
            select(AgentSession).where(AgentSession.status == "completed")
        )
        sessions: List[AgentSession] = sessions_result.scalars().all()

        if not sessions:
            return []

        # 2. Find session IDs that have a resolved SolutionOutcome
        session_ids = [s.id for s in sessions]
        outcomes_result = await self.db.execute(
            select(SolutionOutcome).where(
                SolutionOutcome.session_id.in_(session_ids),
                SolutionOutcome.success.is_(True),
            )
        )
        resolved_ids: set = {
            o.session_id for o in outcomes_result.scalars().all()
            if o.session_id is not None
        }

        resolved_sessions = [s for s in sessions if s.id in resolved_ids]
        if not resolved_sessions:
            return []

        # 3. Cluster sessions by goal similarity (cosine ≥ 0.85 approximated via
        #    SequenceMatcher; pgvector embeddings not yet stored on AgentSession).
        clusters: List[List[AgentSession]] = []
        for session in resolved_sessions:
            placed = False
            for cluster in clusters:
                if _goal_similarity(session.goal, cluster[0].goal) >= 0.85:
                    cluster.append(session)
                    placed = True
                    break
            if not placed:
                clusters.append([session])

        # 4. Filter by min_success_count
        candidates: List[GenerationCandidate] = []
        for cluster in clusters:
            if len(cluster) < min_success_count:
                continue

            cluster_ids = [s.id for s in cluster]

            # Extract sample commands from AgentStep
            steps_result = await self.db.execute(
                select(AgentStep).where(
                    AgentStep.agent_session_id.in_(cluster_ids),
                    AgentStep.step_type == "command",
                    AgentStep.status == "executed",
                )
            )
            steps: List[AgentStep] = steps_result.scalars().all()
            representative_commands = list(
                dict.fromkeys(s.content for s in steps if s.content)
            )[:5]

            # Compute average resolution minutes from SolutionOutcomes
            outcomes_res = await self.db.execute(
                select(SolutionOutcome).where(
                    SolutionOutcome.session_id.in_(cluster_ids),
                    SolutionOutcome.success.is_(True),
                )
            )
            outcomes = outcomes_res.scalars().all()

            completed_at_times = [
                s.completed_at for s in cluster if s.completed_at and s.created_at
            ]
            avg_minutes: Optional[float] = None
            if completed_at_times:
                deltas = [
                    (s.completed_at - s.created_at).total_seconds() / 60
                    for s in cluster
                    if s.completed_at and s.created_at
                ]
                avg_minutes = round(sum(deltas) / len(deltas), 2) if deltas else None

            candidates.append(
                GenerationCandidate(
                    session_ids=cluster_ids,
                    session_count=len(cluster),
                    goal_summary=cluster[0].goal,
                    app_id=None,
                    success_rate=1.0,
                    avg_resolution_minutes=avg_minutes,
                    representative_commands=representative_commands,
                )
            )

        # 5. Sort by session_count descending
        candidates.sort(key=lambda c: c.session_count, reverse=True)
        return candidates

    async def generate_runbook(
        self,
        session_ids: List[UUID],
        runbook_name: Optional[str],
        app_id: Optional[UUID],
        created_by: UUID,
    ) -> Runbook:
        """
        Generate a runbook from the given agent sessions using LLM.

        Args:
            session_ids: IDs of agent sessions to mine.
            runbook_name: Optional override for the runbook name.
            app_id: Optional application association.
            created_by: UUID of the requesting user.

        Returns:
            The newly created Runbook (enabled=False, requires approval).

        Raises:
            ValueError: If a generated command matches the blocklist.
            HTTPException 502: If the LLM call fails.
        """
        # 1. Load successful command steps for the given sessions
        steps_result = await self.db.execute(
            select(AgentStep).where(
                AgentStep.agent_session_id.in_(session_ids),
                AgentStep.step_type == "command",
                AgentStep.status == "executed",
            )
        )
        steps: List[AgentStep] = steps_result.scalars().all()

        command_sequences = [
            {
                "command": s.content,
                "reasoning": s.reasoning or "",
                "output_preview": (s.output or "")[:200],
            }
            for s in steps
            if s.content
        ]

        # 2. Scan for non-idempotent patterns (pre-LLM check)
        requires_review_reasons: List[str] = []
        for cmd_info in command_sequences:
            if _is_non_idempotent(cmd_info["command"]):
                requires_review_reasons.append(
                    f"Potentially destructive command detected: {cmd_info['command'][:80]}"
                )

        # 3. Call LLM to generate generalised runbook
        n = len(session_ids)
        llm_output = await self._call_llm(command_sequences, n)

        # 4. Validate generated commands against CommandBlocklist
        blocklist_result = await self.db.execute(
            select(CommandBlocklist).where(CommandBlocklist.enabled.is_(True))
        )
        blocklist: List[CommandBlocklist] = blocklist_result.scalars().all()

        for step_data in llm_output.get("steps", []):
            cmd_template = step_data.get("command_template", "")
            for bl_entry in blocklist:
                if self._matches_blocklist(cmd_template, bl_entry):
                    raise ValueError(
                        f"Generated command matches blocklist pattern "
                        f"'{bl_entry.pattern}': {cmd_template[:80]}"
                    )

        # 5. Build non-idempotent reasons list from generated steps
        for step_data in llm_output.get("steps", []):
            cmd_template = step_data.get("command_template", "")
            if _is_non_idempotent(cmd_template):
                reason = f"Non-idempotent step '{step_data.get('name', 'unknown')}' requires guard"
                if reason not in requires_review_reasons:
                    requires_review_reasons.append(reason)

        # 6. Create Runbook record
        auto_name = runbook_name or llm_output.get(
            "name", f"Auto-Generated Runbook ({n} sessions)"
        )
        description = (
            llm_output.get("description", "")
            + f"\n\nAuto-generated from {n} sessions. Requires human review before activation."
        ).strip()

        runbook = Runbook(
            name=auto_name,
            description=description,
            source="auto_generated",
            enabled=False,
            auto_execute=False,
            created_by=created_by,
        )
        self.db.add(runbook)
        await self.db.flush()  # get runbook.id

        # 7. Create RunbookStep records
        for idx, step_data in enumerate(llm_output.get("steps", []), start=1):
            cmd_template = step_data.get("command_template", "")
            step = RunbookStep(
                runbook_id=runbook.id,
                step_order=idx,
                name=step_data.get("name", f"Step {idx}"),
                description=step_data.get("name", ""),
                step_type=step_data.get("step_type", "command"),
                command_linux=cmd_template,
                rollback_command_linux=step_data.get("rollback_command") or None,
            )
            self.db.add(step)

        await self.db.commit()
        await self.db.refresh(runbook)
        return runbook

    async def approve_draft(
        self,
        runbook_id: UUID,
        approved_by: UUID,
        enable_auto_trigger: bool = False,
    ) -> Runbook:
        """
        Approve a draft runbook for production use.

        Sets ``enabled = True`` and optionally ``auto_execute = True``.

        Args:
            runbook_id: UUID of the runbook to approve.
            approved_by: UUID of the approving user.
            enable_auto_trigger: Whether to enable automatic execution.

        Returns:
            The updated Runbook.

        Raises:
            HTTPException 404 if the runbook does not exist.
        """
        result = await self.db.execute(
            select(Runbook).where(Runbook.id == runbook_id)
        )
        runbook = result.scalar_one_or_none()
        if runbook is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Runbook {runbook_id} not found",
            )

        runbook.enabled = True
        runbook.auto_execute = enable_auto_trigger

        await self.db.commit()
        await self.db.refresh(runbook)
        return runbook

    async def list_drafts(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple:
        """
        Return paginated auto-generated runbooks that have not yet been approved.

        Returns:
            Tuple of (items, total_count).
        """
        query = select(Runbook).where(
            Runbook.source == "auto_generated",
            Runbook.enabled.is_(False),
        )

        total_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = total_result.scalar_one()

        query = (
            query
            .order_by(Runbook.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        items = result.scalars().all()
        return items, total

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _matches_blocklist(self, command: str, entry: CommandBlocklist) -> bool:
        """Return True if *command* matches a blocklist *entry*."""
        pattern = entry.pattern
        pattern_type = entry.pattern_type or "contains"
        try:
            if pattern_type == "regex":
                return bool(re.search(pattern, command, re.IGNORECASE))
            elif pattern_type == "exact":
                return command.strip() == pattern.strip()
            else:  # contains
                return pattern.lower() in command.lower()
        except re.error:
            # Malformed regex pattern — treat as plain substring match
            return pattern.lower() in command.lower()

    def _build_runbook_response(
        self,
        runbook: Runbook,
        steps: List[RunbookStep],
        session_count: int,
    ) -> RunbookDraftResponse:
        """Build a RunbookDraftResponse from a Runbook ORM instance."""
        step_previews: List[GeneratedStepPreview] = []
        all_variables: List[str] = []
        requires_review_reasons: List[str] = []

        for s in sorted(steps, key=lambda x: x.step_order):
            cmd = s.command_linux or ""
            variables = _extract_variables(cmd)
            non_idempotent = _is_non_idempotent(cmd)
            step_previews.append(
                GeneratedStepPreview(
                    step_number=s.step_order,
                    name=s.name,
                    step_type=s.step_type or "command",
                    command_template=cmd,
                    variables_required=variables,
                    is_idempotent=None if non_idempotent else True,
                    requires_human_review=non_idempotent,
                )
            )
            all_variables.extend(variables)
            if non_idempotent:
                reason = f"Step '{s.name}' contains non-idempotent operation"
                if reason not in requires_review_reasons:
                    requires_review_reasons.append(reason)

        unique_vars = list(dict.fromkeys(all_variables))
        return RunbookDraftResponse(
            runbook_id=runbook.id,
            name=runbook.name,
            description=runbook.description or "",
            source="auto_generated",
            auto_trigger_enabled=bool(runbook.auto_execute),
            steps=step_previews,
            variables=unique_vars,
            requires_review_reasons=requires_review_reasons,
            session_count=session_count,
        )

    async def _call_llm(
        self,
        command_sequences: List[Dict[str, Any]],
        n: int,
    ) -> Dict[str, Any]:
        """
        Call the LLM to produce a generalised runbook from command sequences.

        Returns:
            Dict with keys: name, description, steps.

        Raises:
            HTTPException 502 on LLM failure.
        """
        from app.database import SessionLocal  # noqa: PLC0415
        from app.services.llm_service import generate_completion  # noqa: PLC0415

        system_prompt = (
            "You are an SRE expert creating reusable runbooks from successful "
            "troubleshooting sessions."
        )
        user_prompt = (
            f"Given these successful command sequences from {n} real incidents, "
            "generate a generalized runbook.\n\n"
            "REQUIREMENTS:\n"
            "- Replace hardcoded values (hostnames, IPs, service names, thresholds) "
            "with Jinja2 {{ variable_name }} placeholders\n"
            "- Add conditional steps using if/else logic where appropriate\n"
            "- Include rollback steps for any destructive or state-changing operations\n"
            "- Wrap non-idempotent operations with idempotency guards (check before apply)\n"
            "- Name each step clearly\n\n"
            "OUTPUT FORMAT: JSON with fields: name, description, steps (array of "
            "{step_number, name, step_type, command_template, variables_required, "
            "rollback_command, is_idempotent})\n\n"
            f"Command sequences:\n{json.dumps(command_sequences, indent=2)}"
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
            logger.error("LLM call failed for runbook generation: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM generation failed: {exc}",
            )

        # Parse JSON response
        try:
            raw = analysis.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = re.sub(r"^```[^\n]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw.strip())
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Failed to parse LLM JSON response: %s", exc)
            # Return a minimal safe structure so the caller can still create a runbook
            return {
                "name": "Auto-Generated Runbook",
                "description": "Generated from agent sessions",
                "steps": [
                    {
                        "step_number": i + 1,
                        "name": f"Step {i + 1}",
                        "step_type": "command",
                        "command_template": cmd["command"],
                        "variables_required": [],
                        "rollback_command": None,
                        "is_idempotent": not _is_non_idempotent(cmd["command"]),
                    }
                    for i, cmd in enumerate(command_sequences[:10])
                ],
            }
