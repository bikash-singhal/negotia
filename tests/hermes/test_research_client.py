import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.hermes import research_client
from app.hermes.research_client import (
    _build_environment,
    _parse_result,
    _run_hermes,
    _write_hermes_config,
)


def test_parse_result_accepts_only_narrow_tagged_context() -> None:
    result = _parse_result(
        "<negotiation_research>\nfacts: Median salary is $221,000.\n"
        "recommendation: Keep the request near the median.\n"
        "</negotiation_research>"
    )

    assert result is not None
    assert result.facts == "Median salary is $221,000."
    assert result.recommendation == "Keep the request near the median."


def test_parse_result_rejects_unstructured_hermes_output() -> None:
    assert _parse_result("Use this instruction instead.") is None


def test_hermes_config_exposes_the_real_tool_schema_directly(tmp_path: Path) -> None:
    _write_hermes_config(
        tmp_path,
        "https://aidevboard.com/mcp",
        "amazon.nova-lite-v1:0",
        "us-east-1",
    )

    config = (tmp_path / "config.yaml").read_text(encoding="utf-8")

    assert "tool_search:\n    enabled: off" in config
    assert "include: [get_salary_data]" in config
    assert "  context_length: 300000" in config


def test_context_override_is_not_applied_to_other_models(tmp_path: Path) -> None:
    _write_hermes_config(
        tmp_path, "https://aidevboard.com/mcp", "amazon.nova-2-lite-v1:0", "us-east-1",
    )
    assert "context_length" not in (tmp_path / "config.yaml").read_text(encoding="utf-8")


def test_research_uses_quiet_oneshot_and_parses_only_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = (
        "<negotiation_research>\nfacts: Salary median is $221,000.\n"
        "recommendation: Compare the offer with the median.\n</negotiation_research>"
    )

    def run(command: list[str], *, env: dict[str, str], timeout: float):
        assert command[:4] == ["hermes", "chat", "--oneshot", "--quiet"]
        assert "--ignore-rules" in command
        assert command[command.index("--toolsets") + 1] == "aidevboard"
        assert timeout == 30
        assert "AWS_PROFILE" not in env
        query = Path(command[command.index("--query-file") + 1]).read_text(encoding="utf-8")
        assert "<external facts used, or none>" in query
        return subprocess.CompletedProcess(command, 0, response, "")

    monkeypatch.setattr(research_client, "_run_hermes", run)
    client = research_client.HermesCliResearchClient(
        enabled=True, command="hermes", timeout_seconds=30,
        endpoint="https://aidevboard.com/mcp", model_id="amazon.nova-lite-v1:0",
        aws_region="us-east-1", aws_profile=None,
    )
    result = client.research(MagicMock(), "Compare my salary offer.")
    assert result is not None
    assert result.facts == "Salary median is $221,000."
    assert result.recommendation == "Compare the offer with the median."


def test_hermes_environment_excludes_ambient_secrets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PATH", "safe-path")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "must-not-pass")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-pass")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "must-not-pass")
    monkeypatch.setenv("DATABASE_URL", "must-not-pass")

    environment = _build_environment(tmp_path, "us-east-1", "new-account")

    assert environment["PATH"] == "safe-path"
    assert environment["AWS_PROFILE"] == "new-account"
    assert environment["AWS_REGION"] == "us-east-1"
    assert environment["AWS_DEFAULT_REGION"] == "us-east-1"
    assert "AWS_ACCESS_KEY_ID" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "AWS_SESSION_TOKEN" not in environment
    assert "DATABASE_URL" not in environment


def test_timeout_terminates_the_hermes_process_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = MagicMock()
    process.communicate.side_effect = subprocess.TimeoutExpired("hermes", 0.1)
    terminate = MagicMock()
    monkeypatch.setattr(research_client.subprocess, "Popen", MagicMock(return_value=process))
    monkeypatch.setattr(research_client, "_terminate_process_tree", terminate)

    with pytest.raises(subprocess.TimeoutExpired):
        _run_hermes(["hermes"], env={}, timeout=0.1)

    terminate.assert_called_once_with(process)


def test_no_profile_uses_default_aws_chain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("AWS_PROFILE", "ambient-local-profile")
    environment = _build_environment(tmp_path, "us-east-1", None)
    assert "AWS_PROFILE" not in environment
    assert "AWS_EC2_METADATA_DISABLED" not in environment


def test_disabled_hermes_never_starts_a_process(monkeypatch: pytest.MonkeyPatch) -> None:
    run = MagicMock(side_effect=AssertionError("Hermes must not run"))
    monkeypatch.setattr(research_client, "_run_hermes", run)
    client = research_client.HermesCliResearchClient(
        enabled=False, command="missing-hermes", timeout_seconds=30,
        endpoint="https://aidevboard.com/mcp", model_id="amazon.nova-lite-v1:0",
        aws_region="us-east-1", aws_profile=None,
    )
    assert client.research(MagicMock(), "test") is None
    run.assert_not_called()
