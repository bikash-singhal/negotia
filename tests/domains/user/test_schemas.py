import pytest
from pydantic import ValidationError

from app.domains.user.schemas import UserLogin, UserRegister


def test_registration_strips_username_and_accepts_valid_password() -> None:
    request = UserRegister(username="  negotiator  ", password="secure-pass")

    assert request.username == "negotiator"
    assert request.password == "secure-pass"


@pytest.mark.parametrize("password", ["short", "x" * 73, "🔐" * 19])
def test_registration_rejects_password_outside_bcrypt_limits(password: str) -> None:
    with pytest.raises(ValidationError):
        UserRegister(username="negotiator", password=password)


def test_registration_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        UserRegister.model_validate(
            {
                "username": "negotiator",
                "password": "secure-pass",
                "is_admin": True,
            }
        )


def test_login_accepts_wrong_but_structurally_valid_password() -> None:
    request = UserLogin(username="negotiator", password="wrong")

    assert request.password == "wrong"
