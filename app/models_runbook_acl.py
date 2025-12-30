"""
Runbook ACL Models

Resource-level access control for runbooks - allows granting view/edit/execute
permissions to specific groups on individual runbooks.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class RunbookACL(Base):
    """
    ACL entry granting a group permissions on a specific runbook.
    
    This is an ADDITIVE model - ACLs extend global permissions.
    Users with global permissions (execute_runbooks, edit_runbooks) can access all runbooks.
    ACLs grant additional access to groups that don't have global perms.
    """
    __tablename__ = "runbook_acls"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runbook_id = Column(UUID(as_uuid=True), ForeignKey("runbooks.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    
    # Permissions
    can_view = Column(Boolean, default=True)      # Can see runbook in list
    can_edit = Column(Boolean, default=False)     # Can modify runbook configuration
    can_execute = Column(Boolean, default=False)  # Can trigger runbook execution
    
    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    # Relationships
    runbook = relationship("Runbook", backref="acl_entries")
    group = relationship("Group")
    created_by_user = relationship("User")
    
    __table_args__ = (
        UniqueConstraint("runbook_id", "group_id", name="uq_runbook_group_acl"),
        Index("idx_runbook_acl_runbook", "runbook_id"),
        Index("idx_runbook_acl_group", "group_id"),
    )
