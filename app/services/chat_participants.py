"""
Chat Participant System

Provides @participant mentions for context injection in the AI terminal.
Inspired by VS Code Copilot Chat participants (@workspace, @terminal).
"""

import logging
from typing import Optional, List, Dict, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class ChatParticipant:
    """Definition of a chat participant"""
    name: str  # e.g., "@server"
    description: str  # Short description for autocomplete
    context_provider: Callable  # Function that returns context string
    requires_server: bool = True
    example: str = ""  # e.g., "What's the uptime? @server"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API responses"""
        return {
            "name": self.name,
            "description": self.description,
            "requires_server": self.requires_server,
            "example": self.example
        }


class ParticipantRegistry:
    """
    Registry for chat participants.
    Participants provide context when @-mentioned in chat.
    """
    
    def __init__(self):
        self._participants: Dict[str, ChatParticipant] = {}
        self._register_builtin_participants()
    
    def register(self, participant: ChatParticipant):
        """Register a new chat participant"""
        if not participant.name.startswith("@"):
            participant.name = f"@{participant.name}"
        
        self._participants[participant.name] = participant
        logger.info(f"Registered chat participant: {participant.name}")
    
    def get_context(
        self, 
        mentions: List[str], 
        db: Session,
        args: Dict[str, Any]
    ) -> str:
        """
        Get aggregated context from all mentioned participants.
        
        Args:
            mentions: List of participant names (e.g., ["@server", "@logs"])
            db: Database session for context fetching
            args: Additional arguments (server_id, session_id, etc.)
            
        Returns:
            Aggregated context string
        """
        contexts = []
        
        for mention in mentions:
            if not mention.startswith("@"):
                mention = f"@{mention}"
            
            participant = self._participants.get(mention)
            if not participant:
                logger.warning(f"Unknown participant: {mention}")
                continue
            
            try:
                context = participant.context_provider(db, args)
                if context:
                    contexts.append(f"### Context from {mention}\n{context}")
            except Exception as e:
                logger.error(f"Error getting context from {mention}: {e}")
                contexts.append(f"### Context from {mention}\n(Error: {str(e)})")
        
        return "\n\n".join(contexts) if contexts else ""
    
    def get_all_participants(self) -> List[ChatParticipant]:
        """Get all registered participants"""
        return list(self._participants.values())
    
    def get_participant(self, name: str) -> Optional[ChatParticipant]:
        """Get a specific participant by name"""
        if not name.startswith("@"):
            name = f"@{name}"
        return self._participants.get(name)
    
    def get_completions(self, prefix: str) -> List[ChatParticipant]:
        """
        Get participant suggestions based on prefix.
        
        Args:
            prefix: Partial participant (e.g., "@ser")
            
        Returns:
            List of matching participants
        """
        prefix = prefix.lower()
        
        matches = []
        for participant in self._participants.values():
            if participant.name.startswith(prefix):
                matches.append(participant)
        
        matches.sort(key=lambda p: len(p.name))
        return matches
    
    def _register_builtin_participants(self):
        """Register built-in chat participants"""
        
        # @server - Current server context
        self.register(ChatParticipant(
            name="@server",
            description="Current server information",
            context_provider=self._get_server_context,
            example="What's the uptime? @server"
        ))
        
        # @logs - Recent log entries
        self.register(ChatParticipant(
            name="@logs",
            description="Recent log entries",
            context_provider=self._get_logs_context,
            example="Any errors? @logs"
        ))
        
        # @metrics - Recent performance metrics
        self.register(ChatParticipant(
            name="@metrics",
            description="Recent performance metrics",
            context_provider=self._get_metrics_context,
            example="Show CPU trends @metrics"
        ))
        
        # @runbook - Relevant runbook steps
        self.register(ChatParticipant(
            name="@runbook",
            description="Relevant runbook steps",
            context_provider=self._get_runbook_context,
            requires_server=False,
            example="How do I restart nginx? @runbook"
        ))
        
        # @alert - Current alert context
        self.register(ChatParticipant(
            name="@alert",
            description="Current alert details",
            context_provider=self._get_alert_context,
            requires_server=False,
            example="Analyze this @alert"
        ))
    
    # Context provider implementations
    
    def _get_server_context(self, db: Session, args: Dict) -> str:
        """Get server information"""
        from app.models import ServerCredential
        
        server_id = args.get("server_id")
        if not server_id:
            return "No server selected"
        
        server = db.query(ServerCredential).filter(ServerCredential.id == server_id).first()
        if not server:
            return "Server not found"
        
        context = f"""
Server: {server.name}
Hostname: {server.hostname}
Port: {server.port}
OS: {server.os_type or 'Unknown'}
"""
        return context.strip()
    
    def _get_logs_context(self, db: Session, args: Dict) -> str:
        """Get recent log entries"""
        # TODO: Implement log fetching from server
        # For now, return placeholder
        return "Recent logs: (Feature coming soon - will fetch from /var/log)"
    
    def _get_metrics_context(self, db: Session, args: Dict) -> str:
        """Get recent performance metrics"""
        server_id = args.get("server_id")
        if not server_id:
            return "No server selected"
        
        # TODO: Fetch from Prometheus/metrics DB
        # For now, return placeholder
        return "Recent metrics: (Will fetch CPU, memory, disk from Prometheus)"
    
    def _get_runbook_context(self, db: Session, args: Dict) -> str:
        """Get relevant runbook steps"""
        from app.models_remediation import Runbook
        
        query = args.get("query", "")
        if not query:
            return "No query provided"
        
        # Search runbooks by title/description
        runbooks = db.query(Runbook).filter(
            Runbook.title.ilike(f"%{query}%")
        ).limit(3).all()
        
        if not runbooks:
            return f"No runbooks found matching: {query}"
        
        context_parts = []
        for rb in runbooks:
            context_parts.append(f"- **{rb.title}**: {rb.description or 'No description'}")
        
        return "Relevant runbooks:\n" + "\n".join(context_parts)
    
    def _get_alert_context(self, db: Session, args: Dict) -> str:
        """Get current alert details"""
        from app.models import Alert
        
        alert_id = args.get("alert_id")
        if not alert_id:
            return "No alert selected"
        
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return "Alert not found"
        
        context = f"""
Alert: {alert.alert_name}
Severity: {alert.severity}
Instance: {alert.instance}
Status: {alert.status}
Timestamp: {alert.timestamp}
"""
        
        if alert.description:
            context += f"\nDescription: {alert.description}"
        
        return context.strip()


# Global registry instance
_registry = ParticipantRegistry()


def get_registry() -> ParticipantRegistry:
    """Get the global participant registry"""
    return _registry
