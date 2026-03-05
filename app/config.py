"""
Application configuration using Pydantic Settings
"""
import sys
from pydantic import model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache

# Weak default values that must be overridden in production
_WEAK_JWT_SECRET = "your-secret-key-change-in-production"
_WEAK_ADMIN_PASSWORD = "admin123"


class Settings(BaseSettings):
    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "aiops"
    postgres_user: str = "aiops"
    postgres_password: str = "aiops"

    # Authentication
    jwt_secret: str = _WEAK_JWT_SECRET
    jwt_expiry_hours: int = 24
    jwt_algorithm: str = "HS256"
    encryption_key: str = ""

    # Initial Admin
    admin_username: str = "admin"
    admin_password: str = ""  # Must be set via ADMIN_PASSWORD env var

    # CORS — set to a comma-separated list of allowed origins, e.g.
    # CORS_ALLOWED_ORIGINS=https://ops.example.com,https://admin.example.com
    # Leave empty to disable cross-origin requests entirely.
    cors_allowed_origins: str = ""

    # LLM API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    # App
    debug: bool = False
    app_port: int = 8080
    recording_dir: str = "storage/recordings"
    testing: bool = False

    # Agent rate limits
    agent_max_commands_per_minute: int = 10
    agent_max_sessions_per_hour: int = 30

    # Prometheus Integration
    prometheus_url: str = "http://prometheus:9090"
    enable_prometheus_queries: bool = True
    prometheus_timeout: int = 30  # seconds

    # Prometheus Dashboard Settings
    prometheus_dashboard_enabled: bool = True
    prometheus_refresh_interval: int = 30  # seconds
    prometheus_default_time_range: str = "24h"  # 24h, 7d, 30d

    # Infrastructure Metrics Configuration
    infrastructure_metrics_enabled: bool = True
    infrastructure_show_cpu: bool = True
    infrastructure_show_memory: bool = True
    infrastructure_show_disk: bool = True
    infrastructure_cpu_warning_threshold: int = 75  # percentage
    infrastructure_cpu_critical_threshold: int = 90  # percentage
    infrastructure_memory_warning_threshold: int = 75  # percentage
    infrastructure_memory_critical_threshold: int = 90  # percentage
    infrastructure_disk_warning_threshold: int = 75  # percentage
    infrastructure_disk_critical_threshold: int = 90  # percentage

    # Chart Configuration
    chart_library: str = "echarts"  # echarts or chartjs
    chart_theme: str = "grafana-dark"  # grafana-dark, default, light
    chart_enable_zoom: bool = True
    chart_enable_animations: bool = True
    chart_max_data_points: int = 1000

    # Alert Trends Configuration
    alert_trends_enabled: bool = True
    alert_trends_default_hours: int = 24
    alert_trends_step: str = "1h"  # 15s, 1m, 5m, 1h

    # Prometheus Query Optimization
    prometheus_use_cache: bool = True
    prometheus_cache_ttl: int = 60  # seconds
    prometheus_max_retries: int = 3
    prometheus_retry_delay: int = 2  # seconds

    # Notification System
    notification_worker_enabled: bool = True
    notification_retry_max: int = 3
    notification_retry_delay_seconds: int = 30

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def cors_origins_list(self) -> list[str]:
        """Return the CORS allowed origins as a list."""
        if not self.cors_allowed_origins:
            return []
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validate_secrets(self) -> "Settings":
        """Refuse to start if obviously unsafe defaults are still in use."""
        errors: list[str] = []
        if self.jwt_secret == _WEAK_JWT_SECRET:
            errors.append(
                "JWT_SECRET is still the insecure default value. "
                "Set a strong, random secret in your environment or .env file."
            )
        if self.admin_password == _WEAK_ADMIN_PASSWORD:
            errors.append(
                "ADMIN_PASSWORD is still the insecure default 'admin123'. "
                "Set a strong password in your environment or .env file."
            )
        if errors:
            print("\n[STARTUP ERROR] Refusing to start — insecure configuration detected:", file=sys.stderr)
            for e in errors:
                print(f"  • {e}", file=sys.stderr)
            print("\nSet the required environment variables (or update .env) and restart.", file=sys.stderr)
            sys.exit(1)
        return self

    model_config = {
        "env_file": ".env",
        "case_sensitive": False
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
