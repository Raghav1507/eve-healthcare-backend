"""Pydantic schemas — the CONTRACT for what clients may send and receive.

Why a separate file from models.py?
- models.py  = what the DATABASE accepts (tables, constraints)
- schemas.py = what the API accepts (validation, docs, JSON shapes)

Never expose model objects directly: User model contains hashed_password —
leaking it would let attackers crack passwords offline. Pydantic
response_model acts as a WHITELIST: only listed fields leave the server.
"""
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, field_validator


def _normalize_email(value: str) -> str:
    """Strip whitespace + lowercase. Without this, 'Raghav@X.com' and
    'raghav@x.com' become TWO different accounts (unique constraint
    compares exact bytes). Emails are treated case-insensitively in
    practice — normalize BEFORE hitting the DB."""
    return value.strip().lower()


# EmailStr = must be a valid email format (checked by email-validator lib).
# AfterValidator = transform AFTER format validation.
NormalizedEmail = Annotated[EmailStr, AfterValidator(_normalize_email)]


class UserCreate(BaseModel):
    """Request body for POST /auth/signup."""

    # extra="forbid": unknown fields (typos, attacks like "is_admin": true)
    # get a 422 instead of being silently ignored — loud beats quiet.
    model_config = ConfigDict(extra="forbid")

    email: NormalizedEmail
    full_name: str = Field(min_length=1, max_length=120)
    # bcrypt limit is 72 BYTES — reject longer at the door (422) rather than
    # crashing in hash_password. min 8 = basic password policy.
    password: str = Field(min_length=8, max_length=72)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, v: str) -> str:
        # "   " passes min_length=1 BEFORE stripping → stored empty name.
        # Strip first (mode="before"), then length rules apply to the result.
        return v.strip() if isinstance(v, str) else v


class UserLogin(BaseModel):
    """Request body for POST /auth/login.

    Note min_length=1 (not 8): we must NOT enforce the signup policy here —
    an existing user with an old 6-char password would be locked out by
    our own validation before their password is even checked.
    """

    model_config = ConfigDict(extra="forbid")

    email: NormalizedEmail
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    """Safe public shape of a user. NO password field exists here at all —
    the safest thing to never leak is something that can't be serialized."""

    # from_attributes = build from ORM object (user.id → .id), not dict
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    created_at: datetime


class Token(BaseModel):
    """What login/signup return to the client."""

    access_token: str
    token_type: str = "bearer"  # FastAPI's OAuth2 scheme reads this
