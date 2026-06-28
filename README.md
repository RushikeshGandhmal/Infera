# Infera

> Lightweight inference logging & observability platform for LLM applications.
> A multi-turn streaming chatbot, instrumented end-to-end by a Python SDK, with a
> near real-time event-based ingestion pipeline and dashboards.

## Why this exists

LLM applications are hard to operate: you need to know how fast each model is, how
many tokens (and dollars) you're burning, what's failing, and what users are sending —
without slowing down the chat itself. Infera captures all of that out-of-band.

## Architecture (high level)

```
Web (Next.js)  ──►  Gateway (FastAPI)  ──►  Infera SDK  ──►  OpenRouter ──► LLM
                         │  (Postgres: conversations, messages)
                         └─► logs (async, non-blocking)
                                   │
                          Ingestion API (FastAPI) ─► Redpanda ─► Worker
                                   (PII redact + enrich) ─► ClickHouse ─► Grafana
```

- **Chat path** is synchronous and user-facing.
- **Logging path** is asynchronous and never blocks chat; it survives outages via the broker.

See `docs/architecture.md` for the detailed design.

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind, shadcn/ui |
| Gateway + Ingestion | Python, FastAPI |
| SDK | Python (`infera`) |
| LLM access | OpenRouter (multi-provider) |
| Transactional DB | PostgreSQL |
| Analytics DB | ClickHouse |
| Broker | Redpanda (Kafka API) |
| PII redaction | Microsoft Presidio |
| Dashboards | Grafana |

## Prerequisites

- Docker + Docker Compose
- `uv` (Python), Node.js + pnpm (for the web app)

## Quickstart

```bash
cp .env.example .env        # then set OPENROUTER_API_KEY
make infra                  # start postgres, clickhouse, redpanda, grafana
make health                 # check everything is up
```

| Service | URL |
|---|---|
| Grafana | http://localhost:3001 (admin / admin) |
| Redpanda Console | http://localhost:8080 |
| ClickHouse HTTP | http://localhost:8123 |
| Postgres | localhost:5432 |
| Kafka (host) | localhost:19092 |

Tear down with `make down` (keeps data) or `make clean` (deletes data).

## Project structure

```
Infera/
├── docker-compose.yml      # local infrastructure
├── Makefile                # developer commands
├── infra/                  # clickhouse / postgres / grafana / k8s config
├── packages/infera-sdk/    # the instrumentation SDK
├── services/gateway/       # FastAPI chat + conversations API
├── services/ingestion/     # ingestion API + Redpanda worker
└── apps/web/               # Next.js chat UI + dashboards
```
