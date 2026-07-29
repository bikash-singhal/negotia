import logging
from time import perf_counter
from typing import Any

from app.aws.session import get_bedrock_runtime_client

logger = logging.getLogger(__name__)


class BedrockLLMProvider:
    def __init__(
        self,
        model_id: str,
        client: Any | None = None,
    ) -> None:
        self._model_id = model_id
        self._client = client if client is not None else get_bedrock_runtime_client()

        logger.info(
            "Initialized Bedrock LLM provider with model ID: %s",
            self._model_id,
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        logger.debug(
            "Starting Bedrock request for model ID: %s",
            self._model_id,
        )
        start = perf_counter()

        try:
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
        except Exception:
            logger.exception(
                "Bedrock request failed for model ID: %s",
                self._model_id,
            )
            raise

        elapsed = perf_counter() - start
        logger.debug("Bedrock request completed in %.3f seconds", elapsed)

        return response["output"]["message"]["content"][0]["text"]
