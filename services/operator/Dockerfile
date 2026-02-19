# Build from repo root so shared/ is available. Use:
#   docker compose build --build-arg BUILDKIT_CONTEXT=../..
# Or run docker compose from repo root with context: ../..
# This file is intended to be used with context at repo root (fov-notification-service).

FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy shared and operator so "shared" dependency resolves (path = ../../shared)
COPY shared /app/shared
COPY services/operator /app/services/operator

WORKDIR /app/services/operator

# Install dependencies (no dev group for smaller image)
RUN uv sync --no-dev

# Listen on all interfaces so the container port mapping works
EXPOSE 8000
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
