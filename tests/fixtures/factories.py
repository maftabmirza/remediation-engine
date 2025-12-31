"""
Factory Boy factories for generating test data.

This module uses Factory Boy to generate realistic test data for models.
"""
import factory
from factory import fuzzy
from datetime import datetime, timedelta
import uuid

from app.models import (
    User, Alert, AlertCluster, AutoAnalyzeRule as Rule,
    LLMProvider, ServerCredential
)
from app.models_remediation import Runbook, RunbookStep
from app.models_knowledge import DesignDocument
from app.services.auth_service import get_password_hash


class UserFactory(factory.Factory):
    """Factory for User model."""
    
    class Meta:
        model = User
    
    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    username = factory.Sequence(lambda n: f"user{n}")
    password_hash = factory.LazyFunction(lambda: get_password_hash("TestPassword123!"))
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@test.com")
    role = fuzzy.FuzzyChoice(["admin", "engineer", "operator", "viewer"])
    is_active = True
    created_at = factory.LazyFunction(datetime.utcnow)


class AlertFactory(factory.Factory):
    """Factory for Alert model."""
    
    class Meta:
        model = Alert
    
    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    fingerprint = factory.Sequence(lambda n: f"fingerprint_{n}_{uuid.uuid4().hex[:8]}")
    timestamp = factory.LazyFunction(lambda: datetime.utcnow())
    alert_name = fuzzy.FuzzyChoice([
        "NginxDown", "HighCPUUsage", "HighMemoryUsage",
        "DiskSpaceLow", "ServiceUnavailable", "DatabaseConnectionFailed"
    ])
    severity = fuzzy.FuzzyChoice(["critical", "warning", "info"])
    instance = fuzzy.FuzzyChoice([
        "web-server-01", "db-server-01", "proxy-server-01",
        "app-server-01", "cache-server-01"
    ])
    job = fuzzy.FuzzyChoice([
        "node-exporter", "nginx-exporter", "postgres-exporter",
        "application-metrics"
    ])
    status = fuzzy.FuzzyChoice(["firing", "resolved"])
    labels_json = factory.LazyAttribute(lambda obj: {
        "alertname": obj.alert_name,
        "severity": obj.severity,
        "instance": obj.instance,
        "job": obj.job
    })
    annotations_json = factory.LazyAttribute(lambda obj: {
        "summary": f"{obj.alert_name} on {obj.instance}",
        "description": f"Alert {obj.alert_name} triggered on {obj.instance}"
    })
    analyzed = False


class RuleFactory(factory.Factory):
    """Factory for Rule model."""
    
    class Meta:
        model = Rule
    
    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name = factory.Sequence(lambda n: f"Rule {n}")
    description = factory.Faker('sentence')
    priority = fuzzy.FuzzyInteger(1, 100)
    alert_name_pattern = "*"
    severity_pattern = "*"
    instance_pattern = "*"
    job_pattern = "*"
    action = fuzzy.FuzzyChoice(["auto_analyze", "trigger_runbook", "notify", "ignore"])
    enabled = True
    created_at = factory.LazyFunction(datetime.utcnow)


class RunbookStepFactory(factory.Factory):
    """Factory for RunbookStep model."""
    
    class Meta:
        model = RunbookStep
    
    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name = factory.Sequence(lambda n: f"Step {n}")
    step_order = factory.Sequence(lambda n: n + 1)  # Start at 1
    step_type = "command"
    command_linux = fuzzy.FuzzyChoice([
        "systemctl status nginx",
        "sudo systemctl restart nginx",
        "df -h",
        "free -m"
    ])
    target_os = "linux"
    timeout_seconds = 30
    continue_on_fail = False


class RunbookFactory(factory.Factory):
    """Factory for Runbook model."""
    
    class Meta:
        model = Runbook
    
    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name = factory.Sequence(lambda n: f"Runbook {n}")
    description = factory.Faker('paragraph')
    category = fuzzy.FuzzyChoice([
        "service_recovery", "database_maintenance",
        "security_response", "capacity_management"
    ])
    enabled = True
    auto_execute = False
    approval_required = True
    max_executions_per_hour = 5
    cooldown_minutes = 10
    version = 1
    
    @factory.post_generation
    def steps(self, create, extracted, **kwargs):
        """Add steps to the runbook after creation."""
        if not create:
            return
        
        if extracted:
            # Use provided steps
            for step in extracted:
                step.runbook_id = self.id
        else:
            # Create 3 default steps
            for i in range(1, 4):
                step = RunbookStepFactory(
                    runbook_id=self.id,
                    step_order=i,
                    name=f"Step {i}"
                )


class LLMProviderFactory(factory.Factory):
    """Factory for LLMProvider model."""
    
    class Meta:
        model = LLMProvider
    
    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name = factory.Sequence(lambda n: f"LLM Provider {n}")
    provider_type = fuzzy.FuzzyChoice(["anthropic", "openai", "gemini"])
    model_id = factory.LazyAttribute(lambda obj: {
        "anthropic": "claude-3-sonnet-20240229",
        "openai": "gpt-4",
        "gemini": "gemini-pro"
    }[obj.provider_type])
    is_default = False
    is_enabled = True
    config_json = factory.LazyFunction(lambda: {
        "temperature": 0.3,
        "max_tokens": 2000
    })
    created_at = factory.LazyFunction(datetime.utcnow)


class ServerCredentialFactory(factory.Factory):
    """Factory for ServerCredential model."""
    
    class Meta:
        model = ServerCredential
    
    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name = factory.Sequence(lambda n: f"Server {n}")
    hostname = factory.LazyAttribute(lambda obj: f"{obj.name.lower().replace(' ', '-')}.example.com")
    port = 22
    username = "ubuntu"
    os_type = fuzzy.FuzzyChoice(["linux", "windows"])
    protocol = fuzzy.FuzzyChoice(["ssh", "winrm"])
    auth_type = fuzzy.FuzzyChoice(["key", "password"])
    environment = fuzzy.FuzzyChoice(["production", "staging", "development"])
    is_active = True
    created_at = factory.LazyFunction(datetime.utcnow)


class DesignDocumentFactory(factory.Factory):
    """Factory for DesignDocument (Knowledge Base) model."""
    
    class Meta:
        model = DesignDocument
    
    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    title = factory.Faker('sentence')
    content = factory.Faker('text', max_nb_chars=1000)
    content_type = fuzzy.FuzzyChoice(["markdown", "pdf", "text"])
    category = fuzzy.FuzzyChoice([
        "architecture", "runbook", "troubleshooting",
        "sop", "design", "configuration"
    ])
    tags = factory.LazyFunction(lambda: ["test", "documentation"])
    status = "active"
    version = 1
    created_at = factory.LazyFunction(datetime.utcnow)


# Batch creation helpers

def create_test_alerts(count=10, **kwargs):
    """Create multiple test alerts."""
    return [AlertFactory(**kwargs) for _ in range(count)]


def create_test_users(count=5, **kwargs):
    """Create multiple test users."""
    return [UserFactory(**kwargs) for _ in range(count)]


def create_test_runbooks(count=3, **kwargs):
    """Create multiple test runbooks with steps."""
    return [RunbookFactory(**kwargs) for _ in range(count)]
