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
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith(".md"):
                        file_path = Path(root) / file
                        stats["found"] += 1
                        
                        try:
                            self._process_file(file_path, repo_url, app_id, user_id)
                            stats["processed"] += 1
                        except Exception as e:
                            logger.error(f"Failed to process {file}: {e}")
                            stats["errors"] += 1
                            
            # Commit all changes
            self.db.commit()
            return stats
            
        finally:
            # Cleanup
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def _process_file(self, file_path: Path, repo_url: str, app_id: Optional[UUID], user_id: Optional[UUID]):
        """Read and import a single file."""
        content = file_path.read_text(encoding="utf-8")
        title = file_path.stem.replace("-", " ").title()
        
        # Calculate a source URL (approximate for now)
        # e.g. https://github.com/user/repo.git -> https://github.com/user/repo/blob/main/filename.md
        # This is simplified; a robust calc would handle different hosts.
        rel_path = file_path.name # This is just filename, ideally should be relative to root
        
        document = self.doc_service.create_document(
            title=title,
            doc_type="design_doc",
            content=content,
            app_id=app_id,
            source_url=f"{repo_url}::{file_path.name}",
            user_id=user_id,
            source_type="git"
        )
        
        # Create chunks
        self.doc_service.create_chunks_for_document(document, chunk_size=1000, overlap=200)

