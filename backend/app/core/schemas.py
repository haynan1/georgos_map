"""Reusable request/response building blocks."""

from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
)

from app.security.passwords import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH


class RequestModel(BaseModel):
    """Unknown fields are rejected: silently ignoring them hides client bugs and
    mass-assignment attempts (e.g. a stray ``role`` in a profile update)."""

    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _require_visible_characters(value: SecretStr) -> SecretStr:
    if not value.get_secret_value().strip():
        raise ValueError("a senha não pode ser composta apenas por espaços")
    return value


Email = Annotated[EmailStr, Field(max_length=320), AfterValidator(str.lower)]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
OrganizationName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)
]
NewPassword = Annotated[
    SecretStr,
    Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH),
    AfterValidator(_require_visible_characters),
]
# Existing passwords are only length-capped: policy changes must never lock people out.
AnyPassword = Annotated[SecretStr, Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)]
OpaqueToken = Annotated[str, StringConstraints(min_length=16, max_length=128)]
