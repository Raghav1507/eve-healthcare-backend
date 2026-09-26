"""Password hashing + JWT issuing/verification.

Two separate jobs live here:

1. PASSWORD HASHING (bcrypt)
   - One-way: hash_pw("secret") -> $2b$12$LKj...  cannot be reversed.
   - Salted: each call adds random salt → same password, different hash.
     (Prevents rainbow-table attacks where attackers precompute hashes.)
   - Slow by design (cost factor 12 = 2^12 rounds): a stolen DB makes
     brute-forcing painfully expensive for the attacker.

   NOTE: we use the `bcrypt` package directly. The older `passlib` wrapper
   is unmaintained and breaks with bcrypt>=4 — avoiding it is deliberate.

2. JWT (JSON Web Token)
   - A signed token proving "user 5 is who they say they are, until T".
   - Structure: base64(header).base64(payload).signature
   - HS256 signature = HMAC-SHA256(payload, JWT_SECRET).
     Tamper with payload → signature no longer matches → rejected.
   - STATELESS: no DB lookup needed per request; the signature IS the proof.
     Tradeoff: tokens can't be revoked early (until expiry) — acceptable
     here with a 30-min lifetime.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()


# ---------- passwords ----------

def hash_password(password: str) -> str:
    """Plaintext → bcrypt hash. Always encode() first: bcrypt works on bytes."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time check. Returns False on ANY problem (wrong password,
    corrupted hash) instead of raising — callers just get True/False.

    bcrypt.checkpw re-derives the hash from the salt embedded IN the stored
    hash and compares — so we never need the original salt separately.
    """
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # stored value isn't a valid bcrypt hash at all
        return False


# ---------- JWT ----------

def create_access_token(subject: str) -> str:
    """subject = user id as string (JWT spec puts ids in 'sub' as strings).

    Claims we add:
      sub — who the user is
      exp — expires-at (unix seconds). Without it a stolen token works forever.
      iat — issued-at, for debugging/auditing.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Verify signature + expiry. Returns the user-id (sub) or None.

    Why None instead of exceptions: auth failures are EXPECTED traffic
    (expired/absent tokens happen constantly) — returning None keeps
    the calling dependency clean. Real bugs should still raise.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        sub = payload.get("sub")
        return str(sub) if sub is not None else None
    except JWTError:
        # covers: bad signature, expired, malformed, wrong algorithm
        return None
