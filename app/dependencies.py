"""Shared FastAPI dependencies — reusable 'givens' injected into endpoints.

A dependency is just a function FastAPI calls (and caches per-request)
when an endpoint declares Depends(that_function). The beauty: FastAPI
resolves nested dependencies automatically — get_current_user needs a
db AND a token, so FastAPI fetches both before calling it.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_access_token

# OAuth2PasswordBearer: reads "Authorization: Bearer <token>" header.
# - If the header is MISSING → FastAPI itself raises 401 before our code runs.
# - tokenUrl powers Swagger's "Authorize" button (docs URL we'll add later).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """The GUARD every protected endpoint will use.

    Flow:
      Authorization header → decode+verify JWT → load user from DB → User
      any failure → HTTP 401 (never 500: bad tokens are EXPECTED traffic)

    Why load the user from DB even though JWT says sub=5?
    1. User might have been DELETED after the token was issued — a pure
       stateless check would still let a ghost in.
    2. Endpoints need fresh attributes (email, name) anyway.
    """
    user_id = decode_access_token(token)

    if user_id is None:
        # 401 = "who are you?" (WWW-Authenticate tells clients HOW to auth)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user_id.isdigit():
        # Belt-and-suspenders: sub should always be numeric (we mint it).
        # Anything else is a forged/corrupt token — reject, don't int() crash.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, int(user_id))
    if user is None:
        # Token valid but account gone (deleted user) → still unauthorized
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
