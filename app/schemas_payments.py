"""Payment schemas."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.types import Id


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booking_id: Id
    # Our MOCK control: force the provider's answer. None = random.
    # (Real webhooks wouldn't have this — it exists so tests are deterministic.)
    outcome: Literal["SUCCESS", "FAILED"] | None = None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Id
    booking_id: Id
    # Decimal, NOT str: Pydantic v2 strict-types the field - a str annotation
    # rejects Decimal input at response serialization (we hit this: HTTP 500
    # AFTER the row committed). Decimal keeps money exact (no float rounding).
    amount: Decimal
    status: str
    created_at: datetime
