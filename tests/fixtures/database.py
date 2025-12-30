"""
Database fixtures for pytest tests.

This module provides reusable database fixtures for testing.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.database import Base


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Get the test database URL from environment or use default."""
    import os
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://aiops:aiops_secure_password@postgres-test:5432/aiops_test"
    )


@pytest.fixture(scope="session")
def test_engine(test_database_url):
    """Create a test database engine for the session."""
    from app.database import Base
    
    engine = create_engine(test_database_url)
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """
    Provide a transactional database session for each test.
    
    Each test gets a fresh session that is rolled back after the test,
    ensuring test isolation.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionLocal()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def clean_database(test_engine):
    """
    Provide a clean database by truncating all tables.
    
    Use this when you need a completely clean slate without existing data.
    """
    from app.database import Base
    
    # Truncate all tables
    with test_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()
    
    yield test_engine


@pytest.fixture(scope="module")
def seeded_database(test_engine):
    """
    Provide a database with basic seed data for read-only tests.
    
    This fixture is module-scoped for performance. Use for tests that
    don't modify data.
    """
    from app.models import User, LLMProvider
    from app.services.auth_service import get_password_hash
    import uuid
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = SessionLocal()
    
    try:
        # Create test users
        admin_user = User(
            id=str(uuid.uuid4()),
            username="test_admin",
            password_hash=get_password_hash("TestPassword123!"),
            role="admin",
            is_active=True
        )
        session.add(admin_user)
        
        operator_user = User(
            id=str(uuid.uuid4()),
            username="test_operator",
            password_hash=get_password_hash("TestPassword123!"),
            role="operator",
            is_active=True
        )
        session.add(operator_user)
        
        # Create default LLM provider
        llm_provider = LLMProvider(
            id=str(uuid.uuid4()),
            name="Test Claude",
            provider_type="anthropic",
            model_id="claude-3-sonnet-20240229",
            is_default=True,
            is_enabled=True,
            config_json={"temperature": 0.3, "max_tokens": 2000}
        )
        session.add(llm_provider)
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
    
    yield test_engine
    
    # Cleanup after module
    with test_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()
