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

    def sync_repository(self, repo_url: str, app_id: Optional[UUID] = None, branch: str = "main", user_id: Optional[UUID] = None, sync_mode: str = "all") -> dict:
        """
        Clone/pull a repo and import markdown files.
        sync_mode: 'all', 'docs_only', 'code_only'
        """
        temp_dir = tempfile.mkdtemp(prefix="kb_sync_")
        stats = {"found": 0, "processed": 0, "errors": 0}
        
        try:
            logger.info(f"Cloning {repo_url} (branch: {branch}) to {temp_dir}...")
            self._run_git_command(["clone", "--depth", "1", "--branch", branch, repo_url, temp_dir])
            
            # Define extension groups
            docs_exts = ('.md', '.txt', '.markdown')
            code_exts = (
                '.py', '.js', '.ts', '.go', '.java', '.cpp', '.h', '.cs', '.rb', '.php', '.html', '.css', 
                '.yaml', '.yml', '.json', '.toml', '.xml', '.properties', '.dockerfile', '.sql', '.sh', '.bat', '.ps1'
            )
            
            # Determine active extensions based on sync_mode
            active_extensions = []
            if sync_mode == 'all':
                active_extensions = docs_exts + code_exts
            elif sync_mode == 'docs_only':
                active_extensions = docs_exts
            elif sync_mode == 'code_only':
                active_extensions = code_exts
            else:
                active_extensions = docs_exts + code_exts # Fallback
                
            active_extensions = tuple(active_extensions)
            logger.info(f"=== GIT SYNC DEBUG ===")
            logger.info(f"Repo: {repo_url}")
            logger.info(f"Branch: {branch}")
            logger.info(f"Sync Mode: '{sync_mode}'")
            logger.info(f"Active Extensions: {active_extensions}")
            
            # Walk the directory
            file_count = 0
            for root, _, files in os.walk(temp_dir):
                file_count += len(files)
                for file in files:
                    lower_name = file.lower()
                    
                    # Check if file matches active extensions or specific filenames
                    is_match = False
                    if lower_name.endswith(active_extensions):
                        is_match = True
                    elif (sync_mode in ['all', 'code_only']) and lower_name == 'dockerfile':
                        is_match = True
                        
                    if is_match:
                        file_path = Path(root) / file
                        stats["found"] += 1
                        logger.info(f"[MATCH] Processing file: {file} (Ext: {file_path.suffix})")
                        
                        try:
                            self._process_file(file_path, repo_url, app_id, user_id, branch)
                            stats["processed"] += 1
                        except Exception as e:
                            logger.error(f"[ERROR] Failed to process {file}: {e}")
                            stats["errors"] += 1
                    else:
                        # Log missed files for debugging only if they look like code/docs
                        if lower_name.endswith(('.py', '.md', '.json', '.yaml')):
                             logger.info(f"[SKIP] File skipped due to filter: {file}")

            logger.info(f"=== SYNC COMPLETE ===")
            logger.info(f"Total files seen: {file_count}")
            logger.info(f"Stats: {stats}")
            return stats
            
        finally:
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
