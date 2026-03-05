"""
Unit tests for RagAlertDiagnosisService (Feature B7).
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models import Alert
from app.schemas import RAGDiagnosisContext, RAGSimilarIncident, RAGKnowledgeChunk
from app.services.rag_alert_diagnosis_service import RagAlertDiagnosisService


def _utc_now():
    return datetime.now(timezone.utc)


def _make_alert(embedding=None, ai_analysis=None):
    """Build a minimal Alert object for testing."""
    alert = MagicMock(spec=Alert)
    alert.id = uuid4()
    alert.alert_name = "HighCPUUsage"
    alert.severity = "critical"
    alert.instance = "web-01"
    alert.job = "node-exporter"
    alert.timestamp = _utc_now()
    alert.annotations_json = {
        "summary": "CPU over 90%",
        "description": "Node is overloaded",
    }
    alert.embedding = embedding
    alert.ai_analysis = ai_analysis
    return alert


def _make_similar_incident(**kwargs):
    defaults = dict(
        alert_id=uuid4(),
        alert_name="HighCPUUsage",
        similarity_score=0.92,
        occurred_at=_utc_now(),
        severity="critical",
        instance="web-02",
    )
    defaults.update(kwargs)
    return MagicMock(**defaults)


@pytest.mark.unit
class TestGetContext:
    """Tests for RagAlertDiagnosisService.get_context()."""

    def _make_service(self, db=None):
        db = db or MagicMock()
        return RagAlertDiagnosisService(db)

    def test_returns_empty_context_when_no_embedding(self):
        """Happy path: alert without embedding returns empty similar_incidents."""
        alert = _make_alert(embedding=None)
        svc = self._make_service()

        with patch.object(svc.embedding_service, "is_configured", return_value=False):
            ctx = svc.get_context(alert)

        assert isinstance(ctx, RAGDiagnosisContext)
        assert ctx.similar_incidents == []
        assert ctx.knowledge_chunks == []

    def test_returns_similar_incidents_when_embedding_present(self):
        """Happy path: alert with embedding returns similar incidents."""
        alert = _make_alert(embedding=[0.1] * 1536)
        similar_incident = _make_similar_incident()

        mock_response = MagicMock()
        mock_response.similar_incidents = [similar_incident]

        db = MagicMock()
        # Mocking the similar alert lookup in DB
        similar_alert = MagicMock()
        similar_alert.ai_analysis = "Previous analysis text"
        db.query.return_value.filter.return_value.first.return_value = similar_alert

        svc = RagAlertDiagnosisService(db)

        with (
            patch.object(svc.similarity_service, "find_similar_alerts", return_value=mock_response),
            patch.object(svc.embedding_service, "is_configured", return_value=False),
        ):
            ctx = svc.get_context(alert, max_similar_incidents=3)

        assert len(ctx.similar_incidents) == 1
        inc = ctx.similar_incidents[0]
        assert isinstance(inc, RAGSimilarIncident)
        assert inc.similarity_score == similar_incident.similarity_score

    def test_returns_knowledge_chunks_when_embedding_configured(self):
        """Happy path: configured embedding returns knowledge chunks."""
        alert = _make_alert(embedding=None)

        chunk = MagicMock()
        chunk.id = uuid4()
        chunk.content = "This is a relevant SOP for CPU alerts."
        chunk.source_type = "document"
        chunk.source_id = uuid4()

        doc = MagicMock()
        doc.title = "CPU Alert Runbook"
        doc.doc_type = "document"

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = doc

        svc = RagAlertDiagnosisService(db)

        rows = [(chunk, 0.85)]
        with (
            patch.object(svc.embedding_service, "is_configured", return_value=True),
            patch.object(svc.embedding_service, "generate_embedding", return_value=[0.1] * 1536),
            patch.object(svc.similarity_service, "find_similar_alerts", return_value=None),
            patch(
                "app.services.rag_alert_diagnosis_service."
                "RagAlertDiagnosisService._get_knowledge_chunks",
                return_value=[
                    RAGKnowledgeChunk(
                        chunk_id=chunk.id,
                        document_title=doc.title,
                        content_excerpt=chunk.content,
                        similarity_score=0.85,
                        doc_type=doc.doc_type,
                    )
                ],
            ),
        ):
            ctx = svc.get_context(alert)

        assert len(ctx.knowledge_chunks) == 1
        kc = ctx.knowledge_chunks[0]
        assert kc.document_title == "CPU Alert Runbook"
        assert kc.similarity_score == 0.85

    def test_context_text_is_empty_when_no_results(self):
        """Edge case: context_text is empty string when no RAG results."""
        alert = _make_alert(embedding=None)
        svc = self._make_service()

        with patch.object(svc.embedding_service, "is_configured", return_value=False):
            ctx = svc.get_context(alert)

        assert ctx.context_text == ""

    def test_context_text_includes_section_headers_when_results_present(self):
        """Happy path: context_text includes expected section headers."""
        similar = RAGSimilarIncident(
            alert_id=uuid4(),
            alert_name="HighCPUUsage",
            similarity_score=0.9,
            occurred_at=_utc_now(),
            severity="critical",
            instance="web-01",
        )
        ctx = RAGDiagnosisContext(
            similar_incidents=[similar],
            knowledge_chunks=[],
            context_text="",  # will be overwritten below
        )
        # Build context text directly
        svc = self._make_service()
        text = svc._format_context_text([similar], [])
        assert "## Retrieved Context (RAG)" in text
        assert "Similar Historical Incidents" in text
        assert "HighCPUUsage" in text


@pytest.mark.unit
class TestBuildQueryText:
    """Tests for RagAlertDiagnosisService._build_query_text()."""

    def test_query_includes_alert_name(self):
        """Happy path: query text includes alert name."""
        alert = _make_alert()
        text = RagAlertDiagnosisService._build_query_text(alert)
        assert "HighCPUUsage" in text

    def test_query_includes_severity(self):
        """Happy path: query text includes severity."""
        alert = _make_alert()
        text = RagAlertDiagnosisService._build_query_text(alert)
        assert "critical" in text

    def test_query_includes_annotations(self):
        """Edge case: query text includes summary annotation."""
        alert = _make_alert()
        text = RagAlertDiagnosisService._build_query_text(alert)
        assert "CPU over 90%" in text

    def test_query_handles_missing_annotations(self):
        """Edge case: missing annotations_json does not raise."""
        alert = _make_alert()
        alert.annotations_json = None
        text = RagAlertDiagnosisService._build_query_text(alert)
        assert "HighCPUUsage" in text  # should still include at least the name


@pytest.mark.unit
class TestFormatContextText:
    """Tests for RagAlertDiagnosisService._format_context_text()."""

    def test_empty_inputs_return_empty_string(self):
        """Edge case: empty inputs produce an empty context string."""
        text = RagAlertDiagnosisService._format_context_text([], [])
        assert text == ""

    def test_similar_incidents_section_rendered(self):
        """Happy path: similar incidents are formatted into the context."""
        similar = RAGSimilarIncident(
            alert_id=uuid4(),
            alert_name="DiskSpaceLow",
            similarity_score=0.88,
            occurred_at=_utc_now(),
            severity="warning",
            instance="db-01",
        )
        text = RagAlertDiagnosisService._format_context_text([similar], [])
        assert "DiskSpaceLow" in text
        assert "88%" in text

    def test_knowledge_chunks_section_rendered(self):
        """Happy path: knowledge chunks are formatted into the context."""
        chunk = RAGKnowledgeChunk(
            chunk_id=uuid4(),
            document_title="Database Recovery SOP",
            content_excerpt="Step 1: Check disk usage with df -h",
            similarity_score=0.75,
            doc_type="document",
        )
        text = RagAlertDiagnosisService._format_context_text([], [chunk])
        assert "Database Recovery SOP" in text
        assert "df -h" in text

    def test_ai_analysis_excerpt_included(self):
        """Edge case: previous AI analysis excerpt is included when present."""
        similar = RAGSimilarIncident(
            alert_id=uuid4(),
            alert_name="HighMem",
            similarity_score=0.80,
            occurred_at=_utc_now(),
            severity="critical",
            instance="host-1",
            ai_analysis_excerpt="Root cause: memory leak in service X.",
        )
        text = RagAlertDiagnosisService._format_context_text([similar], [])
        assert "memory leak in service X" in text


@pytest.mark.unit
class TestBuildRagPromptSection:
    """Tests for RagAlertDiagnosisService.build_rag_prompt_section()."""

    def test_returns_context_text_from_context(self):
        """Happy path: returns the pre-built context_text."""
        ctx = RAGDiagnosisContext(
            similar_incidents=[],
            knowledge_chunks=[],
            context_text="## My RAG Context\nSome details here.",
        )
        svc = RagAlertDiagnosisService(MagicMock())
        result = svc.build_rag_prompt_section(ctx)
        assert result == ctx.context_text

    def test_returns_empty_string_for_empty_context(self):
        """Edge case: empty context yields empty string."""
        ctx = RAGDiagnosisContext(
            similar_incidents=[],
            knowledge_chunks=[],
            context_text="",
        )
        svc = RagAlertDiagnosisService(MagicMock())
        assert svc.build_rag_prompt_section(ctx) == ""
