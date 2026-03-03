"""
Runbook Git Sync Service

Clones/pulls a git repository and imports all runbook YAML files it contains
into the database, reusing the same import logic as the manual YAML upload.

Authentication:
  - none   — public repo, no credentials
  - token  — GitHub/GitLab PAT or OAuth token embedded in HTTPS URL
  - basic  — username / password embedded in HTTPS URL
  - ssh    — PEM private key passed via GIT_SSH_COMMAND
"""
from __future__ import annotations

import fnmatch
import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models_remediation import (
    CircuitBreaker,
    Runbook,
    RunbookGitSyncConfig,
    RunbookStep,
    RunbookTrigger,
)
from app.utils.crypto import decrypt_value

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Credential / URL helpers
# ---------------------------------------------------------------------------

def _build_clone_url(config: RunbookGitSyncConfig) -> str:
    """Return the repo URL with embedded credentials where required."""
    url = config.repo_url

    if config.auth_type == "token" and config.token_encrypted:
        token = decrypt_value(config.token_encrypted)
        if "github.com" in url:
            return url.replace("https://", f"https://{token}@")
        # GitLab / generic
        return url.replace("https://", f"https://oauth2:{token}@")

    if config.auth_type == "basic" and config.username and config.password_encrypted:
        password = decrypt_value(config.password_encrypted)
        return url.replace("https://", f"https://{config.username}:{password}@")

    return url


def _build_git_env(config: RunbookGitSyncConfig) -> Tuple[Dict[str, str], Optional[str]]:
    """Return git subprocess environment and optional temporary SSH key path."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"
    env["SSH_ASKPASS"] = "false"
    ssh_key_path: Optional[str] = None

    if config.auth_type == "ssh" and config.ssh_key_encrypted:
        ssh_key = decrypt_value(config.ssh_key_encrypted)
        tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".key")
        tmp.write(ssh_key)
        tmp.close()
        os.chmod(tmp.name, 0o600)
        ssh_key_path = tmp.name
        env["GIT_SSH_COMMAND"] = f"ssh -i {tmp.name} -o StrictHostKeyChecking=no"

    return env, ssh_key_path


# ---------------------------------------------------------------------------
# Core import helper (reusable, no HTTP layer)
# ---------------------------------------------------------------------------

async def import_runbook_from_dict(
    db: AsyncSession,
    data: Dict[str, Any],
    overwrite: bool,
    source_path: Optional[str] = None,
    created_by: Optional[UUID] = None,
) -> Dict[str, Any]:
    """
    Import a single parsed runbook dict into the database.

    Returns a dict with keys:
        action  — "created" | "updated" | "skipped"
        name    — runbook name
        error   — str | None
    """
    if data.get("kind") != "Runbook":
        return {"action": "skipped", "name": str(data.get("metadata", {}).get("name", "?")),
                "error": "kind != 'Runbook'"}

    metadata = data.get("metadata", {})
    spec = data.get("spec", {})
    name = metadata.get("name")

    if not name:
        return {"action": "skipped", "name": "?", "error": "Missing metadata.name"}

    # Checksum of the raw YAML dict for change detection
    content_hash = hashlib.sha256(
        yaml.dump(data, sort_keys=True).encode()
    ).hexdigest()

    # ── Check existing ──────────────────────────────────────────────────────
    result = await db.execute(
        select(Runbook)
        .where(Runbook.name == name)
        .options(
            selectinload(Runbook.steps),
            selectinload(Runbook.triggers),
        )
    )
    existing_runbook = result.scalar_one_or_none()

    if existing_runbook:
        if not overwrite:
            return {"action": "skipped", "name": name, "error": None}

        # Skip if content is identical
        if existing_runbook.checksum == content_hash:
            return {"action": "skipped", "name": name, "error": None}

        runbook = existing_runbook
        runbook.version += 1
        for step in list(runbook.steps):
            await db.delete(step)
        for trigger in list(runbook.triggers):
            await db.delete(trigger)
        action = "updated"
    else:
        runbook = Runbook(created_by=created_by)
        db.add(runbook)
        action = "created"

    # ── Populate fields ──────────────────────────────────────────────────────
    execution_spec = spec.get("execution", {})
    safety_spec = spec.get("safety", {})
    target_spec = spec.get("target", {})

    runbook.name = name
    runbook.description = metadata.get("description")
    runbook.category = metadata.get("category")
    runbook.tags = metadata.get("tags", [])
    runbook.documentation_url = metadata.get("documentation_url")
    runbook.auto_execute = execution_spec.get("auto_execute", False)
    runbook.approval_required = execution_spec.get("approval_required", True)
    runbook.approval_roles = execution_spec.get("approval_roles", ["admin", "engineer"])
    runbook.approval_timeout_minutes = execution_spec.get("approval_timeout_minutes", 30)
    runbook.max_executions_per_hour = safety_spec.get("max_executions_per_hour", 5)
    runbook.cooldown_minutes = safety_spec.get("cooldown_minutes", 10)
    runbook.target_os_filter = target_spec.get("os_filter", ["linux", "windows"])
    runbook.target_from_alert = target_spec.get("from_alert", True)
    runbook.target_alert_label = target_spec.get("alert_label", "instance")
    runbook.notifications_json = spec.get("notifications", {})
    runbook.source = "git"
    runbook.source_path = source_path
    runbook.checksum = content_hash

    await db.flush()

    # ── Steps ────────────────────────────────────────────────────────────────
    for idx, step_data in enumerate(data.get("steps", [])):
        step = RunbookStep(
            runbook_id=runbook.id,
            step_order=idx + 1,
            name=step_data.get("name", f"Step {idx + 1}"),
            description=step_data.get("description"),
            command_linux=step_data.get("command_linux"),
            command_windows=step_data.get("command_windows"),
            target_os=step_data.get("target_os", "any"),
            timeout_seconds=step_data.get("timeout_seconds", 60),
            requires_elevation=step_data.get("requires_elevation", False),
            working_directory=step_data.get("working_directory"),
            environment_json=step_data.get("environment"),
            continue_on_fail=step_data.get("continue_on_fail", False),
            retry_count=step_data.get("retry_count", 0),
            retry_delay_seconds=step_data.get("retry_delay_seconds", 5),
            expected_exit_code=step_data.get("expected_exit_code", 0),
            expected_output_pattern=step_data.get("expected_output_pattern"),
            rollback_command_linux=step_data.get("rollback_command_linux"),
            rollback_command_windows=step_data.get("rollback_command_windows"),
        )
        db.add(step)

    # ── Triggers ─────────────────────────────────────────────────────────────
    for trigger_data in data.get("triggers", []):
        trigger = RunbookTrigger(
            runbook_id=runbook.id,
            alert_name_pattern=trigger_data.get("alert_name_pattern", "*"),
            severity_pattern=trigger_data.get("severity_pattern", "*"),
            instance_pattern=trigger_data.get("instance_pattern", "*"),
            job_pattern=trigger_data.get("job_pattern", "*"),
            label_matchers_json=trigger_data.get("label_matchers"),
            min_duration_seconds=trigger_data.get("min_duration_seconds", 0),
            min_occurrences=trigger_data.get("min_occurrences", 1),
            priority=trigger_data.get("priority", 100),
            enabled=trigger_data.get("enabled", True),
        )
        db.add(trigger)

    # ── Circuit breaker for new runbooks ─────────────────────────────────────
    if action == "created":
        db.add(CircuitBreaker(scope="runbook", scope_id=runbook.id, state="closed"))

    return {"action": action, "name": name, "error": None}


# ---------------------------------------------------------------------------
# Main sync function
# ---------------------------------------------------------------------------

async def sync_git_config(
    db: AsyncSession,
    config: RunbookGitSyncConfig,
) -> Dict[str, Any]:
    """
    Execute a full sync cycle for one git sync configuration.

    Clones the repository to a temp directory, discovers all YAML/YML files
    under ``config.path_prefix``, and imports each one that looks like a
    Runbook document.

    Returns aggregated statistics dict.

    Args:
        db: Async SQLAlchemy session.
        config: The :class:`RunbookGitSyncConfig` to process.

    Returns:
        Dict with keys ``synced``, ``created``, ``updated``, ``skipped``, ``errors``.
    """
    stats: Dict[str, Any] = {
        "synced": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": [],
    }

    temp_dir = tempfile.mkdtemp(prefix="rb_git_sync_")
    ssh_key_path: Optional[str] = None
    try:
        clone_url = _build_clone_url(config)
        env, ssh_key_path = _build_git_env(config)

        logger.info(
            "Git sync starting: config=%s repo=%s branch=%s",
            config.name,
            config.repo_url,
            config.branch,
        )

        # ── Clone ────────────────────────────────────────────────────────────
        cmd = [
            "git",
            "-c", "core.askpass=false",
            "-c", "credential.helper=",
            "clone",
            "--depth", "1",
            "--branch", config.branch,
            clone_url,
            temp_dir,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr.strip()}")

        repo_path = Path(temp_dir)
        scan_root = repo_path / config.path_prefix.strip("/") if config.path_prefix else repo_path

        if not scan_root.is_dir():
            raise RuntimeError(
                f"path_prefix '{config.path_prefix}' not found in repository"
            )

        # ── Discover YAML files ──────────────────────────────────────────────
        yaml_files: List[Path] = []
        for pattern in ("*.yaml", "*.yml"):
            yaml_files.extend(scan_root.rglob(pattern))

        # Deduplicate (rglob may return same file twice via symlinks)
        seen: set = set()
        unique_files: List[Path] = []
        for f in yaml_files:
            resolved = str(f.resolve())
            if resolved not in seen:
                seen.add(resolved)
                unique_files.append(f)

        logger.info(
            "Git sync: found %d YAML file(s) to inspect in '%s'",
            len(unique_files),
            scan_root,
        )

        # ── Import each file ─────────────────────────────────────────────────
        for yaml_file in unique_files:
            rel_path = str(yaml_file.relative_to(repo_path))
            try:
                content = yaml_file.read_text(encoding="utf-8", errors="ignore")
                data = yaml.safe_load(content)
            except Exception as exc:
                logger.warning("Skipping %s: parse error — %s", rel_path, exc)
                stats["errors"].append(f"{rel_path}: {exc}")
                continue

            if not isinstance(data, dict) or data.get("kind") != "Runbook":
                # Not a runbook file; silently skip
                continue

            try:
                outcome = await import_runbook_from_dict(
                    db=db,
                    data=data,
                    overwrite=config.overwrite_existing,
                    source_path=f"{config.repo_url}/blob/{config.branch}/{rel_path}",
                    created_by=config.created_by,
                )
                if outcome["action"] in {"created", "updated"}:
                    await db.commit()
            except Exception as exc:
                logger.error("Failed to import %s: %s", rel_path, exc, exc_info=True)
                stats["errors"].append(f"{rel_path}: {exc}")
                await db.rollback()
                continue

            action = outcome["action"]
            stats["synced"] += 1

            if action == "created":
                stats["created"] += 1
            elif action == "updated":
                stats["updated"] += 1
            else:
                stats["synced"] -= 1  # skipped doesn't count toward synced
                stats["skipped"] += 1

            if outcome.get("error"):
                stats["errors"].append(f"{rel_path}: {outcome['error']}")

        await db.commit()
        logger.info("Git sync complete for '%s': %s", config.name, stats)

    except subprocess.TimeoutExpired:
        stats["errors"].append("git clone timed out after 5 minutes")
        logger.error("Git sync timeout for config '%s'", config.name)
    except Exception as exc:
        stats["errors"].append(str(exc))
        logger.error("Git sync failed for config '%s': %s", config.name, exc, exc_info=True)
        try:
            await db.rollback()
        except Exception:
            pass
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if ssh_key_path and os.path.exists(ssh_key_path):
            try:
                os.remove(ssh_key_path)
            except Exception:
                logger.warning("Failed to remove temporary SSH key file: %s", ssh_key_path)

    return stats


async def run_all_enabled_syncs(db: AsyncSession) -> None:
    """
    Periodic task: iterate all enabled git sync configs and run those whose
    ``sync_interval_minutes`` has elapsed since ``last_sync_at``.

    Called by the APScheduler background job registered in main.py.

    Args:
        db: Async SQLAlchemy session.
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(RunbookGitSyncConfig).where(RunbookGitSyncConfig.enabled.is_(True))
    )
    configs = result.scalars().all()

    for cfg in configs:
        # Skip if next sync time has not arrived yet
        if cfg.last_sync_at is not None:
            next_sync = cfg.last_sync_at + timedelta(minutes=cfg.sync_interval_minutes)
            if now < next_sync:
                continue

        cfg.last_sync_status = "running"
        cfg.last_sync_at = now
        await db.commit()

        stats = await sync_git_config(db, cfg)

        cfg.last_sync_status = "error" if stats["errors"] else "success"
        cfg.last_sync_message = (
            "; ".join(stats["errors"][:3]) if stats["errors"] else
            f"Synced {stats['synced']} runbook(s) ({stats['created']} new, {stats['updated']} updated, {stats['skipped']} unchanged)"
        )
        cfg.runbooks_synced = stats["synced"]
        cfg.last_sync_at = datetime.now(timezone.utc)
        await db.commit()


# ---------------------------------------------------------------------------
# APScheduler integration
# ---------------------------------------------------------------------------

async def _git_sync_scheduler_job() -> None:
    """
    Async no-argument wrapper called by APScheduler every minute.
    Creates its own database session so the scheduler loop stays decoupled
    from the request lifecycle.
    """
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            await run_all_enabled_syncs(db)
        except Exception as exc:
            logger.error("Git sync scheduler job failed: %s", exc, exc_info=True)


def start_git_sync_jobs(scheduler) -> None:
    """
    Register the runbook git-sync poller with APScheduler.

    The job runs every minute and internally skips configs that have not yet
    reached their ``sync_interval_minutes`` threshold.

    Args:
        scheduler: APScheduler ``AsyncIOScheduler`` instance from main.py.
    """
    scheduler.add_job(
        func="app.services.runbook_git_sync_service:_git_sync_scheduler_job",
        trigger="interval",
        minutes=1,
        id="runbook_git_sync_poller",
        name="Runbook Git Sync Poller",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("✅ Runbook git-sync poller registered (interval: 1 min)")
