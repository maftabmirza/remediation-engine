"""Unit tests for deploy verification behavior."""

from pathlib import Path

import pytest

from scripts.verify_deploy import (
    CheckResult,
    check_postmortems_endpoint,
    evaluate_results,
    load_env_file,
)


@pytest.mark.unit
def test_load_env_file_parses_comments_quotes_and_values(tmp_path: Path) -> None:
    """The dotenv parser ignores comments and strips surrounding quotes."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\nADMIN_USERNAME='admin'\nADMIN_PASSWORD=\"secret\"\nDEBUG=false\n",
        encoding="utf-8",
    )

    values = load_env_file(env_file)

    assert values["ADMIN_USERNAME"] == "admin"
    assert values["ADMIN_PASSWORD"] == "secret"
    assert values["DEBUG"] == "false"


@pytest.mark.unit
def test_evaluate_results_warn_mode_does_not_block_on_failures(capsys: pytest.CaptureFixture[str]) -> None:
    """Warn mode reports failures but returns success for the deploy script."""
    exit_code = evaluate_results([CheckResult("atlas", "fail", "status failed")], "warn")

    assert exit_code == 0
    assert "continuing because mode=warn" in capsys.readouterr().out


@pytest.mark.unit
def test_evaluate_results_strict_mode_blocks_on_failures(capsys: pytest.CaptureFixture[str]) -> None:
    """Strict mode fails the deploy when any verification check fails."""
    exit_code = evaluate_results([CheckResult("postmortems", "fail", "endpoint 500")], "strict")

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "strict mode" in captured.err


@pytest.mark.unit
def test_check_postmortems_endpoint_reports_500_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Authenticated postmortem smoke test fails when the endpoint returns 500."""

    responses = iter(
        [
            (200, '{"access_token": "abc"}'),
            (500, '{"detail": "boom"}'),
        ]
    )

    def fake_request(*args, **kwargs):
        return next(responses)

    monkeypatch.setattr("scripts.verify_deploy.http_json_request", fake_request)

    result = check_postmortems_endpoint("http://localhost:8080", "admin", "secret")

    assert result.status == "fail"
    assert "500" in result.detail


@pytest.mark.unit
def test_check_postmortems_endpoint_warns_without_password() -> None:
    """If admin credentials are unavailable, the smoke test is skipped with a warning."""
    result = check_postmortems_endpoint("http://localhost:8080", "admin", None)

    assert result.status == "warn"
    assert "ADMIN_PASSWORD" in result.detail