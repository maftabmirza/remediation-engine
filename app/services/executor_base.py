"""
Executor Framework - Base Classes

Provides abstract base classes for command execution on remote servers.
Supports multiple protocols (SSH, WinRM) with a unified interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, AsyncIterator
from enum import Enum
import asyncio


class ErrorType(str, Enum):
    """Types of execution errors."""
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    AUTH = "auth"
    COMMAND = "command"
    PERMISSION = "permission"
    UNKNOWN = "unknown"


@dataclass
class ExecutionResult:
    """
    Result of a command execution.
    
    Contains all information about a single command execution,
    including output, exit code, timing, and error details.
    """
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    
    # Command context
    command: str
    server_hostname: str
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Error handling
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None
    retryable: bool = False
    
    # For streaming output
    output_lines: List[str] = field(default_factory=list)
    
    @property
    def combined_output(self) -> str:
        """Combine stdout and stderr for display."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"[STDERR]\n{self.stderr}")
        return "\n".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "command": self.command,
            "server_hostname": self.server_hostname,
            "executed_at": self.executed_at.isoformat(),
            "error_type": self.error_type.value if self.error_type else None,
            "error_message": self.error_message,
            "retryable": self.retryable
        }


@dataclass
class ServerInfo:
    """Information about a remote server."""
    hostname: str
    os_type: str  # "linux" or "windows"
    os_version: Optional[str] = None
    kernel_version: Optional[str] = None
    architecture: Optional[str] = None
    uptime_seconds: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hostname": self.hostname,
            "os_type": self.os_type,
            "os_version": self.os_version,
            "kernel_version": self.kernel_version,
            "architecture": self.architecture,
            "uptime_seconds": self.uptime_seconds
        }


class BaseExecutor(ABC):
    """
    Abstract base class for command executors.
    
    Defines the interface that all executors (SSH, WinRM) must implement.
    Handles connection management, command execution, and error handling.
    """
    
    def __init__(
        self,
        hostname: str,
        port: int,
        username: str,
        timeout: int = 60
    ):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.timeout = timeout
        self._connected = False
        self._connection = None
    
    @property
    def is_connected(self) -> bool:
        """Check if executor is currently connected."""
        return self._connected
    
    @property
    @abstractmethod
    def protocol(self) -> str:
        """Return the protocol name (ssh, winrm)."""
        pass
    
    @property
    @abstractmethod
    def supports_elevation(self) -> bool:
        """Whether this executor supports privilege elevation."""
        pass
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the remote server.
        
        Returns:
            bool: True if connection successful, False otherwise.
        
        Raises:
            ConnectionError: If connection fails with details.
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection to the remote server."""
        pass
    
    @abstractmethod
    async def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        with_elevation: bool = False,
        env: Optional[Dict[str, str]] = None,
        working_directory: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute a command on the remote server.
        
        Args:
            command: The command to execute.
            timeout: Command timeout in seconds (overrides default).
            with_elevation: Run with elevated privileges (sudo/admin).
            env: Additional environment variables.
            working_directory: Directory to run command in.
        
        Returns:
            ExecutionResult with command output and status.
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if connection to server is working.
        
        Returns:
            bool: True if connection test successful.
        """
        pass
    
    @abstractmethod
    async def get_server_info(self) -> ServerInfo:
        """
        Get information about the remote server.
        
        Returns:
            ServerInfo with OS details, version, etc.
        """
        pass
    
    async def execute_with_retry(
        self,
        command: str,
        max_retries: int = 3,
        retry_delay: int = 5,
        timeout: Optional[int] = None,
        with_elevation: bool = False,
        env: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """
        Execute a command with automatic retry on retryable failures.
        
        Args:
            command: The command to execute.
            max_retries: Maximum number of retry attempts.
            retry_delay: Seconds to wait between retries.
            timeout: Command timeout.
            with_elevation: Run with elevated privileges.
            env: Environment variables.
        
        Returns:
            ExecutionResult from the final attempt.
        """
        last_result = None
        
        for attempt in range(max_retries + 1):
            result = await self.execute(
                command=command,
                timeout=timeout,
                with_elevation=with_elevation,
                env=env
            )
            
            if result.success:
                return result
            
            last_result = result
            
            # Only retry if error is retryable
            if not result.retryable or attempt >= max_retries:
                break
            
            # Wait before retry
            await asyncio.sleep(retry_delay)
            
            # Reconnect if connection error
            if result.error_type == ErrorType.CONNECTION:
                try:
                    await self.disconnect()
                    await self.connect()
                except Exception:
                    pass
        
        return last_result
    
    async def stream_execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        with_elevation: bool = False,
        env: Optional[Dict[str, str]] = None
    ) -> AsyncIterator[str]:
        """
        Execute a command and stream output line by line.
        
        Yields lines as they are produced by the command.
        Override in subclasses for protocol-specific streaming.
        
        Args:
            command: The command to execute.
            timeout: Command timeout.
            with_elevation: Run with elevated privileges.
            env: Environment variables.
        
        Yields:
            str: Each line of output.
        """
        # Default implementation - execute and yield all at once
        result = await self.execute(
            command=command,
            timeout=timeout,
            with_elevation=with_elevation,
            env=env
        )
        
        for line in result.stdout.splitlines():
            yield line
        
        if result.stderr:
            yield f"[STDERR] {result.stderr}"
    
    async def upload_file(
        self,
        local_path: str,
        remote_path: str
    ) -> bool:
        """
        Upload a file to the remote server.
        
        Args:
            local_path: Path to local file.
            remote_path: Destination path on remote server.
        
        Returns:
            bool: True if upload successful.
        """
        raise NotImplementedError("File upload not implemented for this executor")
    
    async def download_file(
        self,
        remote_path: str,
        local_path: str
    ) -> bool:
        """
        Download a file from the remote server.
        
        Args:
            remote_path: Path on remote server.
            local_path: Local destination path.
        
        Returns:
            bool: True if download successful.
        """
        raise NotImplementedError("File download not implemented for this executor")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
        return False
