from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domains.negotiation.exceptions import ScenarioNotFoundError
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation_turn.exceptions import (
    EmptyOpponentResponseError,
    NegotiationSessionNotFoundError,
    OpponentResponseOutOfSequenceError,
    OpponentResponseRequiresUserTurnError,
)
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.repository import NegotiationTurnRepository
from app.domains.opponent.profile_builder import OpponentProfileBuilder
from app.domains.scenario.repository import ScenarioRepository
from app.llm.provider import LLMProvider
from app.prompts.opponent import OpponentPromptBuilder


class OpponentService:
    def __init__(
        self,
        negotiation_repository: NegotiationRepository,
        scenario_repository: ScenarioRepository,
        turn_repository: NegotiationTurnRepository,
        profile_builder: OpponentProfileBuilder,
        prompt_builder: OpponentPromptBuilder,
        llm_provider: LLMProvider,
    ) -> None:
        self._negotiation_repository = negotiation_repository
        self._scenario_repository = scenario_repository
        self._turn_repository = turn_repository
        self._profile_builder = profile_builder
        self._prompt_builder = prompt_builder
        self._llm_provider = llm_provider

    def generate_response(self, session_id: UUID) -> NegotiationTurn:
        negotiation = self._negotiation_repository.get(session_id)
        if negotiation is None:
            raise NegotiationSessionNotFoundError(session_id)

        scenario = self._scenario_repository.get(negotiation.scenario_id)
        if scenario is None:
            raise ScenarioNotFoundError(negotiation.scenario_id)

        turns = self._turn_repository.list_by_session(session_id)
        if not turns:
            raise OpponentResponseRequiresUserTurnError(session_id)

        latest_turn = turns[-1]
        if latest_turn.speaker is not NegotiationTurnSpeaker.USER:
            raise OpponentResponseOutOfSequenceError(
                session_id,
                latest_turn.speaker,
            )

        profile = self._profile_builder.build(scenario.difficulty)
        system_prompt = self._prompt_builder.build_system_prompt(scenario, profile)
        user_prompt = self._prompt_builder.build_user_prompt(turns)
        generated_content = self._llm_provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        ).strip()
        if not generated_content:
            raise EmptyOpponentResponseError(session_id)

        opponent_turn = NegotiationTurn(
            id=uuid4(),
            session_id=session_id,
            speaker=NegotiationTurnSpeaker.OPPONENT,
            content=generated_content,
            turn_number=latest_turn.turn_number + 1,
            created_at=datetime.now(UTC),
        )

        return self._turn_repository.create(opponent_turn)
