from app.llm.fake import FakeLLMProvider
from app.main import llm_provider, opponent_service, state_extractor
from app.services.negotiation_state import NegotiationStateExtractor
from app.services.opponent import OpponentService


def test_app_builds_opponent_service_with_configured_provider() -> None:
    assert isinstance(llm_provider, FakeLLMProvider)
    assert isinstance(state_extractor, NegotiationStateExtractor)
    assert isinstance(opponent_service, OpponentService)
    assert state_extractor._llm_provider is llm_provider
    assert opponent_service._state_extractor is state_extractor
    assert opponent_service._llm_provider is llm_provider
