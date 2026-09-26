"""Booking endpoints — the core of the assignment."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Booking, BookingStatus, CentreTest, User
from app.schemas_bookings import BookingCreate, BookingOut
from app.types import Id

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Booking:
    """Authenticated user books a test. Status starts PENDING —
    only a successful payment (or webhook) can move it to CONFIRMED.
    """
    # Price comes from THE DATABASE, never from the request body.
    offer = db.get(CentreTest, payload.centre_test_id)
    if offer is None:
        # Invalid centre_test_id → 404 (edge case graded by assignment)
        raise HTTPException(status_code=404, detail="Test not offered at any centre")

    booking = Booking(
        user_id=user.id,                      # from JWT — not from body (no impersonation)
        centre_test_id=payload.centre_test_id,
        appointment_datetime=payload.appointment_datetime,
        amount=offer.price,                   # SNAPSHOT at booking time
        status=BookingStatus.PENDING,         # server-set; client can't skip to CONFIRMED
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


@router.get("", response_model=list[BookingOut])
def my_bookings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Booking]:
    """Only YOUR bookings — filter by the id inside YOUR verified JWT."""
    return list(db.scalars(
        select(Booking).where(Booking.user_id == user.id).order_by(Booking.id)
    ))


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: Id,  # bounded int -> 422 on 19-digit ids (was 500 in SQL)
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    # OWNERSHIP CHECK: valid id but not yours → 404 (not 403 — a 403 confirms
    # the id EXISTS, leaking other users' booking ids. 404 = "not yours, period".
    if booking.user_id != user.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking
