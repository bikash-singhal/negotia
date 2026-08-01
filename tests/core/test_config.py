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


def test_default_access_token_expiration_is_thirty_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)

    settings = Settings()

    assert settings.access_token_expire_minutes == 30


def test_cors_origins_default_to_local_vite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    settings = Settings()

    assert settings.cors_origins == ["http://localhost:5173"]


def test_cors_origins_can_be_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS",
        '["https://app.example.com","http://localhost:5173"]',
    )

    settings = Settings()

    assert settings.cors_origins == [
        "https://app.example.com",
        "http://localhost:5173",
    ]


def test_access_token_expiration_can_be_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "45")

    settings = Settings()

    assert settings.access_token_expire_minutes == 45


def test_jwt_secret_is_stored_as_a_secret_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_secret = "configured-test-secret-with-32-characters"
    monkeypatch.setenv("JWT_SECRET_KEY", configured_secret)

    settings = Settings()

    assert settings.jwt_secret_key.get_secret_value() == configured_secret
    assert configured_secret not in repr(settings)


def test_jwt_secret_rejects_short_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "too-short")

    with pytest.raises(ValidationError):
        Settings()
