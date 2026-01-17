from sqlalchemy.orm import Session
from app.models_iteration import IterationLoop
from app.models_agent_pool import AgentTask
import uuid
import logging

logger = logging.getLogger(__name__)

class IterationService:
    def __init__(self, db: Session):
        self.db = db

    def record_iteration(
        self,
        agent_task_id: uuid.UUID,
        iteration_number: int,
        command: str,
        output: str,
        exit_code: int
    ) -> IterationLoop:
        """
        Record a command iteration and perform basic error analysis.
        """
        error_detected = False
        error_type = None
        
        # heuristic: non-zero exit code or stderr usually means error
        if exit_code != 0:
            error_detected = True
            error_type = "NonZeroExitCode"
        elif output and "error" in output.lower():  # Simple heuristic
             # Be careful not to flag "Error: 0"
             pass 

        # Analyze error type (basic heuristics)
        if error_detected:
            error_type = self._analyze_error_type(output, exit_code)

        iteration = IterationLoop(
            agent_task_id=agent_task_id,
            iteration_number=iteration_number,
            command=command,
            output=output,
            exit_code=exit_code,
            error_detected=error_detected,
            error_type=error_type,
            # error_analysis and fix_proposed specific to LLM, added later or via update
        )
        self.db.add(iteration)
        self.db.commit()
        self.db.refresh(iteration)
        return iteration

    def _analyze_error_type(self, output: str, exit_code: int) -> str:
        if not output:
             return "Unknown"
        
        output_lower = output.lower()
        if "permission denied" in output_lower:
            return "PermissionDenied"
        if "not found" in output_lower or "no such file" in output_lower:
            return "FileNotFound"
        if "syntax error" in output_lower:
            return "SyntaxError"
        if "timeout" in output_lower:
            return "Timeout"
        
        return "RuntimeError"

    def update_analysis(self, iteration_id: uuid.UUID, analysis: str, fix: str):
        """Update iteration with LLM analysis"""
        iteration = self.db.query(IterationLoop).filter(IterationLoop.id == iteration_id).first()
        if iteration:
            iteration.error_analysis = analysis
            iteration.fix_proposed = fix
            self.db.commit()
