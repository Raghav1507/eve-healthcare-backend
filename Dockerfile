# Python 3.12 slim = small image, matches local dev version.
FROM python:3.12-slim

# Don't write .pyc files, don't buffer stdout (logs appear immediately
# in `docker compose logs` instead of hanging around in a buffer).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies FIRST (not with the code): pip caches this layer, so editing
# a .py file does NOT re-download/reinstall all packages on rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then the application. Order matters only for cache speed, not correctness.
COPY alembic.ini pytest.ini ./
COPY alembic ./alembic
COPY app ./app
COPY tests ./tests

EXPOSE 8000

# On container start: apply migrations, THEN serve.
# `&&` guarantees the API never starts against a schema it doesn't match.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
