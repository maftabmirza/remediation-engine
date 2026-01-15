"""WinRM Terminal Service - Provides interactive terminal-like experience for Windows servers."""
import asyncio
import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models import ServerCredential
from app.utils.crypto import decrypt_value, DecryptionError

try:
    import winrm
except ImportError:
    winrm = None

logger = logging.getLogger(__name__)


class WinRMTerminal:
    """
    WinRM terminal wrapper for Windows server connections.
    
    Unlike SSH which provides a true PTY, WinRM executes commands one at a time.
    This class emulates a terminal experience by maintaining a PowerShell session.
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        transport: str = 'ntlm',
        use_ssl: bool = False,
        cert_validation: bool = False
    ):
        if winrm is None:
            raise ImportError("pywinrm module is not installed")
        
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.transport = transport
        self.use_ssl = use_ssl
        self.cert_validation = cert_validation
        self._session = None
        self._connected = False
        self._current_dir = "C:\\"
        self._command_queue: asyncio.Queue = asyncio.Queue()
        self._output_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        
    def _create_session_sync(self):
        """Create WinRM session synchronously."""
        scheme = 'https' if self.use_ssl else 'http'
        endpoint = f"{scheme}://{self.host}:{self.port}/wsman"
        
        self._session = winrm.Session(
            endpoint,
            auth=(self.username, self.password or ""),
            transport=self.transport,
            server_cert_validation='validate' if self.cert_validation else 'ignore',
            read_timeout_sec=70,
            operation_timeout_sec=60
        )
        self._connected = True
        
    async def connect(self) -> bool:
        """Establish WinRM connection."""
        try:
            logger.info(f"Connecting to WinRM server {self.host}:{self.port} as {self.username}")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._create_session_sync)
            
            # Test connection with a simple command
            def _test():
                result = self._session.run_ps("$env:COMPUTERNAME")
                return result.status_code == 0, result.std_out.decode('utf-8').strip()
            
            success, hostname = await asyncio.wait_for(
                loop.run_in_executor(None, _test),
                timeout=30
            )
            
            if success:
                logger.info(f"WinRM connection established to {self.host} ({hostname})")
                return True
            else:
                raise ConnectionError("Failed to execute test command")
                
        except asyncio.TimeoutError:
            logger.error(f"WinRM connection timeout to {self.host}")
            raise ConnectionError(f"Connection timeout to {self.host}")
        except Exception as e:
            logger.error(f"WinRM connection failed: {e}")
            raise ConnectionError(f"WinRM connection failed: {e}")

    def _execute_command_sync(self, command: str) -> tuple:
        """Execute a command synchronously."""
        if not self._session:
            raise ConnectionError("Not connected")
        
        # Wrap command to get current directory after execution
        ps_command = f"""
$ProgressPreference = 'SilentlyContinue'
try {{
    {command}
}} catch {{
    Write-Error $_
}}
"""
        result = self._session.run_ps(ps_command)
        stdout = result.std_out.decode('utf-8') if result.std_out else ""
        stderr = result.std_err.decode('utf-8') if result.std_err else ""
        return stdout, stderr, result.status_code

    async def execute(self, command: str, timeout: int = 60) -> tuple:
        """Execute a command asynchronously."""
        try:
            loop = asyncio.get_running_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, self._execute_command_sync, command),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return "", f"Command timed out after {timeout} seconds", -1

    async def close(self):
        """Close the WinRM connection."""
        self._session = None
        self._connected = False
        self._running = False
        logger.debug("WinRM connection closed")

    @property
    def is_connected(self) -> bool:
        return self._connected


async def get_winrm_connection(db: Session, server_id: UUID) -> WinRMTerminal:
    """
    Factory to create a WinRM terminal client from database credentials.
    
    Args:
        db: Database session
        server_id: UUID of the server credential
        
    Returns:
        WinRMTerminal configured with the server credentials
        
    Raises:
        ValueError: If server credentials not found
    """
    server = db.query(ServerCredential).filter(ServerCredential.id == server_id).first()
    if not server:
        raise ValueError(f"Server credentials not found for ID: {server_id}")
    
    if server.protocol != 'winrm':
        raise ValueError(f"Server {server.name} is not configured for WinRM (protocol: {server.protocol})")
    
    logger.info(f"Creating WinRM terminal for server: {server.name} ({server.hostname})")
    
    password = None
    
    # Get password from inline or shared profile
    if server.credential_source == 'shared_profile' and server.credential_profile:
        if server.credential_profile.secret_encrypted:
            password = decrypt_value(server.credential_profile.secret_encrypted)
    elif server.password_encrypted:
        password = decrypt_value(server.password_encrypted)
    
    if not password:
        raise ValueError(f"No password available for WinRM server: {server.name}")
    
    client = WinRMTerminal(
        host=server.hostname,
        port=server.port or 5985,
        username=server.username,
        password=password,
        transport=server.winrm_transport or 'ntlm',
        use_ssl=server.winrm_use_ssl or False,
        cert_validation=server.winrm_cert_validation or False
    )
    
    return client
