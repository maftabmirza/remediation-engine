"""
AIOps Platform - Main Application
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import get_settings
from app.database import get_db, engine, Base
from app.models import User, LLMProvider
# Import models to register them with SQLAlchemy
import app.models_application  # noqa: F401
import app.models_application_knowledge  # noqa: F401
import app.models_knowledge  # noqa: F401
import app.models_learning  # noqa: F401 - Phase 3: Learning System
import app.models_dashboards  # noqa: F401 - Prometheus Dashboard Builder
import app.models_agent  # noqa: F401 - Agent Mode
from app.services.auth_service import (
    get_current_user_optional,
    create_user,
    get_user_by_username,
    get_permissions_for_role,
    get_permissions_for_user
)
from app.routers import (
    auth,
    alerts,
    rules,
    webhook,
    settings as settings_router_module,
    servers,
    users,
    auth_config,
    terminal_ws,
    audit,
    metrics,
    remediation,
    roles,
    scheduler,
    applications,
    application_profiles_api,  # Phase 3: Application Profiles
    grafana_datasources_api,  # Phase 3: Grafana Datasources
    observability_api,  # Phase 4: AI-Powered Observability Queries
    revive_api,  # RE-VIVE Widget
    knowledge,  # Phase 2: Knowledge Base
    feedback,  # Phase 3: Learning System
    troubleshooting,  # Phase 4: Troubleshooting Engine
    troubleshooting,  # Phase 4: Troubleshooting Engine
    clusters,  # Week 1-2: Alert Clustering
    analytics,  # Phase 3-4: Analytics API
    itsm,  # Week 5-6: Change Correlation
    changes,  # Week 5-6: Change Correlation
    prometheus,  # Prometheus Integration
    datasources_api,  # Prometheus Dashboard Builder - Datasources
    panels_api,  # Prometheus Dashboard Builder - Panels
    dashboards_api,  # Prometheus Dashboard Builder - Dashboards
    variables_api,  # Prometheus Dashboard Builder - Variables
    alerts_api,  # Prometheus Dashboard Builder - Alerts Integration
    annotations_api,  # Prometheus Dashboard Builder - Annotations
    groups_api,  # Group-based RBAC
    runbook_acl_api,  # Runbook ACL - resource level permissions
    snapshots_api,  # Prometheus Dashboard Builder - Snapshots
    playlists_api,  # Prometheus Dashboard Builder - Playlists
    rows_api,  # Prometheus Dashboard Builder - Panel Rows
    query_history_api,  # Prometheus Dashboard Builder - Query History
    dashboard_permissions_api,  # Dashboard Permissions
    grafana_proxy,  # Grafana Integration - SSO Proxy
    chat_api,  # AI Chat API
    prometheus_proxy,  # Prometheus Integration - Proxy
    troubleshoot_api,  # Troubleshooting Mode API (separated from revive_api)
    knowledge_apps,
    remediation_view,
    agent_api,  # Agent Mode API
)
from app import api_credential_profiles
from app.services.execution_worker import start_execution_worker, stop_execution_worker
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Custom filter to suppress noisy Grafana WebSocket 403 errors
class WebSocketLogFilter(logging.Filter):
    def filter(self, record):
        # Suppress WebSocket connection rejected messages for Grafana live and chat
        message = record.getMessage()
        if "WebSocket /grafana/api/live/ws" in message:
            return False
        if "WebSocket /ws/chat" in message:
            return False
        if "connection rejected (403 Forbidden)" in message:
            return False
        if "connection closed" in message and "WebSocket" not in message:
            # Keep connection closed messages that aren't WebSocket related
            pass
        return True

# Apply filter to uvicorn access logger
logging.getLogger("uvicorn.error").addFilter(WebSocketLogFilter())

logger = logging.getLogger(__name__)

settings = get_settings()

# Rate Limiter
limiter = Limiter(key_func=get_remote_address, enabled=not settings.testing)


def init_db():
    """Initialize database and create initial data"""
    from app.database import SessionLocal
    
    db = SessionLocal()
    try:
        # Check if admin user exists
        admin = get_user_by_username(db, settings.admin_username)
        if not admin:
            logger.info(f"Creating initial admin user: {settings.admin_username}")
            create_user(db, settings.admin_username, settings.admin_password, role="admin")
            logger.info("Admin user created successfully")
        
        # Check if default LLM provider exists
        default_provider = db.query(LLMProvider).filter(LLMProvider.is_default == True).first()
        if not default_provider:
            logger.info("Creating default Claude provider")
            provider = LLMProvider(
                name="Claude Sonnet 4",
                provider_type="anthropic",
                model_id="claude-sonnet-4-20250514",
                is_default=True,
                is_enabled=True,
                config_json={"temperature": 0.3, "max_tokens": 2000}
            )
            db.add(provider)
            db.commit()
            logger.info("Default LLM provider created")

        # Check if default Prometheus datasource exists
        from app.models_dashboards import PrometheusDatasource
        default_datasource = db.query(PrometheusDatasource).filter(
            PrometheusDatasource.is_default == True
        ).first()

        if not default_datasource and settings.prometheus_url:
            logger.info("Creating default Prometheus datasource")
            import uuid
            datasource = PrometheusDatasource(
                id=str(uuid.uuid4()),
                name="Default Prometheus",
                url=settings.prometheus_url,
                description="Default Prometheus server from configuration",
                is_default=True,
                is_enabled=True,
                timeout=settings.prometheus_timeout
            )
            db.add(datasource)
            db.commit()
            logger.info("Default Prometheus datasource created")

        # Seed panel templates
        from app.services.panel_template_seeder import seed_panel_templates
        seed_panel_templates(db)

    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    logger.info("Starting AIOps Platform...")
    
    # PRODUCTION SECURITY: Verify no test code in production
    if not settings.testing:
        try:
            from app.security_checks import check_test_isolation, check_unique_constraints
            check_test_isolation()
            check_unique_constraints()
        except Exception as e:
            logger.error(f"Production security check failed: {e}")
            # In production, we want to fail fast if security checks fail
            if not settings.debug:
                raise
    
    scheduler = None

    if not settings.testing:
        init_db()
        
        # Start background execution worker
        logger.info("Starting execution worker...")
        await start_execution_worker()
        
        # Start scheduler
        logger.info("Starting scheduler...")
        from app.services.scheduler_service import get_scheduler
        from app.models_scheduler import ScheduledJob
        from app.database import get_async_db
        from sqlalchemy import select
        
        scheduler = get_scheduler()
        await scheduler.start()
        
        # Load existing enabled schedules from database
        try:
            async for db in get_async_db():
                result = await db.execute(
                    select(ScheduledJob).where(ScheduledJob.enabled == True)
                )
                schedules = result.scalars().all()
                
                for schedule in schedules:
                    try:
                        await scheduler.add_schedule(schedule)
                        logger.info(f"Loaded schedule: {schedule.name}")
                    except Exception as e:
                        logger.error(f"Failed to load schedule {schedule.name}: {e}")
                
                logger.info(f"✅ Loaded {len(schedules)} schedule(s)")
                break
        except Exception as e:
            logger.error(f"Failed to load schedules: {e}")
        
        # Start alert clustering jobs
        logger.info("Starting alert clustering jobs...")
        from app.services.clustering_worker import start_clustering_jobs
        start_clustering_jobs(scheduler._scheduler)  # Pass APScheduler instance
        logger.info("✅ Alert clustering jobs started")
        
        # Start ITSM sync background jobs
        logger.info("Starting ITSM sync background jobs...")
        from app.services.itsm_sync_worker import start_itsm_sync_jobs
        start_itsm_sync_jobs(scheduler._scheduler)  # Pass APScheduler instance
        logger.info("✅ ITSM sync jobs started")
    else:
        logger.info("Testing mode enabled: skipping init_db and background jobs")
    
    logger.info("AIOps Platform started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AIOps Platform...")
    
    if scheduler is not None:
        # Stop scheduler gracefully
        logger.info("Stopping scheduler...")
        await scheduler.shutdown()
        
        # Stop execution worker gracefully
        logger.info("Stopping execution worker...")
        await stop_execution_worker()
    
    logger.info("AIOps Platform shutdown complete")


from fastapi.openapi.docs import get_redoc_html

# Create FastAPI app
app = FastAPI(
    title="AIOps Platform",
    description="AI-powered Operations Platform with intelligent alert analysis",
    version="2.0.0",
    lifespan=lifespan,
    redoc_url=None  # Disable default to override
)

# Add ProxyHeadersMiddleware to handle X-Forwarded-* headers from reverse proxy
# This ensures HTTPS URLs are used in redirects when behind Nginx/SSL termination
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
    )


# Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Include API routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(auth_config.router)
app.include_router(alerts.router)
app.include_router(rules.router)
app.include_router(webhook.router)
app.include_router(settings_router_module.router)
app.include_router(terminal_ws.router)
app.include_router(servers.router)
app.include_router(audit.router)
app.include_router(metrics.router)
app.include_router(remediation.router)
app.include_router(api_credential_profiles.router)
app.include_router(roles.router)
app.include_router(scheduler.router)

app.include_router(applications.router)  # Phase 1: Application Registry
app.include_router(application_profiles_api.router)  # Phase 3: Application Profiles
app.include_router(grafana_datasources_api.router)  # Phase 3: Grafana Datasources
app.include_router(observability_api.router)  # Phase 4: AI-Powered Observability
app.include_router(revive_api.router)  # RE-VIVE Widget
app.include_router(knowledge.router)      # Phase 2: Knowledge Base
app.include_router(feedback.router, prefix="/api/v1", tags=["learning"])  # Phase 3: Learning System
app.include_router(troubleshooting.router, prefix="/api/v1", tags=["troubleshooting"])  # Phase 4: Troubleshooting Engine
app.include_router(clusters.router)       # Week 1-2: Alert Clustering
app.include_router(analytics.router)      # Phase 3-4: Analytics API
app.include_router(itsm.router)           # Week 5-6: Change Correlation - ITSM
app.include_router(changes.router)        # Week 5-6: Change Correlation - Changes
app.include_router(prometheus.router)     # Prometheus Integration
app.include_router(datasources_api.router)  # Prometheus Dashboard Builder - Datasources
app.include_router(panels_api.router)       # Prometheus Dashboard Builder - Panels
app.include_router(dashboards_api.router)   # Prometheus Dashboard Builder - Dashboards
app.include_router(variables_api.router)    # Prometheus Dashboard Builder - Variables
app.include_router(alerts_api.router)       # Prometheus Dashboard Builder - Alerts Integration
app.include_router(annotations_api.router)  # Prometheus Dashboard Builder - Annotations
app.include_router(groups_api.router)        # Group-based RBAC
app.include_router(runbook_acl_api.router)   # Runbook ACL - resource permissions
app.include_router(snapshots_api.router)    # Prometheus Dashboard Builder - Snapshots
app.include_router(playlists_api.router)    # Prometheus Dashboard Builder - Playlists
app.include_router(rows_api.router)         # Prometheus Dashboard Builder - Panel Rows
app.include_router(query_history_api.router) # Prometheus Dashboard Builder - Query History
app.include_router(dashboard_permissions_api.router) # Dashboard Permissions
app.include_router(grafana_proxy.router)    # Grafana Integration - SSO Proxy
app.include_router(chat_api.router)          # AI Chat API
app.include_router(prometheus_proxy.router) # Prometheus Integration - Proxy
app.include_router(troubleshoot_api.router)  # Troubleshooting Mode API
app.include_router(knowledge_apps.router)
app.include_router(remediation_view.router)
app.include_router(agent_api.router)         # Agent Mode API
app.include_router(agent_api.ws_router)      # Agent Mode WebSocket


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    User profile page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user
    })


# ============== Web UI Routes ==============

@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Dashboard / Home page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    # Get stats
    from app.models import Alert, AutoAnalyzeRule
    
    total_alerts = db.query(Alert).count()
    analyzed = db.query(Alert).filter(Alert.analyzed == True).count()
    pending = db.query(Alert).filter(Alert.analyzed == False).count()
    critical = db.query(Alert).filter(Alert.severity == "critical").count()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "stats": {
            "total_alerts": total_alerts,
            "analyzed": analyzed,
            "pending": pending,
            "critical": critical
        }
    })


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Analytics dashboard page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "user": current_user
    })


@app.get("/changes", response_class=HTMLResponse)
async def changes_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Change Correlation dashboard page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("changes.html", {
        "request": request,
        "user": current_user
    })


@app.get("/dashboards", response_class=HTMLResponse)
async def dashboards_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Dashboard Builder page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("dashboards.html", {
        "request": request,
        "user": current_user
    })


@app.get("/datasources", response_class=HTMLResponse)
async def datasources_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Datasources management page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("datasources.html", {
        "request": request,
        "user": current_user
    })


@app.get("/panels", response_class=HTMLResponse)
async def panels_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Panels library page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("panels.html", {
        "request": request,
        "user": current_user
    })


@app.get("/dashboard-view/{dashboard_id}", response_class=HTMLResponse)
async def dashboard_view_page(
    request: Request,
    dashboard_id: str,
    current_user: User = Depends(get_current_user_optional)
):
    """
    View a specific Prometheus dashboard with its panels
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("dashboard_view.html", {
        "request": request,
        "user": current_user,
        "dashboard_id": dashboard_id
    })


@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Login page
    """
    if current_user:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Registration page
    """
    if current_user:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/alerts", response_class=HTMLResponse)
async def alerts_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Alerts list page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("alerts.html", {
        "request": request,
        "user": current_user
    })


@app.get("/alerts/{alert_id}", response_class=HTMLResponse)
async def alert_detail_page(
    request: Request,
    alert_id: str,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Single alert detail page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("alert_detail.html", {
        "request": request,
        "user": current_user,
        "alert_id": alert_id
    })


@app.get("/ai", response_class=HTMLResponse)
async def ai_chat_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Standalone AI Chat page with terminal
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("ai_chat.html", {
        "request": request,
        "user": current_user
    })


@app.get("/rules", response_class=HTMLResponse)
async def rules_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Rules management page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("rules.html", {
        "request": request,
        "user": current_user
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Settings page (LLM providers)
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user": current_user,
        "permissions": list(get_permissions_for_user(db, current_user)),
    })


@app.get("/credential-profiles", response_class=HTMLResponse)
async def credential_profiles_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    API Credential Profiles management page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("credential_profiles.html", {
        "request": request,
        "user": current_user
    })


@app.get("/audit", response_class=HTMLResponse)
async def audit_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Audit logs page (Admin only)
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    if current_user.role != "admin":
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("audit.html", {
        "request": request,
        "user": current_user
    })


@app.get("/runbooks", response_class=HTMLResponse)
async def runbooks_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Auto-remediation runbooks management page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("runbooks.html", {
        "request": request,
        "user": current_user
    })


@app.get("/runbooks/new", response_class=HTMLResponse)
async def runbook_create_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Create new runbook - full page form
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("runbook_form.html", {
        "request": request,
        "user": current_user,
        "runbook_id": None,
        "mode": "create"
    })


@app.get("/runbooks/{runbook_id}/edit", response_class=HTMLResponse)
async def runbook_edit_page(
    request: Request,
    runbook_id: str,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Edit runbook - full page form
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("runbook_form.html", {
        "request": request,
        "user": current_user,
        "runbook_id": runbook_id,
        "mode": "edit"
    })


@app.get("/executions", response_class=HTMLResponse)
async def executions_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Runbook executions monitoring page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("executions.html", {
        "request": request,
        "user": current_user
    })


@app.get("/applications", response_class=HTMLResponse)
async def applications_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Application Registry list page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("applications.html", {
        "request": request,
        "user": current_user
    })


@app.get("/applications/{app_id}", response_class=HTMLResponse)
async def application_detail_page(
    request: Request,
    app_id: str,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Application detail and topology page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("application_detail.html", {
        "request": request,
        "user": current_user,
        "app_id": app_id
    })


@app.get("/knowledge", response_class=HTMLResponse)
async def knowledge_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Knowledge Base page - manage design documents and SOPs
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("knowledge.html", {
        "request": request,
        "user": current_user
    })


@app.get("/schedules", response_class=HTMLResponse)
async def schedules_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Scheduled runbook executions management page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("schedules.html", {
        "request": request,
        "user": current_user
    })


@app.get("/datasources", response_class=HTMLResponse)
async def datasources_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Prometheus Datasources management page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("datasources.html", {
        "request": request,
        "user": current_user
    })


@app.get("/panels", response_class=HTMLResponse)
async def panels_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Prometheus Panels management page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("panels.html", {
        "request": request,
        "user": current_user
    })


@app.get("/dashboards-builder", response_class=HTMLResponse)
async def dashboards_builder_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Dashboard Builder page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("dashboards.html", {
        "request": request,
        "user": current_user
    })


@app.get("/playlists", response_class=HTMLResponse)
async def playlists_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Playlists management page
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("playlists.html", {
        "request": request,
        "user": current_user
    })


@app.get("/playlists/{playlist_id}/play", response_class=HTMLResponse)
async def playlist_player_page(
    request: Request,
    playlist_id: str,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Playlist player page with auto-rotation
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("playlist_player.html", {
        "request": request,
        "user": current_user,
        "playlist_id": playlist_id
    })


@app.get("/snapshots/{snapshot_key}", response_class=HTMLResponse)
async def snapshot_view_page(
    request: Request,
    snapshot_key: str
):
    """
    Dashboard snapshot view page (public, no auth required)
    Renders a frozen dashboard from a snapshot
    """
    return templates.TemplateResponse("snapshot_view.html", {
        "request": request,
        "snapshot_key": snapshot_key
    })


# ============== Grafana Integration Pages ==============

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Logs page powered by Loki (via Grafana iframe)
    Provides seamless log exploration with LogQL queries
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    response = templates.TemplateResponse("grafana_logs.html", {
        "request": request,
        "user": current_user,
        "active_page": "logs"
    })
    # Allow iframe embedding from same origin
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    origin = str(request.base_url).rstrip("/")
    response.headers["Content-Security-Policy"] = f"frame-src 'self' {origin} http://grafana:3000"
    return response


@app.get("/traces", response_class=HTMLResponse)
async def traces_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Traces page powered by Tempo (via Grafana iframe)
    Provides distributed tracing with TraceQL queries
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    response = templates.TemplateResponse("grafana_traces.html", {
        "request": request,
        "user": current_user,
        "active_page": "traces"
    })
    # Allow iframe embedding from same origin
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    origin = str(request.base_url).rstrip("/")
    response.headers["Content-Security-Policy"] = f"frame-src 'self' {origin} http://grafana:3000"
    return response



@app.get("/prometheus", response_class=HTMLResponse)
async def prometheus_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Prometheus UI page (embedded iframe)
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    response = templates.TemplateResponse("prometheus.html", {
        "request": request,
        "user": current_user
    })
    # Allow iframe embedding - permissive CSP since Prometheus can be on various hosts/ports
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Content-Security-Policy"] = "frame-src 'self' http: https:"
    return response


@app.get("/grafana-alerts", response_class=HTMLResponse)
async def grafana_alerts_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Alert Manager page (via Grafana iframe)
    Provides alert visualization, grouping, and silencing
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    response = templates.TemplateResponse("grafana_alerts.html", {
        "request": request,
        "user": current_user,
        "active_page": "grafana-alerts"
    })
    # Allow iframe embedding from same origin
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    origin = str(request.base_url).rstrip("/")
    response.headers["Content-Security-Policy"] = f"frame-src 'self' {origin} http://grafana:3000"
    return response


@app.get("/grafana-advanced", response_class=HTMLResponse)
async def grafana_advanced_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Advanced Grafana dashboards page
    Provides access to full Grafana functionality including SQL datasources,
    advanced visualizations, and community dashboards
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    response = templates.TemplateResponse("grafana_advanced.html", {
        "request": request,
        "user": current_user,
        "active_page": "grafana-advanced"
    })
    # Allow iframe embedding from same origin
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    origin = str(request.base_url).rstrip("/")
    response.headers["Content-Security-Policy"] = f"frame-src 'self' {origin} http://grafana:3000"
    return response


@app.get("/grafana-diagnostic", response_class=HTMLResponse)
async def grafana_diagnostic_page(request: Request):
    """
    Diagnostic page to test Grafana iframe embedding
    Helps debug frame-busting and proxy issues
    """
    return templates.TemplateResponse("grafana_diagnostic.html", {
        "request": request
    })


# ============== Prometheus View Page ==============

@app.get("/prometheus-view", response_class=HTMLResponse)
async def prometheus_view_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    View Prometheus UI via Proxy
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("prometheus_view.html", {
        "request": request,
        "user": current_user,
        "active_page": "prometheus-view" 
    })


# ============== Health Check ==============

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint
    """
    try:
        # Check database connection
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": "2.0.0"
    }


# ============== WebSocket Endpoints ==============

from fastapi import WebSocket

@app.websocket("/ws/chat/{session_id}")
async def chat_websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for chat sessions.
    Currently closes gracefully as chat uses REST API.
    """
    await websocket.accept()
    await websocket.close(code=1000, reason="Chat uses REST API")
