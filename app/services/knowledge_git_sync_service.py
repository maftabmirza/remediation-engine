"""
Enhanced Knowledge Git Sync Service
Configurable synchronization for documentation and code from git repositories
Supports metadata-only and full code indexing
"""
import os
import shutil
import subprocess
import logging
import tempfile
import ast
import hashlib
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from pathlib import Path
from datetime import datetime

from sqlalchemy.orm import Session
from app.models_ai_helper import KnowledgeSource, KnowledgeSyncHistory
from app.models_knowledge import DesignDocument, DesignChunk
from app.services.embedding_service import EmbeddingService
from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)


class KnowledgeGitSyncService:
    """
    Enhanced git sync service for knowledge sources
    Supports both documentation and code synchronization
    """

    def __init__(self, db: Session):
        self.db = db
        self.doc_service = DocumentService(db)
        self.embedding_service = EmbeddingService(db)

    def _run_git_command(self, args: List[str], cwd: Optional[str] = None) -> str:
        """Run a git command and return output"""
        try:
            git_executable = "/usr/bin/git"
            if not os.path.exists(git_executable):
                git_executable = "git"

            cmd = [git_executable] + args
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300  # 5 minute timeout
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: {e.stderr}")
            raise Exception(f"Git command failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise Exception("Git command timed out")

    async def sync_source(self, source_id: UUID) -> Dict[str, Any]:
        """
        Synchronize a knowledge source
        Returns sync statistics
        """
        source = self.db.query(KnowledgeSource).filter(
            KnowledgeSource.id == source_id
        ).first()

        if not source:
            raise ValueError(f"Knowledge source not found: {source_id}")

        if not source.enabled:
            raise ValueError(f"Knowledge source is disabled: {source_id}")

        # Create sync history entry
        sync_history = KnowledgeSyncHistory(
            source_id=source_id,
            started_at=datetime.utcnow(),
            status='running',
            previous_commit_sha=source.last_commit_sha
        )
        self.db.add(sync_history)
        self.db.commit()

        try:
            # Update source status
            source.last_sync_status = 'syncing'
            self.db.commit()

            # Sync based on source type
            if source.source_type == 'git_docs':
                stats = await self._sync_git_docs(source, sync_history)
            elif source.source_type == 'git_code':
                stats = await self._sync_git_code(source, sync_history)
            elif source.source_type == 'local_files':
                stats = await self._sync_local_files(source, sync_history)
            else:
                raise ValueError(f"Unsupported source type: {source.source_type}")

            # Update sync history
            sync_history.completed_at = datetime.utcnow()
            sync_history.status = 'success'
            sync_history.documents_added = stats.get('documents_added', 0)
            sync_history.documents_updated = stats.get('documents_updated', 0)
            sync_history.documents_deleted = stats.get('documents_deleted', 0)
            sync_history.chunks_created = stats.get('chunks_created', 0)

            # Calculate duration
            duration = (sync_history.completed_at - sync_history.started_at).total_seconds() * 1000
            sync_history.duration_ms = int(duration)

            # Update source
            source.last_sync_at = datetime.utcnow()
            source.last_sync_status = 'success'
            source.sync_count += 1
            source.total_documents += stats.get('documents_added', 0)
            source.total_chunks += stats.get('chunks_created', 0)

            self.db.commit()

            logger.info(
                f"Sync completed for source {source.name}: "
                f"{stats.get('documents_added', 0)} docs added, "
                f"{stats.get('chunks_created', 0)} chunks created"
            )

            return stats

        except Exception as e:
            logger.error(f"Sync failed for source {source.name}: {str(e)}", exc_info=True)

            # Update sync history
            sync_history.completed_at = datetime.utcnow()
            sync_history.status = 'failed'
            sync_history.error_message = str(e)

            # Update source
            source.last_sync_status = 'error'
            source.last_sync_error = str(e)

            self.db.commit()
            raise

    async def _sync_git_docs(
        self,
        source: KnowledgeSource,
        sync_history: KnowledgeSyncHistory
    ) -> Dict[str, Any]:
        """
        Sync documentation from git repository
        """
        config = source.config
        repo_url = config.get('repo')
        path = config.get('path', '/')
        branch = config.get('branch', 'main')

        if not repo_url:
            raise ValueError("Git repository URL not configured")

        temp_dir = tempfile.mkdtemp(prefix="kb_docs_")
        stats = {
            'documents_added': 0,
            'documents_updated': 0,
            'chunks_created': 0
        }

        try:
            logger.info(f"Cloning {repo_url} (branch: {branch}) to {temp_dir}")
            self._run_git_command(["clone", "--depth", "1", "--branch", branch, repo_url, temp_dir])

            # Get current commit SHA
            commit_sha = self._run_git_command(["rev-parse", "HEAD"], cwd=temp_dir)
            sync_history.new_commit_sha = commit_sha
            source.last_commit_sha = commit_sha

            # If same commit, skip processing
            if commit_sha == source.last_commit_sha:
                logger.info(f"No changes detected (commit: {commit_sha})")
                return stats

            # Process markdown and text files
            target_path = os.path.join(temp_dir, path.lstrip('/'))
            if not os.path.exists(target_path):
                raise ValueError(f"Path not found in repository: {path}")

            for root, _, files in os.walk(target_path):
                for file in files:
                    if file.lower().endswith(('.md', '.txt', '.rst', '.adoc')):
                        file_path = Path(root) / file
                        try:
                            await self._process_doc_file(file_path, source, repo_url, branch)
                            stats['documents_added'] += 1
                            stats['chunks_created'] += 1  # Simplified
                        except Exception as e:
                            logger.error(f"Failed to process {file}: {e}")

            return stats

        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    async def _sync_git_code(
        self,
        source: KnowledgeSource,
        sync_history: KnowledgeSyncHistory
    ) -> Dict[str, Any]:
        """
        Sync code from git repository
        Supports metadata-only or full code indexing
        """
        config = source.config
        repo_url = config.get('repo')
        path = config.get('path', '/')
        branch = config.get('branch', 'main')
        index_mode = config.get('index_mode', 'metadata_only')  # or 'full_code'

        if not repo_url:
            raise ValueError("Git repository URL not configured")

        temp_dir = tempfile.mkdtemp(prefix="kb_code_")
        stats = {
            'documents_added': 0,
            'chunks_created': 0
        }

        try:
            logger.info(f"Cloning {repo_url} (branch: {branch}) for code indexing")
            self._run_git_command(["clone", "--depth", "1", "--branch", branch, repo_url, temp_dir])

            # Get current commit SHA
            commit_sha = self._run_git_command(["rev-parse", "HEAD"], cwd=temp_dir)
            sync_history.new_commit_sha = commit_sha
            source.last_commit_sha = commit_sha

            # Process Python files (extensible to other languages)
            target_path = os.path.join(temp_dir, path.lstrip('/'))
            if not os.path.exists(target_path):
                raise ValueError(f"Path not found in repository: {path}")

            for root, _, files in os.walk(target_path):
                for file in files:
                    if file.endswith('.py'):
                        file_path = Path(root) / file
                        try:
                            chunks_count = await self._process_code_file(
                                file_path, source, repo_url, branch, index_mode
                            )
                            stats['documents_added'] += 1
                            stats['chunks_created'] += chunks_count
                        except Exception as e:
                            logger.error(f"Failed to process {file}: {e}")

            return stats

        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    async def _process_doc_file(
        self,
        file_path: Path,
        source: KnowledgeSource,
        repo_url: str,
        branch: str
    ):
        """Process a documentation file"""
        content = file_path.read_text(encoding="utf-8", errors='ignore')
        title = file_path.stem.replace("-", " ").replace("_", " ").title()

        # Create document
        doc = DesignDocument(
            title=title,
            slug=self._generate_slug(title),
            doc_type='design_doc',
            format='markdown',
            raw_content=content,
            source_url=f"{repo_url}/blob/{branch}/{file_path.name}",
            source_type='git',
            source_id=source.id,
            status='active'
        )
        self.db.add(doc)
        self.db.flush()

        # Generate chunks and embeddings
        await self._generate_chunks(doc, content, source.id)

    async def _process_code_file(
        self,
        file_path: Path,
        source: KnowledgeSource,
        repo_url: str,
        branch: str,
        index_mode: str
    ) -> int:
        """
        Process a code file
        Returns number of chunks created
        """
        try:
            code = file_path.read_text(encoding="utf-8", errors='ignore')

            # Parse AST
            tree = ast.parse(code)

            chunks_created = 0

            # Extract functions and classes
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    chunk_content = await self._extract_function_metadata(node, code, index_mode)
                    if chunk_content:
                        await self._create_code_chunk(
                            source.id,
                            str(file_path),
                            chunk_content,
                            'function',
                            node.name
                        )
                        chunks_created += 1

                elif isinstance(node, ast.ClassDef):
                    chunk_content = await self._extract_class_metadata(node, code, index_mode)
                    if chunk_content:
                        await self._create_code_chunk(
                            source.id,
                            str(file_path),
                            chunk_content,
                            'class',
                            node.name
                        )
                        chunks_created += 1

            return chunks_created

        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            return 0

    async def _extract_function_metadata(
        self,
        node: ast.FunctionDef,
        code: str,
        index_mode: str
    ) -> Optional[str]:
        """Extract function metadata or full code"""
        if index_mode == 'metadata_only':
            # Extract just signature and docstring
            params = [arg.arg for arg in node.args.args]
            signature = f"def {node.name}({', '.join(params)})"

            docstring = ast.get_docstring(node) or ""

            return f"{signature}\n\n{docstring}"

        elif index_mode == 'full_code':
            # Extract full function code
            return ast.get_source_segment(code, node)

        return None

    async def _extract_class_metadata(
        self,
        node: ast.ClassDef,
        code: str,
        index_mode: str
    ) -> Optional[str]:
        """Extract class metadata or full code"""
        if index_mode == 'metadata_only':
            # Extract class name and docstring
            docstring = ast.get_docstring(node) or ""
            methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]

            return f"class {node.name}\n\nMethods: {', '.join(methods)}\n\n{docstring}"

        elif index_mode == 'full_code':
            # Extract full class code
            return ast.get_source_segment(code, node)

        return None

    async def _create_code_chunk(
        self,
        source_id: UUID,
        file_path: str,
        content: str,
        code_type: str,
        name: str
    ):
        """Create a code chunk with embedding"""
        chunk = DesignChunk(
            source_type='document',
            source_id=source_id,
            knowledge_source_id=source_id,
            content=content,
            content_type='text',
            chunk_metadata={
                'file_path': file_path,
                'code_type': code_type,
                'name': name
            }
        )
        self.db.add(chunk)
        self.db.flush()

        # Generate embedding
        try:
            embedding = await self.embedding_service.generate_embedding(content)
            chunk.embedding = embedding
        except Exception as e:
            logger.warning(f"Failed to generate embedding for {name}: {e}")

    async def _generate_chunks(self, doc: DesignDocument, content: str, source_id: UUID):
        """Generate chunks and embeddings for a document"""
        # Simple chunking by paragraphs (can be improved)
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

        for idx, para in enumerate(paragraphs):
            if len(para) < 50:  # Skip very short paragraphs
                continue

            chunk = DesignChunk(
                source_type='document',
                source_id=doc.id,
                knowledge_source_id=source_id,
                chunk_index=idx,
                content=para,
                content_type='text',
                chunk_metadata={'doc_title': doc.title}
            )
            self.db.add(chunk)
            self.db.flush()

            # Generate embedding
            try:
                embedding = await self.embedding_service.generate_embedding(para)
                chunk.embedding = embedding
            except Exception as e:
                logger.warning(f"Failed to generate embedding for chunk {idx}: {e}")

    async def _sync_local_files(
        self,
        source: KnowledgeSource,
        sync_history: KnowledgeSyncHistory
    ) -> Dict[str, Any]:
        """
        Sync from local file system
        """
        config = source.config
        path = config.get('path')

        if not path or not os.path.exists(path):
            raise ValueError(f"Local path not found: {path}")

        stats = {'documents_added': 0, 'chunks_created': 0}

        for root, _, files in os.walk(path):
            for file in files:
                if file.lower().endswith(('.md', '.txt')):
                    file_path = Path(root) / file
                    try:
                        content = file_path.read_text(encoding="utf-8", errors='ignore')
                        title = file_path.stem.replace("-", " ").replace("_", " ").title()

                        doc = DesignDocument(
                            title=title,
                            slug=self._generate_slug(title),
                            doc_type='design_doc',
                            format='markdown',
                            raw_content=content,
                            source_type='local_files',
                            source_id=source.id,
                            status='active'
                        )
                        self.db.add(doc)
                        self.db.flush()

                        await self._generate_chunks(doc, content, source.id)

                        stats['documents_added'] += 1
                        stats['chunks_created'] += 1
                    except Exception as e:
                        logger.error(f"Failed to process {file}: {e}")

        return stats

    def _generate_slug(self, title: str) -> str:
        """Generate URL-friendly slug"""
        slug = title.lower().replace(" ", "-")
        slug = ''.join(c for c in slug if c.isalnum() or c == '-')
        # Add hash to ensure uniqueness
        hash_suffix = hashlib.md5(title.encode()).hexdigest()[:8]
        return f"{slug}-{hash_suffix}"

    async def test_connection(self, source: KnowledgeSource) -> Dict[str, Any]:
        """
        Test connection to a knowledge source
        """
        if source.source_type in ['git_docs', 'git_code']:
            repo_url = source.config.get('repo')
            branch = source.config.get('branch', 'main')

            if not repo_url:
                raise ValueError("Repository URL not configured")

            temp_dir = tempfile.mkdtemp(prefix="kb_test_")
            try:
                self._run_git_command(["ls-remote", "--heads", repo_url, branch])
                return {"status": "success", "message": "Connection successful"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)

        elif source.source_type == 'local_files':
            path = source.config.get('path')
            if os.path.exists(path):
                return {"status": "success", "message": "Path exists"}
            else:
                return {"status": "error", "message": "Path not found"}

        return {"status": "error", "message": "Unknown source type"}
