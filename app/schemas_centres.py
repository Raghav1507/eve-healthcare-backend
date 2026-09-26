"""Schemas for centres & tests endpoints."""
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.types import Id


class CentreCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields → 422

    name: str = Field(min_length=1, max_length=120)
    location: str = Field(min_length=1, max_length=255)


class CentreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Id
    name: str
    location: str


class TestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class TestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Id
    name: str
    description: str | None


class OfferCreate(BaseModel):
    """A centre starts offering an existing test at a price."""
    model_config = ConfigDict(extra="forbid")

    test_id: Id
    # Decimal (not float): money. decimal_places=2 → 0.001 gets a clean 422
    # instead of being silently rounded by NUMERIC(10,2) to 0.00 (a free test!)
    price: Decimal = Field(gt=0, le=1_000_000, decimal_places=2)


class OfferOut(BaseModel):
    id: Id
    test_id: Id
    centre_id: Id
    price: Decimal


class CentreDetail(CentreOut):
    """Centre + the tests it offers (one response, no N+1 round trips)."""
    tests: list[OfferOut] = []
