from collections.abc import Callable, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models.memory import (
    NegotiatorMemoryModel,
    NegotiatorMemorySourceModel,
)
from app.database.session import SessionLocal
from app.domains.memory.exceptions import NegotiatorMemoryAlreadyExistsError
from app.domains.memory.models import NegotiatorMemory, NegotiatorMemoryRecord
from app.domains.memory.repository import NegotiatorMemoryRepository

SessionFactory = Callable[[], Session]


def _require_string_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(
            f"Persisted Memory field '{field_name}' must be a list of strings."
        )
    return [item for item in value if isinstance(item, str)]


def negotiator_memory_to_model(
    record: NegotiatorMemoryRecord,
) -> NegotiatorMemoryModel:
    return NegotiatorMemoryModel(
        id=record.id,
        trigger_session_id=record.trigger_session_id,
        recurring_strengths=list(record.memory.recurring_strengths),
        recurring_weaknesses=list(record.memory.recurring_weaknesses),
        improving_skills=list(record.memory.improving_skills),
        persistent_risks=list(record.memory.persistent_risks),
        priority_focus_areas=list(record.memory.priority_focus_areas),
        recommended_drills=list(record.memory.recommended_drills),
        sessions_analyzed=record.memory.sessions_analyzed,
        confidence=record.memory.confidence,
        created_at=record.created_at,
    )


def negotiator_memory_sources_to_models(
    record: NegotiatorMemoryRecord,
) -> list[NegotiatorMemorySourceModel]:
    return [
        NegotiatorMemorySourceModel(
            memory_id=record.id,
            session_id=session_id,
            source_order=source_order,
        )
        for source_order, session_id in enumerate(record.source_session_ids)
    ]


def negotiator_memory_to_domain(
    model: NegotiatorMemoryModel,
    source_models: Sequence[NegotiatorMemorySourceModel],
) -> NegotiatorMemoryRecord:
    ordered_sources = sorted(source_models, key=lambda source: source.source_order)
    if any(source.memory_id != model.id for source in ordered_sources):
        raise TypeError("Persisted Memory sources must belong to the Memory record.")

    expected_source_order = list(range(len(ordered_sources)))
    actual_source_order = [source.source_order for source in ordered_sources]
    if actual_source_order != expected_source_order:
        raise TypeError("Persisted Memory sources must have contiguous ordering.")

    return NegotiatorMemoryRecord(
        id=model.id,
        trigger_session_id=model.trigger_session_id,
        memory=NegotiatorMemory(
            recurring_strengths=_require_string_list(
                model.recurring_strengths,
                "recurring_strengths",
            ),
            recurring_weaknesses=_require_string_list(
                model.recurring_weaknesses,
                "recurring_weaknesses",
            ),
            improving_skills=_require_string_list(
                model.improving_skills,
                "improving_skills",
            ),
            persistent_risks=_require_string_list(
                model.persistent_risks,
                "persistent_risks",
            ),
            priority_focus_areas=_require_string_list(
                model.priority_focus_areas,
                "priority_focus_areas",
            ),
            recommended_drills=_require_string_list(
                model.recommended_drills,
                "recommended_drills",
            ),
            sessions_analyzed=model.sessions_analyzed,
            confidence=model.confidence,
        ),
        source_session_ids=tuple(source.session_id for source in ordered_sources),
        created_at=model.created_at,
    )


class SQLNegotiatorMemoryRepository(NegotiatorMemoryRepository):
    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory

    def create(
        self,
        record: NegotiatorMemoryRecord,
    ) -> NegotiatorMemoryRecord:
        with self._session_factory() as database_session:
            try:
                trigger_session_id = record.trigger_session_id
                if trigger_session_id is not None:
                    duplicate_id = database_session.scalar(
                        select(NegotiatorMemoryModel.id).where(
                            NegotiatorMemoryModel.trigger_session_id
                            == trigger_session_id
                        )
                    )
                    if duplicate_id is not None:
                        raise NegotiatorMemoryAlreadyExistsError(trigger_session_id)

                model = negotiator_memory_to_model(record)
                source_models = negotiator_memory_sources_to_models(record)
                database_session.add(model)
                database_session.flush()
                database_session.add_all(source_models)
                database_session.commit()
                database_session.refresh(model)
                for source_model in source_models:
                    database_session.refresh(source_model)
            except SQLAlchemyError:
                database_session.rollback()
                raise

            return negotiator_memory_to_domain(model, source_models)

    def get_latest(self) -> NegotiatorMemoryRecord | None:
        with self._session_factory() as database_session:
            model = database_session.scalar(
                select(NegotiatorMemoryModel)
                .order_by(
                    NegotiatorMemoryModel.created_at.desc(),
                    NegotiatorMemoryModel.id.desc(),
                )
                .limit(1)
            )
            if model is None:
                return None
            return self._to_domain(database_session, model)

    def list_all(self) -> list[NegotiatorMemoryRecord]:
        with self._session_factory() as database_session:
            models = database_session.scalars(
                select(NegotiatorMemoryModel).order_by(
                    NegotiatorMemoryModel.created_at,
                    NegotiatorMemoryModel.id,
                )
            ).all()
            return [self._to_domain(database_session, model) for model in models]

    def get_by_trigger_session(
        self,
        session_id: UUID,
    ) -> NegotiatorMemoryRecord | None:
        with self._session_factory() as database_session:
            model = database_session.scalar(
                select(NegotiatorMemoryModel).where(
                    NegotiatorMemoryModel.trigger_session_id == session_id
                )
            )
            if model is None:
                return None
            return self._to_domain(database_session, model)

    @staticmethod
    def _to_domain(
        database_session: Session,
        model: NegotiatorMemoryModel,
    ) -> NegotiatorMemoryRecord:
        source_models = database_session.scalars(
            select(NegotiatorMemorySourceModel)
            .where(NegotiatorMemorySourceModel.memory_id == model.id)
            .order_by(NegotiatorMemorySourceModel.source_order)
        ).all()
        return negotiator_memory_to_domain(model, source_models)
