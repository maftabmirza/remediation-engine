"""
Runbook Auto-Generation Service (Feature B2)

Mines successful agent troubleshooting sessions to automatically generate
reusable runbook drafts.  Transforms tribal knowledge into codified automation.
"""
from __future__ import annotations

import json
import logging
import re
import uuid as _uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models_agent import AgentSession, AgentStep
from app.models_remediation import Runbook, RunbookStep, CommandBlocklist
from app.schemas_runbook_generation import (
    GenerationCandidate,
    GeneratedStepPreview,
)

logger = logging.getLogger(__name__)

# Patterns that indicate a command is NOT idempotent / is destructive
_NON_IDEMPOTENT_PATTERNS: List[str] = [
    r"\brm\b",
    r"\bdrop\b",
    r"\bdelete\b",
    r"\btruncate\b",
    r"\bkill\b",
    r"\bformat\b",
    r"\bmkfs\b",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _extract_jinja2_variables(template: str) -> List[str]:
    """Return sorted list of unique Jinja2 variable names found in *template*."""
    return sorted(set(re.findall(r"\{\{\s*(\w+)\s*\}\}", template)))


def _is_non_idempotent(command: str) -> bool:
    """Return True if the command matches any known destructive pattern."""
    lower = command.lower()
    return any(re.search(p, lower) for p in _NON_IDEMPOTENT_PATTERNS)


class RunbookGenerationService:
    """
    Service that converts successful agent sessions into runbook drafts.

    All public methods are async-first and accept an ``AsyncSession``.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # find_generation_candidates
    # ------------------------------------------------------------------

    async def find_generation_candidates(
        self,
        min_success_count: int = 3,
    ) -> List[GenerationCandidate]:
        """
        Find clusters of similar successful sessions suitable for runbook generation.

        Args:
            min_success_count: Minimum number of successful sessions required to
                form a candidate cluster.

        Returns:
            List of ``GenerationCandidate`` sorted by session_count descending.
        """
        # Load completed sessions that have at least one successful SolutionOutcome
        from app.models import SolutionOutcome

        stmt = (
            select(AgentSession)
            .where(AgentSession.status == "completed")
            .options(selectinload(AgentSession.steps))
        )
        result = await self.db.execute(stmt)
        completed_sessions: List[AgentSession] = result.scalars().all()

        if not completed_sessions:
            return []

        # Filter sessions that have a successful SolutionOutcome
        session_ids = [s.id for s in completed_sessions]
        outcome_stmt = select(SolutionOutcome).where(
            and_(
                SolutionOutcome.session_id.in_(session_ids),
                SolutionOutcome.success.is_(True),
            )
        )
        outcome_result = await self.db.execute(outcome_stmt)
        successful_outcome_session_ids = {
            o.session_id for o in outcome_result.scalars().all()
        }

        successful_sessions = [
            s for s in completed_sessions if s.id in successful_outcome_session_ids
        ]

        if not successful_sessions:
            return []

        # Group sessions by goal similarity (simple word-overlap heuristic when
        # pgvector embeddings are not available in unit tests)
        clusters = self._cluster_sessions_by_goal(successful_sessions)

        candidates: List[GenerationCandidate] = []
        for cluster in clusters:
            if len(cluster) < min_success_count:
                continue

            goal_summary = cluster[0].goal or "Unknown goal"
            sample_commands = self._extract_sample_commands(cluster, limit=5)

            candidates.append(
                GenerationCandidate(
                    session_ids=[s.id for s in cluster],
                    session_count=len(cluster),
                    goal_summary=goal_summary,
                    app_id=None,
                    success_rate=1.0,
                    avg_resolution_minutes=self._avg_resolution_minutes(cluster),
                    representative_commands=sample_commands,
                )
            )

        candidates.sort(key=lambda c: c.session_count, reverse=True)
        return candidates

    # ------------------------------------------------------------------
    # generate_runbook
    # ------------------------------------------------------------------

    async def generate_runbook(
        self,
        session_ids: List[UUID],
        runbook_name: Optional[str],
        app_id: Optional[UUID],
        created_by: UUID,
    ) -> Runbook:
        """
        Generate a runbook draft from the given agent sessions.

        Args:
            session_ids: List of AgentSession UUIDs (must be ≥ 1).
            runbook_name: Optional override for the runbook name.
            app_id: Optional application UUID to associate with the runbook.
            created_by: UUID of the user requesting generation.

        Returns:
            A newly created ``Runbook`` record with ``enabled=False``.

        Raises:
            ValueError: If no steps are found or a generated command violates
                        the ``CommandBlocklist``.
        """
        # 1. Load command steps for the given sessions
        stmt = select(AgentStep).where(
            and_(
                AgentStep.agent_session_id.in_(session_ids),
                AgentStep.step_type == "command",
                AgentStep.status == "executed",
            )
        )
        result = await self.db.execute(stmt)
        steps: List[AgentStep] = result.scalars().all()

        if not steps:
            raise ValueError(
                "No successful command steps found for the provided sessions."
            )

        # 2. Build command sequences with context
        command_sequences = self._build_command_sequences(steps)

        # 3. Run LLM to generate the runbook
        generated = await self._call_llm_for_generation(
            command_sequences=command_sequences,
            n_sessions=len(session_ids),
        )

        # 4. Validate generated commands against the blocklist
        await self._validate_against_blocklist(generated.get("steps", []))

        # 5. Derive metadata
        auto_name = runbook_name or generated.get(
            "name",
            f"Auto-generated runbook {_utc_now().strftime('%Y%m%d-%H%M%S')}",
        )
        description = generated.get("description", "")
        description = (
            f"{description} Auto-generated from {len(session_ids)} sessions. "
            "Requires human review before activation."
        ).strip()

        # 6. Create the Runbook record
        runbook = Runbook(
            id=_uuid.uuid4(),
            name=auto_name,
            description=description,
            source="auto_generated",
            auto_execute=False,  # requires human approval
            enabled=False,       # not active until approved
            created_by=created_by,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        self.db.add(runbook)
        await self.db.flush()  # get runbook.id

        # 7. Create RunbookStep records
        for idx, step_data in enumerate(generated.get("steps", []), start=1):
            command_template = step_data.get("command_template", "")
            step = RunbookStep(
                id=_uuid.uuid4(),
                runbook_id=runbook.id,
                step_order=idx,
                name=step_data.get("name", f"Step {idx}"),
                description=step_data.get("description", ""),
                step_type=step_data.get("step_type", "command"),
                command_linux=command_template,
            )
            self.db.add(step)

        await self.db.commit()
        await self.db.refresh(runbook)
        return runbook

    # ------------------------------------------------------------------
    # approve_draft
    # ------------------------------------------------------------------

    async def approve_draft(
        self,
        runbook_id: UUID,
        approved_by: UUID,
        enable_auto_trigger: bool = False,
    ) -> Runbook:
        """
        Approve an auto-generated runbook draft for use.

        Sets ``enabled = True`` (and optionally ``auto_execute = True``).

        Args:
            runbook_id: UUID of the draft runbook.
            approved_by: UUID of the approving admin.
            enable_auto_trigger: If True, also set ``auto_execute = True``.

        Returns:
            Updated ``Runbook`` record.

        Raises:
            ValueError: If the runbook is not found.
        """
        result = await self.db.execute(
            select(Runbook).where(Runbook.id == runbook_id)
        )
        runbook = result.scalar_one_or_none()
        if not runbook:
            raise ValueError(f"Runbook {runbook_id} not found.")

        runbook.enabled = True
        runbook.auto_execute = enable_auto_trigger
        runbook.updated_at = _utc_now()

        # Attempt to write an audit log if the model is available
        try:
            from app.models import AuditLog  # type: ignore

            log = AuditLog(
                user_id=approved_by,
                action="runbook_approved",
                resource_type="runbook",
                resource_id=str(runbook_id),
                details=json.dumps(
                    {
                        "source": runbook.source,
                        "auto_trigger": enable_auto_trigger,
                    }
                ),
                created_at=_utc_now(),
            )
            self.db.add(log)
        except Exception:
            # AuditLog may not exist in all environments — skip silently
            pass

        await self.db.commit()
        await self.db.refresh(runbook)
        return runbook

    # ------------------------------------------------------------------
    # list_drafts
    # ------------------------------------------------------------------

    async def list_drafts(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Runbook], int]:
        """
        List auto-generated runbook drafts pending review.

        Returns:
            Tuple of (list of Runbook records, total count).
        """
        base_filter = and_(
            Runbook.source == "auto_generated",
            Runbook.enabled.is_(False),
        )
        count_result = await self.db.execute(
            select(func.count(Runbook.id)).where(base_filter)
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        list_result = await self.db.execute(
            select(Runbook)
            .where(base_filter)
            .order_by(Runbook.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list_result.scalars().all()
        return list(items), total

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _cluster_sessions_by_goal(
        self, sessions: List[AgentSession]
    ) -> List[List[AgentSession]]:
        """
        Group sessions by goal similarity using a simple normalised-goal key.

        In production, pgvector cosine similarity would be used instead.
        """
        groups: Dict[str, List[AgentSession]] = defaultdict(list)
        for session in sessions:
            key = self._normalise_goal(session.goal or "")
            groups[key].append(session)
        return list(groups.values())

    @staticmethod
    def _normalise_goal(goal: str) -> str:
        """Return a normalised lowercase key from a goal string."""
        words = re.findall(r"\b\w+\b", goal.lower())
        # Use first 5 significant words as cluster key
        stop_words = {"the", "a", "an", "is", "in", "on", "for", "to", "of", "and"}
        significant = [w for w in words if w not in stop_words][:5]
        return " ".join(significant) or goal.lower()[:50]

    @staticmethod
    def _extract_sample_commands(
        sessions: List[AgentSession], limit: int = 5
    ) -> List[str]:
        """Return up to *limit* unique command strings from the session steps."""
        seen: set = set()
        commands: List[str] = []
        for session in sessions:
            for step in (session.steps or []):
                if step.step_type == "command" and step.content:
                    cmd = step.content.strip()
                    if cmd not in seen:
                        seen.add(cmd)
                        commands.append(cmd)
                        if len(commands) >= limit:
                            return commands
        return commands

    @staticmethod
    def _avg_resolution_minutes(
        sessions: List[AgentSession],
    ) -> Optional[float]:
        """Return average resolution time in minutes across sessions."""
        durations: List[float] = []
        for s in sessions:
            if s.created_at and s.completed_at:
                delta = (s.completed_at - s.created_at).total_seconds()
                durations.append(delta / 60.0)
        if not durations:
            return None
        return round(sum(durations) / len(durations), 2)

    @staticmethod
    def _build_command_sequences(steps: List[AgentStep]) -> List[Dict[str, Any]]:
        """Build a serialisable list of command contexts from step records."""
        sequences = []
        for step in steps:
            sequences.append(
                {
                    "command": step.content or "",
                    "reasoning": step.reasoning or "",
                    "output_preview": (step.output or "")[:200],
                }
            )
        return sequences

    async def _call_llm_for_generation(
        self,
        command_sequences: List[Dict[str, Any]],
        n_sessions: int,
    ) -> Dict[str, Any]:
        """
        Call the configured LLM to generate a structured runbook from command sequences.

        Returns:
            Parsed JSON dict with keys: name, description, steps.
        """
        from app.services.llm_service import generate_completion
        from app.database import async_session_factory

        system_part = (
            "You are an SRE expert creating reusable runbooks from successful "
            "troubleshooting sessions."
        )
        user_part = (
            f"Given these successful command sequences from {n_sessions} real incidents, "
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

        full_prompt = f"{system_part}\n\n{user_part}"

        async with async_session_factory() as llm_db:
            text, _ = await generate_completion(llm_db, full_prompt, json_mode=True)

        return self._parse_llm_json(text)

    @staticmethod
    def _parse_llm_json(text: str) -> Dict[str, Any]:
        """Parse LLM response JSON, stripping markdown fences if present."""
        cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON; returning empty structure")
            return {"name": None, "description": "", "steps": []}

    async def _validate_against_blocklist(
        self, steps: List[Dict[str, Any]]
    ) -> None:
        """
        Validate generated commands against the CommandBlocklist.

        Raises:
            ValueError: If any command matches a blocklist entry.
        """
        blocklist_result = await self.db.execute(
            select(CommandBlocklist).where(CommandBlocklist.enabled.is_(True))
        )
        blocklist: List[CommandBlocklist] = blocklist_result.scalars().all()

        if not blocklist:
            return

        for step in steps:
            cmd = step.get("command_template", "")
            for entry in blocklist:
                if self._matches_blocklist(cmd, entry):
                    raise ValueError(
                        f"Generated command matches blocked pattern "
                        f"'{entry.pattern}' (severity: {entry.severity}): {cmd!r}"
                    )

    @staticmethod
    def _matches_blocklist(command: str, entry: CommandBlocklist) -> bool:
        """Return True if *command* matches the given blocklist *entry*."""
        if not command:
            return False
        pattern_type = entry.pattern_type or "contains"
        try:
            if pattern_type == "regex":
                return bool(re.search(entry.pattern, command, re.IGNORECASE))
            elif pattern_type == "exact":
                return command.strip().lower() == entry.pattern.lower()
            else:  # contains
                return entry.pattern.lower() in command.lower()
        except re.error:
            logger.warning("Invalid regex in blocklist entry %s: %s", entry.id, entry.pattern)
            return False

    # ------------------------------------------------------------------
    # Preview helpers (used by the router to build the response)
    # ------------------------------------------------------------------

    @staticmethod
    def build_step_previews(
        steps_data: List[Dict[str, Any]],
    ) -> List[GeneratedStepPreview]:
        """Convert raw LLM step dicts into ``GeneratedStepPreview`` objects."""
        previews = []
        for idx, s in enumerate(steps_data, start=1):
            cmd_template = s.get("command_template", "")
            variables = _extract_jinja2_variables(cmd_template)
            non_idempotent = _is_non_idempotent(cmd_template)
            is_idempotent = s.get("is_idempotent")
            if is_idempotent is None and non_idempotent:
                is_idempotent = False

            previews.append(
                GeneratedStepPreview(
                    step_number=s.get("step_number", idx),
                    name=s.get("name", f"Step {idx}"),
                    step_type=s.get("step_type", "command"),
                    command_template=cmd_template,
                    variables_required=variables,
                    is_idempotent=is_idempotent,
                    requires_human_review=non_idempotent,
                )
            )
        return previews
