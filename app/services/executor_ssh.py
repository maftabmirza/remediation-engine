"""
SSH Executor

Implements command execution on Linux servers via SSH.
Uses AsyncSSH for async, non-blocking operations.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional, Dict, AsyncIterator
import logging

import asyncssh

from .executor_base import (
    BaseExecutor, ExecutionResult, ServerInfo, ErrorType
)

logger = logging.getLogger(__name__)


class SSHExecutor(BaseExecutor):
    """
    SSH-based executor for Linux servers.
    
    Supports:
    - Key-based authentication (preferred)
    - Password authentication
    - Sudo elevation with password or passwordless
    - Command streaming
    - File transfer (SCP/SFTP)
    """
    
    def __init__(
        self,
        hostname: str,
        port: int = 22,
        username: str = "root",
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        private_key_passphrase: Optional[str] = None,
        sudo_password: Optional[str] = None,
        timeout: int = 60,
        known_hosts: Optional[str] = None,
        host_key_checking: bool = False
    ):
        """
        Initialize SSH executor.
        
        Args:
            hostname: Server hostname or IP.
            port: SSH port (default 22).
            username: SSH username.
            password: SSH password (if not using key).
            private_key: SSH private key content.
            private_key_passphrase: Passphrase for encrypted key.
            sudo_password: Password for sudo (if required).
            timeout: Default command timeout.
            known_hosts: Path to known_hosts file.
            host_key_checking: Verify host keys.
        """
        super().__init__(hostname, port, username, timeout)
        self.password = password
        self.private_key = private_key
        self.private_key_passphrase = private_key_passphrase
        self.sudo_password = sudo_password
        self.known_hosts = known_hosts
        self.host_key_checking = host_key_checking
        self._conn: Optional[asyncssh.SSHClientConnection] = None
    
    @property
    def protocol(self) -> str:
        return "ssh"
    
    @property
    def supports_elevation(self) -> bool:
        return True
    
    async def connect(self) -> bool:
        """Establish SSH connection."""
        try:
            connect_options = {
                "host": self.hostname,
                "port": self.port,
                "username": self.username,
                "known_hosts": None if not self.host_key_checking else self.known_hosts,
            }
            
            # Authentication method
            if self.private_key:
                # Key-based auth
                key = asyncssh.import_private_key(
                    self.private_key,
                    passphrase=self.private_key_passphrase
                )
                connect_options["client_keys"] = [key]
            elif self.password:
                # Password auth
                connect_options["password"] = self.password
            
            self._conn = await asyncssh.connect(**connect_options)
            self._connected = True
            logger.info(f"SSH connected to {self.hostname}:{self.port}")
            return True
            
        except asyncssh.DisconnectError as e:
            logger.error(f"SSH disconnect error: {e}")
            raise ConnectionError(f"SSH connection failed: {e}")
        except asyncssh.PermissionDenied as e:
            logger.error(f"SSH auth failed: {e}")
            raise ConnectionError(f"SSH authentication failed: {e}")
        except asyncssh.HostKeyNotVerifiable as e:
            logger.error(f"SSH host key error: {e}")
            raise ConnectionError(f"SSH host key verification failed: {e}")
        except Exception as e:
            logger.error(f"SSH connection error: {e}")
            raise ConnectionError(f"SSH connection failed: {e}")
    
    async def disconnect(self) -> None:
        """Close SSH connection."""
        if self._conn:
            self._conn.close()
            await self._conn.wait_closed()
            self._conn = None
            self._connected = False
            logger.info(f"SSH disconnected from {self.hostname}")
    
    async def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        with_elevation: bool = False,
        env: Optional[Dict[str, str]] = None,
        working_directory: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute a command via SSH.
        
        Args:
            command: Shell command to execute.
            timeout: Command timeout in seconds.
            with_elevation: Use sudo.
            env: Environment variables.
            working_directory: Run in this directory.
        
        Returns:
            ExecutionResult with command output.
        """
        if not self._conn or not self._connected:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Not connected",
                duration_ms=0,
                command=command,
                server_hostname=self.hostname,
                error_type=ErrorType.CONNECTION,
                error_message="SSH connection not established",
                retryable=True
            )
        
        effective_timeout = timeout or self.timeout
        start_time = time.time()
        
        try:
            # Build command with working directory if specified
            full_command = command
            if working_directory:
                full_command = f"cd {working_directory} && {command}"
            
            # Add environment variables
            if env:
                env_prefix = " ".join(f'{k}="{v}"' for k, v in env.items())
                full_command = f"{env_prefix} {full_command}"
            
            # Handle sudo
            if with_elevation:
                if self.sudo_password:
                    # Sudo with password via stdin
                    full_command = f"echo '{self.sudo_password}' | sudo -S {full_command}"
                else:
                    # Passwordless sudo
                    full_command = f"sudo {full_command}"
            
            # Execute command
            result = await asyncio.wait_for(
                self._conn.run(full_command, check=False),
                timeout=effective_timeout
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            success = result.exit_status == 0
            
            return ExecutionResult(
                success=success,
                exit_code=result.exit_status or 0,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                duration_ms=duration_ms,
                command=command,  # Original command (not full)
                server_hostname=self.hostname,
                error_type=ErrorType.COMMAND if not success else None,
                error_message=result.stderr if not success and result.stderr else None,
                retryable=False
            )
            
        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"Command timeout on {self.hostname}: {command}")
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {effective_timeout} seconds",
                duration_ms=duration_ms,
                command=command,
                server_hostname=self.hostname,
                error_type=ErrorType.TIMEOUT,
                error_message=f"Command timed out after {effective_timeout}s",
                retryable=True
            )
            
        except asyncssh.ChannelOpenError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"SSH channel error on {self.hostname}: {e}")
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                command=command,
                server_hostname=self.hostname,
                error_type=ErrorType.CONNECTION,
                error_message=f"SSH channel error: {e}",
                retryable=True
            )
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"SSH execution error on {self.hostname}: {e}")
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                command=command,
                server_hostname=self.hostname,
                error_type=ErrorType.UNKNOWN,
                error_message=str(e),
                retryable=False
            )
    
    async def stream_execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        with_elevation: bool = False,
        env: Optional[Dict[str, str]] = None
    ) -> AsyncIterator[str]:
        """
        Execute a command and stream output line by line.
        
        Yields output lines as they are produced.
        """
        if not self._conn or not self._connected:
            yield "[ERROR] SSH connection not established"
            return
        
        effective_timeout = timeout or self.timeout
        
        # Build command
        full_command = command
        if env:
            env_prefix = " ".join(f'{k}="{v}"' for k, v in env.items())
            full_command = f"{env_prefix} {full_command}"
        
        if with_elevation:
            if self.sudo_password:
                full_command = f"echo '{self.sudo_password}' | sudo -S {full_command}"
            else:
                full_command = f"sudo {full_command}"
        
        try:
            async with self._conn.create_process(full_command) as process:
                async for line in process.stdout:
                    yield line.rstrip('\n')
                
                # Also yield stderr lines
                if process.stderr:
                    async for line in process.stderr:
                        yield f"[STDERR] {line.rstrip()}"
                        
        except asyncio.TimeoutError:
            yield f"[ERROR] Command timed out after {effective_timeout}s"
        except Exception as e:
            yield f"[ERROR] {str(e)}"
    
    async def test_connection(self) -> bool:
        """Test SSH connection with a simple command."""
        try:
            if not self._connected:
                await self.connect()
            
            result = await self.execute("echo 'test'", timeout=10)
            return result.success and "test" in result.stdout
            
        except Exception as e:
            logger.error(f"SSH connection test failed for {self.hostname}: {e}")
            return False
    
    async def get_server_info(self) -> ServerInfo:
        """Get Linux server information."""
        info = ServerInfo(
            hostname=self.hostname,
            os_type="linux"
        )
        
        try:
            # Get OS version
            result = await self.execute("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'\"' -f2", timeout=10)
            if result.success and result.stdout.strip():
                info.os_version = result.stdout.strip()
            
            # Get kernel version
            result = await self.execute("uname -r", timeout=10)
            if result.success:
                info.kernel_version = result.stdout.strip()
            
            # Get architecture
            result = await self.execute("uname -m", timeout=10)
            if result.success:
                info.architecture = result.stdout.strip()
            
            # Get uptime
            result = await self.execute("cat /proc/uptime | cut -d' ' -f1", timeout=10)
            if result.success:
                try:
                    info.uptime_seconds = int(float(result.stdout.strip()))
                except ValueError:
                    pass
                    
        except Exception as e:
            logger.warning(f"Error getting server info for {self.hostname}: {e}")
        
        return info
    
    async def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload a file via SFTP."""
        if not self._conn:
            return False
        
        try:
            async with self._conn.start_sftp_client() as sftp:
                await sftp.put(local_path, remote_path)
            logger.info(f"Uploaded {local_path} to {self.hostname}:{remote_path}")
            return True
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            return False
    
    async def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file via SFTP."""
        if not self._conn:
            return False
        
        try:
            async with self._conn.start_sftp_client() as sftp:
                await sftp.get(remote_path, local_path)
            logger.info(f"Downloaded {self.hostname}:{remote_path} to {local_path}")
            return True
        except Exception as e:
            logger.error(f"File download failed: {e}")
            return False
