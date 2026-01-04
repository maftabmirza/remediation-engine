import os
import shutil
import subprocess
import logging
import tempfile
from typing import List, Optional
from uuid import UUID
from pathlib import Path

from sqlalchemy.orm import Session
from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)

class GitSyncService:
    """Service to synchronize documents from Git repositories."""

    def __init__(self, db: Session):
        self.db = db
        self.doc_service = DocumentService(db)

    def _run_git_command(self, args: List[str], cwd: Optional[str] = None) -> str:
        """Run a git command and return output."""
        try:
            # explicit path to git to avoid path issues
            git_executable = "/usr/bin/git"
            
            # Check if git exists at explicit path, if not try just 'git'
            if not os.path.exists(git_executable):
                git_executable = "git"

            cmd = [git_executable] + args
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: {e.stderr}")
            raise Exception(f"Git command failed: {e.stderr}")

    def sync_repository(self, repo_url: str, app_id: Optional[UUID] = None, branch: str = "main", user_id: Optional[UUID] = None) -> dict:
        """
        Clone/pull a repo and import markdown files.
        
        Args:
            repo_url: URL of the git repository
            app_id: Optional Application ID to link documents to
            branch: Branch to checkout
            user_id: ID of the user initiating the sync
            
        Returns:
            Dict with sync stats
        """
        temp_dir = tempfile.mkdtemp(prefix="kb_sync_")
        stats = {"found": 0, "processed": 0, "errors": 0}
        
        try:
            logger.info(f"Cloning {repo_url} to {temp_dir}...")
            self._run_git_command(["clone", "--depth", "1", "--branch", branch, repo_url, temp_dir])
            
            # Walk the directory
            extensions = (
                # Docs
                '.md', '.txt', '.markdown',
                # Code
                '.py', '.js', '.ts', '.go', '.java', '.cpp', '.h', '.cs', '.rb', '.php', '.html', '.css',
                # Config/Scripts
                '.yaml', '.yml', '.json', '.toml', '.xml', '.properties', '.dockerfile', '.sql', '.sh', '.bat', '.ps1'
            )
            
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    lower_name = file.lower()
                    if lower_name.endswith(extensions) or lower_name == 'dockerfile':
                        file_path = Path(root) / file
                        stats["found"] += 1
                        
                        try:
                            self._process_file(file_path, repo_url, app_id, user_id, branch)
                            stats["processed"] += 1
                        except Exception as e:
                            logger.error(f"Failed to process {file}: {e}")
                            stats["errors"] += 1
                            
            return stats
            
        finally:
            # Cleanup
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def _process_file(self, file_path: Path, repo_url: str, app_id: Optional[UUID], user_id: Optional[UUID], branch: str = "main"):
        """Read and import a single file."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.warning(f"Skipping binary or non-utf8 file: {file_path}")
            return

        title = file_path.name
        
        # Determine doc_type based on extension
        ext = file_path.suffix.lower()
        if ext in ['.md', '.txt', '.markdown']:
            doc_type = "design_doc"
            title = file_path.stem.replace("-", " ").title()
        elif ext in ['.yaml', '.yml', '.json', '.toml', '.xml', '.properties', '.dockerfile'] or file_path.name.lower() == 'dockerfile':
            doc_type = "config"
        else:
            doc_type = "source_code"
        
        # Calculate source URL
        # GitHub convention: blob/branch/path
        # We need the relative path from the temp dir root, but here we only have the full path.
        # This is a limitation of this simple implementation. Ideally we'd pass the temp_root to this method.
        # For now, we'll store the filename, but we should improve this to store relative path.
        # Hack: Since we don't have temp_root passed easily without changing signature drastically, 
        # we will assume the file_path contains the temp dir name "kb_sync_" and split.
        
        rel_path = file_path.name
        parts = str(file_path).split("kb_sync_")
        if len(parts) > 1:
             # parts[1] starts with some random chars then path separator. 
             # let's try to find the standard separator
             path_parts = parts[1].split(os.sep)
             if len(path_parts) > 1:
                 rel_path = "/".join(path_parts[1:]) # Skip the random dir part

        self.doc_service.create_document(
            title=title,
            doc_type=doc_type,
            content=content,
            app_id=app_id,
            source_url=f"{repo_url}/blob/{branch}/{rel_path}",
            user_id=user_id,
            source_type="git"
        )
