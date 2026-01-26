"""
Application configuration using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "aiops"
    postgres_user: str = "aiops"
    postgres_password: str = "aiops"

    # Authentication
    jwt_secret: str = "your-secret-key-change-in-production"
    jwt_expiry_hours: int = 24
    jwt_algorithm: str = "HS256"
    encryption_key: str = ""

    # Initial Admin
    admin_username: str = "admin"
    admin_password: str = "admin123"

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

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    model_config = {
        "env_file": ".env",
        "case_sensitive": False
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
