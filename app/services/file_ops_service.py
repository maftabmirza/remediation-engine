"""
File Operations Service

Handles file reading, writing, backups, and restoration on remote servers via SSH/SFTP.
"""
import logging
import asyncio
import hashlib
import fnmatch
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, timezone
import asyncssh
from uuid import UUID
from sqlalchemy.orm import Session

from app.models import ServerCredential
from app.models_changeset import FileVersion, FileBackup
from app.services.ssh_service import get_ssh_connection, SSHClient
from app.utils.crypto import decrypt_value

logger = logging.getLogger(__name__)

class FileOpsService:
    """Service for handling remote file operations with versioning and backups."""

    def __init__(self, db: Session):
        self.db = db

    async def _get_client(self, server_id: UUID) -> SSHClient:
        """Get an authenticated SSH client."""
        return await get_ssh_connection(self.db, server_id)

    async def read_file(self, server_id: UUID, file_path: str) -> Dict[str, Any]:
        """
        Read file content from remote server.
        
        Returns:
            Dict containing content, size, modified_time, hash
        """
        client = await self._get_client(server_id)
        try:
            await client.connect()
            
            # Use SFTP for safe file reading
            async with client.conn.start_sftp_client() as sftp:
                try:
                    # check if file exists and get attributes
                    attrs = await sftp.stat(file_path)
                    
                    if attrs.size > 5 * 1024 * 1024: # 5MB limit for text view
                        raise ValueError(f"File too large to read directly: {attrs.size} bytes")
                        
                    async with sftp.open(file_path, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        
                    # Calculate hash
                    content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                    
                    return {
                        "content": content,
                        "size": attrs.size,
                        "modified_at": datetime.fromtimestamp(attrs.mtime, timezone.utc) if attrs.mtime else None,
                        "hash": content_hash,
                        "path": file_path
                    }
                    
                except asyncssh.SFTPError as e:
                    if e.code == asyncssh.FX_NO_SUCH_FILE:
                        raise FileNotFoundError(f"File not found: {file_path}")
                    raise
                    
        except Exception as e:
            logger.error(f"Error reading file {file_path} on server {server_id}: {e}")
            raise
        finally:
            await client.close()

    async def write_file(self, server_id: UUID, file_path: str, content: str, create_backup: bool = True) -> Dict[str, Any]:
        """
        Write content to file on remote server.
        
        Args:
            server_id: Server UUID
            file_path: Absolute path to file
            content: New file content
            create_backup: Whether to create a backup of existing file
            
        Returns:
            Dict with write operation details
        """
        client = await self._get_client(server_id)
        try:
            await client.connect()
            
            async with client.conn.start_sftp_client() as sftp:
                file_exists = await sftp.exists(file_path)
                
                # Create backup if requested and file exists
                backup_path = None
                if create_backup and file_exists:
                    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                    backup_path = f"{file_path}.{timestamp}.bak"
                    await sftp.copy(file_path, backup_path)
                    logger.info(f"Created backup of {file_path} at {backup_path}")

                # Write new content
                async with sftp.open(file_path, 'w', encoding='utf-8') as f:
                    await f.write(content)
                    
                # Verify write (get attrs)
                attrs = await sftp.stat(file_path)
                new_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                
                return {
                    "path": file_path,
                    "written_bytes": len(content.encode('utf-8')),
                    "hash": new_hash,
                    "backup_path": backup_path,
                    "modified_at": datetime.fromtimestamp(attrs.mtime, timezone.utc) if attrs.mtime else None
                }
                
        except Exception as e:
            logger.error(f"Error writing file {file_path} on server {server_id}: {e}")
            raise
        finally:
            await client.close()

    async def list_files(self, server_id: UUID, directory: str, pattern: str = "*") -> List[Dict[str, Any]]:
        """
        List files in a directory matching a pattern.
        """
        client = await self._get_client(server_id)
        results = []
        try:
            await client.connect()
            async with client.conn.start_sftp_client() as sftp:
                files = await sftp.scandir(directory)
                for f in files:
                    if fnmatch.fnmatch(f.filename, pattern):
                         results.append({
                             "name": f.filename,
                             "path": f"{directory.rstrip('/')}/{f.filename}",
                             "is_dir": f.attrs.permissions is not None and (f.attrs.permissions & 0o40000), # S_IFDIR
                             "size": f.attrs.size,
                             "modified_at": datetime.fromtimestamp(f.attrs.mtime, timezone.utc) if f.attrs.mtime else None
                         })
            return sorted(results, key=lambda x: (not x['is_dir'], x['name']))
        except Exception as e:
            logger.error(f"Error listing files in {directory} on server {server_id}: {e}")
            raise
        finally:
            await client.close()

    async def create_backup(self, server_id: UUID, file_path: str, session_id: UUID) -> Optional[FileBackup]:
        """
        Create a backup of a file and record it in the database.
        """
        client = await self._get_client(server_id)
        try:
            await client.connect()
            
            async with client.conn.start_sftp_client() as sftp:
                if not await sftp.exists(file_path):
                    logger.warning(f"File {file_path} does not exist, cannot backup.")
                    return None
                
                # Calculate hash and read content for versioning
                async with sftp.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                
                # Remote backup file copy
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                backup_path = f"{file_path}.{timestamp}.bak"
                await sftp.copy(file_path, backup_path)
                
                # Store Version and Backup in DB
                version = FileVersion(
                    session_id=session_id,
                    server_id=server_id,
                    file_path=file_path,
                    content=content,
                    content_hash=content_hash,
                    created_by='agent'
                )
                self.db.add(version)
                self.db.flush() # get ID
                
                backup = FileBackup(
                    file_version_id=version.id,
                    backup_path=backup_path
                )
                self.db.add(backup)
                self.db.commit()
                
                return backup
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create backup for {file_path}: {e}")
            raise
        finally:
            await client.close()

    async def restore_backup(self, server_id: UUID, backup_id: UUID) -> bool:
        """
        Restore a file from a backup info.
        """
        backup = self.db.query(FileBackup).filter(FileBackup.id == backup_id).first()
        if not backup:
            raise ValueError(f"Backup {backup_id} not found")
        
        version = backup.file_version
        
        client = await self._get_client(server_id)
        try:
            await client.connect()
            
            async with client.conn.start_sftp_client() as sftp:
                # Check if backup file exists
                if not await sftp.exists(backup.backup_path):
                    raise FileNotFoundError(f"Backup file {backup.backup_path} not found on server")
                
                # Restore: Copy backup to original path
                # Backup current state before overwriting? Maybe relying on previous backups is enough.
                await sftp.copy(backup.backup_path, version.file_path)
                logger.info(f"Restored {version.file_path} from {backup.backup_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error restoring backup {backup_id}: {e}")
            raise
        finally:
            await client.close()
