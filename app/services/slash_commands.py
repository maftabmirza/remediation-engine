"""
Slash Command System

Provides /command shortcuts for quick actions in the AI terminal.
Inspired by VS Code Copilot Chat slash commands.
"""

import re
import logging
from typing import Optional, List, Dict, Callable, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SlashCommandCategory(str, Enum):
    """Categories for organizing commands"""
    INVESTIGATION = "investigation"
    ACTION = "action"
    INFORMATION = "information"
    MANAGEMENT = "management"


@dataclass
class SlashCommand:
    """Definition of a slash command"""
    name: str  # e.g., "/diagnose"
    description: str  # Short description for autocomplete
    args_pattern: str  # e.g., "<issue description>"
    handler: Callable  # Function to execute
    category: SlashCommandCategory
    requires_server: bool = True
    example: str = ""  # e.g., "/diagnose high CPU on web-01"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API responses"""
        return {
            "name": self.name,
            "description": self.description,
            "args_pattern": self.args_pattern,
            "category": self.category.value,
            "requires_server": self.requires_server,
            "example": self.example
        }


@dataclass
class ParsedCommand:
    """Result of parsing a slash command"""
    command: SlashCommand
    args: str  # Raw arguments string
    parsed_args: Dict[str, Any]  # Structured arguments


class SlashCommandRegistry:
    """
    Central registry for slash commands.
    Handles registration, parsing, and autocomplete.
    """
    
    def __init__(self):
        self._commands: Dict[str, SlashCommand] = {}
        self._register_builtin_commands()
    
    def register(self, command: SlashCommand):
        """Register a new slash command"""
        if not command.name.startswith("/"):
            command.name = f"/{command.name}"
        
        self._commands[command.name] = command
        logger.info(f"Registered slash command: {command.name}")
    
    def parse(self, input_text: str) -> Optional[ParsedCommand]:
        """
        Parse input text and extract slash command if present.
        
        Args:
            input_text: User input (e.g., "/diagnose high cpu")
            
        Returns:
            ParsedCommand if valid command found, None otherwise
        """
        input_text = input_text.strip()
        
        # Must start with /
        if not input_text.startswith("/"):
            return None
        
        # Extract command name (first word)
        parts = input_text.split(maxsplit=1)
        command_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Find command
        command = self._commands.get(command_name)
        if not command:
            return None
        
        # Parse arguments based on command
        parsed_args = self._parse_args(command, args)
        
        return ParsedCommand(
            command=command,
            args=args,
            parsed_args=parsed_args
        )
    
    def _parse_args(self, command: SlashCommand, args: str) -> Dict[str, Any]:
        """Parse arguments for a specific command"""
        # Simple implementation: return args as-is
        # Can be enhanced per-command with structured parsing
        return {"raw": args}
    
    def get_completions(self, prefix: str) -> List[SlashCommand]:
        """
        Get command suggestions based on prefix.
        
        Args:
            prefix: Partial command (e.g., "/diag")
            
        Returns:
            List of matching commands, sorted by relevance
        """
        prefix = prefix.lower()
        
        # Exact and prefix matches
        matches = []
        for cmd in self._commands.values():
            if cmd.name.startswith(prefix):
                matches.append(cmd)
        
        # Sort by name length (shorter = more likely what user wants)
        matches.sort(key=lambda c: len(c.name))
        
        return matches
    
    def get_all_commands(self) -> List[SlashCommand]:
        """Get all registered commands"""
        return list(self._commands.values())
    
    def get_command(self, name: str) -> Optional[SlashCommand]:
        """Get a specific command by name"""
        if not name.startswith("/"):
            name = f"/{name}"
        return self._commands.get(name)
    
    def _register_builtin_commands(self):
        """Register built-in commands"""
        
        # /diagnose - Start investigation
        self.register(SlashCommand(
            name="/diagnose",
            description="Start diagnostic investigation",
            args_pattern="<issue description>",
            handler=None,  # Handler set by router
            category=SlashCommandCategory.INVESTIGATION,
            example="/diagnose high CPU on web-server-01"
        ))
        
        # /fix - Apply a fix
        self.register(SlashCommand(
            name="/fix",
            description="Apply a fix with confirmation",
            args_pattern="<what to fix>",
            handler=None,
            category=SlashCommandCategory.ACTION,
            example="/fix restart nginx service"
        ))
        
        # /explain - Explain command or concept
        self.register(SlashCommand(
            name="/explain",
            description="Explain a command or concept",
            args_pattern="<command or topic>",
            handler=None,
            category=SlashCommandCategory.INFORMATION,
            requires_server=False,
            example="/explain iptables -L"
        ))
        
        # /plan - Manage current plan
        self.register(SlashCommand(
            name="/plan",
            description="Show or edit current plan",
            args_pattern="[show|create|edit]",
            handler=None,
            category=SlashCommandCategory.MANAGEMENT,
            requires_server=False,
            example="/plan show"
        ))
        
        # /rollback - Rollback changes
        self.register(SlashCommand(
            name="/rollback",
            description="Rollback last applied changes",
            args_pattern="[change_set_id]",
            handler=None,
            category=SlashCommandCategory.ACTION,
            example="/rollback"
        ))
        
        # /spawn - Spawn background agent
        self.register(SlashCommand(
            name="/spawn",
            description="Spawn a background agent",
            args_pattern="<agent goal>",
            handler=None,
            category=SlashCommandCategory.MANAGEMENT,
            example="/spawn run all tests and fix failures"
        ))
        
        # /hq - Show Agent HQ
        self.register(SlashCommand(
            name="/hq",
            description="Show Agent HQ status",
            args_pattern="",
            handler=None,
            category=SlashCommandCategory.MANAGEMENT,
            requires_server=False,
            example="/hq"
        ))
        
        # /help - Show available commands
        self.register(SlashCommand(
            name="/help",
            description="Show all available commands",
            args_pattern="[command_name]",
            handler=None,
            category=SlashCommandCategory.INFORMATION,
            requires_server=False,
            example="/help"
        ))


# Global registry instance
_registry = SlashCommandRegistry()


def get_registry() -> SlashCommandRegistry:
    """Get the global slash command registry"""
    return _registry
