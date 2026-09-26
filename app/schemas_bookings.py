"""Booking schemas — API contract for creating/reading bookings."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.types import Id


class BookingCreate(BaseModel):
    """Client picks: WHICH test-at-which-centre + WHEN.
    amount/status are NEVER accepted from the client - the server
    computes them (price tampering via request body = impossible)."""
    model_config = ConfigDict(extra="forbid")  # "amount":1 in body -> 422

    centre_test_id: Id
    appointment_datetime: datetime

    @model_validator(mode="after")
    def appointment_must_be_future(self) -> "BookingCreate":
        # 422 at the door for past dates — cheaper than a pointless DB write.
        # (aware vs naive: treat naive as UTC to keep comparison valid)
        now = datetime.now(self.appointment_datetime.tzinfo) if self.appointment_datetime.tzinfo else datetime.utcnow()
        if self.appointment_datetime <= now:
            raise ValueError("appointment_datetime must be in the future")
        return self


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Id
    centre_test_id: Id
    appointment_datetime: datetime
    amount: Decimal
    status: str
