from app.llm.fake import FakeLLMProvider
from app.main import llm_provider, opponent_service
from app.services.opponent import OpponentService


def test_app_builds_opponent_service_with_configured_provider() -> None:
    assert isinstance(llm_provider, FakeLLMProvider)
    assert isinstance(opponent_service, OpponentService)
    assert opponent_service._llm_provider is llm_provider
