"""
Overview Dashboard Seeder
Seeds the fixed "Operations Overview" dashboard and its widget panels.

These panels mirror the static dashboard.html but as editable, deletable
PrometheusPanel entries of type "widget". Once seeded they appear in the
Panel Library and are assembled into a Dashboard that users can edit,
clone, or delete just like any other dashboard.
"""
import logging
import uuid

from sqlalchemy.orm import Session

from app.models_dashboards import Dashboard, DashboardPanel, PrometheusPanel

logger = logging.getLogger(__name__)

# ── Canonical name so we can idempotently skip re-seeding ──────────────────
OVERVIEW_DASHBOARD_NAME = "Operations Overview"

# ── Panel definitions ───────────────────────────────────────────────────────
# `promql_query` is used as the widget-type identifier by dashboard_view.html.
# `panel_type` must be "widget" so the renderer bypasses Prometheus.
OVERVIEW_PANELS = [
    {
        "name": "AIOps Overview - KPI Metrics",
        "description": "Full KPI ribbon: Total Alerts, Analyzed, Pending, Critical, MTTA, MTTR, Remediation Rate, Reliability Index",
        "promql_query": "widget:kpi_ribbon",
        "panel_type": "widget",
        "time_range": "24h",
        "tags": ["overview", "kpi", "aiops-system"],
        # Grid position inside the overview dashboard
        "grid_x": 0, "grid_y": 0, "grid_width": 12, "grid_height": 2,
    },
    {
        "name": "AIOps Overview - Service Health",
        "description": "Service health tiles derived from active alert states",
        "promql_query": "widget:service_health",
        "panel_type": "widget",
        "time_range": "24h",
        "tags": ["overview", "services", "aiops-system"],
        "grid_x": 0, "grid_y": 2, "grid_width": 12, "grid_height": 4,
    },
    {
        "name": "AIOps Overview - Active Incidents",
        "description": "List of currently active / firing incidents",
        "promql_query": "widget:active_incidents",
        "panel_type": "widget",
        "time_range": "24h",
        "tags": ["overview", "incidents", "aiops-system"],
        "grid_x": 0, "grid_y": 6, "grid_width": 6, "grid_height": 6,
    },
    {
        "name": "AIOps Overview - MTTR Trend",
        "description": "Mean Time to Remediate trend chart",
        "promql_query": "widget:mttr_trend",
        "panel_type": "widget",
        "time_range": "24h",
        "tags": ["overview", "mttr", "aiops-system"],
        "grid_x": 6, "grid_y": 6, "grid_width": 6, "grid_height": 6,
    },
    {
        "name": "AIOps Overview - Alert Volume Trend",
        "description": "Alert volume over time as a line chart",
        "promql_query": "widget:alert_volume_trend",
        "panel_type": "widget",
        "time_range": "24h",
        "tags": ["overview", "alerts", "aiops-system"],
        "grid_x": 0, "grid_y": 12, "grid_width": 6, "grid_height": 6,
    },
    {
        "name": "AIOps Overview - Severity Distribution",
        "description": "Donut chart showing alert counts by severity",
        "promql_query": "widget:severity_distribution",
        "panel_type": "widget",
        "time_range": "24h",
        "tags": ["overview", "severity", "aiops-system"],
        "grid_x": 6, "grid_y": 12, "grid_width": 6, "grid_height": 6,
    },
    {
        "name": "AIOps Overview - ITSM Tickets",
        "description": "Recent open ITSM / incident management tickets",
        "promql_query": "widget:itsm_tickets",
        "panel_type": "widget",
        "time_range": "24h",
        "tags": ["overview", "itsm", "aiops-system"],
        "grid_x": 0, "grid_y": 18, "grid_width": 6, "grid_height": 7,
    },
    {
        "name": "AIOps Overview - Operations Feed",
        "description": "Live timeline feed of recent operational events and alerts",
        "promql_query": "widget:ops_feed",
        "panel_type": "widget",
        "time_range": "24h",
        "tags": ["overview", "feed", "aiops-system"],
        "grid_x": 6, "grid_y": 18, "grid_width": 6, "grid_height": 7,
    },
]


def seed_overview_dashboard(db: Session) -> None:
    """
    Idempotently seed the Operations Overview dashboard.

    1. Create any missing widget panels.
    2. Create the overview Dashboard (is_home=True) if absent.
    3. Link all panels to the dashboard with the grid positions above.
    """
    try:
        # ── 0. Resolve a datasource ID for the DB NOT-NULL constraint ───────
        # Widget panels don't actually query Prometheus, but the DB column
        # datasource_id has a NOT NULL constraint, so we must provide one.
        from app.models_dashboards import PrometheusDatasource
        placeholder_ds = (
            db.query(PrometheusDatasource)
            .filter(PrometheusDatasource.is_default == True)
            .first()
            or db.query(PrometheusDatasource).first()
        )
        placeholder_ds_id = placeholder_ds.id if placeholder_ds else None

        if placeholder_ds_id is None:
            logger.warning(
                "No Prometheus datasource found — skipping overview dashboard seeding. "
                "Create a datasource first, then restart to trigger seeding."
            )
            return

        # ── 1. Ensure all overview widget panels exist ──────────────────────
        panel_ids: dict[str, str] = {}  # promql_query → panel.id

        for pdef in OVERVIEW_PANELS:
            existing = (
                db.query(PrometheusPanel)
                .filter(PrometheusPanel.promql_query == pdef["promql_query"])
                .first()
            )
            if existing:
                panel_ids[pdef["promql_query"]] = existing.id
                logger.debug("Overview panel already exists: %s", pdef["name"])
            else:
                panel = PrometheusPanel(
                    id=str(uuid.uuid4()),
                    name=pdef["name"],
                    description=pdef.get("description"),
                    datasource_id=placeholder_ds_id,  # satisfies NOT NULL constraint
                    promql_query=pdef["promql_query"],
                    panel_type=pdef["panel_type"],
                    time_range=pdef.get("time_range", "24h"),
                    refresh_interval=30,
                    step="auto",
                    is_template=True,
                    is_public=True,
                    tags=pdef.get("tags", []),
                    created_by="system",
                )
                db.add(panel)
                db.flush()  # get the id before commit
                panel_ids[pdef["promql_query"]] = panel.id
                logger.info("Created overview widget panel: %s", pdef["name"])

        # ── 2. Ensure the overview Dashboard exists ─────────────────────────
        dashboard = (
            db.query(Dashboard)
            .filter(Dashboard.name == OVERVIEW_DASHBOARD_NAME)
            .first()
        )

        if not dashboard:
            dashboard = Dashboard(
                id=str(uuid.uuid4()),
                name=OVERVIEW_DASHBOARD_NAME,
                description="Auto-generated Operations Overview dashboard. "
                             "All panels are editable — add, remove, or re-arrange as needed.",
                time_range="24h",
                refresh_interval=30,
                auto_refresh=True,
                is_public=False,
                is_favorite=False,
                is_home=True,
                tags=["overview", "aiops-system"],
                folder="System",
                created_by="system",
            )
            db.add(dashboard)
            db.flush()
            logger.info("Created overview dashboard: %s (id=%s)", dashboard.name, dashboard.id)
        else:
            # Make sure it is flagged as home so the redirect works
            if not dashboard.is_home:
                dashboard.is_home = True
            logger.debug("Overview dashboard already exists (id=%s)", dashboard.id)

        # ── 3. Link panels to dashboard (skip if links already exist) ───────
        existing_panel_ids = {
            dp.panel_id
            for dp in db.query(DashboardPanel)
            .filter(DashboardPanel.dashboard_id == dashboard.id)
            .all()
        }

        added = 0
        for order, pdef in enumerate(OVERVIEW_PANELS):
            pid = panel_ids.get(pdef["promql_query"])
            if not pid or pid in existing_panel_ids:
                continue

            dp = DashboardPanel(
                id=str(uuid.uuid4()),
                dashboard_id=dashboard.id,
                panel_id=pid,
                grid_x=pdef["grid_x"],
                grid_y=pdef["grid_y"],
                grid_width=pdef["grid_width"],
                grid_height=pdef["grid_height"],
                display_order=order,
            )
            db.add(dp)
            added += 1

        db.commit()

        if added:
            logger.info(
                "✅ Overview dashboard seeded: %d panel link(s) added (dashboard id=%s)",
                added,
                dashboard.id,
            )
        else:
            logger.info("Overview dashboard already fully seeded — nothing to do.")

    except Exception as exc:
        logger.error("Failed to seed overview dashboard: %s", exc, exc_info=True)
        db.rollback()
