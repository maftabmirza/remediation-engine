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
from app.services.auth_service import (
    get_current_user_optional, 
    create_user,
    get_user_by_username
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
    chat_ws,
    chat_api,
    terminal_ws,
    audit,
    metrics,
    remediation
)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)


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
            
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    logger.info("Starting AIOps Platform...")
    init_db()
    logger.info("AIOps Platform started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AIOps Platform...")


from fastapi.openapi.docs import get_redoc_html

# Create FastAPI app
app = FastAPI(
    title="AIOps Platform",
    description="AI-powered Operations Platform with intelligent alert analysis",
    version="2.0.0",
    lifespan=lifespan,
    redoc_url=None  # Disable default to override
)

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
app.include_router(chat_ws.router)
app.include_router(chat_api.router)
app.include_router(terminal_ws.router)
app.include_router(servers.router)
app.include_router(audit.router)
app.include_router(metrics.router)
app.include_router(remediation.router)


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
    current_user: User = Depends(get_current_user_optional)
):
    """
    Settings page (LLM providers)
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("settings.html", {
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
