"""
Command Validator Service

Validates commands against blocklist/allowlist patterns.
Prevents execution of dangerous commands.
"""

import re
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models_remediation import CommandBlocklist, CommandAllowlist

logger = logging.getLogger(__name__)


class ValidationResult(str, Enum):
    """Result of command validation."""
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    SUSPICIOUS = "suspicious"


@dataclass
class CommandValidation:
    """Result of validating a command."""
    result: ValidationResult
    command: str
    reason: Optional[str] = None
    matched_pattern: Optional[str] = None
    risk_level: str = "low"  # low, medium, high, critical


# Default dangerous patterns for Linux
DEFAULT_LINUX_BLOCKLIST = [
    # Destructive commands
    (r"rm\s+-rf\s+/(?:\s|$)", "Recursive delete of root filesystem", "critical"),
    (r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*)+\s+/(?:\s|$)", "Destructive rm on root", "critical"),
    (r"dd\s+.*if=/dev/zero.*of=/dev/[sh]d[a-z]", "Overwriting disk with zeros", "critical"),
    (r"mkfs\.", "Filesystem formatting", "critical"),
    (r">\s*/dev/[sh]d[a-z]", "Writing to raw disk device", "critical"),
    
    # Fork bombs
    (r":\(\)\s*\{\s*:\|\:\s*&\s*\}\s*;", "Fork bomb detected", "critical"),
    (r"\.\s*/dev/tcp/", "Reverse shell attempt", "critical"),
    
    # Dangerous permission changes
    (r"chmod\s+(-R\s+)?777\s+/(?:\s|$)", "Dangerous permission change to root", "high"),
    (r"chown\s+(-R\s+)?.*\s+/(?:\s|$)", "Ownership change on root", "high"),
    
    # Remote code execution
    (r"(wget|curl)\s+.*\|\s*(bash|sh)", "Remote code execution via pipe", "critical"),
    (r"(wget|curl)\s+.*>\s*/tmp/.*;\s*(bash|sh)", "Remote script download and execute", "high"),
    
    # Kernel/system manipulation
    (r"insmod\s+", "Loading kernel module", "high"),
    (r"modprobe\s+", "Loading kernel module", "high"),
    (r"sysctl\s+-w", "Modifying kernel parameters", "medium"),
    
    # Credential access
    (r"cat\s+.*(passwd|shadow|sudoers)", "Reading sensitive files", "medium"),
    (r"\.ssh/.*_rsa", "Accessing SSH keys", "medium"),
]

# Default dangerous patterns for Windows/PowerShell
DEFAULT_WINDOWS_BLOCKLIST = [
    # Destructive commands
    (r"Remove-Item\s+.*-Recurse\s+.*-Force\s+[A-Z]:\\(?:\s|$)", "Recursive delete of root", "critical"),
    (r"Format-Volume", "Volume formatting", "critical"),
    (r"Clear-Disk", "Disk clearing", "critical"),
    (r"Initialize-Disk\s+.*-RemoveData", "Disk initialization with data removal", "critical"),
    
    # System manipulation
    (r"Stop-Computer\s+-Force", "Forced shutdown", "high"),
    (r"Restart-Computer\s+-Force", "Forced restart", "high"),
    
    # Remote code execution
    (r"Invoke-Expression", "Arbitrary code execution (IEX)", "high"),
    (r"iex\s*\(", "Arbitrary code execution (IEX)", "high"),
    (r"Invoke-WebRequest.*\|\s*iex", "Remote code execution", "critical"),
    (r"DownloadString.*\|\s*iex", "Remote code execution", "critical"),
    
    # Credential access
    (r"Get-Credential", "Credential prompting", "medium"),
    (r"ConvertTo-SecureString", "Secure string manipulation", "low"),
    
    # Registry manipulation
    (r"Remove-Item\s+.*HKLM:", "Registry deletion", "high"),
    (r"Set-ItemProperty\s+.*HKLM:.*Run", "Modifying startup registry", "high"),
]


class CommandValidator:
    """
    Validates commands against security patterns.
    
    Uses both hardcoded patterns and database patterns
    to validate commands before execution.
    """
    
    def __init__(self, db: Optional[AsyncSession] = None):
        """
        Initialize the validator.
        
        Args:
            db: Database session for loading custom patterns.
        """
        self.db = db
        self._linux_blocklist: List[Tuple[str, str, str]] = list(DEFAULT_LINUX_BLOCKLIST)
        self._windows_blocklist: List[Tuple[str, str, str]] = list(DEFAULT_WINDOWS_BLOCKLIST)
        self._linux_allowlist: List[str] = []
        self._windows_allowlist: List[str] = []
        self._patterns_loaded = False
    
    async def load_patterns(self):
        """Load custom patterns from database."""
        if not self.db or self._patterns_loaded:
            return
        
        try:
            # Load blocklist
            result = await self.db.execute(
                select(CommandBlocklist).where(CommandBlocklist.enabled == True)
            )
            blocklist = result.scalars().all()
            
            for entry in blocklist:
                pattern_tuple = (
                    entry.pattern,
                    entry.reason,
                    entry.severity or "high"
                )
                if entry.os_type == "linux":
                    self._linux_blocklist.append(pattern_tuple)
                elif entry.os_type == "windows":
                    self._windows_blocklist.append(pattern_tuple)
                else:  # "any"
                    self._linux_blocklist.append(pattern_tuple)
                    self._windows_blocklist.append(pattern_tuple)
            
            # Load allowlist
            result = await self.db.execute(
                select(CommandAllowlist).where(CommandAllowlist.enabled == True)
            )
            allowlist = result.scalars().all()
            
            for entry in allowlist:
                if entry.os_type == "linux":
                    self._linux_allowlist.append(entry.pattern)
                elif entry.os_type == "windows":
                    self._windows_allowlist.append(entry.pattern)
                else:
                    self._linux_allowlist.append(entry.pattern)
                    self._windows_allowlist.append(entry.pattern)
            
            self._patterns_loaded = True
            logger.info(f"Loaded {len(blocklist)} blocklist and {len(allowlist)} allowlist patterns")
            
        except Exception as e:
            logger.warning(f"Failed to load patterns from database: {e}")
    
    def validate_command(
        self,
        command: str,
        os_type: str = "linux",
        use_allowlist: bool = False
    ) -> CommandValidation:
        """
        Validate a single command.
        
        Args:
            command: The command to validate.
            os_type: "linux" or "windows".
            use_allowlist: If True, command must match allowlist.
        
        Returns:
            CommandValidation with result and details.
        """
        os_type = os_type.lower()
        command = command.strip()
        
        # Get appropriate patterns
        blocklist = self._linux_blocklist if os_type == "linux" else self._windows_blocklist
        allowlist = self._linux_allowlist if os_type == "linux" else self._windows_allowlist
        
        # Check blocklist first
        for pattern, reason, severity in blocklist:
            try:
                if re.search(pattern, command, re.IGNORECASE):
                    return CommandValidation(
                        result=ValidationResult.BLOCKED,
                        command=command,
                        reason=reason,
                        matched_pattern=pattern,
                        risk_level=severity
                    )
            except re.error as e:
                logger.warning(f"Invalid regex pattern: {pattern}: {e}")
        
        # Check allowlist if required
        if use_allowlist and allowlist:
            for pattern in allowlist:
                try:
                    if re.match(pattern, command, re.IGNORECASE):
                        return CommandValidation(
                            result=ValidationResult.ALLOWED,
                            command=command,
                            reason="Matches allowlist pattern",
                            matched_pattern=pattern,
                            risk_level="low"
                        )
                except re.error as e:
                    logger.warning(f"Invalid allowlist pattern: {pattern}: {e}")
            
            # If allowlist required but no match, block
            return CommandValidation(
                result=ValidationResult.BLOCKED,
                command=command,
                reason="Command not in allowlist",
                risk_level="medium"
            )
        
        # Check for suspicious patterns (warnings, not blocked)
        suspicious_patterns = [
            (r"sudo\s+", "Uses sudo elevation"),
            (r">\s*/etc/", "Writing to /etc"),
            (r"pip\s+install", "Package installation"),
            (r"apt(-get)?\s+install", "Package installation"),
            (r"yum\s+install", "Package installation"),
            (r"Install-Module", "PowerShell module installation"),
        ]
        
        for pattern, reason in suspicious_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandValidation(
                    result=ValidationResult.SUSPICIOUS,
                    command=command,
                    reason=reason,
                    matched_pattern=pattern,
                    risk_level="low"
                )
        
        # Command is allowed
        return CommandValidation(
            result=ValidationResult.ALLOWED,
            command=command,
            reason="No dangerous patterns detected",
            risk_level="low"
        )
    
    def validate_commands(
        self,
        commands: List[str],
        os_type: str = "linux",
        use_allowlist: bool = False
    ) -> List[CommandValidation]:
        """
        Validate multiple commands.
        
        Args:
            commands: List of commands to validate.
            os_type: Operating system type.
            use_allowlist: Require allowlist match.
        
        Returns:
            List of CommandValidation results.
        """
        return [
            self.validate_command(cmd, os_type, use_allowlist)
            for cmd in commands
        ]
    
    def validate_runbook_commands(
        self,
        steps: list,
        os_type: str = "linux",
        use_allowlist: bool = False
    ) -> List[dict]:
        """
        Validate all commands in runbook steps.
        
        Args:
            steps: List of RunbookStep objects or dicts.
            os_type: Operating system type.
            use_allowlist: Require allowlist match.
        
        Returns:
            List of validation results per step.
        """
        results = []
        
        for step in steps:
            step_result = {
                "step_order": getattr(step, 'step_order', step.get('step_order', 0)),
                "step_name": getattr(step, 'name', step.get('name', '')),
                "validations": []
            }
            
            # Get commands for specified OS
            if os_type == "linux":
                command = getattr(step, 'command_linux', None) or step.get('command_linux')
            else:
                command = getattr(step, 'command_windows', None) or step.get('command_windows')
            
            if command:
                validation = self.validate_command(command, os_type, use_allowlist)
                step_result["validations"].append({
                    "command_type": f"command_{os_type}",
                    **vars(validation)
                })
            
            # Also check rollback commands
            if os_type == "linux":
                rollback = getattr(step, 'rollback_command_linux', None) or step.get('rollback_command_linux')
            else:
                rollback = getattr(step, 'rollback_command_windows', None) or step.get('rollback_command_windows')
            
            if rollback:
                validation = self.validate_command(rollback, os_type, use_allowlist)
                step_result["validations"].append({
                    "command_type": f"rollback_{os_type}",
                    **vars(validation)
                })
            
            results.append(step_result)
        
        return results
    
    def has_blocked_commands(self, validations: List[CommandValidation]) -> bool:
        """Check if any validations are blocked."""
        return any(v.result == ValidationResult.BLOCKED for v in validations)
    
    def get_blocked_reasons(self, validations: List[CommandValidation]) -> List[str]:
        """Get reasons for blocked commands."""
        return [
            f"{v.command[:50]}... - {v.reason}"
            for v in validations
            if v.result == ValidationResult.BLOCKED
        ]


# Convenience function for quick validation
def validate_command(
    command: str,
    os_type: str = "linux"
) -> CommandValidation:
    """
    Quick validation without database patterns.
    
    Args:
        command: Command to validate.
        os_type: Operating system type.
    
    Returns:
        CommandValidation result.
    """
    validator = CommandValidator()
    return validator.validate_command(command, os_type)
