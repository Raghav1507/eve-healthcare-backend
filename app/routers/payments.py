"""Simulated payment endpoint.

Flow:
  POST /payments/ {booking_id, outcome}
        ↓
  auth → booking exists? → yours? → still PENDING?
        ↓
  INSERT payment + UPDATE booking.status   ← ONE commit = ONE transaction
        ↓
  return {payment status, booking status}
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Booking, BookingStatus, Payment, PaymentStatus, User
from app.schemas_payments import PaymentCreate, PaymentOut

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Payment:
    booking = db.get(Booking, payload.booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    # Ownership: someone else's booking id → same 404 (no existence leak).
    if booking.user_id != user.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    # One attempt per booking: CONFIRMED/FAILED/CANCELLED are terminal for
    # payment purposes → 409. This is the RULE; the DB unique constraint
    # below is the ENFORCEMENT if two requests race past this check.
    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Booking is {booking.status.value}, not payable",
        )

    # Simulated provider answer: explicit for tests, random otherwise.
    outcome = payload.outcome or (
        "SUCCESS" if secrets.randbelow(2) == 0 else "FAILED"
    )

    payment = Payment(
        booking_id=booking.id,
        amount=booking.amount,          # copy of the SNAPSHOT — never client input
        status=PaymentStatus(outcome),
    )
    db.add(payment)
    # Move the booking in the SAME transaction as the payment insert:
    # both persist or neither does. A half-state (paid but PENDING) would
    # corrupt money records — this is exactly what transactions are FOR.
    booking.status = (
        BookingStatus.CONFIRMED if outcome == "SUCCESS" else BookingStatus.FAILED
    )
    try:
        db.commit()
    except IntegrityError:
        # uq_payment_booking fired: a concurrent request inserted first.
        db.rollback()
        raise HTTPException(status_code=409, detail="Payment already exists")
    db.refresh(payment)
    return payment
