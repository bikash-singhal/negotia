import logging
from collections.abc import Iterator
from typing import Any

from app.aws.session import get_bedrock_runtime_client
from app.core.observability import log_event
from app.llm.exceptions import MissingLLMProviderTextError

logger = logging.getLogger(__name__)


class BedrockLLMProvider:
    def __init__(
        self,
        model_id: str,
        client: Any | None = None,
    ) -> None:
        self._model_id = model_id
        self._client = client if client is not None else get_bedrock_runtime_client()

        log_event(
            logger,
            logging.INFO,
            "provider_initialized",
            operation="provider_initialization",
            provider=type(self).__name__,
            model_id=self._model_id,
            outcome="success",
        )

    @property
    def model_id(self) -> str:
        return self._model_id

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
    ) -> str:
        request: dict[str, Any] = {
            "modelId": self._model_id,
            "system": [
                {
                    "text": system_prompt,
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": user_prompt,
                        }
                    ],
                }
            ],
        }
        if temperature is not None:
            request["inferenceConfig"] = {"temperature": temperature}

        response = self._client.converse(**request)
        return _extract_first_text_block(response)

    def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
    ) -> Iterator[str]:
        request: dict[str, Any] = {
            "modelId": self._model_id,
            "system": [{"text": system_prompt}],
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": user_prompt}],
                }
            ],
        }
        if temperature is not None:
            request["inferenceConfig"] = {"temperature": temperature}

        response = self._client.converse_stream(**request)
        if not isinstance(response, dict) or response.get("stream") is None:
            raise MissingLLMProviderTextError()

        has_non_blank_text = False
        for event in response["stream"]:
            text = _extract_stream_delta(event)
            if text:
                has_non_blank_text = has_non_blank_text or bool(text.strip())
                yield text

        if not has_non_blank_text:
            raise MissingLLMProviderTextError()


def _extract_first_text_block(response: object) -> str:
    if not isinstance(response, dict):
        raise MissingLLMProviderTextError()

    output = response.get("output")
    if not isinstance(output, dict):
        raise MissingLLMProviderTextError()

    message = output.get("message")
    if not isinstance(message, dict):
        raise MissingLLMProviderTextError()

    content = message.get("content")
    if not isinstance(content, list):
        raise MissingLLMProviderTextError()

    for block in content:
        if not isinstance(block, dict) or "text" not in block:
            continue

        text = block["text"]
        if not isinstance(text, str) or not text.strip():
            raise MissingLLMProviderTextError()
        return text

    raise MissingLLMProviderTextError()


def _extract_stream_delta(event: object) -> str | None:
    if not isinstance(event, dict):
        return None
    content_block_delta = event.get("contentBlockDelta")
    if not isinstance(content_block_delta, dict):
        return None
    delta = content_block_delta.get("delta")
    if not isinstance(delta, dict):
        return None
    text = delta.get("text")
    return text if isinstance(text, str) and text else None
