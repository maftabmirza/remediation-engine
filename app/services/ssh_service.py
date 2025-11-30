"""
SSH Service - AsyncSSH integration for Web Terminal
"""
import asyncio
import logging
import asyncssh
from typing import Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.models import ServerCredential
from app.utils.crypto import decrypt_value

logger = logging.getLogger(__name__)

class SSHClient:
    def __init__(self, host: str, port: int, username: str, client_keys: list = None, password: str = None):
        self.host = host
        self.port = port
        self.username = username
        self.client_keys = client_keys
        self.password = password
        self.conn = None
        self.process = None

    async def connect(self):
        """Establish SSH connection"""
        try:
            self.conn = await asyncssh.connect(
                self.host,
                port=self.port,
                username=self.username,
                client_keys=self.client_keys,
                password=self.password,
                known_hosts=None  # In production, you should verify hosts
            )
            return True
        except Exception as e:
            logger.error(f"SSH Connection failed: {str(e)}")
            raise e

    async def start_shell(self, term_type='xterm', term_size=(80, 24)):
        """Start an interactive shell"""
        if not self.conn:
            await self.connect()
            
        self.process = await self.conn.create_process(
            term_type=term_type,
            term_size=term_size
        )
        return self.process

    async def close(self):
        """Close connection"""
        if self.conn:
            self.conn.close()
            await self.conn.wait_closed()

async def get_ssh_connection(db: Session, server_id: UUID) -> SSHClient:
    """
    Factory to create an SSH client from database credentials
    """
    server = db.query(ServerCredential).filter(ServerCredential.id == server_id).first()
    if not server:
        raise ValueError("Server credentials not found")
        
    client_keys = None
    password = None
    
    if server.auth_type == 'key' and server.ssh_key_encrypted:
        private_key_str = decrypt_value(server.ssh_key_encrypted)
        # Load key from string
        client_keys = [asyncssh.import_private_key(private_key_str)]
    elif server.auth_type == 'password' and server.password_encrypted:
        password = decrypt_value(server.password_encrypted)
        
    client = SSHClient(
        host=server.hostname,
        port=server.port,
        username=server.username,
        client_keys=client_keys,
        password=password
    )
    
    return client
