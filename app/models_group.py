"""Group models for RBAC - Groups contain users and can have a role assigned."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class Group(Base):
    """
    Groups for organizing users.
    A group can have a role assigned, giving all members that role's permissions.
    Supports future AD sync integration.
    """
    __tablename__ = "groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=True)
    
    # AD Sync Configuration
    ad_group_dn = Column(String(500), nullable=True)  # e.g., "CN=SRE-Team,OU=Groups,DC=corp,DC=com"
    sync_enabled = Column(Boolean, default=False, index=True)
    last_synced = Column(DateTime(timezone=True), nullable=True)
    
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    role = relationship("Role")
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    created_by_user = relationship("User", foreign_keys=[created_by])


class GroupMember(Base):
    """
    Junction table for group membership.
    Tracks how the user was added (manual vs AD sync).
    """
    __tablename__ = "group_members"
    
    __table_args__ = (
        UniqueConstraint('group_id', 'user_id', name='uq_group_member'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(20), default="manual", index=True)  # manual | ad_sync
    joined_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    group = relationship("Group", back_populates="members")
    user = relationship("User")
