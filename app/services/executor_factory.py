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
from ..models import ServerCredential, APICredentialProfile
from .executor_base import BaseExecutor, ExecutionResult, ErrorType
from .executor_ssh import SSHExecutor
from .executor_api import APIExecutor
from .executor_winrm import WinRMExecutor

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
        "api": APIExecutor,
        "winrm": WinRMExecutor,
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
        api_token = None

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

        # Handle shared credential profile
        if getattr(server, 'credential_source', 'inline') == 'shared_profile':
            profile = getattr(server, 'credential_profile', None)
            if profile and profile.secret_encrypted:
                try:
                    secret = fernet.decrypt(profile.secret_encrypted.encode()).decode()
                    if profile.credential_type == 'key':
                        private_key = secret
                    elif profile.credential_type == 'password':
                        password = secret
                        # Use profile username if not overridden
                        if not server.username:
                            server.username = profile.username
                except Exception as e:
                    logger.error(f"Failed to decrypt shared secret for {server.hostname}: {e}")
            elif profile and not profile.secret_encrypted:
                 logger.warning(f"Shared profile {profile.name} has no secret")

        # Decrypt API token (if field exists)
        api_token_encrypted = getattr(server, 'api_token_encrypted', None)
        if api_token_encrypted:
            try:
                api_token = fernet.decrypt(api_token_encrypted.encode()).decode()
            except Exception as e:
                logger.error(f"Failed to decrypt API token for {server.hostname}: {e}")

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

        elif protocol == "api":
            return APIExecutor(
                hostname=server.hostname,
                port=server.port or 443,
                username=server.username or "",
                base_url=getattr(server, 'api_base_url', None),
                auth_type=getattr(server, 'api_auth_type', 'none'),
                auth_header=getattr(server, 'api_auth_header', None),
                auth_token=api_token,
                verify_ssl=getattr(server, 'api_verify_ssl', True),
                timeout=getattr(server, 'api_timeout_seconds', 30),
                default_headers=getattr(server, 'api_headers_json', {}) or {},
                metadata=getattr(server, 'api_metadata_json', {}) or {}
            )

        elif protocol == "winrm":
            # WinRM executor
            port = server.port or 5985  # Default to HTTP port
            
            # Auto-detect SSL based on port if not explicitly set
            use_ssl = getattr(server, 'winrm_use_ssl', None)
            if use_ssl is None:
                use_ssl = (port == 5986)  # HTTPS on 5986, HTTP on 5985
            
            return WinRMExecutor(
                hostname=server.hostname,
                port=port,
                username=server.username or "Administrator",
                password=password,
                transport=getattr(server, 'winrm_transport', 'ntlm') or 'ntlm',
                use_ssl=use_ssl,
                cert_validation=getattr(server, 'winrm_cert_validation', False)
            )

        else:
            raise ValueError(f"Unknown protocol: {protocol}")

    @classmethod
    def get_api_executor_from_profile(
        cls,
        profile: APICredentialProfile,
        fernet_key: Optional[str] = None
    ) -> APIExecutor:
        """
        Create an API executor from an API credential profile.

        Args:
            profile: APICredentialProfile with API connection details.
            fernet_key: Encryption key for credentials.

        Returns:
            APIExecutor instance.

        Raises:
            ValueError: If encryption key not configured.
        """
        settings = get_settings()
        key = fernet_key or settings.encryption_key

        if not key:
            raise ValueError("Encryption key not configured")

        fernet = Fernet(key.encode() if isinstance(key, str) else key)

        # Decrypt token if present
        auth_token = None
        if profile.token_encrypted:
            try:
                auth_token = fernet.decrypt(profile.token_encrypted.encode()).decode()
            except Exception as e:
                logger.error(f"Failed to decrypt token for profile {profile.name}: {e}")

        # Create API executor
        return APIExecutor(
            hostname="",  # Not used for pure API profiles
            port=443,  # Default HTTPS port
            username=profile.username or "",
            base_url=profile.base_url,
            auth_type=profile.auth_type,
            auth_header=profile.auth_header,
            auth_token=auth_token,
            verify_ssl=profile.verify_ssl,
            timeout=profile.timeout_seconds,
            default_headers=profile.default_headers or {},
            metadata=profile.profile_metadata or {}
        )

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
            protocol = getattr(server, 'protocol', 'ssh') or 'ssh'

            async with executor:
                # Different test commands for different protocols
                if protocol == "api":
                    # For API, just test connectivity
                    is_connected = await executor.test_connection()
                    if is_connected:
                        info = await executor.get_server_info()
                        return ExecutionResult(
                            success=True,
                            exit_code=0,
                            stdout=f"API connection successful\nBase URL: {executor.base_url}\nAuth Type: {executor.auth_type}",
                            stderr="",
                            duration_ms=0,
                            command="connection_test",
                            server_hostname=server.hostname
                        )
                    else:
                        return ExecutionResult(
                            success=False,
                            exit_code=-1,
                            stdout="",
                            stderr="API connection test failed",
                            duration_ms=0,
                            command="connection_test",
                            server_hostname=server.hostname,
                            error_type=ErrorType.CONNECTION,
                            error_message="Unable to connect to API",
                            retryable=True
                        )
                else:
                    # For command executors (SSH, WinRM)
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

    @classmethod
    async def execute_command(
        cls,
        server: ServerCredential,
        command: str,
        timeout: int = 60,
        use_sudo: bool = False,
        fernet_key: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute a command on a server and return clean output.
        
        Args:
            server: ServerCredential with connection details.
            command: Command to execute.
            timeout: Command timeout in seconds.
            use_sudo: Whether to prepend sudo to command.
            fernet_key: Encryption key.
        
        Returns:
            ExecutionResult with stdout, stderr, exit_code.
        """
        try:
            executor = cls.get_executor(server, fernet_key)
            
            async with executor:
                # Optionally wrap with sudo
                cmd = f"sudo {command}" if use_sudo else command
                
                # Execute the command
                result = await executor.execute(cmd, timeout=timeout)
                
                return result
                
        except ConnectionError as e:
            logger.error(f"Connection error executing command on {server.hostname}: {e}")
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=0,
                command=command,
                server_hostname=server.hostname,
                error_type=ErrorType.CONNECTION,
                error_message=str(e),
                retryable=True
            )
        except Exception as e:
            logger.error(f"Error executing command on {server.hostname}: {e}")
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=0,
                command=command,
                server_hostname=server.hostname,
                error_type=ErrorType.UNKNOWN,
                error_message=str(e),
                retryable=False
            )
