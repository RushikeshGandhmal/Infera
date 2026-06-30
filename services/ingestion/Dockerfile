# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY packages/infera-sdk /app/packages/infera-sdk
COPY services/ingestion/pyproject.toml services/ingestion/uv.lock /app/services/ingestion/

WORKDIR /app/services/ingestion
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/services/ingestion/.venv/bin:$PATH"

RUN useradd --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY --from=builder /app/packages/infera-sdk /app/packages/infera-sdk
COPY --from=builder /app/services/ingestion/.venv /app/services/ingestion/.venv
COPY services/ingestion/app /app/services/ingestion/app
COPY services/ingestion/pyproject.toml /app/services/ingestion/pyproject.toml

RUN chown -R appuser:appuser /app

USER appuser
WORKDIR /app/services/ingestion

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
