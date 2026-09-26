# EVE Healthcare — Diagnostic Booking & Payments Backend

A REST API for booking diagnostic tests at medical centres, with simulated
payments and an **idempotent payment webhook**. Built with **FastAPI,
PostgreSQL, SQLAlchemy 2.0, and Alembic**.

---

## 1. How to Run the Project Locally

### Prerequisites

| Tool | Version tested | Purpose |
|---|---|---|
| Python | 3.12.8 | Runtime |
| Docker | 27.x | Runs PostgreSQL (no local PG install needed) |

### Step-by-step

```powershell
# 1. Clone and enter the repo
git clone <repo-url>
cd eve-healthcare-backend

# 2. Create an isolated virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1        # macOS/Linux: source venv/bin/activate

# 3. Install dependencies (pinned in requirements.txt)
pip install -r requirements.txt

# 4. Start PostgreSQL in Docker
docker run -d --name eve-pg `
  -e POSTGRES_USER=eve `
  -e POSTGRES_PASSWORD=eve_secret `
  -e POSTGRES_DB=eve_healthcare `
  -p 5433:5432 `
  postgres:16

# 5. Create your .env (see below), then apply the database migration
alembic upgrade head                # creates all 6 tables

# 6. Run the server
uvicorn app.main:app --reload
```

- **API root:** http://127.0.0.1:8000
- **Interactive docs (Swagger UI):** http://127.0.0.1:8000/docs
- **Health check:** `GET /health` → `{"status":"ok"}`

### `.env`

```ini
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5433/eve_healthcare
JWT_SECRET=generate_a_random_secret_here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30
```

> `.env` is git-ignored on purpose — secrets must never be committed.
> Note the **5433** host port: the container maps `5433 → 5432`.

### Run the tests

```powershell
pytest
```

Tests use a **separate database** (`eve_healthcare_test`, created
automatically) and rebuild the schema before every test, so your dev data
is never touched. Expected: **20 passed**.

---

## 2. API Endpoints & Example Requests

All request/response bodies are JSON. 🔒 = requires
`Authorization: Bearer <token>` (from signup/login).

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | — | Register, returns JWT |
| POST | `/auth/login` | — | Login, returns JWT |
| GET | `/auth/me` | 🔒 | Current user profile |

```powershell
# Signup (201)
curl -X POST http://127.0.0.1:8000/auth/signup `
  -H "Content-Type: application/json" `
  -d '{"email":"raghav@example.com","full_name":"Raghav","password":"strongpass123"}'

# Login (200) -> {"access_token":"eyJ...","token_type":"bearer"}
curl -X POST http://127.0.0.1:8000/auth/login `
  -H "Content-Type: application/json" `
  -d '{"email":"raghav@example.com","password":"strongpass123"}'

# Me (200) / missing-or-bad token (401)
curl http://127.0.0.1:8000/auth/me -H "Authorization: Bearer eyJ..."
```

### Centres & Tests

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/centres` | 🔒 | Create a centre |
| GET | `/centres` | — | List centres |
| GET | `/centres/{id}` | — | Centre detail **with tests + prices** |
| POST | `/centres/tests` | 🔒 | Add a test to the global catalog |
| GET | `/centres/tests` | — | List all tests |
| POST | `/centres/{id}/tests` | 🔒 | Offer a test **at this centre** (price) |

```powershell
# Create centre (201)
curl -X POST http://127.0.0.1:8000/centres `
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" `
  -d '{"name":"Lab A","location":"Delhi"}'

# Create test (201)
curl -X POST http://127.0.0.1:8000/centres/tests `
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" `
  -d '{"name":"CBC","description":"Complete blood count"}'

# Offer test 1 at centre 1 for 500 (201)
curl -X POST http://127.0.0.1:8000/centres/1/tests `
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" `
  -d '{"test_id":1,"price":500}'

# Centre detail with its tests (200)
curl http://127.0.0.1:8000/centres/1
```

### Bookings

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/bookings` | 🔒 | Book a test (status starts `PENDING`) |
| GET | `/bookings` | 🔒 | My bookings only |
| GET | `/bookings/{id}` | 🔒 | One booking (owner only, else 404) |

```powershell
# Book (201): amount comes from the DB price, never from this body
curl -X POST http://127.0.0.1:8000/bookings `
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" `
  -d '{"centre_test_id":1,"appointment_datetime":"2027-06-01T10:00:00Z"}'
# -> {"id":1,"amount":"500.00","status":"PENDING", ...}
```

Booking status flow:

```
PENDING ──payment SUCCESS──► CONFIRMED
   │
   └────payment FAILED─────► FAILED
   │
   └────(future work)──────► CANCELLED
```

### Payments (simulated)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/payments` | 🔒 | Charge a booking → updates its status |

```powershell
# Force outcome (201); omit "outcome" for random SUCCESS/FAILED
curl -X POST http://127.0.0.1:8000/payments `
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" `
  -d '{"booking_id":1,"outcome":"SUCCESS"}'
```

### Payment Webhook (idempotent)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/payments/webhook/` | server-to-server | Provider confirms a payment; **safe to replay** |

```powershell
# Deliver the SAME event 3 times -> always 200, always identical body,
# exactly ONE payment row in the database.
curl -X POST http://127.0.0.1:8000/payments/webhook/ `
  -H "Content-Type: application/json" `
  -d '{"event_id":"evt_123","booking_id":1,"status":"SUCCESS","amount":500}'
```

### Error summary

| Code | Meaning | Examples |
|---|---|---|
| 200/201 | OK / created | success, webhook replays |
| 401 | Not authenticated | missing/expired token, bad login |
| 404 | Not found / not yours | unknown id, foreign booking |
| 409 | Conflict | duplicate email, double payment, amount mismatch |
| 422 | Validation failed | bad email, past date, huge/negative id, unknown fields |

---

## 3. Database / Schema Design

6 tables, created by Alembic migration `59698e5e0281_create_core_tables`.
Full reasoning lives in [`DESIGN.md`](DESIGN.md).

```
users                          diagnostic_centres
├─ id PK                       ├─ id PK
├─ email UNIQUE                ├─ name
├─ full_name                   └─ location
├─ hashed_password (bcrypt)
└─ created_at                  medical_tests
                               ├─ id PK
1:N                            ├─ name
└─► bookings                   └─ description
     ├─ id PK
     ├─ user_id FK ──► users   centre_tests   (junction + PRICE)
     ├─ centre_test_id FK ──►  ├─ id PK
     │        centre_tests     ├─ centre_id FK   UNIQUE(centre_id,test_id)
     ├─ appointment_datetime   ├─ test_id FK
     ├─ amount (NUMERIC 10,2)  └─ price  ◄── price lives HERE
     ├─ status ENUM                (same test, different price per centre)
     │   PENDING|CONFIRMED|FAILED|CANCELLED
     └─ created_at             payments
                               ├─ id PK
1:1                            ├─ booking_id FK  UNIQUE  ◄── guard #1
└─► payments                   ├─ amount (NUMERIC 10,2)
     ├─ status SUCCESS|FAILED  ├─ status ENUM
     ├─ provider_event_id UNIQUE ◄── guard #2 (idempotency)
     └─ created_at             └─ created_at
```

**Key decisions**

1. **N:M centre ↔ test via `centre_tests` with `price` on the junction** —
   CBC costs ₹500 at Lab A and ₹800 at Lab B; one global price would be wrong.
2. **`bookings.amount` is a price snapshot** taken at booking time — later
   price changes never rewrite history.
3. **Two UNIQUE constraints power idempotency** (belt + suspenders):
   `payments.booking_id` makes a second payment physically impossible, and
   `payments.provider_event_id` makes a replayed event insert nothing new.
   Application-level lookups return the *same* 200 body on replay so the
   provider stops retrying.
4. **Money is `NUMERIC(10,2)`, never float** — binary floats cannot
   represent 0.1 exactly; NUMERIC is base-10 and exact.
5. **FKs use `RESTRICT` on user/centre_test** so a paid booking can't be
   orphaned by deleting its parents; `CASCADE` on `centre_tests` removes
   offers when a centre/test disappears.
6. **Indexes** on every FK column and `users.email` (lookups by user/email
   stay fast as data grows).

---

## 4. Important Assumptions

1. **Payments are simulated.** `POST /payments/` is a mock provider: the
   caller (or randomness) decides SUCCESS/FAILED. No real gateway.
2. **One payment attempt per booking.** Retrying a FAILED booking means
   creating a new booking. (Simplifies money accounting; a real system
   would allow attempts keyed by attempt-id.)
3. **Price is stored per centre-test offer**; a booking stores the chosen
   `centre_test_id`, so "which centre + which test + which price" is always
   one row — impossible to book a test/centre combination that isn't offered.
4. **Webhook trust:** the endpoint has no auth/HMAC verification because the
   "provider" is simulated in-process. Amounts are still cross-checked
   against the booking (mismatch → 409, nothing written).
5. **`/centres` write endpoints require login but have no roles** — any
   authenticated user can add centres/tests. A real system would need
   admin/staff roles.
6. **Naive datetimes are treated as UTC** for the "must be future" check.
7. **`CANCELLED` is defined in the enum but not yet reachable via an
   endpoint** (no cancel API in scope).
8. **IDs are bounded to PostgreSQL INTEGER range** (`1 … 2,147,483,647`);
   anything else is rejected with 422 instead of crashing SQL with 500.

---

## 5. What I Would Improve With More Time

**Bonus engineering (planned next):**
- **Docker Compose** — one command for app + PostgreSQL (+ Redis); the DB
  container already exists, compose removes the manual `docker run`.
- **Redis caching** for hot reads (`GET /centres`, centre details) with
  invalidation on write.
- **Structured logging** (JSON) + request IDs for traceability.
- **Rate limiting** on `/auth/*` (brute-force) and `/payments/webhook`
  (retry storms).
- **Pagination, filtering, search** on list endpoints (`?page=1&size=20`,
  `?location=Delhi`).
- **Webhook HMAC signature** verification + a `webhook_events` inbox table
  (persist raw deliveries for audit/debugging).
- **Retry/backoff handling** documentation for the provider side.

**Product features:**
- Booking **cancellation** endpoint + admin **confirmation flow**.
- **Roles** (admin vs patient) for centre/test management.
- **Refresh tokens** (long-lived) + short-lived access tokens; token
  revocation list.
- **Background jobs** (e.g. appointment reminders) via a queue.

**Engineering quality:**
- CI pipeline running `pytest` on every push.
- Coverage reporting; concurrency test for the webhook race (two truly
  parallel deliveries in the suite).
- API versioning (`/v1/...`) before the first external consumer arrives.

---

## Project Structure

```
eve-healthcare-backend/
├── app/
│   ├── main.py              # FastAPI app + router mounting
│   ├── config.py            # .env → typed settings
│   ├── database.py          # engine, session, Base
│   ├── models.py            # 6 ORM tables
│   ├── security.py          # bcrypt hashing + JWT
│   ├── dependencies.py      # get_current_user guard
│   ├── types.py             # bounded Id annotation
│   ├── schemas*.py          # Pydantic request/response contracts
│   └── routers/
│       ├── auth_routes.py   # signup / login / me
│       ├── centres.py       # centres + tests catalog
│       ├── bookings.py      # booking lifecycle
│       ├── payments.py      # simulated payments
│       └── webhooks.py      # idempotent webhook
├── tests/                   # 20 pytest tests (isolated DB)
├── alembic/                 # migrations
├── DESIGN.md                # schema design notes
└── .env                     # secrets (git-ignored)
```
