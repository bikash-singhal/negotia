from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.database.repositories.coach import SQLCoachObservationRepository
from app.database.repositories.debrief import SQLNegotiationDebriefRepository
from app.database.repositories.memory import SQLNegotiatorMemoryRepository
from app.database.repositories.negotiation import SQLNegotiationRepository
from app.database.repositories.negotiation_turn import (
    SQLNegotiationTurnRepository,
)
from app.database.repositories.scenario import SQLScenarioRepository
from app.database.repositories.strategy import SQLNegotiationStrategyRepository
from app.database.repositories.user import SQLUserRepository
from app.domains.coach.models import CoachObservation, CoachObservationRecord
from app.domains.debrief.models import NegotiationDebrief, NegotiationDebriefRecord
from app.domains.memory.models import NegotiatorMemory, NegotiatorMemoryRecord
from app.domains.negotiation.models import NegotiationSession, NegotiationStatus
from app.domains.negotiation_turn.exceptions import NegotiationSessionNotFoundError
from app.domains.negotiation_turn.models import (
    NegotiationTurn,
    NegotiationTurnSpeaker,
)
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
)
from app.domains.user.models import User
from tests.ownership import OTHER_USER_ID, TEST_USER_ID

from .conftest import SessionFactory


def _scenario(user_id: UUID, title: str) -> Scenario:
    return Scenario(
        user_id=user_id,
        title=title,
        description="Negotiate supplier pricing and delivery commitments.",
        industry="Manufacturing",
        opponent_role="Supplier account director",
        objective="Secure reliable delivery while protecting commercial value.",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        personality="Analytical and composed",
        negotiation_style="Collaborative but firm",
    )


def _session(user_id: UUID, scenario_id: UUID) -> NegotiationSession:
    now = datetime.now(UTC)
    return NegotiationSession(
        id=uuid4(),
        user_id=user_id,
        scenario_id=scenario_id,
        status=NegotiationStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )


def _turn(
    session_id: UUID,
    speaker: NegotiationTurnSpeaker,
    turn_number: int,
) -> NegotiationTurn:
    return NegotiationTurn(
        id=uuid4(),
        session_id=session_id,
        speaker=speaker,
        content="A persisted negotiation message.",
        turn_number=turn_number,
        created_at=datetime.now(UTC) + timedelta(seconds=turn_number),
    )


def _debrief(session_id: UUID) -> NegotiationDebriefRecord:
    return NegotiationDebriefRecord(
        id=uuid4(),
        session_id=session_id,
        debrief=NegotiationDebrief(
            repeated_strengths=["Uses conditional concessions."],
            repeated_weaknesses=["Anchors before discovery."],
            key_missed_opportunities=["Did not test the deadline."],
            recurring_risks=["Makes unilateral concessions."],
            overall_assessment="Constructive but too quick to concede.",
            confidence="high",
        ),
        observation_count=1,
        created_at=datetime.now(UTC),
    )


def _strategy(
    session_id: UUID,
    debrief_id: UUID,
) -> NegotiationStrategyRecord:
    return NegotiationStrategyRecord(
        id=uuid4(),
        session_id=session_id,
        debrief_id=debrief_id,
        strategy=NegotiationStrategy(
            primary_objective="Make every concession conditional.",
            expected_outcome="Receive reciprocal value for concessions.",
            prioritized_tactics=[],
            long_term_skills=["Concession planning"],
            preparation_checklist=["Define reciprocal asks."],
            avoid_next_time=["Avoid unilateral concessions."],
            confidence="high",
        ),
        created_at=datetime.now(UTC),
    )


def _memory(
    user_id: UUID,
    session_id: UUID,
) -> NegotiatorMemoryRecord:
    return NegotiatorMemoryRecord(
        id=uuid4(),
        user_id=user_id,
        trigger_session_id=session_id,
        memory=NegotiatorMemory(
            stable_strengths=["Uses conditional concessions."],
            stable_weaknesses=["Anchors before discovery."],
            improving_skills=["Diagnostic questioning"],
            persistent_risks=["Concedes without reciprocal value."],
            highest_priority_skill="Concession planning",
            next_session_drill="Prepare reciprocal asks.",
            progress_summary="Questioning is improving; concessions remain a risk.",
            sessions_analyzed=1,
            confidence="high",
        ),
        source_session_ids=(session_id,),
        created_at=datetime.now(UTC),
    )


def test_sql_repositories_enforce_resource_ownership(
    database_session_factory: SessionFactory,
) -> None:
    SQLUserRepository(database_session_factory).create(
        User(
            id=OTHER_USER_ID,
            username="other-owner",
            password_hash="not-used-by-repository-tests",
            created_at=datetime.now(UTC),
        )
    )
    scenario_repository = SQLScenarioRepository(database_session_factory)
    negotiation_repository = SQLNegotiationRepository(database_session_factory)
    turn_repository = SQLNegotiationTurnRepository(database_session_factory)
    coach_repository = SQLCoachObservationRepository(database_session_factory)
    debrief_repository = SQLNegotiationDebriefRepository(database_session_factory)
    strategy_repository = SQLNegotiationStrategyRepository(database_session_factory)
    memory_repository = SQLNegotiatorMemoryRepository(database_session_factory)

    scenario_a = scenario_repository.create(_scenario(TEST_USER_ID, "Owner A"))
    scenario_b = scenario_repository.create(_scenario(OTHER_USER_ID, "Owner B"))
    session_a = negotiation_repository.create(
        _session(TEST_USER_ID, scenario_a.scenario_id)
    )
    session_b = negotiation_repository.create(
        _session(OTHER_USER_ID, scenario_b.scenario_id)
    )
    user_turn = turn_repository.create(
        _turn(session_a.id, NegotiationTurnSpeaker.USER, 1),
        TEST_USER_ID,
    )
    opponent_turn = turn_repository.create(
        _turn(session_a.id, NegotiationTurnSpeaker.OPPONENT, 2),
        TEST_USER_ID,
    )
    observation = coach_repository.create(
        CoachObservationRecord(
            id=uuid4(),
            session_id=session_a.id,
            user_turn_id=user_turn.id,
            opponent_turn_id=opponent_turn.id,
            observation=CoachObservation(
                strengths=["Prepared an opening position."],
                weaknesses=[],
                missed_opportunities=[],
                risk_signals=[],
                confidence="high",
            ),
            created_at=datetime.now(UTC),
        ),
        TEST_USER_ID,
    )
    debrief = debrief_repository.create(_debrief(session_a.id), TEST_USER_ID)
    strategy = strategy_repository.create(
        _strategy(session_a.id, debrief.id),
        TEST_USER_ID,
    )
    memory = memory_repository.create(_memory(TEST_USER_ID, session_a.id))

    assert scenario_repository.list_for_user(TEST_USER_ID) == [scenario_a]
    assert scenario_repository.list_for_user(OTHER_USER_ID) == [scenario_b]
    assert (
        scenario_repository.get_for_user(scenario_a.scenario_id, OTHER_USER_ID) is None
    )
    assert negotiation_repository.list_for_user(TEST_USER_ID) == [session_a]
    assert negotiation_repository.list_for_user(OTHER_USER_ID) == [session_b]
    assert negotiation_repository.get_for_user(session_a.id, OTHER_USER_ID) is None
    assert turn_repository.get_for_user(user_turn.id, OTHER_USER_ID) is None
    assert turn_repository.list_by_session_for_user(session_a.id, OTHER_USER_ID) == []
    assert coach_repository.list_by_session_for_user(session_a.id, TEST_USER_ID) == [
        observation
    ]
    assert coach_repository.list_by_session_for_user(session_a.id, OTHER_USER_ID) == []
    assert (
        debrief_repository.get_by_session_for_user(session_a.id, TEST_USER_ID)
        == debrief
    )
    assert (
        debrief_repository.get_by_session_for_user(session_a.id, OTHER_USER_ID) is None
    )
    assert (
        strategy_repository.get_by_session_for_user(session_a.id, TEST_USER_ID)
        == strategy
    )
    assert strategy_repository.list_for_user(OTHER_USER_ID) == []
    assert memory_repository.get_latest(TEST_USER_ID) == memory
    assert memory_repository.get_latest(OTHER_USER_ID) is None
    assert memory_repository.list_for_user(OTHER_USER_ID) == []
    assert memory_repository.get_by_trigger_session(session_a.id, OTHER_USER_ID) is None

    with pytest.raises(NegotiationSessionNotFoundError):
        turn_repository.create(
            _turn(session_a.id, NegotiationTurnSpeaker.USER, 3),
            OTHER_USER_ID,
        )
    with pytest.raises(NegotiationSessionNotFoundError):
        debrief_repository.create(_debrief(session_a.id), OTHER_USER_ID)
    with pytest.raises(NegotiationSessionNotFoundError):
        strategy_repository.create(
            _strategy(session_a.id, debrief.id),
            OTHER_USER_ID,
        )
    with pytest.raises(NegotiationSessionNotFoundError):
        memory_repository.create(_memory(OTHER_USER_ID, session_a.id))
