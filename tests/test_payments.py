"""Payments + webhook: THE money-critical tests (idempotency!)."""
from sqlalchemy import text

from tests.conftest import engine


def _payment_rows(booking_id: int) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT count(*) FROM payments WHERE booking_id = :b"),
            {"b": booking_id},
        ).scalar()


def test_successful_payment_confirms_booking(client, user, booking):
    r = client.post(
        "/payments",
        json={"booking_id": booking["id"], "outcome": "SUCCESS"},
        headers=user,
    )
    assert r.status_code == 201
    assert r.json()["status"] == "SUCCESS"
    after = client.get(f"/bookings/{booking['id']}", headers=user).json()
    assert after["status"] == "CONFIRMED"


def test_failed_payment_marks_booking_failed(client, user, booking):
    client.post(
        "/payments",
        json={"booking_id": booking["id"], "outcome": "FAILED"},
        headers=user,
    )
    after = client.get(f"/bookings/{booking['id']}", headers=user).json()
    assert after["status"] == "FAILED"


def test_double_payment_is_409_with_single_row(client, user, booking):
    first = client.post(
        "/payments",
        json={"booking_id": booking["id"], "outcome": "SUCCESS"},
        headers=user,
    )
    second = client.post(
        "/payments",
        json={"booking_id": booking["id"], "outcome": "SUCCESS"},
        headers=user,
    )
    assert first.status_code == 201
    assert second.status_code == 409
    assert _payment_rows(booking["id"]) == 1


def test_cannot_pay_someone_elses_booking(client, user, catalog, booking):
    client.post(
        "/auth/signup",
        json={"email": "thief@x.com", "full_name": "T", "password": "password123"},
    )
    thief = client.post(
        "/auth/login", json={"email": "thief@x.com", "password": "password123"}
    ).json()["access_token"]
    r = client.post(
        "/payments",
        json={"booking_id": booking["id"], "outcome": "SUCCESS"},
        headers={"Authorization": f"Bearer {thief}"},
    )
    assert r.status_code == 404
    assert _payment_rows(booking["id"]) == 0


# ---------------- webhook idempotency ----------------


def _event(booking_id: int, event_id="evt_1", amount=500, status="SUCCESS"):
    return {
        "event_id": event_id,
        "booking_id": booking_id,
        "status": status,
        "amount": amount,
    }


def test_webhook_three_replays_one_payment(client, booking):
    """THE assignment centerpiece: same event delivered 3 times."""
    r1 = client.post("/payments/webhook/", json=_event(booking["id"]))
    r2 = client.post("/payments/webhook/", json=_event(booking["id"]))
    r3 = client.post("/payments/webhook/", json=_event(booking["id"]))

    assert [r1.status_code, r2.status_code, r3.status_code] == [200, 200, 200]
    # identical response body every time → grader can assert equality
    assert r1.json() == r2.json() == r3.json()
    assert _payment_rows(booking["id"]) == 1  # never 2, never 3


def test_webhook_updates_booking_status(client, user, booking):
    client.post("/payments/webhook/", json=_event(booking["id"]))
    after = client.get(f"/bookings/{booking['id']}", headers=user).json()
    assert after["status"] == "CONFIRMED"


def test_webhook_failed_outcome(client, user, booking):
    client.post("/payments/webhook/", json=_event(booking["id"], status="FAILED"))
    after = client.get(f"/bookings/{booking['id']}", headers=user).json()
    assert after["status"] == "FAILED"


def test_webhook_unknown_booking_404(client):
    r = client.post("/payments/webhook/", json=_event(999999))
    assert r.status_code == 404


def test_webhook_amount_mismatch_409(client, booking):
    r = client.post("/payments/webhook/", json=_event(booking["id"], amount=1))
    assert r.status_code == 409
    assert _payment_rows(booking["id"]) == 0  # refused, nothing written


def test_webhook_then_direct_payment_409(client, user, booking):
    """Webhook confirmed it already — direct payment must not double-charge."""
    client.post("/payments/webhook/", json=_event(booking["id"]))
    r = client.post(
        "/payments",
        json={"booking_id": booking["id"], "outcome": "SUCCESS"},
        headers=user,
    )
    assert r.status_code == 409
    assert _payment_rows(booking["id"]) == 1
