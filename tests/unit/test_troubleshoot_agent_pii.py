import asyncio
from types import SimpleNamespace
import types
import sys
import pytest


pytest.importorskip("sqlalchemy")
pytest.importorskip("litellm")


class _StubToolRegistry:
    def get_anthropic_tools(self):
        return []

    def get_openai_tools(self):
        return []


class _StubDetection:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return dict(self._payload)


class _StubDetectionResponse:
    def __init__(self, detections):
        self.detections = detections
        self.detection_count = len(detections)


class _StubRedactionResponse:
    def __init__(self, redacted_text: str):
        self.redacted_text = redacted_text


class _StubPIIService:
    def __init__(self):
        self.logged = []

    async def detect(self, text: str, source_type: str, source_id: str):
        if "@" in text:
            return _StubDetectionResponse([
                _StubDetection({
                    "entity_type": "EMAIL_ADDRESS",
                    "engine": "presidio",
                    "confidence": 0.95,
                })
            ])
        return _StubDetectionResponse([])

    async def log_detection(self, detection, source_type: str, source_id: str):
        self.logged.append((detection, source_type, source_id))

    async def redact(self, text: str, redaction_type: str):
        return _StubRedactionResponse(text.replace("test@example.com", "[EMAIL_ADDRESS]"))


def test_troubleshoot_agent_redacts_user_input(monkeypatch):
    from app.services.agentic.troubleshoot_native_agent import TroubleshootNativeAgent

    # Inject a stub llm_service module so we don't need optional deps (e.g., litellm)
    # during unit testing.
    import app.services as services_pkg

    stub_pii = _StubPIIService()

    async def _factory():
        return stub_pii

    stub_llm_service = types.ModuleType("app.services.llm_service")
    stub_llm_service._pii_service_factory = _factory
    sys.modules["app.services.llm_service"] = stub_llm_service
    services_pkg.llm_service = stub_llm_service

    provider = SimpleNamespace(id="prov", provider_type="openai", config_json={})
    agent = TroubleshootNativeAgent(
        db=None,
        provider=provider,
        registry_factory=lambda db, alert_id=None: _StubToolRegistry(),
    )

    redacted = asyncio.run(
        agent._scan_and_redact_text(
            "Hello test@example.com",
            source_type="user_input",
            source_id="unit_test",
            context_label="user input",
        )
    )

    assert "test@example.com" not in redacted
    assert "[EMAIL_ADDRESS]" in redacted
    assert len(stub_pii.logged) == 1
