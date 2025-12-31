"""
Configuration settings for Test Management WebApp
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # App settings
    APP_NAME: str = "AIOps Test Manager"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database settings
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "aiops_test_manager"
    POSTGRES_USER: str = "aiops"
    POSTGRES_PASSWORD: str = "aiops_secure_password"

    # Remediation Engine API
    REMEDIATION_ENGINE_URL: str = "http://remediation-engine:8080"

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # JWT for auth (shared with main app)
    JWT_SECRET: str = "your-super-secret-jwt-key-change-in-production"

    # Background job settings
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Test execution settings
    TEST_TIMEOUT: int = 300  # 5 minutes default timeout
    MAX_CONCURRENT_TESTS: int = 5

    @property
    def database_url(self) -> str:
        """Get async database URL"""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def database_url_sync(self) -> str:
        """Get sync database URL for Alembic"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
