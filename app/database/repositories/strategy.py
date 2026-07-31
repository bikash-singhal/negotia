from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models.strategy import NegotiationStrategyModel
from app.database.repositories._session import (
    RepositorySessionManager,
    SessionFactory,
)
from app.domains.strategy.exceptions import NegotiationStrategyAlreadyExistsError
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
    NegotiationTactic,
)
from app.domains.strategy.repository import NegotiationStrategyRepository


def _tactic_to_json(tactic: NegotiationTactic) -> dict[str, object]:
    return {
        "priority": tactic.priority,
        "title": tactic.title,
        "rationale": tactic.rationale,
        "actions": list(tactic.actions),
        "example_language": list(tactic.example_language),
        "success_indicator": tactic.success_indicator,
    }


def _require_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Persisted tactic field '{field_name}' must be a string.")
    return value


def _require_string_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(
            f"Persisted tactic field '{field_name}' must be a list of strings."
        )
    return [item for item in value if isinstance(item, str)]


def _tactic_to_domain(data: dict[str, object]) -> NegotiationTactic:
    priority = data.get("priority")
    if not isinstance(priority, int) or isinstance(priority, bool):
        raise TypeError("Persisted tactic field 'priority' must be an integer.")

    return NegotiationTactic(
        priority=priority,
        title=_require_string(data.get("title"), "title"),
        rationale=_require_string(data.get("rationale"), "rationale"),
        actions=_require_string_list(data.get("actions"), "actions"),
        example_language=_require_string_list(
            data.get("example_language"),
            "example_language",
        ),
        success_indicator=_require_string(
            data.get("success_indicator"),
            "success_indicator",
        ),
    )


def negotiation_strategy_to_model(
    record: NegotiationStrategyRecord,
) -> NegotiationStrategyModel:
    return NegotiationStrategyModel(
        id=record.id,
        session_id=record.session_id,
        debrief_id=record.debrief_id,
        primary_objective=record.strategy.primary_objective,
        expected_outcome=record.strategy.expected_outcome,
        prioritized_tactics=[
            _tactic_to_json(tactic) for tactic in record.strategy.prioritized_tactics
        ],
        long_term_skills=list(record.strategy.long_term_skills),
        preparation_checklist=list(record.strategy.preparation_checklist),
        avoid_next_time=list(record.strategy.avoid_next_time),
        confidence=record.strategy.confidence,
        created_at=record.created_at,
    )


def negotiation_strategy_to_domain(
    model: NegotiationStrategyModel,
) -> NegotiationStrategyRecord:
    return NegotiationStrategyRecord(
        id=model.id,
        session_id=model.session_id,
        debrief_id=model.debrief_id,
        strategy=NegotiationStrategy(
            primary_objective=model.primary_objective,
            expected_outcome=model.expected_outcome,
            prioritized_tactics=[
                _tactic_to_domain(tactic) for tactic in model.prioritized_tactics
            ],
            long_term_skills=list(model.long_term_skills),
            preparation_checklist=list(model.preparation_checklist),
            avoid_next_time=list(model.avoid_next_time),
            confidence=model.confidence,
        ),
        created_at=model.created_at,
    )


class SQLNegotiationStrategyRepository(NegotiationStrategyRepository):
    def __init__(
        self,
        session_factory: SessionFactory | None = None,
        *,
        session: Session | None = None,
    ) -> None:
        self._session_manager = RepositorySessionManager(
            session_factory,
            session=session,
        )

    def create(
        self,
        record: NegotiationStrategyRecord,
    ) -> NegotiationStrategyRecord:
        with self._session_manager.session_scope() as database_session:
            try:
                duplicate_id = database_session.scalar(
                    select(NegotiationStrategyModel.id).where(
                        NegotiationStrategyModel.session_id == record.session_id
                    )
                )
                if duplicate_id is not None:
                    raise NegotiationStrategyAlreadyExistsError(record.session_id)

                model = negotiation_strategy_to_model(record)
                database_session.add(model)
                self._session_manager.finish_write(database_session, [model])
            except SQLAlchemyError:
                self._session_manager.rollback_owned_transaction(database_session)
                raise

            return negotiation_strategy_to_domain(model)

    def get_by_session(
        self,
        session_id: UUID,
    ) -> NegotiationStrategyRecord | None:
        with self._session_manager.session_scope() as database_session:
            model = database_session.scalar(
                select(NegotiationStrategyModel).where(
                    NegotiationStrategyModel.session_id == session_id
                )
            )
            return None if model is None else negotiation_strategy_to_domain(model)

    def list_all(self) -> list[NegotiationStrategyRecord]:
        with self._session_manager.session_scope() as database_session:
            models = database_session.scalars(
                select(NegotiationStrategyModel).order_by(
                    NegotiationStrategyModel.created_at,
                    NegotiationStrategyModel.id,
                )
            ).all()
            return [negotiation_strategy_to_domain(model) for model in models]
