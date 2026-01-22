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

from ..models import ServerCredential, Alert, APICredentialProfile, IncidentMetrics
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
                    "alert_name": alert.alert_name,
                    "alert_severity": alert.severity,
                    "alert_instance": alert.instance,
                    "alert_job": alert.job,
                    "alert_labels": alert.labels_json or {},
                    "alert_annotations": alert.annotations_json or {}
                }
        
        # Runtime variables for this execution
        runtime_vars = {}
        
        # Build context for template rendering
        context = self._build_context(
            runbook=runbook,
            server=server,
            alert_context=alert_context,
            execution=execution,
            runtime_vars=runtime_vars
        )
        
        # Update execution status
        execution.status = "running"
        execution.started_at = utc_now()
        execution.steps_total = len(runbook.steps)
        await self.db.commit()

        # Update Alert engagement time (MTTR)
        if execution.alert_id:
            try:
                # Find metrics record
                result = await self.db.execute(
                    select(IncidentMetrics).where(IncidentMetrics.alert_id == execution.alert_id)
                )
                metrics = result.scalar_one_or_none()
                
                if metrics:
                    # Mark as engaged if not already
                    if not metrics.incident_engaged:
                        metrics.incident_engaged = utc_now()
                        metrics.resolution_type = "automated"
                        metrics.calculate_durations()
                        await self.db.commit()
            except Exception as e:
                logger.error(f"Failed to update incident metrics for alert {execution.alert_id}: {e}")
        
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
                    
                    # Check conditional execution
                    if step.run_if_variable:
                        should_run = self._check_conditional(step, runtime_vars)
                        if not should_run:
                            step_exec.status = "skipped"
                            step_exec.completed_at = utc_now()
                            step_exec.error_message = f"Skipped: Condition not met ({step.run_if_variable} did not match)"
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
                    
                    # Capture Output Variables for subsequent steps
                    # Store step execution result in steps.<step_name> context
                    if "steps" not in runtime_vars:
                        runtime_vars["steps"] = {}
                    
                    # Sanitize step name for use as variable (replace spaces/special chars)
                    safe_step_name = re.sub(r'[^a-zA-Z0-9_]', '_', step.name)
                    
                    step_output_data = {
                        "stdout": step_exec.stdout or "",
                        "stderr": step_exec.stderr or "",
                        "exit_code": step_exec.exit_code,
                        "success": step_success
                    }
                    runtime_vars["steps"][safe_step_name] = step_output_data
                    
                    # Custom Variable Extraction
                    if step.output_variable:
                        extracted_value = None
                        
                        # 1. API: Check for configured extraction (JSONPath/Regex)
                        if step.step_type == "api" and step.api_response_extract_json:
                            # Not implemented yet in this iteration, but schema supports it
                            pass
                            
                        # 2. Command/API: Regex extraction from stdout/response body
                        if step.output_extract_pattern:
                            try:
                                content = step_exec.stdout or step_exec.http_response_body or ""
                                match = re.search(step.output_extract_pattern, content)
                                if match:
                                    # Use first group if available, else full match
                                    extracted_value = match.group(1) if match.groups() else match.group(0)
                            except Exception as e:
                                logger.warning(f"Failed to extract variable {step.output_variable}: {e}")
                        
                        # 3. Default: Full stdout if no pattern
                        elif not step.output_extract_pattern:
                             extracted_value = (step_exec.stdout or step_exec.http_response_body or "").strip()
                        
                        # Store variable if found
                        if extracted_value is not None:
                            runtime_vars[step.output_variable] = extracted_value
                            logger.info(f"Captured variable '{step.output_variable}': {extracted_value[:50]}...")
                            
                    # Update context for next iteration
                    context = self._build_context(
                        runbook=runbook,
                        server=server,
                        alert_context=alert_context,
                        execution=execution,
                        runtime_vars=runtime_vars
                    )

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
            
            # Resolve incident if successful and configured (implicit for now)
            if execution.status == "success" and execution.alert_id:
                try:
                    result = await self.db.execute(
                        select(IncidentMetrics).where(IncidentMetrics.alert_id == execution.alert_id)
                    )
                    metrics = result.scalar_one_or_none()
                    if metrics and not metrics.incident_resolved:
                        metrics.incident_resolved = utc_now()
                        metrics.resolution_type = "automated"
                        metrics.calculate_durations()
                        
                        # Also update Alert status
                        result = await self.db.execute(
                            select(Alert).where(Alert.id == execution.alert_id)
                        )
                        alert = result.scalar_one_or_none()
                        if alert and alert.status != "resolved":
                            alert.status = "resolved"
                except Exception as e:
                     logger.error(f"Failed to auto-resolve incident for alert {execution.alert_id}: {e}")
            
            # Auto-learning: Record successful runbook execution as a proven solution
            if execution.status == "success" and execution.alert_id and not execution.dry_run:
                try:
                    await self._record_successful_solution(execution, runbook)
                except Exception as e:
                    logger.error(f"Failed to record solution learning for execution {execution.id}: {e}")

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

            # Get executor (API profile or server-based)
            executor = await self._get_executor_for_step(step, server)

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
        extra_vars: Optional[Dict[str, str]] = None,
        runtime_vars: Optional[Dict[str, Any]] = None
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
            
        # Add runtime variables (from previous steps)
        if runtime_vars:
            # Merge into top-level for direct access
            context.update(runtime_vars)
            # Also set in vars for consistency
            context["vars"] = {**context.get("vars", {}), **runtime_vars}
            
            # Add steps context if available
            if "steps" in runtime_vars:
                context["steps"] = runtime_vars["steps"]
        
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

    async def _get_executor_for_step(self, step: RunbookStep, server: ServerCredential):
        """
        Get the appropriate executor for the step type.

        For API steps with credential profiles: uses APIExecutor from profile.
        For command steps or legacy API steps: uses standard server executor.
        """
        # For API steps with credential profile
        if step.step_type == "api" and step.api_credential_profile_id:
            # Load the API credential profile from database
            result = await self.db.execute(
                select(APICredentialProfile).where(
                    APICredentialProfile.id == step.api_credential_profile_id
                )
            )
            profile = result.scalar_one_or_none()

            if not profile:
                raise ValueError(
                    f"API credential profile {step.api_credential_profile_id} not found"
                )

            if not profile.enabled:
                raise ValueError(
                    f"API credential profile '{profile.name}' is disabled"
                )

            # Create executor from profile
            return ExecutorFactory.get_api_executor_from_profile(profile, self.fernet_key)

        # For command steps or legacy API steps (using server credentials)
        else:
            return ExecutorFactory.get_executor(server, self.fernet_key)

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
    
    def _check_conditional(self, step: RunbookStep, runtime_vars: Dict[str, Any]) -> bool:
        """
        Check if step should run based on variable validation.
        Returns True if step should run (or no condition), False otherwise.
        """
        if not step.run_if_variable:
            return True
            
        # Get variable value
        actual_value = runtime_vars.get(step.run_if_variable)
        
        # If variable doesn't exist, we skip (fail open or closed? usually closed for safety)
        if actual_value is None:
            logger.info(f"Conditional step {step.step_order}: Variable '{step.run_if_variable}' not found. Skipping.")
            return False
            
        target_value = step.run_if_value or ""
        
        # Check for regex match if target looks like regex (simple heuristic or always regex?)
        # Let's support regex if it starts with regex: prefix, otherwise exact string match
        # Actually, user requirement implies "match", usually regex or equality. 
        # Existing logic uses regex for extraction. Let's assume equality for now, or regex if flexible.
        # Let's do exact match OR regex.
        
        # 1. Exact match
        if str(actual_value) == target_value:
            return True
            
        # 2. Regex match
        try:
            if re.fullmatch(target_value, str(actual_value)):
                return True
        except re.error:
            pass # Not a valid regex or didn't match
            
        logger.info(f"Conditional step {step.step_order}: Value '{actual_value}' did not match target '{target_value}'")
        return False

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
    
    async def _record_successful_solution(
        self,
        execution: RunbookExecution,
        runbook: Runbook
    ):
        """
        Auto-record successful runbook execution as a proven solution.
        
        This enables the learning system to automatically capture what worked
        for which problems, improving future troubleshooting.
        """
        from ..models import SolutionOutcome
        from ..services.embedding_service import EmbeddingService
        
        try:
            # Get the alert to build problem description
            result = await self.db.execute(
                select(Alert).where(Alert.id == execution.alert_id)
            )
            alert = result.scalar_one_or_none()
            
            if not alert:
                logger.warning(f"Alert {execution.alert_id} not found - skipping learning")
                return
            
            # Build problem description from alert
            problem_parts = [
                f"Alert: {alert.alert_name}",
                f"Severity: {alert.severity}",
            ]
            
            if alert.instance:
                problem_parts.append(f"Instance: {alert.instance}")
            
            # Add description from annotations if available
            if alert.annotations_json and isinstance(alert.annotations_json, dict):
                description = (
                    alert.annotations_json.get('description') or
                    alert.annotations_json.get('summary')
                )
                if description:
                    problem_parts.append(f"Description: {description}")
            
            problem_description = "\n".join(problem_parts)
            
            # Generate embedding for the problem (synchronous call in async context)
            problem_embedding = None
            try:
                embedding_service = EmbeddingService()
                if embedding_service.is_configured():
                    # Use the alert embedding generation method
                    problem_embedding = embedding_service.generate_for_alert(alert)
                    if problem_embedding:
                        logger.info(f"Generated embedding for auto-learning from execution {execution.id}")
                else:
                    logger.debug("Embedding service not configured - learning without embedding")
            except Exception as e:
                logger.warning(f"Failed to generate embedding for learning: {e}")
                # Continue without embedding - still valuable to record the solution
            
            # Create solution outcome record
            outcome = SolutionOutcome(
                session_id=None,  # Not associated with a chat session
                problem_description=problem_description,
                problem_embedding=problem_embedding,
                alert_id=alert.id,
                server_id=execution.server_id,
                solution_type='runbook',
                solution_reference=str(execution.runbook_id),
                solution_summary=f"Runbook: {runbook.name}",
                success=True,
                auto_detected=True,  # Automatically detected success
                user_feedback=None,
                feedback_timestamp=utc_now()
            )
            
            self.db.add(outcome)
            await self.db.commit()
            
            logger.info(
                f"Auto-recorded successful solution: runbook '{runbook.name}' "
                f"for alert '{alert.alert_name}' (execution {execution.id})"
            )
            
        except Exception as e:
            logger.error(f"Error recording successful solution: {e}", exc_info=True)
            # Don't raise - this is a non-critical enhancement
