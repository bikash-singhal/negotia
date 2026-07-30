from app.llm.fake import FakeLLMProvider
from app.main import (
    app,
    coach_observation_extractor,
    coach_observation_repository,
    coach_service,
    llm_provider,
    negotiation_engine,
    opponent_service,
    state_extractor,
)
from app.services.coach import CoachObservationExtractor, CoachService
from app.services.negotiation_engine import NegotiationEngine
from app.services.negotiation_state import NegotiationStateExtractor
from app.services.opponent import OpponentService


def test_app_builds_llm_services_with_configured_provider() -> None:
    assert isinstance(llm_provider, FakeLLMProvider)
    assert isinstance(coach_observation_extractor, CoachObservationExtractor)
    assert isinstance(coach_service, CoachService)
    assert isinstance(negotiation_engine, NegotiationEngine)
    assert isinstance(state_extractor, NegotiationStateExtractor)
    assert isinstance(opponent_service, OpponentService)
    assert coach_observation_extractor._llm_provider is llm_provider
    assert coach_service._extractor is coach_observation_extractor
    assert coach_service._repository is coach_observation_repository
    assert app.state.coach_service is coach_service
    assert not hasattr(app.state, "coach_observation_repository")
    assert negotiation_engine._opponent_service is opponent_service
    assert negotiation_engine._coach_service is coach_service
    assert app.state.negotiation_engine is negotiation_engine
    assert state_extractor._llm_provider is llm_provider
    assert opponent_service._state_extractor is state_extractor
    assert opponent_service._llm_provider is llm_provider
