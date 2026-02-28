import pytest
from app.services.revive.mode_detector import ReviveModeDetector, ModeDetectionResult

def test_detect_explicit_mode():
    detector = ReviveModeDetector()
    result = detector.detect("list dashboards", explicit_mode="grafana")
    assert result.mode == "grafana"
    assert result.confidence == 1.0
    assert result.detected_intent == "explicit_selection"

def test_detect_grafana_keywords():
    detector = ReviveModeDetector()
    result = detector.detect("Show me the prometheus metrics for cpu")
    assert result.mode == "grafana"
    assert result.confidence == 0.8
    assert result.detected_intent == "grafana_interaction"

def test_detect_aiops_keywords():
    detector = ReviveModeDetector()
    result = detector.detect("execute runbook for server restart")
    assert result.mode == "aiops"
    assert result.confidence == 0.8
    assert result.detected_intent == "aiops_interaction"

def test_detect_ambiguous():
    detector = ReviveModeDetector()
    result = detector.detect("hello world")
    assert result.mode == "ambiguous"
    assert result.confidence == 0.0

def test_detect_context_boost():
    detector = ReviveModeDetector()
    # "rule" is in AIOps keywords (e.g. auto-analyze rule), but "alert rule" is Grafana.
    # Let's test context boosting.
    # "permission" is AIOps.
    result = detector.detect("check permissions", current_page="/admin/users")
    assert result.mode == "aiops"
    
    # "dashboard" is Grafana.
    result = detector.detect("dashboard view", current_page="/grafana/dashboards")
    assert result.mode == "grafana"

@pytest.mark.asyncio
async def test_detect_with_llm_fallback():
    detector = ReviveModeDetector()
    # Currently just calls detect(), so we test that behavior
    result = await detector.detect_with_llm("show dashboards")
    assert result.mode == "grafana"
