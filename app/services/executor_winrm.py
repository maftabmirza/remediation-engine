
"""
WinRM Executor Implementation

Provides command execution on Windows servers via WinRM protocol.
Wraps synchronous pywinrm calls in executor threads to avoid blocking the event loop.
"""
import logging
import winrm
import asyncio
from typing import Optional, Dict, List, Any
import base64
from functools import partial

from .executor_base import BaseExecutor, ExecutionResult, ErrorType, ServerInfo

logger = logging.getLogger(__name__)

class WinRMExecutor(BaseExecutor):
    """
    Executor implementation for Windows Remote Management (WinRM).
    
    Uses pywinrm library to communicate with Windows servers.
    """
    
    def __init__(
        self,
        hostname: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        timeout: int = 60,
        transport: str = 'ntlm',
        use_ssl: bool = False,
        cert_validation: bool = True
    ):
        super().__init__(hostname, port, username, timeout)
        self.password = password
        self.transport = transport
        self.use_ssl = use_ssl
        self.cert_validation = cert_validation
        self._session = None
        
    @property
    def protocol(self) -> str:
        return "winrm"

    @property
    def supports_elevation(self) -> bool:
        return False 

    def _create_session_sync(self):
        """Synchronous session creation"""
        scheme = 'https' if self.use_ssl else 'http'
        endpoint = f"{scheme}://{self.hostname}:{self.port}/wsman"
        
        self._session = winrm.Session(
            endpoint,
            auth=(self.username, self.password or ""),
            transport=self.transport,
            server_cert_validation='validate' if self.cert_validation else 'ignore'
        )
        self._connected = True

    async def connect(self) -> bool:
        """Establish WinRM session (async wrapper)."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._create_session_sync)
            return True
        except Exception as e:
            logger.error(f"Failed to create WinRM session for {self.hostname}: {e}")
            raise ConnectionError(f"WinRM connection failure: {e}")

    async def disconnect(self) -> None:
        """Close connection."""
        self._session = None
        self._connected = False

    def _run_cmd_sync(self, command: str):
        """Run command synchronously using pywinrm"""
        if not self._connected or not self._session:
            self._create_session_sync()
            
        # Detect if this is likely a CMD command (starts with cmd /c or similar)
        # Otherwise default to PowerShell for better experience and consistency
        cmd_lower = command.lower().strip()
        use_cmd = cmd_lower.startswith("cmd") or cmd_lower.startswith("dir") and not cmd_lower.startswith("gci")
        
        if use_cmd:
             return self._session.run_cmd(command)
        else:
             # Use PowerShell by default
             # Prepend progress suppression to avoid CLIXML garbage in stderr
             ps_command = f"$ProgressPreference = 'SilentlyContinue'; {command}"
             # Encode command to avoid issues with special chars if needed, but pywinrm handles basic strings well
             # We rely on run_ps which handles wrapping
             return self._session.run_ps(ps_command)

    async def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        with_elevation: bool = False,
        env: Optional[Dict[str, str]] = None,
        working_directory: Optional[str] = None
    ) -> ExecutionResult:
        try:
            loop = asyncio.get_running_loop()
            
            # Offload to thread pool
            result = await loop.run_in_executor(None, partial(self._run_cmd_sync, command))
            
            success = result.status_code == 0
            
            return ExecutionResult(
                success=success,
                exit_code=result.status_code,
                stdout=result.std_out.decode('utf-8') if isinstance(result.std_out, bytes) else str(result.std_out),
                stderr=result.std_err.decode('utf-8') if isinstance(result.std_err, bytes) else str(result.std_err),
                duration_ms=0,
                command=command,
                server_hostname=self.hostname
            )
            
        except Exception as e:
            logger.error(f"WinRM execution error on {self.hostname}: {e}")
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=0,
                command=command,
                server_hostname=self.hostname,
                error_type=ErrorType.CONNECTION,
                error_message=str(e),
                retryable=True
            )

    async def test_connection(self) -> bool:
        """Test connectivity."""
        try:
            loop = asyncio.get_running_loop()
            # Wrap specific check
            def _check():
                if not self._connected:
                     self._create_session_sync()
                res = self._session.run_cmd("echo OK")
                return res.status_code == 0
            
            return await loop.run_in_executor(None, _check)
        except Exception:
            return False

    async def get_server_info(self) -> ServerInfo:
        cmd = 'systeminfo /FO CSV'
        res = await self.execute(cmd)
        
        info = ServerInfo(
            hostname=self.hostname,
            os_type="windows",
            os_version="Unknown", 
            kernel_version="N/A",
            architecture="x64"
        )
        return info
