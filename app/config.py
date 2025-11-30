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

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
