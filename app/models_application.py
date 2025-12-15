"""Application Registry Models

SQLAlchemy ORM models for application registry, components, and dependencies.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, JSON, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class Application(Base):
    """
    Application registry - represents a monitored application/service.
    """
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
    display_name = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    team_owner = Column(String(100), nullable=True)
    criticality = Column(String(20), nullable=True)  # critical, high, medium, low
    tech_stack = Column(JSON, default={})
    alert_label_matchers = Column(JSON, default={})  # How to match alerts to this  app
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    components = relationship("ApplicationComponent", back_populates="application", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="application")
    
    # Knowledge base relationships
    design_documents = relationship("DesignDocument", back_populates="application", cascade="all, delete-orphan")
    design_images = relationship("DesignImage", back_populates="application", cascade="all, delete-orphan")
    design_chunks = relationship("DesignChunk", back_populates="application", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "criticality IN ('critical', 'high', 'medium', 'low')",
            name='ck_applications_criticality'
        ),
    )


class ApplicationComponent(Base):
    """
    Component within an application (e.g., API server, database, cache).
    """
    __tablename__ = "application_components"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    component_type = Column(String(50), nullable=True)  # compute, database, cache, queue, etc.
    subtype = Column(String(50), nullable=True)  # postgresql, mysql, nginx, etc.
    hostname = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    description = Column(Text, nullable=True)
    endpoints = Column(JSON, default={})  # {host, port, health_check_url}
    alert_label_matchers = Column(JSON, default={})  # How to match alerts to this component
    criticality = Column(String(20), default='high')
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    application = relationship("Application", back_populates="components")
    dependencies_from = relationship(
        "ComponentDependency",
        foreign_keys="ComponentDependency.from_component_id",
        back_populates="from_component",
        cascade="all, delete-orphan"
    )
    dependencies_to = relationship(
        "ComponentDependency",
        foreign_keys="ComponentDependency.to_component_id",
        back_populates="to_component",
        cascade="all, delete-orphan"
    )
    alerts = relationship("Alert", back_populates="component")

    __table_args__ = (
        CheckConstraint(
            "component_type IN ('compute', 'container', 'vm', 'database', 'cache', 'queue', 'storage', "
            "'load_balancer', 'firewall', 'switch', 'router', 'cloud_function', 'cloud_storage', "
            "'cloud_db', 'external', 'monitoring', 'cdn', 'api_gateway')",
            name='ck_components_type'
        ),
    )


class ComponentDependency(Base):
    """
    Directed edge in the component dependency graph.
    From component depends on To component.
    """
    __tablename__ = "component_dependencies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_component_id = Column(UUID(as_uuid=True), ForeignKey("application_components.id", ondelete="CASCADE"), nullable=False, index=True)
    to_component_id = Column(UUID(as_uuid=True), ForeignKey("application_components.id", ondelete="CASCADE"), nullable=False, index=True)
    dependency_type = Column(String(20), nullable=True)  # sync, async, optional
    failure_impact = Column(Text, nullable=True)  # What happens when this dependency fails
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    from_component = relationship("ApplicationComponent", foreign_keys=[from_component_id], back_populates="dependencies_from")
    to_component = relationship("ApplicationComponent", foreign_keys=[to_component_id], back_populates="dependencies_to")

    __table_args__ = (
        CheckConstraint(
            "dependency_type IN ('sync', 'async', 'optional')",
            name='ck_dependencies_type'
        ),
    )
