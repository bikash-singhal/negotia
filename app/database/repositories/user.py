from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models.user import UserModel
from app.database.session import SessionLocal
from app.domains.user.exceptions import UsernameAlreadyExistsError
from app.domains.user.models import User
from app.domains.user.repository import UserRepository

SessionFactory = Callable[[], Session]


def user_to_model(user: User) -> UserModel:
    return UserModel(
        id=user.id,
        username=user.username,
        password_hash=user.password_hash,
        created_at=user.created_at,
    )


def user_to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        username=model.username,
        password_hash=model.password_hash,
        created_at=model.created_at,
    )


class SQLUserRepository(UserRepository):
    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory

    def create(self, user: User) -> User:
        with self._session_factory() as database_session:
            model = user_to_model(user)
            database_session.add(model)
            try:
                database_session.commit()
                database_session.refresh(model)
            except IntegrityError as exc:
                database_session.rollback()
                if _constraint_name(exc) == "uq_users_username":
                    raise UsernameAlreadyExistsError(user.username) from exc
                raise
            except SQLAlchemyError:
                database_session.rollback()
                raise

            return user_to_domain(model)

    def get(self, user_id: UUID) -> User | None:
        with self._session_factory() as database_session:
            model = database_session.get(UserModel, user_id)
            return None if model is None else user_to_domain(model)

    def get_by_username(self, username: str) -> User | None:
        with self._session_factory() as database_session:
            model = database_session.scalar(
                select(UserModel).where(UserModel.username == username)
            )
            return None if model is None else user_to_domain(model)


def _constraint_name(exc: IntegrityError) -> str | None:
    diagnostic = getattr(exc.orig, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None)
    return constraint_name if isinstance(constraint_name, str) else None
