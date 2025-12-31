"""
FastAPI Application for Test Management System
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
import os

from app.config import settings
from app.database import init_db
from app.api import dashboard, test_cases, test_runs, webhook


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events - startup and shutdown
    """
    # Startup
    print("Starting Test Management WebApp...")
    print(f"Environment: {settings.POSTGRES_HOST}")

    # Initialize database tables
    try:
        await init_db()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")

    yield

    # Shutdown
    print("Shutting down Test Management WebApp...")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Comprehensive test management system for AIOps platform",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include routers
app.include_router(dashboard.router)
app.include_router(test_cases.router)
app.include_router(test_runs.router)
app.include_router(webhook.router)


@app.get("/")
async def root():
    """
    Root endpoint - redirect to dashboard
    """
    return RedirectResponse(url="/dashboard")


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/api/info")
async def api_info():
    """
    API information endpoint
    """
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.POSTGRES_HOST,
        "endpoints": {
            "dashboard": "/dashboard",
            "test_cases": "/test-cases",
            "test_runs": "/test-runs",
            "api_docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
