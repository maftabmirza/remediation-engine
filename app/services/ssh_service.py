"""SSH Service - AsyncSSH integration for Web Terminal."""
import asyncio
import logging
import asyncssh
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session

from app.models import ServerCredential
from app.utils.crypto import decrypt_value, DecryptionError

logger = logging.getLogger(__name__)


class SSHClient:
    """Async SSH client wrapper for terminal connections."""
    
    def __init__(
        self, 
        host: str, 
        port: int, 
        username: str, 
        client_keys: Optional[List] = None, 
        password: Optional[str] = None
    ):
        self.host = host
        self.port = port
        self.username = username
        self.client_keys = client_keys
        self.password = password
        self.conn: Optional[asyncssh.SSHClientConnection] = None
        self.process: Optional[asyncssh.SSHClientProcess] = None

    async def connect(self) -> bool:
        """Establish SSH connection."""
        try:
            logger.info(f"Connecting to SSH server {self.host}:{self.port} as {self.username}")
            
            # Build connection options
            connect_options = {
                "host": self.host,
                "port": self.port,
                "username": self.username,
                "known_hosts": None,  # Skip host key verification
            }
            
            # Set authentication method
            if self.client_keys:
                connect_options["client_keys"] = self.client_keys
            elif self.password:
                connect_options["password"] = self.password
                connect_options["client_keys"] = []  # Disable key auth when using password
            
            self.conn = await asyncssh.connect(**connect_options)
            logger.info(f"SSH connection established to {self.host}")
            return True
            
        except asyncssh.DisconnectError as e:
            logger.error(f"SSH Disconnect error: {e.reason}")
            raise ConnectionError(f"SSH server disconnected: {e.reason}")
        except asyncssh.PermissionDenied as e:
            logger.error(f"SSH Permission denied for {self.username}@{self.host}")
            raise PermissionError(f"Authentication failed for {self.username}")
        except asyncssh.HostKeyNotVerifiable as e:
            logger.error(f"SSH Host key not verifiable for {self.host}")
            raise ConnectionError(f"Host key verification failed for {self.host}")
        except OSError as e:
            logger.error(f"SSH Connection error to {self.host}: {e}")
            raise ConnectionError(f"Cannot connect to {self.host}:{self.port}: {e}")
        except Exception as e:
            logger.error(f"SSH Connection failed: {type(e).__name__}: {e}")
            raise

    async def start_shell(self, term_type: str = 'xterm-256color', term_size: tuple = (80, 24)):
        """Start an interactive shell session."""
        if not self.conn:
            await self.connect()
        
        try:
            logger.debug(f"Starting shell with term={term_type}, size={term_size}")
            self.process = await self.conn.create_process(
                term_type=term_type,
                term_size=term_size,
                encoding='utf-8',  # Use string mode for terminal
                errors='replace'   # Replace invalid UTF-8 chars instead of failing
            )
            return self.process
        except Exception as e:
            logger.error(f"Failed to start shell: {e}")
            raise

    async def close(self):
        """Close SSH connection and cleanup."""
        if self.process:
            try:
                self.process.close()
            except Exception as e:
                logger.debug(f"Error closing process: {e}")
        
        if self.conn:
            try:
                self.conn.close()
                await self.conn.wait_closed()
                logger.debug("SSH connection closed")
            except Exception as e:
                logger.debug(f"Error closing connection: {e}")

async def get_ssh_connection(db: Session, server_id: UUID) -> SSHClient:
    """
    Factory to create an SSH client from database credentials.
    
    Args:
        db: Database session
        server_id: UUID of the server credential
        
    Returns:
        SSHClient configured with the server credentials
        
    Raises:
        ValueError: If server credentials not found
        DecryptionError: If credentials cannot be decrypted
    """
    server = db.query(ServerCredential).filter(ServerCredential.id == server_id).first()
    if not server:
        raise ValueError(f"Server credentials not found for ID: {server_id}")
    
    logger.info(f"Creating SSH client for server: {server.name} ({server.hostname})")
    
    client_keys = None
    password = None
    
    try:
        if server.auth_type == 'key' and server.ssh_key_encrypted:
            private_key_str = decrypt_value(server.ssh_key_encrypted)
            if private_key_str:
                try:
                    client_keys = [asyncssh.import_private_key(private_key_str)]
                except asyncssh.KeyImportError as e:
                    logger.error(f"Failed to import SSH key: {e}")
                    raise ValueError(f"Invalid SSH private key format: {e}")
        elif server.auth_type == 'password' and server.password_encrypted:
            password = decrypt_value(server.password_encrypted)
            if not password:
                raise ValueError("Password is empty after decryption")
    except DecryptionError as e:
        logger.error(f"Failed to decrypt credentials for server {server.name}: {e}")
        raise ValueError(f"Cannot decrypt server credentials: {e}")
    
    # Validate we have at least one auth method
    if not client_keys and not password:
        raise ValueError(f"No valid authentication credentials for server: {server.name}")
        
    client = SSHClient(
        host=server.hostname,
        port=server.port,
        username=server.username,
        client_keys=client_keys,
        password=password
    )
    
    return client
