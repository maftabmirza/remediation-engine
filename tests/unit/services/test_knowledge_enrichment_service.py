"""
Unit tests for app/services/knowledge_enrichment_service.py
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from uuid import uuid4

from app.services.knowledge_enrichment_service import KnowledgeEnrichmentService, _MAX_CHARS


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_alert(
    *,
    alert_id=None,
    alert_name="HighCPUUsage",
    embedding=None,
    app_id=None,
    status="firing",
    ai_analysis=None,
):
    alert = MagicMock()
    alert.id = alert_id or uuid4()
    alert.alert_name = alert_name
    alert.embedding = embedding
    alert.app_id = app_id
    alert.status = status
    alert.ai_analysis = ai_analysis
    return alert


def _make_db(query_returns=None):
    """Return a minimal mock db session."""
    db = MagicMock()
    return db


# ---------------------------------------------------------------------------
# Happy path: chunks found via text search
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_get_context_text_search_returns_formatted_context():
    """Happy path: when alert has no embedding, ILIKE text search returns chunks."""
    alert = _make_alert(alert_name="HighCPUUsage", embedding=None, app_id=None)

    chunk = {"content": "High CPU usage is caused by runaway processes.", "similarity": 0.5}

    db = MagicMock()
    svc = KnowledgeEnrichmentService(db)

    with patch.object(svc, "_text_search", return_value=[chunk]), \
         patch.object(svc, "_fetch_image_descriptions", return_value=""), \
         patch.object(svc, "_fetch_resolved_alerts", return_value=""):
        result = svc.get_context_for_alert(alert)

    assert "High CPU usage is caused by runaway processes." in result
    assert "Knowledge Base Sections" in result


@pytest.mark.unit
def test_get_context_vector_search_returns_formatted_context():
    """Happy path: when alert has an embedding, vector search returns results."""
    alert = _make_alert(embedding=[0.1] * 1536, app_id=uuid4())

    db = MagicMock()
    row = MagicMock()
    row.content = "Architecture overview: 3-tier web application."
    row.similarity = 0.85
    db.execute.return_value.fetchall.return_value = [row]

    svc = KnowledgeEnrichmentService(db)

    with patch.object(svc, "_fetch_image_descriptions", return_value="[Arch Diagram] Overview"), \
         patch.object(svc, "_fetch_resolved_alerts", return_value=""):
        result = svc.get_context_for_alert(alert)

    assert "Architecture overview" in result
    assert "Knowledge Base Sections" in result


# ---------------------------------------------------------------------------
# No embedding: graceful fallback
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_no_embedding_falls_back_to_text_search_gracefully():
    """Alert without embedding falls back to text search; empty result returns ''."""
    alert = _make_alert(embedding=None, app_id=None)

    db = MagicMock()
    # Text search returns nothing
    db.query.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = []

    svc = KnowledgeEnrichmentService(db)

    with patch.object(svc, "_fetch_image_descriptions", return_value=""), \
         patch.object(svc, "_fetch_resolved_alerts", return_value=""):
        result = svc.get_context_for_alert(alert)

    assert result == ""


# ---------------------------------------------------------------------------
# No matching application: returns empty string
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_no_matching_application_returns_empty():
    """When app_id is None and no text matches, service returns empty string."""
    alert = _make_alert(embedding=None, app_id=None)

    db = MagicMock()
    db.query.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = []

    svc = KnowledgeEnrichmentService(db)
    result = svc.get_context_for_alert(alert)

    assert result == ""


# ---------------------------------------------------------------------------
# Empty knowledge base: returns empty string
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_empty_knowledge_base_returns_empty():
    """When the knowledge base has no chunks, service returns empty string."""
    alert = _make_alert(embedding=[0.1] * 1536, app_id=uuid4())

    db = MagicMock()
    # Vector search returns no rows
    db.execute.return_value.fetchall.return_value = []

    svc = KnowledgeEnrichmentService(db)

    with patch.object(svc, "_fetch_image_descriptions", return_value=""), \
         patch.object(svc, "_fetch_resolved_alerts", return_value=""):
        result = svc.get_context_for_alert(alert)

    assert result == ""


# ---------------------------------------------------------------------------
# Max token truncation
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_truncation_keeps_output_within_token_budget():
    """Output should be truncated when the combined context exceeds _MAX_CHARS."""
    # Build a single chunk with content much larger than _MAX_CHARS
    large_content = "X" * (_MAX_CHARS + 500)
    chunk = {"content": large_content, "similarity": 0.5}

    alert = _make_alert(embedding=None, app_id=None)

    db = MagicMock()
    svc = KnowledgeEnrichmentService(db)

    with patch.object(svc, "_text_search", return_value=[chunk]), \
         patch.object(svc, "_fetch_image_descriptions", return_value=""), \
         patch.object(svc, "_fetch_resolved_alerts", return_value=""):
        result = svc.get_context_for_alert(alert)

    # Truncated marker must be present
    assert "[Context truncated for length]" in result
    # Result length should be close to _MAX_CHARS (allow a small buffer for header text)
    assert len(result) <= _MAX_CHARS + 200


# ---------------------------------------------------------------------------
# Successfully resolved alerts included as RAG source
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_resolved_alerts_included_when_embedding_present():
    """Past resolved alerts are included in the context when the alert has an embedding."""
    alert = _make_alert(embedding=[0.1] * 1536, app_id=uuid4())

    db = MagicMock()
    # First execute call is for vector chunk search (returns empty)
    # Second execute call is for resolved alert search
    resolved_row = MagicMock()
    resolved_row.alert_name = "PastHighCPU"
    resolved_row.ai_analysis = "Restarted the node exporter service."
    resolved_row.similarity = 0.92

    # Vector chunk search = no chunks; resolved alert search = one row
    db.execute.return_value.fetchall.side_effect = [[], [resolved_row]]

    svc = KnowledgeEnrichmentService(db)

    with patch.object(svc, "_fetch_image_descriptions", return_value=""), \
         patch.object(svc, "_fetch_postmortems", return_value=""):
        result = svc.get_context_for_alert(alert)

    assert "PastHighCPU" in result
    assert "Restarted the node exporter service." in result


# ---------------------------------------------------------------------------
# get_context_for_alert_id: alert not found
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_get_context_for_alert_id_not_found_returns_empty():
    """Returns empty string when the alert_id does not exist in the DB."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    svc = KnowledgeEnrichmentService(db)
    result = svc.get_context_for_alert_id(uuid4())

    assert result == ""


# ---------------------------------------------------------------------------
# Image descriptions included
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_image_descriptions_included_for_app():
    """Architecture image descriptions are included when app_id is set."""
    app_id = uuid4()
    alert = _make_alert(embedding=None, app_id=app_id)

    db = MagicMock()
    # Text chunk search returns nothing
    db.query.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = []

    img = MagicMock()
    img.title = "System Architecture"
    img.ai_description = "A 3-tier architecture with load balancer, web server, and DB."

    svc = KnowledgeEnrichmentService(db)

    with patch.object(svc, "_text_search", return_value=[]), \
         patch.object(svc, "_fetch_image_descriptions", return_value="[System Architecture] A 3-tier architecture"), \
         patch.object(svc, "_fetch_resolved_alerts", return_value=""):
        result = svc.get_context_for_alert(alert)

    assert "Architecture Context" in result
    assert "System Architecture" in result


# ---------------------------------------------------------------------------
# Exception resilience
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_service_returns_empty_on_db_exception():
    """Service swallows exceptions and returns empty string rather than raising."""
    alert = _make_alert(embedding=None, app_id=None)

    db = MagicMock()
    db.query.side_effect = Exception("DB connection lost")

    svc = KnowledgeEnrichmentService(db)
    result = svc.get_context_for_alert(alert)

    assert result == ""
