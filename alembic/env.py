"""Alembic migration environment configuration"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import app's database configuration
from app.config import get_settings
from app.database import Base

# Import all models so Alembic can detect them
from app.models import *
from app.models_agent import *
from app.models_application import *
from app.models_chat import *
from app.models_dashboards import *
from app.models_group import *
from app.models_itsm import *
from app.models_knowledge import *
from app.models_learning import *
from app.models_remediation import *
from app.models_runbook_acl import *
from app.models_scheduler import *
from app.models_troubleshooting import *

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Set target metadata for autogenerate support
target_metadata = Base.metadata

# Get database URL from app settings
settings = get_settings()
db_url = os.environ.get("DATABASE_URL") or settings.database_url
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
