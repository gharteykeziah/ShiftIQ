# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — ShiftIQ FastAPI backend
#
# Build:  docker build -t shiftiq .
# Run:    docker run -p 8000:8000 --env-file .env shiftiq
# ─────────────────────────────────────────────────────────────────────────────

# Use a slim official Python image — small download, no extras we don't need
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# ── Install system dependencies ───────────────────────────────────────────────
# libpq-dev is needed by psycopg2 to talk to PostgreSQL
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# ── Install Python dependencies ───────────────────────────────────────────────
# Copy requirements first so Docker caches this layer.
# If only your code changes (not requirements), Docker skips this step on rebuild.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# ── Copy application code ─────────────────────────────────────────────────────
COPY *.py ./
COPY scripts/ ./scripts/
COPY routers/ ./routers/
COPY services/ ./services/

# ── Runtime config ────────────────────────────────────────────────────────────
# PORT is set by AWS App Runner automatically — default to 8000 for local use
ENV PORT=8000

# Tell Python not to buffer stdout/stderr so logs appear immediately
ENV PYTHONUNBUFFERED=1

# Expose the port the app listens on
EXPOSE $PORT

# ── Start the API ─────────────────────────────────────────────────────────────
# uvicorn is the ASGI server that runs FastAPI in production
CMD uvicorn api:app --host 0.0.0.0 --port $PORT
