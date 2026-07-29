from unittest.mock import MagicMock, patch

import pytest

from app.llm.bedrock import BedrockLLMProvider
from app.llm.provider import LLMProvider

MODEL_ID = "example-model-id"
SYSTEM_PROMPT = "You are a negotiation counterpart."
USER_PROMPT = "Can you improve the offer?"
RESPONSE_TEXT = "I can consider a smaller adjustment."


def _bedrock_response() -> dict[str, object]:
    return {
        "output": {
            "message": {
                "content": [
                    {
                        "text": RESPONSE_TEXT,
                    }
                ]
            }
        }
    }


def test_bedrock_provider_satisfies_protocol() -> None:
    assert isinstance(BedrockLLMProvider(MODEL_ID, MagicMock()), LLMProvider)


def test_constructor_uses_injected_client() -> None:
    client = MagicMock()

    provider = BedrockLLMProvider(MODEL_ID, client)

    assert provider._client is client
    assert provider._model_id == MODEL_ID


def test_constructor_uses_client_factory_when_client_is_not_injected() -> None:
    client = MagicMock()

    with patch(
        "app.llm.bedrock.get_bedrock_runtime_client",
        return_value=client,
    ) as client_factory:
        provider = BedrockLLMProvider(MODEL_ID)

    assert provider._client is client
    client_factory.assert_called_once_with()


def test_generate_calls_converse_with_exact_request() -> None:
    client = MagicMock()
    client.converse.return_value = _bedrock_response()
    provider = BedrockLLMProvider(MODEL_ID, client)

    provider.generate(SYSTEM_PROMPT, USER_PROMPT)

    client.converse.assert_called_once_with(
        modelId=MODEL_ID,
        system=[
            {
                "text": SYSTEM_PROMPT,
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": USER_PROMPT,
                    }
                ],
            }
        ],
    )


def test_generate_returns_extracted_response_text() -> None:
    client = MagicMock()
    client.converse.return_value = _bedrock_response()
    provider = BedrockLLMProvider(MODEL_ID, client)

    response = provider.generate(SYSTEM_PROMPT, USER_PROMPT)

    assert response == RESPONSE_TEXT


def test_generate_propagates_bedrock_exception() -> None:
    expected_error = RuntimeError("Bedrock request failed")
    client = MagicMock()
    client.converse.side_effect = expected_error
    provider = BedrockLLMProvider(MODEL_ID, client)

    with pytest.raises(RuntimeError) as exc_info:
        provider.generate(SYSTEM_PROMPT, USER_PROMPT)

    assert exc_info.value is expected_error


def test_repeated_injected_construction_does_not_create_client() -> None:
    client = MagicMock()

    with patch("app.llm.bedrock.get_bedrock_runtime_client") as client_factory:
        first_provider = BedrockLLMProvider(MODEL_ID, client)
        second_provider = BedrockLLMProvider(MODEL_ID, client)

    assert first_provider._client is client
    assert second_provider._client is client
    client_factory.assert_not_called()
