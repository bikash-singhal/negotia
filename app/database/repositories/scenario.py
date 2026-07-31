from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models.scenario import ScenarioModel
from app.database.session import SessionLocal
from app.domains.scenario.models import Scenario, ScenarioDifficulty
from app.domains.scenario.repository import ScenarioRepository

SessionFactory = Callable[[], Session]


def scenario_to_model(scenario: Scenario) -> ScenarioModel:
    return ScenarioModel(
        scenario_id=scenario.scenario_id,
        title=scenario.title,
        description=scenario.description,
        industry=scenario.industry,
        opponent_role=scenario.opponent_role,
        objective=scenario.objective,
        difficulty=scenario.difficulty.value,
        personality=scenario.personality,
        negotiation_style=scenario.negotiation_style,
        constraints=list(scenario.constraints),
        hidden_context=list(scenario.hidden_context),
        walk_away_conditions=list(scenario.walk_away_conditions),
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
    )


def scenario_to_domain(model: ScenarioModel) -> Scenario:
    return Scenario(
        scenario_id=model.scenario_id,
        title=model.title,
        description=model.description,
        industry=model.industry,
        opponent_role=model.opponent_role,
        objective=model.objective,
        difficulty=ScenarioDifficulty(model.difficulty),
        personality=model.personality,
        negotiation_style=model.negotiation_style,
        constraints=list(model.constraints),
        hidden_context=list(model.hidden_context),
        walk_away_conditions=list(model.walk_away_conditions),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLScenarioRepository(ScenarioRepository):
    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory

    def create(self, scenario: Scenario) -> Scenario:
        with self._session_factory() as database_session:
            model = scenario_to_model(scenario)
            database_session.add(model)
            try:
                database_session.commit()
                database_session.refresh(model)
            except SQLAlchemyError:
                database_session.rollback()
                raise

            return scenario_to_domain(model)

    def get(self, scenario_id: UUID) -> Scenario | None:
        with self._session_factory() as database_session:
            model = database_session.get(ScenarioModel, scenario_id)
            return None if model is None else scenario_to_domain(model)

    def list(self) -> list[Scenario]:
        with self._session_factory() as database_session:
            models = database_session.scalars(
                select(ScenarioModel).order_by(
                    ScenarioModel.created_at,
                    ScenarioModel.scenario_id,
                )
            ).all()
            return [scenario_to_domain(model) for model in models]
