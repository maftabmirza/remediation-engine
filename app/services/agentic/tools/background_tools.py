"""
Background Agent Tools - SECURITY DISABLED

⚠️ SECURITY NOTICE ⚠️
This module previously allowed autonomous command execution on servers.
This functionality has been PERMANENTLY DISABLED for security reasons.

Background agents are now READ-ONLY:
- Can query monitoring systems (Prometheus, Grafana)
- Can search knowledge base (runbooks, documentation)  
- Can read logs
- CANNOT execute arbitrary commands

For command execution:
- Use interactive agents with suggest_ssh_command (user approval required)
- Use action proposal mechanism (coming in Phase 4.1)
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID

from app.services.agentic.tools import Tool, ToolParameter, ToolModule

logger = logging.getLogger(__name__)

class BackgroundTools(ToolModule):
    """
    DEPRECATED AND DISABLED MODULE
    
    This class is kept for compatibility but registers NO tools.
    execute_server_command has been removed for security.
    """

    def _register_tools(self):
        """
        SECURITY: No tools registered.
        
        The execute_server_command tool has been permanently removed.
        Background agents must use:
        - ObservabilityTools (read-only monitoring)
        - KnowledgeTools (read-only documentation)
        """
        logger.warning(
            "BackgroundTools module loaded but contains no tools. "
            "Autonomous command execution has been disabled for security."
        )
        # No tools registered - this module is a no-op
        pass
