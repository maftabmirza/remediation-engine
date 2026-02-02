"""
API Routers package
"""
from app.routers.auth import router as auth_router
from app.routers.alerts import router as alerts_router
from app.routers.rules import router as rules_router
from app.routers.webhook import router as webhook_router
from app.routers.settings import router as settings_router
from app.routers.servers import router as servers_router
from app.routers.users import router as users_router
from app.routers.auth_config import router as auth_config_router
from app.routers.commands_api import router as commands_router

from app.routers.terminal_ws import router as terminal_ws_router
from app.routers.audit import router as audit_router

# PII & Secret Detection routers
from app.routers import pii
from app.routers import pii_logs
from app.routers import pii_feedback
