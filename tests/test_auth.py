"""Auth: signup, login, JWT guard, validation edge cases."""


def test_signup_then_login_works(client):
    r = client.post(
        "/auth/signup",
        json={"email": "a@x.com", "full_name": "A", "password": "password123"},
    )
    assert r.status_code == 201
    assert "access_token" in r.json()

    r = client.post(
        "/auth/login", json={"email": "a@x.com", "password": "password123"}
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_duplicate_email_is_409(client):
    body = {"email": "dup@x.com", "full_name": "D", "password": "password123"}
    assert client.post("/auth/signup", json=body).status_code == 201
    # case-insensitive duplicate: EmailStr + normalization must catch this
    assert client.post(
        "/auth/signup", json={**body, "email": "DUP@X.com"}
    ).status_code == 409


def test_invalid_email_and_short_password_are_422(client):
    assert client.post(
        "/auth/signup",
        json={"email": "not-an-email", "full_name": "X", "password": "password123"},
    ).status_code == 422
    assert client.post(
        "/auth/signup",
        json={"email": "ok@x.com", "full_name": "X", "password": "short"},
    ).status_code == 422


def test_login_errors_identical_no_enumeration(client):
    """Unknown email and wrong password must be INDISTINGUISHABLE —
    otherwise attackers can enumerate which emails have accounts."""
    client.post(
        "/auth/signup",
        json={"email": "real@x.com", "full_name": "R", "password": "password123"},
    )
    unknown = client.post(
        "/auth/login", json={"email": "ghost@x.com", "password": "whatever123"}
    )
    wrong_pw = client.post(
        "/auth/login", json={"email": "real@x.com", "password": "wrongwrong1"}
    )
    assert unknown.status_code == wrong_pw.status_code == 401
    assert unknown.json() == wrong_pw.json()


def test_me_requires_valid_token(client, user):
    assert client.get("/auth/me").status_code == 401
    assert client.get(
        "/auth/me", headers={"Authorization": "Bearer garbage.token.here"}
    ).status_code == 401
    me = client.get("/auth/me", headers=user)
    assert me.status_code == 200
    assert "hashed_password" not in me.json()  # response whitelist works
