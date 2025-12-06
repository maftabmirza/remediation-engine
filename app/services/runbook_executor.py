"""
Runbook Executor Service

Orchestrates the execution of runbooks on remote servers.
Handles step execution, retries, rollbacks, and result tracking.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable, AsyncIterator
from uuid import UUID
from jinja2 import Template, Environment, BaseLoader, UndefinedError

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..models import ServerCredential, Alert
from ..models_remediation import (
    Runbook, RunbookStep, RunbookExecution, StepExecution,
    CircuitBreaker
)
from .executor_base import ExecutionResult, ErrorType
from .executor_factory import ExecutorFactory

logger = logging.getLogger(__name__)


def utc_now():
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class RunbookExecutor:
    """
    Executes runbooks on remote servers.
    
    Features:
    - Step-by-step execution with progress tracking
    - Jinja2 template variable substitution
    - Retry handling per step
    - Rollback on failure
    - Real-time output streaming
    - Dry-run mode
    """
    
    def __init__(
        self,
        db: AsyncSession,
        fernet_key: Optional[str] = None
    ):
        """
        Initialize the runbook executor.
        
        Args:
            db: Database session for status updates.
            fernet_key: Encryption key for credentials.
        """
        self.db = db
        self.fernet_key = fernet_key
        self.jinja_env = Environment(loader=BaseLoader())
        self._cancelled = False
    
    def cancel(self):
        """Signal cancellation of current execution."""
        self._cancelled = True
    
    async def execute_runbook(
        self,
        execution: RunbookExecution,
        on_step_start: Optional[Callable[[int, str], None]] = None,
        on_step_complete: Optional[Callable[[int, str, bool], None]] = None,
        on_output: Optional[Callable[[str], None]] = None
    ) -> RunbookExecution:
        """
        Execute a runbook and update execution record.
        
        Args:
            execution: RunbookExecution record to execute.
            on_step_start: Callback when step starts (step_order, step_name).
            on_step_complete: Callback when step completes (step_order, step_name, success).
            on_output: Callback for real-time output lines.
        
        Returns:
            Updated RunbookExecution with results.
        """
        self._cancelled = False
        
        # Load runbook with steps
        result = await self.db.execute(
            select(Runbook)
            .options(selectinload(Runbook.steps))
            .where(Runbook.id == execution.runbook_id)
        )
        runbook = result.scalar_one_or_none()
        
        if not runbook:
            execution.status = "failed"
            execution.error_message = "Runbook not found"
            execution.completed_at = utc_now()
            await self.db.commit()
            return execution
        
        # Load server
        result = await self.db.execute(
            select(ServerCredential).where(ServerCredential.id == execution.server_id)
        )
        server = result.scalar_one_or_none()
        
        if not server:
            execution.status = "failed"
            execution.error_message = "Target server not found"
            execution.completed_at = utc_now()
            await self.db.commit()
            return execution
        
        # Load alert context if available
        alert_context = {}
        if execution.alert_id:
            result = await self.db.execute(
                select(Alert).where(Alert.id == execution.alert_id)
            )
            alert = result.scalar_one_or_none()
            if alert:
                alert_context = {
                    "alert_name": alert.name,
                    "alert_severity": alert.severity,
                    "alert_source": alert.source,
                    "alert_labels": alert.labels_json or {},
                    "alert_annotations": alert.annotations_json or {}
                }
        
        # Build context for template rendering
        context = self._build_context(
            runbook=runbook,
            server=server,
            alert_context=alert_context,
            execution=execution
        )
        
        # Update execution status
        execution.status = "running"
        execution.started_at = utc_now()
        execution.steps_total = len(runbook.steps)
        await self.db.commit()
        
        # Sort steps by order
        steps = sorted(runbook.steps, key=lambda s: s.step_order)
        
        # Track completed steps for potential rollback
        completed_steps: List[tuple] = []  # (step, StepExecution)
        all_success = True
        
        try:
            # Get executor
            executor = ExecutorFactory.get_executor(server, self.fernet_key)
            
            async with executor:
                for step in steps:
                    if self._cancelled:
                        execution.status = "cancelled"
                        execution.error_message = "Execution cancelled by user"
                        break
                    
                    # Create step execution record
                    step_exec = StepExecution(
                        execution_id=execution.id,
                        step_id=step.id,
                        step_order=step.step_order,
                        step_name=step.name,
                        status="running",
                        started_at=utc_now()
                    )
                    self.db.add(step_exec)
                    await self.db.commit()
                    
                    if on_step_start:
                        on_step_start(step.step_order, step.name)
                    
                    # Check if step should run based on OS
                    if not self._should_run_step(step, server):
                        step_exec.status = "skipped"
                        step_exec.completed_at = utc_now()
                        step_exec.error_message = f"Skipped: OS mismatch (server: {server.os_type}, step: {step.target_os})"
                        await self.db.commit()
                        
                        if on_step_complete:
                            on_step_complete(step.step_order, step.name, True)
                        continue
                    
                    # Get appropriate command/config based on step type
                    command = self._get_command_for_step(step, server)

                    if not command:
                        step_exec.status = "skipped"
                        step_exec.completed_at = utc_now()
                        step_exec.error_message = f"No command/config defined for {server.os_type}"
                        await self.db.commit()

                        if on_step_complete:
                            on_step_complete(step.step_order, step.name, True)
                        continue

                    # Render command template
                    try:
                        rendered_command = self._render_template(command, context)
                    except Exception as e:
                        step_exec.status = "failed"
                        step_exec.completed_at = utc_now()
                        step_exec.error_message = f"Template rendering failed: {e}"
                        all_success = False
                        await self.db.commit()

                        if not step.continue_on_fail:
                            break
                        continue

                    step_exec.command_executed = rendered_command

                    # Execute with retries
                    result = await self._execute_with_retries(
                        executor=executor,
                        command=rendered_command,
                        step=step,
                        step_exec=step_exec,
                        execution=execution,
                        on_output=on_output
                    )

                    # Update step execution based on step type
                    if step.step_type == "api":
                        # Store API response data
                        step_exec.http_status_code = result.exit_code  # HTTP status code is stored as exit_code
                        step_exec.http_response_body = result.stdout[:10000] if result.stdout else ""
                        step_exec.http_request_method = getattr(step, 'api_method', None)
                        step_exec.http_request_url = None  # Will be set from result if available
                        # Try to extract from error message or result
                        import json as json_module
                        try:
                            cmd_config = json_module.loads(rendered_command)
                            endpoint = cmd_config.get('endpoint', '')
                            base_url = getattr(server, 'api_base_url', '')
                            step_exec.http_request_url = f"{base_url}{endpoint}" if not endpoint.startswith('http') else endpoint
                        except:
                            pass
                    else:
                        # Store command execution results
                        step_exec.stdout = result.stdout[:10000] if result.stdout else ""
                        step_exec.stderr = result.stderr[:10000] if result.stderr else ""
                        step_exec.exit_code = result.exit_code

                    step_exec.completed_at = utc_now()
                    step_exec.duration_ms = result.duration_ms
                    
                    # Check success criteria
                    step_success = self._check_step_success(result, step)
                    
                    if step_success:
                        step_exec.status = "success"
                        execution.steps_completed += 1
                        completed_steps.append((step, step_exec))
                    else:
                        step_exec.status = "failed"
                        step_exec.error_type = result.error_type.value if result.error_type else "command"
                        step_exec.error_message = result.error_message or result.stderr
                        execution.steps_failed += 1
                        all_success = False
                    
                    await self.db.commit()
                    
                    if on_step_complete:
                        on_step_complete(step.step_order, step.name, step_success)
                    
                    # Stop on failure unless continue_on_fail
                    if not step_success and not step.continue_on_fail:
                        execution.error_message = f"Step '{step.name}' failed"
                        break
            
            # Set final status
            if self._cancelled:
                execution.status = "cancelled"
            elif all_success:
                execution.status = "success"
                execution.result_summary = f"All {len(steps)} steps completed successfully"
            else:
                execution.status = "failed"
                
                # Attempt rollback if configured
                if completed_steps and not execution.dry_run:
                    await self._execute_rollback(
                        executor=executor,
                        completed_steps=completed_steps,
                        context=context,
                        server=server,
                        execution=execution
                    )
            
        except ConnectionError as e:
            execution.status = "failed"
            execution.error_message = f"Connection error: {e}"
            logger.error(f"Runbook execution failed - connection error: {e}")
            
        except Exception as e:
            execution.status = "failed"
            execution.error_message = f"Execution error: {e}"
            logger.exception(f"Runbook execution failed: {e}")
        
        finally:
            execution.completed_at = utc_now()
            
            # Update circuit breaker
            await self._update_circuit_breaker(
                runbook_id=runbook.id,
                success=(execution.status == "success")
            )
            
            await self.db.commit()
        
        return execution
    
    async def execute_dry_run(
        self,
        runbook: Runbook,
        server: ServerCredential,
        alert_context: Optional[Dict[str, Any]] = None,
        variables: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Perform a dry run - validate without executing.
        
        Returns dict with:
        - valid: bool
        - steps: List of rendered commands
        - errors: List of validation errors
        - warnings: List of warnings
        """
        result = {
            "valid": True,
            "steps": [],
            "errors": [],
            "warnings": []
        }
        
        context = self._build_context(
            runbook=runbook,
            server=server,
            alert_context=alert_context or {},
            execution=None,
            extra_vars=variables
        )
        
        # Validate each step
        for step in sorted(runbook.steps, key=lambda s: s.step_order):
            step_info = {
                "order": step.step_order,
                "name": step.name,
                "skip_reason": None,
                "command": None,
                "rendered_command": None
            }
            
            # Check OS compatibility
            if not self._should_run_step(step, server):
                step_info["skip_reason"] = f"OS mismatch (server: {server.os_type}, step: {step.target_os})"
                result["steps"].append(step_info)
                continue
            
            # Get command/config for step
            command = self._get_command_for_step(step, server)
            step_info["command"] = command

            if not command:
                step_info["skip_reason"] = f"No command/config for {server.os_type if step.step_type != 'api' else 'API'}"
                result["steps"].append(step_info)
                continue
            
            # Try to render template
            try:
                rendered = self._render_template(command, context)
                step_info["rendered_command"] = rendered
                
                # Check for unresolved variables
                if "{{" in rendered or "}}" in rendered:
                    result["warnings"].append(
                        f"Step {step.step_order}: Command may have unresolved variables"
                    )
                
            except Exception as e:
                result["valid"] = False
                result["errors"].append(f"Step {step.step_order}: Template error - {e}")
            
            result["steps"].append(step_info)
        
        # Test server connectivity
        try:
            executor = ExecutorFactory.get_executor(server, self.fernet_key)
            async with executor:
                conn_test = await executor.test_connection()
                if not conn_test:
                    result["warnings"].append("Server connection test returned unexpected result")
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Server connection failed: {e}")
        
        return result

    async def execute_single_step(
        self,
        execution: RunbookExecution,
        step: RunbookStep,
        step_execution: StepExecution,
        server: ServerCredential,
        variables: Optional[Dict[str, str]] = None,
        alert_context: Optional[Dict[str, Any]] = None
    ) -> StepExecution:
        """
        Execute a single step for testing purposes.

        Args:
            execution: RunbookExecution record (can be temporary)
            step: RunbookStep to execute
            step_execution: StepExecution record to update
            server: Target server
            variables: Template variables
            alert_context: Alert context for template rendering

        Returns:
            Updated StepExecution record
        """
        try:
            # Load runbook
            result = await self.db.execute(
                select(Runbook).where(Runbook.id == step.runbook_id)
            )
            runbook = result.scalar_one_or_none()

            if not runbook:
                step_execution.status = "failed"
                step_execution.error_message = "Runbook not found"
                step_execution.completed_at = utc_now()
                return step_execution

            # Build context for template rendering
            context = self._build_context(
                runbook=runbook,
                server=server,
                alert_context=alert_context or {},
                execution=execution,
                extra_vars=variables
            )

            # Check if step should run on this OS
            if not self._should_run_step(step, server):
                step_execution.status = "skipped"
                step_execution.error_message = f"OS mismatch: server is {server.os_type}, step requires {step.target_os}"
                step_execution.completed_at = utc_now()
                return step_execution

            # Get command/config for step
            command = self._get_command_for_step(step, server)
            if not command:
                step_execution.status = "skipped"
                step_execution.error_message = f"No command/config defined for {server.os_type if step.step_type != 'api' else 'API'}"
                step_execution.completed_at = utc_now()
                return step_execution

            # Render command template
            try:
                rendered_command = self._render_template(command, context)
                step_execution.command_executed = rendered_command
            except Exception as e:
                step_execution.status = "failed"
                step_execution.error_message = f"Template rendering failed: {e}"
                step_execution.completed_at = utc_now()
                return step_execution

            # Get executor
            executor = ExecutorFactory.get_executor(server, self.fernet_key)

            # Execute command
            async with executor:
                # Test connection first
                conn_ok = await executor.test_connection()
                if not conn_ok:
                    step_execution.status = "failed"
                    step_execution.error_message = "Connection test failed"
                    step_execution.completed_at = utc_now()
                    return step_execution

                # Execute the command
                step_execution.status = "running"
                await self.db.commit()

                exec_result = await executor.execute(
                    command=rendered_command,
                    timeout=step.timeout_seconds,
                    working_dir=step.working_directory,
                    environment=step.environment_json
                )

                # Update step execution with results
                step_execution.stdout = exec_result.stdout[:10000] if exec_result.stdout else ""
                step_execution.stderr = exec_result.stderr[:10000] if exec_result.stderr else ""
                step_execution.exit_code = exec_result.exit_code
                step_execution.duration_ms = exec_result.duration_ms
                step_execution.completed_at = utc_now()

                # Check success criteria
                step_success = self._check_step_success(exec_result, step)

                if step_success:
                    step_execution.status = "success"
                else:
                    step_execution.status = "failed"
                    step_execution.error_type = exec_result.error_type.value if exec_result.error_type else "command"
                    step_execution.error_message = exec_result.error_message or exec_result.stderr

        except Exception as e:
            step_execution.status = "failed"
            step_execution.error_message = f"Execution error: {str(e)}"
            step_execution.completed_at = utc_now()
            logger.exception(f"Single step execution failed: {e}")

        return step_execution

    def _build_context(
        self,
        runbook: Runbook,
        server: ServerCredential,
        alert_context: Dict[str, Any],
        execution: Optional[RunbookExecution],
        extra_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Build Jinja2 template context."""
        context = {
            # Server info
            "server": {
                "hostname": server.hostname,
                "ip": server.hostname,  # Alias
                "os_type": getattr(server, 'os_type', 'linux'),
                "environment": server.environment,
                "username": server.username,
                "port": server.port,
            },
            # Runbook info
            "runbook": {
                "name": runbook.name,
                "category": runbook.category,
            },
            # Alert context
            "alert": alert_context,
            # Environment variables from runbook
            "env": runbook.notifications_json or {},
            # Execution info
            "execution": {
                "id": str(execution.id) if execution else "dry-run",
                "mode": execution.execution_mode if execution else "dry_run",
                "dry_run": execution.dry_run if execution else True,
            } if execution else {"id": "dry-run", "mode": "dry_run", "dry_run": True},
            # Timestamp
            "now": utc_now().isoformat(),
        }
        
        # Add alert labels as top-level for convenience
        if alert_context.get("alert_labels"):
            context["labels"] = alert_context["alert_labels"]
        
        # Add extra variables
        if extra_vars:
            context["vars"] = extra_vars
        
        # Add execution variables
        if execution and execution.variables_json:
            context["vars"] = {**context.get("vars", {}), **execution.variables_json}
        
        return context
    
    def _render_template(self, template_str: str, context: Dict[str, Any]) -> str:
        """Render a Jinja2 template string."""
        try:
            template = self.jinja_env.from_string(template_str)
            return template.render(**context)
        except UndefinedError as e:
            raise ValueError(f"Undefined variable in template: {e}")
        except Exception as e:
            raise ValueError(f"Template rendering error: {e}")
    
    def _should_run_step(self, step: RunbookStep, server: ServerCredential) -> bool:
        """Check if step should run on this server."""
        # API steps don't have OS restrictions
        if step.step_type == "api":
            return True

        step_os = step.target_os or "any"
        server_os = getattr(server, 'os_type', 'linux') or 'linux'

        if step_os == "any":
            return True

        return step_os.lower() == server_os.lower()

    def _get_command_for_step(self, step: RunbookStep, server: ServerCredential) -> Optional[str]:
        """
        Get the appropriate command or config for the step.

        For command steps: returns the command string for the OS
        For API steps: returns JSON config for the API request
        """
        import json

        step_type = getattr(step, 'step_type', 'command')

        if step_type == "api":
            # Build API request configuration as JSON
            config = {
                "method": step.api_method,
                "endpoint": step.api_endpoint,
                "headers": step.api_headers_json or {},
                "query_params": step.api_query_params_json or {},
                "body": step.api_body,
                "body_type": step.api_body_type or "json",
                "expected_status_codes": step.api_expected_status_codes or [200, 201, 202, 204],
                "extract": step.api_response_extract_json or {},
                "follow_redirects": step.api_follow_redirects if step.api_follow_redirects is not None else True
            }
            return json.dumps(config)

        else:
            # Command step - get command for OS
            return self._get_command_for_os(step, getattr(server, 'os_type', 'linux'))

    def _get_command_for_os(self, step: RunbookStep, os_type: str) -> Optional[str]:
        """Get the appropriate command for the OS type."""
        os_type = os_type.lower() if os_type else "linux"

        if os_type == "linux":
            return step.command_linux
        elif os_type == "windows":
            return step.command_windows
        else:
            # Default to linux
            return step.command_linux
    
    async def _execute_with_retries(
        self,
        executor,
        command: str,
        step: RunbookStep,
        step_exec: StepExecution,
        execution: RunbookExecution,
        on_output: Optional[Callable[[str], None]] = None
    ) -> ExecutionResult:
        """Execute a command with retry logic."""
        max_retries = step.retry_count or 0
        retry_delay = step.retry_delay_seconds or 5
        
        last_result = None
        
        for attempt in range(max_retries + 1):
            step_exec.retry_attempt = attempt
            
            if execution.dry_run:
                # Dry run - don't actually execute
                return ExecutionResult(
                    success=True,
                    exit_code=0,
                    stdout="[DRY RUN] Command would be executed",
                    stderr="",
                    duration_ms=0,
                    command=command,
                    server_hostname=executor.hostname
                )
            
            # Execute command
            result = await executor.execute(
                command=command,
                timeout=step.timeout_seconds or 60,
                with_elevation=step.requires_elevation,
                env=step.environment_json,
                working_directory=step.working_directory
            )
            
            # Stream output
            if on_output and result.stdout:
                for line in result.stdout.splitlines():
                    on_output(line)
            
            last_result = result
            
            if result.success:
                return result
            
            # Check if retryable
            if not result.retryable or attempt >= max_retries:
                break
            
            # Wait before retry
            await asyncio.sleep(retry_delay)
        
        return last_result
    
    def _check_step_success(self, result: ExecutionResult, step: RunbookStep) -> bool:
        """Check if step execution was successful."""
        step_type = getattr(step, 'step_type', 'command')

        if step_type == "api":
            # For API steps, check if HTTP status code is in expected codes
            expected_status_codes = getattr(step, 'api_expected_status_codes', None) or [200, 201, 202, 204]
            http_status = result.exit_code  # HTTP status code is stored in exit_code for API requests

            if http_status not in expected_status_codes:
                return False

            # Check output pattern if specified (applies to response body)
            if step.expected_output_pattern:
                try:
                    pattern = re.compile(step.expected_output_pattern, re.IGNORECASE | re.MULTILINE)
                    if not pattern.search(result.stdout):
                        return False
                except re.error:
                    logger.warning(f"Invalid regex pattern: {step.expected_output_pattern}")

            return True

        else:
            # For command steps, check exit code
            expected_exit = step.expected_exit_code if step.expected_exit_code is not None else 0
            if result.exit_code != expected_exit:
                return False

            # Check output pattern if specified
            if step.expected_output_pattern:
                try:
                    pattern = re.compile(step.expected_output_pattern, re.IGNORECASE | re.MULTILINE)
                    if not pattern.search(result.stdout):
                        return False
                except re.error:
                    logger.warning(f"Invalid regex pattern: {step.expected_output_pattern}")

            return True
    
    async def _execute_rollback(
        self,
        executor,
        completed_steps: List[tuple],
        context: Dict[str, Any],
        server: ServerCredential,
        execution: RunbookExecution
    ):
        """Execute rollback commands for completed steps in reverse order."""
        logger.info(f"Executing rollback for {len(completed_steps)} steps")
        
        execution.rollback_executed = True
        
        for step, step_exec in reversed(completed_steps):
            rollback_command = self._get_rollback_command_for_os(step, server.os_type)
            
            if not rollback_command:
                continue
            
            try:
                rendered = self._render_template(rollback_command, context)
                result = await executor.execute(
                    command=rendered,
                    timeout=step.timeout_seconds or 60,
                    with_elevation=step.requires_elevation
                )
                
                if result.success:
                    logger.info(f"Rollback successful for step: {step.name}")
                else:
                    logger.warning(f"Rollback failed for step: {step.name}: {result.stderr}")
                    
            except Exception as e:
                logger.error(f"Rollback error for step {step.name}: {e}")
    
    def _get_rollback_command_for_os(self, step: RunbookStep, os_type: str) -> Optional[str]:
        """Get the appropriate rollback command for the OS type."""
        os_type = os_type.lower() if os_type else "linux"
        
        if os_type == "linux":
            return step.rollback_command_linux
        elif os_type == "windows":
            return step.rollback_command_windows
        else:
            return step.rollback_command_linux
    
    async def _update_circuit_breaker(self, runbook_id: UUID, success: bool):
        """Update circuit breaker state based on execution result."""
        result = await self.db.execute(
            select(CircuitBreaker).where(
                CircuitBreaker.scope == "runbook",
                CircuitBreaker.scope_id == runbook_id
            )
        )
        cb = result.scalar_one_or_none()
        
        if not cb:
            return
        
        now = utc_now()
        
        if success:
            cb.success_count += 1
            cb.last_success_at = now
            
            # If half-open and success, close
            if cb.state == "half_open":
                if cb.success_count >= (cb.failure_threshold // 2 or 1):
                    cb.state = "closed"
                    cb.failure_count = 0
                    cb.success_count = 0
                    logger.info(f"Circuit breaker closed for runbook {runbook_id}")
        else:
            cb.failure_count += 1
            cb.last_failure_at = now
            cb.success_count = 0  # Reset success count
            
            # Check if should open
            if cb.state == "closed" and cb.failure_count >= cb.failure_threshold:
                cb.state = "open"
                cb.opened_at = now
                logger.warning(f"Circuit breaker opened for runbook {runbook_id}")
            elif cb.state == "half_open":
                # Back to open on failure
                cb.state = "open"
                cb.opened_at = now
        
        await self.db.commit()
