"""Bookings: creation rules, ownership, price snapshot."""


def test_create_booking_snapshots_price_and_starts_pending(
    client, user, catalog
):
    r = client.post(
        "/bookings",
        json={
            "centre_test_id": catalog["offer_id"],
            "appointment_datetime": "2027-06-01T10:00:00Z",
        },
        headers=user,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["amount"] == "500.00"  # price from DB, not client
    assert body["status"] == "PENDING"


def test_client_cannot_set_amount_or_status(client, user, catalog):
    """Even if the body smuggles amount/status, server must ignore them."""
    r = client.post(
        "/bookings",
        json={
            "centre_test_id": catalog["offer_id"],
            "appointment_datetime": "2027-06-01T10:00:00Z",
            "amount": 1,
            "status": "CONFIRMED",
        },
        headers=user,
    )
    # extra="forbid" rejects loudly (422) — better than silently ignoring
    assert r.status_code == 422


def test_booking_requires_auth(client, catalog):
    r = client.post(
        "/bookings",
        json={
            "centre_test_id": catalog["offer_id"],
            "appointment_datetime": "2027-06-01T10:00:00Z",
        },
    )
    assert r.status_code == 401


def test_unknown_offer_404_and_past_date_422(client, user):
    assert client.post(
        "/bookings",
        json={
            "centre_test_id": 999999,
            "appointment_datetime": "2027-06-01T10:00:00Z",
        },
        headers=user,
    ).status_code == 404
    assert client.post(
        "/bookings",
        json={"centre_test_id": 1, "appointment_datetime": "2020-01-01T10:00:00Z"},
        headers=user,
    ).status_code == 422


def test_ownership_user_cannot_read_others_booking(client, user, catalog, booking):
    # second user
    client.post(
        "/auth/signup",
        json={"email": "other@x.com", "full_name": "O", "password": "password123"},
    )
    other = client.post(
        "/auth/login", json={"email": "other@x.com", "password": "password123"}
    ).json()["access_token"]
    other_h = {"Authorization": f"Bearer {other}"}

    # owner sees it, stranger gets 404 (not 403 — don't leak existence)
    assert client.get(f"/bookings/{booking['id']}", headers=user).status_code == 200
    assert (
        client.get(f"/bookings/{booking['id']}", headers=other_h).status_code == 404
    )
    # and stranger's list is empty
    assert client.get("/bookings", headers=other_h).json() == []
