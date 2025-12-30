#!/usr/bin/env python3
"""
Database seeding script for test environment.

This script populates the test database with sample data for integration testing
and development purposes.

Usage:
    python tests/fixtures/seed_database.py
"""
import os
import sys
from datetime import datetime, timedelta
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment
os.environ["POSTGRES_DB"] = "aiops_test"
os.environ["ENVIRONMENT"] = "test"

from app.database import Base
from app.models import (
    User, Alert, Rule, Runbook, RunbookStep,
    LLMProvider, ServerCredential, Application
)
from app.services.auth_service import get_password_hash


def get_test_database_url():
    """Get test database URL."""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://aiops:aiops_secure_password@localhost:5432/aiops_test"
    )


def seed_users(session):
    """Create test users."""
    print("Creating test users...")
    
    users = [
        User(
            id=str(uuid.uuid4()),
            username="admin",
            password_hash=get_password_hash("Passw0rd"),
            email="admin@example.com",
            role="admin",
            is_active=True
        ),
        User(
            id=str(uuid.uuid4()),
            username="engineer",
            password_hash=get_password_hash("Passw0rd"),
            email="engineer@example.com",
            role="engineer",
            is_active=True
        ),
        User(
            id=str(uuid.uuid4()),
            username="operator",
            password_hash=get_password_hash("Passw0rd"),
            email="operator@example.com",
            role="operator",
            is_active=True
        ),
    ]
    
    for user in users:
        session.add(user)
    
    session.commit()
    print(f"Created {len(users)} users")


def seed_llm_providers(session):
    """Create test LLM providers."""
    print("Creating LLM providers...")
    
    providers = [
        LLMProvider(
            id=str(uuid.uuid4()),
            name="Claude Sonnet (Test)",
            provider_type="anthropic",
            model_id="claude-3-sonnet-20240229",
            is_default=True,
            is_enabled=True,
            config_json={"temperature": 0.3, "max_tokens": 2000}
        ),
        LLMProvider(
            id=str(uuid.uuid4()),
            name="GPT-4 (Test)",
            provider_type="openai",
            model_id="gpt-4",
            is_default=False,
            is_enabled=True,
            config_json={"temperature": 0.3, "max_tokens": 2000}
        ),
    ]
    
    for provider in providers:
        session.add(provider)
    
    session.commit()
    print(f"Created {len(providers)} LLM providers")


def seed_rules(session):
    """Create test rules."""
    print("Creating rules...")
    
    rules = [
        Rule(
            id=str(uuid.uuid4()),
            name="Auto-analyze critical alerts",
            description="Automatically analyze all critical severity alerts",
            priority=1,
            alert_name_pattern="*",
            severity_pattern="critical",
            instance_pattern="*",
            job_pattern="*",
            action="auto_analyze",
            enabled=True
        ),
        Rule(
            id=str(uuid.uuid4()),
            name="Nginx down alerts",
            description="Auto-trigger remediation for Nginx down",
            priority=5,
            alert_name_pattern="NginxDown",
            severity_pattern="*",
            instance_pattern="*",
            job_pattern="*",
            action="trigger_runbook",
            enabled=True
        ),
        Rule(
            id=str(uuid.uuid4()),
            name="Info alerts - notify only",
            description="Only notify for info severity alerts",
            priority=10,
            alert_name_pattern="*",
            severity_pattern="info",
            instance_pattern="*",
            job_pattern="*",
            action="notify",
            enabled=True
        ),
    ]
    
    for rule in rules:
        session.add(rule)
    
    session.commit()
    print(f"Created {len(rules)} rules")


def seed_runbooks(session):
    """Create test runbooks with steps."""
    print("Creating runbooks...")
    
    # Runbook 1: Restart Nginx
    runbook1 = Runbook(
        id=str(uuid.uuid4()),
        name="Restart Nginx Service",
        description="Standard procedure to restart Nginx web server",
        category="service_recovery",
        enabled=True,
        auto_execute=False,
        approval_required=True,
        timeout_seconds=300,
        max_executions_per_hour=5,
        cooldown_minutes=10,
        version=1
    )
    session.add(runbook1)
    session.flush()  # Get the ID
    
    steps1 = [
        RunbookStep(
            id=str(uuid.uuid4()),
            runbook_id=runbook1.id,
            name="Check Nginx status",
            order=1,
            command="systemctl status nginx",
            executor_type="ssh",
            timeout_seconds=30,
            continue_on_error=True
        ),
        RunbookStep(
            id=str(uuid.uuid4()),
            runbook_id=runbook1.id,
            name="Restart Nginx",
            order=2,
            command="sudo systemctl restart nginx",
            executor_type="ssh",
            timeout_seconds=60,
            continue_on_error=False
        ),
        RunbookStep(
            id=str(uuid.uuid4()),
            runbook_id=runbook1.id,
            name="Verify Nginx is running",
            order=3,
            command="systemctl is-active nginx",
            executor_type="ssh",
            timeout_seconds=30,
            continue_on_error=False
        ),
    ]
    
    for step in steps1:
        session.add(step)
    
    # Runbook 2: Clear disk space
    runbook2 = Runbook(
        id=str(uuid.uuid4()),
        name="Clear disk space",
        description="Clean up temporary files and logs",
        category="capacity_management",
        enabled=True,
        auto_execute=False,
        approval_required=True,
        timeout_seconds=180,
        max_executions_per_hour=3,
        cooldown_minutes=30,
        version=1
    )
    session.add(runbook2)
    session.flush()
    
    steps2 = [
        RunbookStep(
            id=str(uuid.uuid4()),
            runbook_id=runbook2.id,
            name="Check disk usage",
            order=1,
            command="df -h",
            executor_type="ssh",
            timeout_seconds=30,
            continue_on_error=True
        ),
        RunbookStep(
            id=str(uuid.uuid4()),
            runbook_id=runbook2.id,
            name="Clear temp files",
            order=2,
            command="sudo rm -rf /tmp/*",
            executor_type="ssh",
            timeout_seconds=60,
            continue_on_error=True
        ),
        RunbookStep(
            id=str(uuid.uuid4()),
            runbook_id=runbook2.id,
            name="Clear old logs",
            order=3,
            command="sudo find /var/log -name '*.log.*' -mtime +7 -delete",
            executor_type="ssh",
            timeout_seconds=60,
            continue_on_error=True
        ),
    ]
    
    for step in steps2:
        session.add(step)
    
    session.commit()
    print("Created 2 runbooks with steps")


def seed_alerts(session):
    """Create sample alerts."""
    print("Creating sample alerts...")
    
    alerts = []
    
    # Create 5 firing alerts
    for i in range(5):
        alert = Alert(
            id=str(uuid.uuid4()),
            fingerprint=f"test-fp-{uuid.uuid4().hex[:16]}",
            alert_name=["HighCPUUsage", "NginxDown", "DiskSpaceWarning", "MemoryLeak", "DatabaseSlow"][i],
            severity="critical" if i < 2 else "warning",
            instance=f"server-{i+1:02d}",
            job="node-exporter",
            status="firing",
            summary=f"Test alert {i+1}",
            description=f"This is a test alert for integration testing",
            starts_at=datetime.utcnow() - timedelta(minutes=10),
            labels={
                "alertname": ["HighCPUUsage", "NginxDown", "DiskSpaceWarning", "MemoryLeak", "DatabaseSlow"][i],
                "severity": "critical" if i < 2 else "warning",
                "instance": f"server-{i+1:02d}",
                "job": "node-exporter"
            },
            annotations={
                "summary": f"Test alert {i+1}",
                "description": f"This is a test alert for integration testing"
            },
            analyzed=False
        )
        alerts.append(alert)
        session.add(alert)
    
    # Create 3 resolved alerts
    for i in range(5, 8):
        alert = Alert(
            id=str(uuid.uuid4()),
            fingerprint=f"test-fp-{uuid.uuid4().hex[:16]}",
            alert_name="HighCPUUsage",
            severity="critical",
            instance=f"server-{i+1:02d}",
            job="node-exporter",
            status="resolved",
            summary=f"Resolved alert {i+1}",
            description=f"This alert was resolved",
            starts_at=datetime.utcnow() - timedelta(hours=1),
            ends_at=datetime.utcnow() - timedelta(minutes=30),
            labels={
                "alertname": "HighCPUUsage",
                "severity": "critical",
                "instance": f"server-{i+1:02d}",
                "job": "node-exporter"
            },
            annotations={
                "summary": f"Resolved alert {i+1}",
                "description": f"This alert was resolved"
            },
            analyzed=True
        )
        alerts.append(alert)
        session.add(alert)
    
    session.commit()
    print(f"Created {len(alerts)} sample alerts")


def seed_server_credentials(session):
    """Create test server credentials."""
    print("Creating server credentials...")
    
    servers = [
        ServerCredential(
            id=str(uuid.uuid4()),
            name="Test Web Server",
            hostname="web-server-01.test.local",
            port=22,
            username="ubuntu",
            os_type="linux",
            protocol="ssh",
            auth_type="key",
            environment="test",
            is_active=True
        ),
        ServerCredential(
            id=str(uuid.uuid4()),
            name="Test DB Server",
            hostname="db-server-01.test.local",
            port=22,
            username="postgres",
            os_type="linux",
            protocol="ssh",
            auth_type="key",
            environment="test",
            is_active=True
        ),
    ]
    
    for server in servers:
        session.add(server)
    
    session.commit()
    print(f"Created {len(servers)} server credentials")


def main():
    """Main function to seed the database."""
    print("=" * 60)
    print("Test Database Seeding Script")
    print("=" * 60)
    
    # Get database URL
    db_url = get_test_database_url()
    print(f"\nDatabase URL: {db_url}")
    
    # Create engine and session
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        # Create tables
        print("\nCreating database tables...")
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully")
        
        # Seed data
        print("\n" + "=" * 60)
        print("Seeding Data")
        print("=" * 60)
        
        seed_users(session)
        seed_llm_providers(session)
        seed_rules(session)
        seed_runbooks(session)
        seed_alerts(session)
        seed_server_credentials(session)
        
        print("\n" + "=" * 60)
        print("Database seeded successfully!")
        print("=" * 60)
        
        print("\nTest Credentials:")
        print("  Username: admin, engineer, operator")
        print("  Password: Passw0rd")
        
    except Exception as e:
        print(f"\nError seeding database: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
