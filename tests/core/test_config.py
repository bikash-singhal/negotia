from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_llm_provider_is_fake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    settings = Settings()

    assert settings.llm_provider == "fake"


def test_llm_provider_can_be_set_to_bedrock_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")

    settings = Settings()

    assert settings.llm_provider == "bedrock"


def test_bedrock_model_id_can_be_overridden_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BEDROCK_MODEL_ID", "custom-model-id")

    settings = Settings()

    assert settings.bedrock_model_id == "custom-model-id"


def test_invalid_llm_provider_fails_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "unsupported")

    with pytest.raises(ValidationError):
        Settings()


def test_unrelated_dotenv_variables_are_ignored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "POSTGRES_DB=negotia\n"
        "POSTGRES_USER=negotia\n"
        "POSTGRES_PASSWORD=local-development-password\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    settings = Settings()

    assert settings.app_name == "Negotia API"
    assert not hasattr(settings, "postgres_password")
