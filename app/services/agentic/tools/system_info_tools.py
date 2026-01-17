"""
System Info Tools

Safe, read-only system information tools with hardcoded commands.
Background agents can use these to gather server status without arbitrary command execution.

SECURITY: All commands are hardcoded. No user input in command strings.
"""

import logging
import re
from typing import Dict, Any, Optional

from app.services.agentic.tools import Tool, ToolParameter, ToolModule
from app.models import ServerCredential
from app.services.ssh_service import get_ssh_connection

logger = logging.getLogger(__name__)


class SystemInfoTools(ToolModule):
    """
    Safe system information tools for background agents.
    
    All commands are hardcoded for security.
    No arbitrary command execution allowed.
    """
    
    # Hardcoded safe commands
    SAFE_COMMANDS = {
        'uptime': 'uptime',
        'disk': 'df -h',
        'memory': 'free -m',
        'load': 'cat /proc/loadavg',
        'processes': 'ps aux --sort=-%cpu | head -20'
    }
    
    # Whitelist of allowed services for status checks
    ALLOWED_SERVICES = [
        'nginx', 'apache2', 'httpd',
        'mysql', 'mariadb', 'postgresql', 'redis',
        'docker', 'containerd',
        'ssh', 'sshd',
        'cron', 'systemd-timesyncd',
        'prometheus', 'grafana', 'alertmanager',
        'node-exporter'
    ]
    
    def _register_tools(self):
        """Register safe system info tools"""
        
        # get_server_status
        self._register_tool(
            Tool(
                name="get_server_status",
                description="Get server health metrics (uptime, disk usage, memory usage, load average). Read-only, safe to use.",
                parameters=[
                    ToolParameter(
                        name="server",
                        type="string",
                        description="Server IP address or hostname",
                        required=True
                    )
                ]
            ),
            self._get_server_status
        )
        
        # list_processes
        self._register_tool(
            Tool(
                name="list_processes",
                description="List top 20 processes by CPU usage. Read-only, safe to use.",
                parameters=[
                    ToolParameter(
                        name="server",
                        type="string",
                        description="Server IP address or hostname",
                        required=True
                    )
                ]
            ),
            self._list_processes
        )
        
        # check_service_status
        self._register_tool(
            Tool(
                name="check_service_status",
                description="Check if a service is running using systemctl status. Only works for whitelisted services (nginx, mysql, etc.). Read-only, safe to use.",
                parameters=[
                    ToolParameter(
                        name="server",
                        type="string",
                        description="Server IP address or hostname",
                        required=True
                    ),
                    ToolParameter(
                        name="service_name",
                        type="string",
                        description="Service name (must be from whitelist: nginx, mysql, postgresql, redis, docker, etc.)",
                        required=True
                    )
                ]
            ),
            self._check_service_status
        )
    
    async def _get_server_status(self, args: Dict[str, Any]) -> str:
        """Get comprehensive server status using hardcoded safe commands"""
        server_host = args.get("server", "").strip()
        
        if not server_host:
            return "Error: server is required"
        
        try:
            # Resolve server credential
            credential = await self._resolve_server(server_host)
            if not credential:
                return f"Error: Could not find credentials for server '{server_host}'"
            
            # Get SSH connection
            client = await get_ssh_connection(self.db, credential.id)
            
            try:
                results = {}
                
                # Execute each hardcoded safe command
                for key, command in self.SAFE_COMMANDS.items():
                    if key == 'processes':
                        continue  # Skip process list for general status
                    
                    stdout, stderr, exit_code = await client.execute_command(command)
                    results[key] = {
                        'output': stdout.strip() if stdout else '',
                        'exit_code': exit_code
                    }
                
                # Format output
                output = f"**Server Status: {server_host}**\n\n"
                
                if results['uptime']['exit_code'] == 0:
                    output += f"📊 **Uptime**\n```\n{results['uptime']['output']}\n```\n\n"
                
                if results['load']['exit_code'] == 0:
                    output += f"⚡ **Load Average**\n```\n{results['load']['output']}\n```\n\n"
                
                if results['memory']['exit_code'] == 0:
                    output += f"💾 **Memory Usage**\n```\n{results['memory']['output']}\n```\n\n"
                
                if results['disk']['exit_code'] == 0:
                    output += f"💿 **Disk Usage**\n```\n{results['disk']['output']}\n```\n\n"
                
                return output
                
            finally:
                await client.close()
                
        except Exception as e:
            logger.error(f"Error getting server status: {e}")
            return f"Error getting server status: {str(e)}"
    
    async def _list_processes(self, args: Dict[str, Any]) -> str:
        """List top processes using hardcoded ps command"""
        server_host = args.get("server", "").strip()
        
        if not server_host:
            return "Error: server is required"
        
        try:
            credential = await self._resolve_server(server_host)
            if not credential:
                return f"Error: Could not find credentials for server '{server_host}'"
            
            client = await get_ssh_connection(self.db, credential.id)
            
            try:
                # Execute hardcoded ps command
                command = self.SAFE_COMMANDS['processes']
                stdout, stderr, exit_code = await client.execute_command(command)
                
                if exit_code != 0:
                    return f"Error listing processes (exit code {exit_code}): {stderr}"
                
                output = f"**Top Processes on {server_host}** (by CPU usage)\n\n```\n{stdout}\n```"
                return output
                
            finally:
                await client.close()
                
        except Exception as e:
            logger.error(f"Error listing processes: {e}")
            return f"Error listing processes: {str(e)}"
    
    async def _check_service_status(self, args: Dict[str, Any]) -> str:
        """Check service status with validation"""
        server_host = args.get("server", "").strip()
        service_name = args.get("service_name", "").strip()
        
        if not server_host or not service_name:
            return "Error: server and service_name are required"
        
        # SECURITY: Validate service name
        if not self._is_valid_service_name(service_name):
            return (
                f"Error: '{service_name}' is not in the allowed services list. "
                f"Allowed: {', '.join(self.ALLOWED_SERVICES)}"
            )
        
        try:
            credential = await self._resolve_server(server_host)
            if not credential:
                return f"Error: Could not find credentials for server '{server_host}'"
            
            client = await get_ssh_connection(self.db, credential.id)
            
            try:
                # Use hardcoded systemctl status command with validated service
                command = f"systemctl status {service_name}"
                stdout, stderr, exit_code = await client.execute_command(command)
                
                # Parse status
                is_running = "active (running)" in stdout.lower()
                is_active = "active" in stdout.lower()
                
                status_emoji = "✅" if is_running else "⚠️"
                
                output = f"{status_emoji} **Service Status: {service_name}** on {server_host}\n\n"
                output += f"Status: **{'Running' if is_running else 'Not Running'}**\n\n"
                output += f"```\n{stdout[:500]}\n```"  # Truncate to first 500 chars
                
                return output
                
            finally:
                await client.close()
                
        except Exception as e:
            logger.error(f"Error checking service status: {e}")
            return f"Error checking service status: {str(e)}"
    
    def _is_valid_service_name(self, service_name: str) -> bool:
        """
        Validate service name for security.
        
        Must be:
        - Alphanumeric with hyphens only
        - In the whitelist
        """
        # Check format (alphanumeric, hyphens, underscores only)
        if not re.match(r'^[a-zA-Z0-9_-]+$', service_name):
            return False
        
        # Check whitelist
        return service_name in self.ALLOWED_SERVICES
    
    async def _resolve_server(self, server_host: str) -> Optional[ServerCredential]:
        """Resolve server host to credential"""
        # Try exact match on hostname or IP
        credential = self.db.query(ServerCredential).filter(
            (ServerCredential.hostname == server_host) | 
            (ServerCredential.ip_address == server_host)
        ).first()
        
        # If not found, try fuzzy match on name
        if not credential:
            candidates = self.db.query(ServerCredential).filter(
                ServerCredential.name.ilike(f"%{server_host}%")
            ).all()
            if len(candidates) == 1:
                credential = candidates[0]
        
        return credential
