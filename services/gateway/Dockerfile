# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY packages/infera-sdk /app/packages/infera-sdk
COPY services/gateway/pyproject.toml services/gateway/uv.lock /app/services/gateway/

WORKDIR /app/services/gateway
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/services/gateway/.venv/bin:$PATH"

RUN useradd --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY --from=builder /app/packages/infera-sdk /app/packages/infera-sdk
COPY --from=builder /app/services/gateway/.venv /app/services/gateway/.venv
COPY services/gateway/app /app/services/gateway/app
COPY services/gateway/pyproject.toml /app/services/gateway/pyproject.toml

RUN chown -R appuser:appuser /app

USER appuser
WORKDIR /app/services/gateway

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
