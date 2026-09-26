# EVE Healthcare — Database Design

## Tables

1. **users** — id (PK), email (unique), full_name, hashed_password, created_at
2. **diagnostic_centres** — id (PK), name, location, created_at
3. **medical_tests** — id (PK), name, description
4. **centre_tests** (join table) — id (PK), centre_id (FK), test_id (FK), price
5. **bookings** — id (PK), user_id (FK), centre_test_id (FK), appointment_datetime, amount, status (PENDING/CONFIRMED/FAILED/CANCELLED), created_at
6. **payments** — id (PK), booking_id (FK, UNIQUE), amount, status (SUCCESS/FAILED), provider_event_id (UNIQUE), created_at

## Relationships

- User → Bookings: 1:N
- Centre ↔ Tests: N:M via `centre_tests` (price lives here, per centre)
- Booking → Payment: 1:1 (`payments.booking_id` is UNIQUE)
- `payments.provider_event_id` is UNIQUE — this is the idempotency guard for webhooks

## Key design decisions

- `bookings.amount` is a **snapshot** of the price at booking time — not looked up live from `centre_tests`, so old bookings aren't affected if prices change later.
- `centre_test_id` on bookings (not separate `centre_id`/`test_id`) ensures a booking can only reference a real, existing centre+test+price combination.
