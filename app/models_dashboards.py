"""
Prometheus Dashboard Models

Database models for custom Prometheus dashboards, panels, and data sources.
Allows users to create Grafana-like dashboards with custom PromQL queries.
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
import uuid

from app.database import Base


class PrometheusDatasource(Base):
    """
    Prometheus data source configuration

    Supports multiple Prometheus instances for large deployments
    """
    __tablename__ = "prometheus_datasources"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True, index=True)
    url = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)

    # Authentication
    auth_type = Column(String(50), default="none")  # none, basic, bearer
    username = Column(String(255), nullable=True)
    password = Column(String(512), nullable=True)  # encrypted
    bearer_token = Column(String(512), nullable=True)  # encrypted

    # Configuration
    timeout = Column(Integer, default=30)
    is_default = Column(Boolean, default=False)
    is_enabled = Column(Boolean, default=True)

    # Custom headers (JSON)
    custom_headers = Column(JSON, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String(255), nullable=True)

    # Relationships
    panels = relationship("PrometheusPanel", back_populates="datasource", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PrometheusDatasource {self.name} ({self.url})>"


class PanelType(str, enum.Enum):
    """Panel visualization types"""
    GRAPH = "graph"  # Line/area chart
    GAUGE = "gauge"  # Single value gauge
    STAT = "stat"  # Single stat number
    TABLE = "table"  # Data table
    HEATMAP = "heatmap"  # Heatmap
    BAR = "bar"  # Bar chart
    PIE = "pie"  # Pie/donut chart


class PrometheusPanel(Base):
    """
    Individual panel/graph configuration

    Stores PromQL query, visualization settings, and panel metadata
    """
    __tablename__ = "prometheus_panels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Data source
    datasource_id = Column(String(36), ForeignKey("prometheus_datasources.id"), nullable=False)

    # Query configuration
    promql_query = Column(Text, nullable=False)
    legend_format = Column(String(255), nullable=True)  # e.g., "{{instance}}"

    # Time range
    time_range = Column(String(50), default="24h")  # 1h, 6h, 24h, 7d, 30d
    refresh_interval = Column(Integer, default=30)  # seconds
    step = Column(String(20), default="auto")  # auto, 15s, 1m, 5m, 1h

    # Visualization
    panel_type = Column(String(50), default="graph")  # graph, gauge, stat, table, heatmap, bar, pie

    # Panel options (JSON)
    # For GRAPH: {lineWidth, fillOpacity, showPoints, yAxisLabel, etc}
    # For GAUGE: {min, max, thresholds: [{value, color}]}
    # For STAT: {unit, decimals, thresholds}
    visualization_config = Column(JSON, nullable=True)

    # Thresholds (for color coding)
    # Example: [{"value": 50, "color": "yellow"}, {"value": 80, "color": "red"}]
    thresholds = Column(JSON, nullable=True)

    # Tags for organization
    tags = Column(JSON, nullable=True)  # ["infrastructure", "cpu", "production"]

    # Sharing
    is_public = Column(Boolean, default=False)
    is_template = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String(255), nullable=True)

    # Relationships
    datasource = relationship("PrometheusDatasource", back_populates="panels")
    dashboard_panels = relationship("DashboardPanel", back_populates="panel", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PrometheusPanel {self.name} ({self.panel_type})>"


class Dashboard(Base):
    """
    Dashboard containing multiple panels

    Allows users to compose custom dashboards with saved panels
    """
    __tablename__ = "dashboards"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Layout configuration (JSON)
    # Grid-based layout: [{panelId, x, y, width, height}]
    layout = Column(JSON, nullable=True)

    # Dashboard settings
    time_range = Column(String(50), default="24h")  # Default for all panels
    refresh_interval = Column(Integer, default=60)  # seconds
    auto_refresh = Column(Boolean, default=True)

    # Tags and organization
    tags = Column(JSON, nullable=True)
    folder = Column(String(255), nullable=True)

    # Sharing and permissions
    is_public = Column(Boolean, default=False)
    is_favorite = Column(Boolean, default=False)
    is_home = Column(Boolean, default=False)  # Set as home dashboard

    # Metadata
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String(255), nullable=True)

    # Relationships
    panels = relationship("DashboardPanel", back_populates="dashboard", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Dashboard {self.name}>"


class DashboardPanel(Base):
    """
    Junction table for Dashboard and Panel relationship

    Stores panel position and size within a dashboard
    """
    __tablename__ = "dashboard_panels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    panel_id = Column(String(36), ForeignKey("prometheus_panels.id"), nullable=False)

    # Grid position (0-indexed)
    grid_x = Column(Integer, default=0)
    grid_y = Column(Integer, default=0)
    grid_width = Column(Integer, default=6)  # Out of 12 columns
    grid_height = Column(Integer, default=4)  # In grid units

    # Override panel settings (optional)
    override_time_range = Column(String(50), nullable=True)
    override_refresh_interval = Column(Integer, nullable=True)

    # Display order
    display_order = Column(Integer, default=0)

    # Relationships
    dashboard = relationship("Dashboard", back_populates="panels")
    panel = relationship("PrometheusPanel", back_populates="dashboard_panels")

    def __repr__(self):
        return f"<DashboardPanel dashboard={self.dashboard_id} panel={self.panel_id}>"


class VariableType(str, enum.Enum):
    """Dashboard variable types"""
    QUERY = "query"  # Populated from Prometheus query
    CUSTOM = "custom"  # Manual list of values
    CONSTANT = "constant"  # Single constant value
    TEXTBOX = "textbox"  # Free-text input
    INTERVAL = "interval"  # Time interval selector


class DashboardVariable(Base):
    """
    Dashboard variables for dynamic filtering

    Enables template variables like $instance, $job, $namespace
    that can be used in panel queries for dynamic dashboards.
    """
    __tablename__ = "dashboard_variables"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)

    # Variable identification
    name = Column(String(100), nullable=False)  # e.g., "instance", "job"
    label = Column(String(255), nullable=True)  # Display label, defaults to name

    # Variable type and configuration
    type = Column(String(50), nullable=False, default="query")  # query, custom, constant, textbox, interval

    # For query type
    query = Column(Text, nullable=True)  # PromQL query to fetch values
    datasource_id = Column(String(36), ForeignKey("prometheus_datasources.id"), nullable=True)
    regex = Column(String(255), nullable=True)  # Filter/transform query results

    # For custom type
    custom_values = Column(JSON, nullable=True)  # List of values: ["value1", "value2"]

    # Default value
    default_value = Column(Text, nullable=True)  # Can be single value or JSON array for multi-select
    current_value = Column(Text, nullable=True)  # Currently selected value(s)

    # Options
    multi_select = Column(Boolean, default=False)  # Allow multiple selections
    include_all = Column(Boolean, default=False)  # Include "All" option
    all_value = Column(String(255), nullable=True)  # Value to use when "All" selected (e.g., ".*")

    # Display
    hide = Column(Integer, default=0)  # 0=visible, 1=label only, 2=hidden
    sort = Column(Integer, default=0)  # Display order

    # Metadata
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    dashboard = relationship("Dashboard", backref="variables")
    datasource = relationship("PrometheusDatasource")

    def __repr__(self):
        return f"<DashboardVariable {self.name} ({self.type})>"


class DashboardAnnotation(Base):
    """
    Dashboard annotations for marking events

    Annotations are visual markers on charts that mark important events
    like deployments, incidents, maintenance windows, etc.
    """
    __tablename__ = "dashboard_annotations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=True)  # Null for global annotations
    panel_id = Column(String(36), ForeignKey("prometheus_panels.id"), nullable=True)  # Null for dashboard-wide

    # Time information
    time = Column(DateTime, nullable=False, index=True)  # When the event occurred
    time_end = Column(DateTime, nullable=True)  # For time range annotations

    # Content
    text = Column(Text, nullable=False)  # Annotation text/description
    title = Column(String(255), nullable=True)  # Optional title

    # Tags for filtering and categorization
    tags = Column(JSON, nullable=True)  # ["deployment", "production", "backend"]

    # Visual styling
    color = Column(String(50), default="#FF6B6B")  # Hex color for marker
    icon = Column(String(50), nullable=True)  # Optional icon name

    # Metadata
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String(255), nullable=True)

    # Relationships
    dashboard = relationship("Dashboard", backref="annotations")
    panel = relationship("PrometheusPanel", backref="annotations")

    def __repr__(self):
        return f"<DashboardAnnotation {self.title or self.text[:30]}>"
