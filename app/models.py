"""SQLAlchemy ORM models — the actual tables of our database.

Mental model: each class = one table, each attribute = one column.
SQLAlchemy reads this file and can (a) generate SQL and (b) let Alembic
'autogenerate' a migration that matches these classes exactly.

Design rationale lives in DESIGN.md. Key rules enforced here:
- Money is NUMERIC(10,2), never FLOAT (floats round: 0.1+0.2=0.30000000000000004).
- payments.booking_id is UNIQUE → the database itself makes a second
  payment for the same booking impossible (idempotency line of defense #1).
- payments.provider_event_id is UNIQUE → a replayed webhook event cannot
  insert twice (idempotency line of defense #2).
- bookings.amount is a price SNAPSHOT taken at booking time.
"""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BookingStatus(str, enum.Enum):
    """Allowed booking states. Using str-enum so values compare/serialize
    as plain strings ('PENDING') in JSON responses for free."""

    PENDING = "PENDING"        # booking created, payment not yet done
    CONFIRMED = "CONFIRMED"    # payment succeeded
    FAILED = "FAILED"          # payment failed
    CANCELLED = "CANCELLED"    # user/centre cancelled


class PaymentStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique=True adds a DB constraint: two signups with the same email
    # will be REJECTED by PostgreSQL itself, not just by our Python code.
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    # NEVER store plaintext passwords — this holds the bcrypt hash.
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")


class DiagnosticCentre(Base):
    __tablename__ = "diagnostic_centres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    centre_tests: Mapped[list["CentreTest"]] = relationship(back_populates="centre")


class MedicalTest(Base):
    __tablename__ = "medical_tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    centre_tests: Mapped[list["CentreTest"]] = relationship(back_populates="test")


class CentreTest(Base):
    """Junction table: 'this centre offers this test at this price'.

    price lives HERE (not on MedicalTest) because the same test costs
    differently at different centres — e.g. CBC = ₹500 at Lab A, ₹800 at Lab B.
    """

    __tablename__ = "centre_tests"
    # A centre cannot list the same test twice (e.g. via a double-click bug).
    __table_args__ = (
        UniqueConstraint("centre_id", "test_id", name="uq_centre_test"),
        CheckConstraint("price >= 0", name="ck_centre_test_price_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    centre_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_centres.id", ondelete="CASCADE"), index=True
    )
    test_id: Mapped[int] = mapped_column(
        ForeignKey("medical_tests.id", ondelete="CASCADE"), index=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    centre: Mapped["DiagnosticCentre"] = relationship(back_populates="centre_tests")
    test: Mapped["MedicalTest"] = relationship(back_populates="centre_tests")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        # Booking amount must never be negative — DB-level guard.
        CheckConstraint("amount >= 0", name="ck_booking_amount_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    # One FK (not centre_id + test_id) ⇒ a booking can ONLY reference a real
    # centre+test+price row. Impossible to book "test 5 at centre 99" if that
    # combination isn't offered.
    centre_test_id: Mapped[int] = mapped_column(
        ForeignKey("centre_tests.id", ondelete="RESTRICT"), index=True
    )
    appointment_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # SNAPSHOT of centre_tests.price at booking moment. If the centre raises
    # prices tomorrow, historical bookings still show what was agreed.
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"),
        default=BookingStatus.PENDING,   # app-level default on INSERT
        server_default="PENDING",        # DB-level default (raw SQL inserts too)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="bookings")
    centre_test: Mapped["CentreTest"] = relationship()
    payment: Mapped["Payment | None"] = relationship(
        back_populates="booking", uselist=False
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        # IDEMPOTENCY GUARD #1: at most one payment row per booking,
        # enforced by PostgreSQL — even if our Python code has a bug.
        UniqueConstraint("booking_id", name="uq_payment_booking"),
        # IDEMPOTENCY GUARD #2: a replayed provider event (same event id)
        # can never insert a second row.
        UniqueConstraint("provider_event_id", name="uq_payment_event"),
        CheckConstraint("amount >= 0", name="ck_payment_amount_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status")
    )
    # ID from the payment provider carried by the webhook. NULL is allowed
    # for locally-initiated payments; when present it must be unique
    # (PostgreSQL ignores NULLs in unique checks, so multiple NULL rows are OK).
    provider_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    booking: Mapped["Booking"] = relationship(back_populates="payment")
