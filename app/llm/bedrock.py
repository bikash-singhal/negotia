import logging
from typing import Any

from app.aws.session import get_bedrock_runtime_client
from app.core.observability import log_event

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
    ) -> str:
        response = self._client.converse(
            modelId=self._model_id,
            system=[
                {
                    "text": system_prompt,
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": user_prompt,
                        }
                    ],
                }
            ],
        )
        return response["output"]["message"]["content"][0]["text"]
