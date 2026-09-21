import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from uuid import UUID, uuid4

from app.domains.negotiation.exceptions import ScenarioNotFoundError
from app.domains.negotiation.repository import NegotiationRepository
from app.domains.negotiation_state.models import NegotiationState
from app.domains.negotiation_turn.exceptions import (
    EmptyOpponentResponseError,
    NegotiationSessionNotFoundError,
    OpponentResponseInProgressError,
    OpponentResponseOutOfSequenceError,
    OpponentResponseRequiresUserTurnError,
)
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.repository import NegotiationTurnRepository
from app.domains.opponent.profile_builder import OpponentProfileBuilder
from app.domains.scenario.models import Scenario
from app.domains.scenario.repository import ScenarioRepository
from app.llm.observability import (
    generate_with_observability,
    stream_with_observability,
)
from app.llm.provider import LLMProvider
from app.mcp.salary_client import (
    SalaryDataClient,
    SalaryDataQuery,
    SalaryMarketData,
    validate_query,
)
from app.prompts.opponent import OpponentPromptBuilder
from app.services.adaptive_context import AdaptiveContextService
from app.services.negotiation_state import NegotiationStateExtractor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpponentResponseResult:
    user_turn: NegotiationTurn
    opponent_turn: NegotiationTurn
    conversation_turns: list[NegotiationTurn]


@dataclass(frozen=True)
class OpponentResponsePreparation:
    session_id: UUID
    user_id: UUID
    lease_id: UUID
    user_turn: NegotiationTurn
    conversation_turns: list[NegotiationTurn]
    system_prompt: str
    user_prompt: str


class OpponentService:
    def __init__(
        self,
        negotiation_repository: NegotiationRepository,
        scenario_repository: ScenarioRepository,
        turn_repository: NegotiationTurnRepository,
        state_extractor: NegotiationStateExtractor,
        profile_builder: OpponentProfileBuilder,
        prompt_builder: OpponentPromptBuilder,
        llm_provider: LLMProvider,
        adaptive_context_service: AdaptiveContextService,
        salary_data_client: SalaryDataClient | None = None,
    ) -> None:
        self._negotiation_repository = negotiation_repository
        self._scenario_repository = scenario_repository
        self._turn_repository = turn_repository
        self._state_extractor = state_extractor
        self._profile_builder = profile_builder
        self._prompt_builder = prompt_builder
        self._llm_provider = llm_provider
        self._adaptive_context_service = adaptive_context_service
        self._salary_data_client = salary_data_client
        self._in_flight_lock = Lock()
        self._in_flight_sessions: dict[UUID, UUID] = {}

    def generate_response(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> OpponentResponseResult:
        preparation = self.begin_streaming_response(session_id, user_id)
        try:
            generated_content = generate_with_observability(
                self._llm_provider,
                logger,
                "opponent_response_generation",
                system_prompt=preparation.system_prompt,
                user_prompt=preparation.user_prompt,
                session_id=session_id,
            )
            return self.complete_streaming_response(
                preparation,
                generated_content,
            )
        finally:
            self.cancel_streaming_response(preparation)

    def begin_streaming_response(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> OpponentResponsePreparation:
        lease_id = self._acquire_session(session_id)
        try:
            return self._prepare_response(session_id, user_id, lease_id)
        except BaseException:
            self._release_session(session_id, lease_id)
            raise

    def stream_response(
        self,
        preparation: OpponentResponsePreparation,
    ) -> Iterator[str]:
        self._require_active_lease(preparation)
        return stream_with_observability(
            self._llm_provider,
            logger,
            "opponent_response_stream",
            system_prompt=preparation.system_prompt,
            user_prompt=preparation.user_prompt,
            session_id=preparation.session_id,
        )

    def complete_streaming_response(
        self,
        preparation: OpponentResponsePreparation,
        generated_content: str,
    ) -> OpponentResponseResult:
        self._require_active_lease(preparation)
        normalized_content = generated_content.strip()
        if not normalized_content:
            raise EmptyOpponentResponseError(preparation.session_id)

        current_turns = self._turn_repository.list_by_session_for_user(
            preparation.session_id,
            preparation.user_id,
        )
        latest_turn = current_turns[-1] if current_turns else None
        if latest_turn is None:
            raise OpponentResponseRequiresUserTurnError(preparation.session_id)
        if (
            latest_turn.id != preparation.user_turn.id
            or latest_turn.speaker is not NegotiationTurnSpeaker.USER
        ):
            raise OpponentResponseOutOfSequenceError(
                preparation.session_id,
                latest_turn.speaker,
            )

        opponent_turn = NegotiationTurn(
            id=uuid4(),
            session_id=preparation.session_id,
            speaker=NegotiationTurnSpeaker.OPPONENT,
            content=normalized_content,
            turn_number=latest_turn.turn_number + 1,
            created_at=datetime.now(UTC),
        )
        persisted_turn = self._turn_repository.create(
            opponent_turn,
            preparation.user_id,
        )

        return OpponentResponseResult(
            user_turn=preparation.user_turn,
            opponent_turn=persisted_turn,
            conversation_turns=self._turn_repository.list_by_session_for_user(
                preparation.session_id,
                preparation.user_id,
            ),
        )

    def cancel_streaming_response(
        self,
        preparation: OpponentResponsePreparation,
    ) -> None:
        self._release_session(preparation.session_id, preparation.lease_id)

    def _prepare_response(
        self,
        session_id: UUID,
        user_id: UUID,
        lease_id: UUID,
    ) -> OpponentResponsePreparation:
        negotiation = self._negotiation_repository.get_for_user(session_id, user_id)
        if negotiation is None:
            raise NegotiationSessionNotFoundError(session_id)

        scenario = self._scenario_repository.get_for_user(
            negotiation.scenario_id,
            user_id,
        )
        if scenario is None:
            raise ScenarioNotFoundError(negotiation.scenario_id)

        turns = self._turn_repository.list_by_session_for_user(session_id, user_id)
        if not turns:
            raise OpponentResponseRequiresUserTurnError(session_id)

        latest_turn = turns[-1]
        if latest_turn.speaker is not NegotiationTurnSpeaker.USER:
            raise OpponentResponseOutOfSequenceError(
                session_id,
                latest_turn.speaker,
            )

        state: NegotiationState = self._state_extractor.extract(turns)
        profile = self._profile_builder.build(scenario.difficulty)
        adaptive_context = self._adaptive_context_service.get_context(user_id)
        salary_market_data = self._get_salary_market_data(scenario, latest_turn)
        if salary_market_data is None:
            system_prompt = self._prompt_builder.build_system_prompt(
                scenario,
                profile,
                state,
                adaptive_context,
            )
        else:
            system_prompt = self._prompt_builder.build_system_prompt(
                scenario,
                profile,
                state,
                adaptive_context,
                salary_market_data,
            )
        user_prompt = self._prompt_builder.build_user_prompt(turns)
        return OpponentResponsePreparation(
            session_id=session_id,
            user_id=user_id,
            lease_id=lease_id,
            user_turn=latest_turn,
            conversation_turns=turns,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    def _get_salary_market_data(
        self,
        scenario: Scenario,
        latest_turn: NegotiationTurn,
    ) -> SalaryMarketData | None:
        if self._salary_data_client is None or not _is_salary_related(
            scenario,
            latest_turn.content,
        ):
            return None

        try:
            query = _build_salary_query(scenario, latest_turn.content)
            return self._salary_data_client.get_salary_data(query)
        except Exception as exc:  # noqa: BLE001 - lookup availability must not block turns.
            logger.warning(
                "Salary market lookup failed; continuing without market data (%s).",
                type(exc).__name__,
            )
            return None

    def _acquire_session(self, session_id: UUID) -> UUID:
        with self._in_flight_lock:
            if session_id in self._in_flight_sessions:
                raise OpponentResponseInProgressError(session_id)
            lease_id = uuid4()
            self._in_flight_sessions[session_id] = lease_id
            return lease_id

    def _require_active_lease(
        self,
        preparation: OpponentResponsePreparation,
    ) -> None:
        with self._in_flight_lock:
            if (
                self._in_flight_sessions.get(preparation.session_id)
                != preparation.lease_id
            ):
                raise OpponentResponseInProgressError(preparation.session_id)

    def _release_session(self, session_id: UUID, lease_id: UUID) -> None:
        with self._in_flight_lock:
            if self._in_flight_sessions.get(session_id) == lease_id:
                del self._in_flight_sessions[session_id]


def _is_salary_related(scenario: Scenario, candidate_message: str) -> bool:
    scenario_text = " ".join(
        str(getattr(scenario, field, ""))
        for field in ("title", "description", "industry", "opponent_role", "objective")
    ).lower()
    text = f"{scenario_text} {candidate_message}".lower()
    return any(
        phrase in text
        for phrase in (
            "salary",
            "compensation",
            "base pay",
            "annual pay",
            "total pay",
            "job offer",
            "employment offer",
        )
    )


def _build_salary_query(
    scenario: Scenario,
    candidate_message: str,
) -> SalaryDataQuery:
    text = " ".join(
        [
            str(getattr(scenario, field, ""))
            for field in ("title", "description", "industry", "opponent_role", "objective")
        ]
        + [candidate_message]
    ).lower()

    level = next(
        (level for level in ("principal", "lead", "senior", "mid", "junior") if level in text),
        None,
    )
    if level is None and ("mid-level" in text or "mid level" in text):
        level = "mid"

    workplace = next(
        (
            workplace
            for workplace in ("remote", "hybrid", "onsite")
            if workplace in text
        ),
        None,
    )
    if workplace is None and "on-site" in text:
        workplace = "onsite"

    return validate_query(
        SalaryDataQuery(
            tag="llm" if "llm" in text else None,
            level=level,
            workplace=workplace,
        )
    )
