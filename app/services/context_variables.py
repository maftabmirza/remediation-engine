"""
Context Variable System

Provides #variable references for accessing prior data in the AI terminal.
Inspired by VS Code Copilot Chat context variables (#file, #selection).
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ContextVariableResolver:
    """
    Resolves #variable references in chat messages.
    Example: "Explain #output" → resolves #output to last command output
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def resolve(self, variable_name: str, session_id: UUID, args: Dict[str, Any] = None) -> str:
        """
        Resolve a context variable to its value.
        
        Args:
            variable_name: Variable name (with or without #)
            session_id: Current AI session ID
            args: Additional context (server_id, agent_step_id, etc.)
            
        Returns:
            Resolved value or error message
        """
        args = args or {}
        
        # Normalize variable name
        if variable_name.startswith("#"):
            variable_name = variable_name[1:]
        
        # Route to appropriate resolver
        if variable_name.startswith("file:"):
            return self._resolve_file(variable_name, args)
        elif variable_name == "output":
            return self._resolve_output(session_id, args)
        elif variable_name == "error":
            return self._resolve_error(session_id, args)
        elif variable_name == "plan":
            return self._resolve_plan(session_id, args)
        elif variable_name == "changeset":
            return self._resolve_changeset(session_id, args)
        else:
            return f"Unknown variable: #{variable_name}"
    
    def list_available(self, session_id: UUID) -> List[str]:
        """
        List all available variables for a session.
        
        Args:
            session_id: Current session ID
            
        Returns:
            List of variable names (with #)
        """
        # Base variables always available
        base_vars = ["#file:<path>", "#output", "#error", "#plan", "#changeset"]
        
        # TODO: Add session-specific variables (e.g., #output available if commands run)
        
        return base_vars
    
    def _resolve_file(self, variable: str, args: Dict) -> str:
        """
        Resolve #file:<path> variable.
        Example: #file:/etc/nginx/nginx.conf
        """
        from app.services.file_ops_service import FileOpsService
        
        # Extract file path
        if ":" not in variable:
            return "Error: #file requires path (e.g., #file:/etc/nginx/nginx.conf)"
        
        file_path = variable.split(":", 1)[1]
        server_id = args.get("server_id")
        
        if not server_id:
            return f"Error: No server selected for #file:{file_path}"
        
        try:
            # Use FileOpsService to read file
            file_service = FileOpsService(self.db)
            result = asyncio.run(file_service.read_file(server_id, file_path))
            
            content = result.get("content", "")
            # Truncate if too long
            if len(content) > 2000:
                content = content[:2000] + f"\n... (truncated, total {len(content)} characters)"
            
            return f"File: {file_path}\n```\n{content}\n```"
        except Exception as e:
            logger.error(f"Error resolving #file:{file_path}: {e}")
            return f"Error reading file {file_path}: {str(e)}"
    
    def _resolve_output(self, session_id: UUID, args: Dict) -> str:
        """Resolve #output variable (last command output)"""
        from app.models_agent import AgentStep
        
        # Get most recent agent step with command output
        step = self.db.query(AgentStep).join(
            AgentStep.session
        ).filter(
            AgentStep.session.has(id=session_id),
            AgentStep.step_type == "command",
            AgentStep.output.isnot(None)
        ).order_by(AgentStep.created_at.desc()).first()
        
        if not step:
            return "(No recent command output)"
        
        output = step.output or "(Empty output)"
        
        # Truncate if too long
        if len(output) > 1500:
            output = output[:1500] + f"\n... (truncated, total {len(output)} characters)"
        
        return f"Last command output:\n```\n{output}\n```"
    
    def _resolve_error(self, session_id: UUID, args: Dict) -> str:
        """Resolve #error variable (last error message)"""
        from app.models_agent import AgentStep
        
        # Get most recent agent step with error
        step = self.db.query(AgentStep).join(
            AgentStep.session
        ).filter(
            AgentStep.session.has(id=session_id),
            AgentStep.error_message.isnot(None)
        ).order_by(AgentStep.created_at.desc()).first()
        
        if not step:
            return "(No recent errors)"
        
        return f"Last error:\n```\n{step.error_message}\n```"
    
    def _resolve_plan(self, session_id: UUID, args: Dict) -> str:
        """Resolve #plan variable (current plan)"""
        # TODO: Implement when plan models are available
        # For now, return placeholder
        return "(Current plan - feature coming soon)"
    
    def _resolve_changeset(self, session_id: UUID, args: Dict) -> str:
        """Resolve #changeset variable (pending changes)"""
        from app.models_changeset import ChangeSet
        
        # Get most recent pending or previewing changeset
        changeset = self.db.query(ChangeSet).filter(
            ChangeSet.session_id == session_id,
            ChangeSet.status.in_(["pending", "previewing"])
        ).order_by(ChangeSet.created_at.desc()).first()
        
        if not changeset:
            return "(No pending changes)"
        
        # Summarize changeset
        items = changeset.items or []
        summary = f"Pending changes ({len(items)} files):\n"
        for item in items[:5]:  # Show first 5
            summary += f"- {item.operation.upper()}: {item.file_path}\n"
        
        if len(items) > 5:
            summary += f"... and {len(items) - 5} more"
        
        return summary


# Import asyncio for async file ops
import asyncio


def resolve_all_variables(text: str, db: Session, session_id: UUID, args: Dict[str, Any] = None) -> str:
    """
    Find and resolve all #variables in text.
    
    Args:
        text: Input text with #variables
        db: Database session
        session_id: Current session ID
        args: Additional context
        
    Returns:
        Text with variables replaced by their values
    """
    import re
    
    resolver = ContextVariableResolver(db)
    args = args or {}
    
    # Pattern to match #variable or #variable:arg
    pattern = r'#([\w:/.]+)'
    
    def replace_var(match):
        var_name = match.group(1)
        try:
            return resolver.resolve(var_name, session_id, args)
        except Exception as e:
            logger.error(f"Error resolving #{var_name}: {e}")
            return f"(Error resolving #{var_name})"
    
    return re.sub(pattern, replace_var, text)
