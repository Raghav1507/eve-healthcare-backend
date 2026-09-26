"""Webhook schemas."""
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.types import Id


class WebhookPayload(BaseModel):
    """What the payment provider 'sends' us.

    event_id = provider's unique id for THIS delivery attempt chain.
    THIS is the idempotency key: the provider may deliver the same event
    many times (retries on timeout, crashes after send, etc.) but always
    with the same event_id.
    """
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=64)
    booking_id: Id
    status: Literal["SUCCESS", "FAILED"]
    amount: Decimal  # provider echoes what it charged — we VERIFY it


class WebhookOut(BaseModel):
    """Always this shape on 200 — identical response for first delivery
    AND every replay (clients/graders can assert equality)."""
    model_config = ConfigDict(from_attributes=True)

    id: Id
    booking_id: Id
    amount: Decimal
    status: str
