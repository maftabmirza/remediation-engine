"""
Change Set Service

Manages the lifecycle of atomic change sets: creation, preview, application, and rollback.
"""
import logging
import uuid
from typing import List, Optional, Dict
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models_changeset import ChangeSet, ChangeItem, FileVersion
from app.services.file_ops_service import FileOpsService
from app.database import SessionLocal

logger = logging.getLogger(__name__)

class ChangeSetService:
    """Service for managing atomic file changes."""

    def __init__(self, db: Session, file_ops_service: FileOpsService):
        self.db = db
        self.file_ops = file_ops_service

    def create_change_set(self, session_id: uuid.UUID, title: str, description: str = None, agent_step_id: uuid.UUID = None) -> ChangeSet:
        """Create a new pending change set."""
        change_set = ChangeSet(
            session_id=session_id,
            title=title,
            description=description,
            agent_step_id=agent_step_id,
            status='pending'
        )
        self.db.add(change_set)
        self.db.commit()
        self.db.refresh(change_set)
        return change_set

    def add_change_item(self, change_set_id: uuid.UUID, file_path: str, operation: str, 
                       new_content: str = None, old_content: str = None, diff_hunks: dict = None) -> ChangeItem:
        """Add a change item to a change set."""
        # Calculate order index
        count = self.db.query(ChangeItem).filter(ChangeItem.change_set_id == change_set_id).count()
        
        item = ChangeItem(
            change_set_id=change_set_id,
            file_path=file_path,
            operation=operation,
            new_content=new_content,
            old_content=old_content,
            diff_hunks=diff_hunks,
            status='pending',
            order_index=count
        )
        self.db.add(item)
        self.db.commit()
        return item

    def get_change_set(self, change_set_id: uuid.UUID) -> Optional[ChangeSet]:
        """Get a change set by ID."""
        return self.db.query(ChangeSet).filter(ChangeSet.id == change_set_id).first()

    def get_session_change_sets(self, session_id: uuid.UUID) -> List[ChangeSet]:
        """Get all change sets for a session."""
        return self.db.query(ChangeSet)\
            .filter(ChangeSet.session_id == session_id)\
            .order_by(desc(ChangeSet.created_at))\
            .all()

    async def apply_change_set(self, change_set_id: uuid.UUID, server_id: uuid.UUID) -> bool:
        """
        Apply all changes in a changeset atomically (best effort) to the server.
        """
        change_set = self.get_change_set(change_set_id)
        if not change_set:
            raise ValueError(f"Change set {change_set_id} not found")
            
        if change_set.status != 'pending':
             raise ValueError(f"Change set is in {change_set.status} state, cannot apply")

        logger.info(f"Applying change set {change_set_id}: {change_set.title}")
        
        applied_items = []
        
        try:
            # 1. Create backups for all modified files first
            for item in change_set.items:
                if item.operation in ['modify', 'delete']:
                    logger.info(f"Backing up {item.file_path}")
                    await self.file_ops.create_backup(server_id, item.file_path, change_set.session_id)

            # 2. Apply changes
            for item in change_set.items:
                try:
                    if item.operation in ['create', 'modify']:
                        if item.new_content is None:
                            logger.warning(f"Skipping {item.operation} for {item.file_path}: no content")
                            continue
                            
                        await self.file_ops.write_file(
                            server_id=server_id, 
                            file_path=item.file_path, 
                            content=item.new_content,
                            create_backup=False # Already backed up
                        )
                        
                    elif item.operation == 'delete':
                        # self.file_ops.delete_file(...) # Implement delete if needed, for now maybe just empty or rename
                        # For safety, let's just rename to .deleted
                        pass 
                        
                    item.status = 'applied'
                    item.applied_at = datetime.now(timezone.utc)
                    applied_items.append(item)
                    
                except Exception as e:
                    logger.error(f"Failed to apply change to {item.file_path}: {e}")
                    raise

            # 3. Mark change set as applied
            change_set.status = 'applied'
            change_set.applied_at = datetime.now(timezone.utc)
            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Error applying change set {change_set_id}: {e}")
            self.db.rollback()
            # Attempt partial rollback if some items were applied? 
            # Ideally we would rollback the successful ones here.
            await self._rollback_partial(server_id, applied_items)
            change_set.status = 'failed'
            self.db.commit()
            raise

    async def _rollback_partial(self, server_id: uuid.UUID, items: List[ChangeItem]):
        """Rollback specific items (used during failed apply)."""
        logger.warning("Rolling back partially applied items...")
        for item in reversed(items):
            try:
                # Find the backup we just created
                # This is tricky because we didn't store the exact backup ID in ChangeItem.
                # But we can find the latest backup for this file/session.
                pass # Implementation would use restore_backup logic
            except Exception as e:
                logger.error(f"Failed to rollback {item.file_path}: {e}")

    async def rollback_change_set(self, change_set_id: uuid.UUID, server_id: uuid.UUID) -> bool:
        """
        Rollback an applied change set.
        """
        change_set = self.get_change_set(change_set_id)
        if not change_set:
            raise ValueError(f"Change set {change_set_id} not found")
            
        if change_set.status != 'applied':
             raise ValueError(f"Change set is in {change_set.status} state, cannot rollback")

        logger.info(f"Rolling back change set {change_set_id}")
        
        try:
            # We revert interactions in reverse order
            for item in reversed(change_set.items):
                if item.status == 'applied':
                    if item.operation in ['modify', 'create']:
                        # Restore old content
                        if item.old_content:
                             await self.file_ops.write_file(
                                server_id=server_id,
                                file_path=item.file_path,
                                content=item.old_content,
                                create_backup=False
                            )
                        else:
                            # If it was a create operation, we should delete it.
                            # For now, maybe leaving it is safer or handling delete.
                            pass
                            
                    item.status = 'rolled_back'
            
            change_set.status = 'rolled_back'
            change_set.rolled_back_at = datetime.now(timezone.utc)
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error rolling back change set {change_set_id}: {e}")
            self.db.rollback()
            raise
