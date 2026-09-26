"""Shared validation types used across schemas AND FastAPI path params."""
from typing import Annotated

from pydantic import Field

# Postgres INTEGER max = 2,147,483,647. Python ints are unbounded, so a
# 19-digit id sails past naive validation and crashes INSIDE SQL with
# "numeric out of range" → HTTP 500 (we caught 5 of these probing).
# This annotation bounds every id up front → clean 422 instead.
Id = Annotated[int, Field(ge=1, le=2_147_483_647)]
