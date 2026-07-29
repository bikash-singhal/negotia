from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.llm.bedrock import BedrockLLMProvider
from app.llm.factory import build_llm_provider
from app.llm.fake import FakeLLMProvider


def test_default_selection_returns_fake_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    settings = Settings()

    provider = build_llm_provider(settings)

    assert isinstance(provider, FakeLLMProvider)


def test_bedrock_selection_returns_bedrock_provider() -> None:
    settings = Settings(
        llm_provider="bedrock",
    )

    with patch(
        "app.llm.bedrock.get_bedrock_runtime_client",
    ) as client_factory:
        provider = build_llm_provider(settings)

    assert isinstance(provider, BedrockLLMProvider)
    client_factory.assert_called_once_with()


def test_bedrock_provider_receives_configured_model_id() -> None:
    settings = Settings(
        llm_provider="bedrock",
        bedrock_model_id="custom-model-id",
    )

    with patch("app.llm.bedrock.get_bedrock_runtime_client"):
        provider = build_llm_provider(settings)

    assert isinstance(provider, BedrockLLMProvider)
    assert provider._model_id == "custom-model-id"


def test_fake_selection_does_not_create_bedrock_client() -> None:
    settings = Settings(
        llm_provider="fake",
    )

    with patch(
        "app.llm.bedrock.get_bedrock_runtime_client",
    ) as client_factory:
        provider = build_llm_provider(settings)

    assert isinstance(provider, FakeLLMProvider)
    client_factory.assert_not_called()


def test_factory_rejects_unsupported_provider() -> None:
    settings = Settings()
    object.__setattr__(settings, "llm_provider", "unsupported")

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        build_llm_provider(settings)
