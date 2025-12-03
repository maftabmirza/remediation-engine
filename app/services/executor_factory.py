"""
Executor Factory

Creates appropriate executor instances based on server configuration.
Handles credential decryption and connection pooling.
"""

import logging
from typing import Optional, Dict, Type
from uuid import UUID

from cryptography.fernet import Fernet

from ..config import get_settings
from ..models import ServerCredential
from .executor_base import BaseExecutor, ExecutionResult, ErrorType
from .executor_ssh import SSHExecutor

logger = logging.getLogger(__name__)


class ExecutorFactory:
    """
    Factory for creating executor instances.
    
    Handles:
    - Executor type selection based on server OS/protocol
    - Credential decryption
    - Connection pooling (optional)
    """
    
    # Registry of executor classes
    _executors: Dict[str, Type[BaseExecutor]] = {
        "ssh": SSHExecutor,
        # "winrm": WinRMExecutor,  # Added in Phase 7
    }
    
    # Connection pool for reuse
    _pool: Dict[str, BaseExecutor] = {}
    
    @classmethod
    def register_executor(cls, protocol: str, executor_class: Type[BaseExecutor]):
        """Register a new executor type."""
        cls._executors[protocol] = executor_class
        logger.info(f"Registered executor: {protocol} -> {executor_class.__name__}")
    
    @classmethod
    def get_executor(
        cls,
        server: ServerCredential,
        fernet_key: Optional[str] = None
    ) -> BaseExecutor:
        """
        Create an executor for the given server.
        
        Args:
            server: ServerCredential with connection details.
            fernet_key: Encryption key for credentials.
        
        Returns:
            Appropriate BaseExecutor subclass instance.
        
        Raises:
            ValueError: If protocol not supported.
        """
        settings = get_settings()
        key = fernet_key or settings.encryption_key
        
        if not key:
            raise ValueError("Encryption key not configured")
        
        fernet = Fernet(key.encode() if isinstance(key, str) else key)
        
        # Determine protocol
        protocol = getattr(server, 'protocol', 'ssh') or 'ssh'
        os_type = getattr(server, 'os_type', 'linux') or 'linux'
        
        # Get executor class
        executor_class = cls._executors.get(protocol)
        if not executor_class:
            raise ValueError(f"Unsupported protocol: {protocol}")
        
        # Decrypt credentials
        password = None
        private_key = None
        sudo_password = None
        
        if server.password_encrypted:
            try:
                password = fernet.decrypt(server.password_encrypted.encode()).decode()
            except Exception as e:
                logger.error(f"Failed to decrypt password for {server.hostname}: {e}")
        
        if server.ssh_key_encrypted:
            try:
                private_key = fernet.decrypt(server.ssh_key_encrypted.encode()).decode()
            except Exception as e:
                logger.error(f"Failed to decrypt SSH key for {server.hostname}: {e}")
        
        # Check for sudo password (if field exists)
        sudo_password_encrypted = getattr(server, 'sudo_password_encrypted', None)
        if sudo_password_encrypted:
            try:
                sudo_password = fernet.decrypt(sudo_password_encrypted.encode()).decode()
            except Exception:
                pass
        
        # Create executor based on protocol
        if protocol == "ssh":
            return SSHExecutor(
                hostname=server.hostname,
                port=server.port or 22,
                username=server.username or "root",
                password=password,
                private_key=private_key,
                private_key_passphrase=None,  # Could add this field to model
                sudo_password=sudo_password,
                timeout=60,
                host_key_checking=False
            )
        elif protocol == "winrm":
            # WinRM executor (Phase 7)
            raise NotImplementedError("WinRM executor not yet implemented")
        else:
            raise ValueError(f"Unknown protocol: {protocol}")
    
    @classmethod
    async def get_pooled_executor(
        cls,
        server: ServerCredential,
        fernet_key: Optional[str] = None
    ) -> BaseExecutor:
        """
        Get an executor from the connection pool, creating if needed.
        
        Args:
            server: ServerCredential with connection details.
            fernet_key: Encryption key.
        
        Returns:
            Connected executor from pool.
        """
        pool_key = f"{server.hostname}:{server.port or 22}"
        
        if pool_key in cls._pool:
            executor = cls._pool[pool_key]
            if executor.is_connected:
                return executor
            else:
                # Remove stale connection
                del cls._pool[pool_key]
        
        # Create new executor
        executor = cls.get_executor(server, fernet_key)
        await executor.connect()
        cls._pool[pool_key] = executor
        
        return executor
    
    @classmethod
    async def close_all(cls):
        """Close all pooled connections."""
        for key, executor in list(cls._pool.items()):
            try:
                await executor.disconnect()
            except Exception as e:
                logger.warning(f"Error closing executor {key}: {e}")
        cls._pool.clear()
    
    @classmethod
    async def test_server_connection(
        cls,
        server: ServerCredential,
        fernet_key: Optional[str] = None
    ) -> ExecutionResult:
        """
        Test connection to a server.
        
        Args:
            server: ServerCredential to test.
            fernet_key: Encryption key.
        
        Returns:
            ExecutionResult with test results.
        """
        try:
            executor = cls.get_executor(server, fernet_key)
            async with executor:
                result = await executor.execute("echo 'Connection test successful'", timeout=30)
                
                if result.success:
                    # Get server info
                    info = await executor.get_server_info()
                    result.stdout = (
                        f"Connection successful\n"
                        f"OS: {info.os_version or info.os_type}\n"
                        f"Kernel: {info.kernel_version or 'N/A'}\n"
                        f"Arch: {info.architecture or 'N/A'}"
                    )
                
                return result
                
        except ConnectionError as e:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=0,
                command="connection_test",
                server_hostname=server.hostname,
                error_type=ErrorType.CONNECTION,
                error_message=str(e),
                retryable=True
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=0,
                command="connection_test",
                server_hostname=server.hostname,
                error_type=ErrorType.UNKNOWN,
                error_message=str(e),
                retryable=False
            )
    
    @classmethod
    async def test_all_servers(
        cls,
        servers: list,
        fernet_key: Optional[str] = None
    ) -> Dict[str, ExecutionResult]:
        """
        Test connection to multiple servers.
        
        Args:
            servers: List of ServerCredential objects.
            fernet_key: Encryption key.
        
        Returns:
            Dict mapping hostname to ExecutionResult.
        """
        import asyncio
        
        results = {}
        
        async def test_one(server):
            result = await cls.test_server_connection(server, fernet_key)
            results[server.hostname] = result
        
        # Test concurrently (with limit)
        semaphore = asyncio.Semaphore(10)
        
        async def test_with_limit(server):
            async with semaphore:
                await test_one(server)
        
        await asyncio.gather(*[test_with_limit(s) for s in servers])
        
        return results
