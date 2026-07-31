from itertools import pairwise
from uuid import UUID

from app.database.unit_of_work import CompletionUnitOfWorkFactory
from app.domains.debrief.models import NegotiationDebriefRecord
from app.domains.memory.models import NegotiatorMemoryRecord
from app.domains.negotiation.exceptions import (
    CompletedNegotiationMissingDebriefError,
    CompletedNegotiationMissingStrategyError,
    CompletionArtifactsChangedError,
    InvalidNegotiationStatusTransitionError,
    NegotiationCompletionLatestTurnFromUserError,
    NegotiationCompletionRequiresExchangeError,
    NegotiationCompletionWithoutTurnsError,
)
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation.service import NegotiationService
from app.domains.negotiation_turn.exceptions import NegotiationSessionNotFoundError
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.negotiation_turn.service import NegotiationTurnService
from app.domains.strategy.models import NegotiationStrategyRecord
from app.services.debrief import DebriefService
from app.services.memory import MemoryService
from app.services.strategy import StrategyService
from app.workflows.completion.state import (
    CompletionWorkflowState,
    CompletionWorkflowUpdate,
)


class CompletionWorkflowNodes:
    def __init__(
        self,
        negotiation_service: NegotiationService,
        negotiation_turn_service: NegotiationTurnService,
        debrief_service: DebriefService,
        strategy_service: StrategyService,
        memory_service: MemoryService,
        unit_of_work_factory: CompletionUnitOfWorkFactory,
    ) -> None:
        self._negotiation_service = negotiation_service
        self._negotiation_turn_service = negotiation_turn_service
        self._debrief_service = debrief_service
        self._strategy_service = strategy_service
        self._memory_service = memory_service
        self._unit_of_work_factory = unit_of_work_factory

    def validate_session(
        self,
        state: CompletionWorkflowState,
    ) -> CompletionWorkflowUpdate:
        session_id = state["session_id"]
        session = self._negotiation_service.validate_completion_transition(session_id)
        if session.status is not NegotiationStatus.COMPLETED:
            turns = self._negotiation_turn_service.list_turns(session_id)
            self._validate_completion_turns(session_id, turns)

        return {"session": session}

    def create_or_reuse_debrief(
        self,
        state: CompletionWorkflowState,
    ) -> CompletionWorkflowUpdate:
        session = self._get_session(state)
        record = self._debrief_service.get_for_session(session.id)
        prepared = False
        if record is None:
            if session.status is NegotiationStatus.COMPLETED:
                raise CompletedNegotiationMissingDebriefError(session.id)
            record = self._debrief_service.prepare_for_session(session.id)
            prepared = True

        return {"debrief_record": record, "debrief_prepared": prepared}

    def create_or_reuse_strategy(
        self,
        state: CompletionWorkflowState,
    ) -> CompletionWorkflowUpdate:
        session = self._get_session(state)
        debrief_record = self._get_debrief_record(state)
        record = self._strategy_service.get_for_session(session.id)
        prepared = False
        if record is None:
            if session.status is NegotiationStatus.COMPLETED:
                raise CompletedNegotiationMissingStrategyError(session.id)
            record = self._strategy_service.prepare_for_session(
                session.id,
                debrief_record,
            )
            prepared = True

        return {"strategy_record": record, "strategy_prepared": prepared}

    def create_or_reuse_memory(
        self,
        state: CompletionWorkflowState,
    ) -> CompletionWorkflowUpdate:
        session = self._get_session(state)
        record = self._memory_service.get_by_trigger_session(session.id)
        prepared = False
        if record is None and session.status is not NegotiationStatus.COMPLETED:
            record = self._memory_service.prepare_for_session(
                session.id,
                self._get_debrief_record(state),
                self._get_strategy_record(state),
            )
            prepared = record is not None

        return {"memory_record": record, "memory_prepared": prepared}

    def finalize_completion(
        self,
        state: CompletionWorkflowState,
    ) -> CompletionWorkflowUpdate:
        session_id = self._get_session(state).id
        with self._unit_of_work_factory() as unit_of_work:
            session = unit_of_work.negotiation_repository.get_for_update(session_id)
            if session is None:
                raise NegotiationSessionNotFoundError(session_id)

            debrief_record = unit_of_work.debrief_repository.get_by_session(session_id)
            strategy_record = unit_of_work.strategy_repository.get_by_session(
                session_id
            )
            memory_record = unit_of_work.memory_repository.get_by_trigger_session(
                session_id
            )

            if session.status is NegotiationStatus.COMPLETED:
                if debrief_record is None:
                    raise CompletedNegotiationMissingDebriefError(session_id)
                if strategy_record is None:
                    raise CompletedNegotiationMissingStrategyError(session_id)
                self._validate_strategy_lineage(
                    session_id,
                    debrief_record.id,
                    strategy_record,
                )
                return {
                    "session": session,
                    "debrief_record": debrief_record,
                    "strategy_record": strategy_record,
                    "memory_record": memory_record,
                }

            if session.status not in {
                NegotiationStatus.CREATED,
                NegotiationStatus.ACTIVE,
            }:
                raise InvalidNegotiationStatusTransitionError(
                    session_id,
                    session.status,
                    NegotiationStatus.COMPLETED,
                )

            prepared_debrief = self._get_debrief_record(state)
            self._validate_debrief_lineage(session_id, prepared_debrief)
            if debrief_record is None:
                debrief_record = unit_of_work.debrief_repository.create(
                    prepared_debrief
                )

            prepared_strategy = self._get_strategy_record(state)
            if state.get("strategy_prepared", False):
                self._validate_strategy_lineage(
                    session_id,
                    debrief_record.id,
                    prepared_strategy,
                )
            if strategy_record is None:
                self._validate_strategy_lineage(
                    session_id,
                    debrief_record.id,
                    prepared_strategy,
                )
                strategy_record = unit_of_work.strategy_repository.create(
                    prepared_strategy
                )
            else:
                self._validate_strategy_lineage(
                    session_id,
                    debrief_record.id,
                    strategy_record,
                )

            prepared_memory = state.get("memory_record")
            if memory_record is None and prepared_memory is not None:
                self._validate_memory_lineage(session_id, prepared_memory)
                memory_record = unit_of_work.memory_repository.create(prepared_memory)

            self._negotiation_service.prepare_completion(session)
            session = unit_of_work.negotiation_repository.update(session)
            unit_of_work.commit()

        return {
            "session": session,
            "debrief_record": debrief_record,
            "strategy_record": strategy_record,
            "memory_record": memory_record,
        }

    @staticmethod
    def _get_session(state: CompletionWorkflowState) -> NegotiationSession:
        if "session" not in state:
            raise RuntimeError("Completion workflow session state is unavailable.")
        return state["session"]

    @staticmethod
    def _get_debrief_record(
        state: CompletionWorkflowState,
    ) -> NegotiationDebriefRecord:
        if "debrief_record" not in state:
            raise RuntimeError("Completion workflow debrief state is unavailable.")
        return state["debrief_record"]

    @staticmethod
    def _get_strategy_record(
        state: CompletionWorkflowState,
    ) -> NegotiationStrategyRecord:
        if "strategy_record" not in state:
            raise RuntimeError("Completion workflow strategy state is unavailable.")
        return state["strategy_record"]

    @staticmethod
    def _validate_debrief_lineage(
        session_id: UUID,
        record: NegotiationDebriefRecord,
    ) -> None:
        if record.session_id != session_id:
            raise CompletionArtifactsChangedError(session_id)

    @staticmethod
    def _validate_strategy_lineage(
        session_id: UUID,
        debrief_id: UUID,
        record: NegotiationStrategyRecord,
    ) -> None:
        if record.session_id != session_id or record.debrief_id != debrief_id:
            raise CompletionArtifactsChangedError(session_id)

    @staticmethod
    def _validate_memory_lineage(
        session_id: UUID,
        record: NegotiatorMemoryRecord,
    ) -> None:
        if (
            record.trigger_session_id != session_id
            or session_id not in record.source_session_ids
        ):
            raise CompletionArtifactsChangedError(session_id)

    @staticmethod
    def _validate_completion_turns(
        session_id: UUID,
        turns: list[NegotiationTurn],
    ) -> None:
        if not turns:
            raise NegotiationCompletionWithoutTurnsError(session_id)

        if turns[-1].speaker is NegotiationTurnSpeaker.USER:
            raise NegotiationCompletionLatestTurnFromUserError(session_id)

        has_completed_exchange = any(
            first.speaker is NegotiationTurnSpeaker.USER
            and second.speaker is NegotiationTurnSpeaker.OPPONENT
            for first, second in pairwise(turns)
        )
        if not has_completed_exchange:
            raise NegotiationCompletionRequiresExchangeError(session_id)
