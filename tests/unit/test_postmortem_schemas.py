"""Unit tests for postmortem request/response schemas."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas_postmortem import PostmortemReportUpdate


@pytest.mark.unit
def test_postmortem_report_update_accepts_editable_fields() -> None:
    """Editable fields are accepted and preserved."""
    payload = PostmortemReportUpdate(
        title="Revised postmortem",
        impact_summary="Updated impact summary",
        incident_start=datetime(2026, 3, 7, 10, 0, tzinfo=timezone.utc),
    )

    assert payload.title == "Revised postmortem"
    assert payload.impact_summary == "Updated impact summary"


@pytest.mark.unit
def test_postmortem_report_update_rejects_status_field() -> None:
    """Status changes must use the dedicated publish workflow."""
    with pytest.raises(ValidationError):
        PostmortemReportUpdate(status="published")


@pytest.mark.unit
def test_postmortem_report_update_rejects_unknown_extra_fields() -> None:
    """Unexpected fields are rejected to keep the update contract strict."""
    with pytest.raises(ValidationError):
        PostmortemReportUpdate(title="Valid", unexpected_field="nope")