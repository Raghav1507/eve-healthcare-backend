"""FastAPI application entry point.

Run:  uvicorn app.main:app --reload
Then: http://127.0.0.1:8000/docs  (auto-generated Swagger UI)
"""
from fastapi import FastAPI

from app.routers import auth_routes, bookings, centres, payments, webhooks

app = FastAPI(
    title="EVE Healthcare — Diagnostic Booking & Payments API",
    version="0.1.0",
    description="Backend for diagnostic test booking with simulated payments.",
)

# Routers are modular: each feature file mounts its own URLs.
# prefix="/auth" + router's own "/signup" → full path "/auth/signup".
# tags= groups them in Swagger UI — reviewers of 'API design' love a tidy /docs.
app.include_router(auth_routes.router)
app.include_router(centres.router)
app.include_router(bookings.router)
app.include_router(payments.router)
app.include_router(webhooks.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe: is the process up? (Used by Docker later.)"""
    return {"status": "ok"}
