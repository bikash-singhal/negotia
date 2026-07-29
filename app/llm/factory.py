from app.core.config import Settings
from app.llm.bedrock import BedrockLLMProvider
from app.llm.fake import FakeLLMProvider
from app.llm.provider import LLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "fake":
        return FakeLLMProvider()

    if settings.llm_provider == "bedrock":
        return BedrockLLMProvider(settings.bedrock_model_id)

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
