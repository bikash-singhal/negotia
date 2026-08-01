from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    StringConstraints,
)


def _validate_bcrypt_length(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 UTF-8 bytes.")
    return value


Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=50),
]
RegistrationPassword = Annotated[
    str,
    StringConstraints(min_length=8, max_length=72),
    AfterValidator(_validate_bcrypt_length),
]
LoginPassword = Annotated[
    str,
    StringConstraints(min_length=1, max_length=72),
    AfterValidator(_validate_bcrypt_length),
]


class UserRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Username
    password: RegistrationPassword


class UserLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Username
    password: LoginPassword


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    created_at: AwareDatetime


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
