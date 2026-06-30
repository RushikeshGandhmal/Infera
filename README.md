# Infera

Lightweight inference logging and observability for LLM applications.

Infera is a streaming multi-turn chatbot plus a Python SDK and ingestion
pipeline. It records model latency, token usage, errors, provider/model, cost,
and redacted previews without blocking the chat path.

## What It Shows

- Streaming chat UI with conversation history and model picker.
- Python SDK that wraps LLM calls and emits inference log events.
- Event-based ingestion pipeline using Redpanda.
- Transactional chat storage in Postgres.
- Analytics storage in ClickHouse.
- Grafana dashboard plus an in-app metrics page.
- Docker Compose for one-command local setup.
- Dockerfiles and Kubernetes manifests for self-hosted deployment.

## Architecture

```text
User Browser
  |
  v
Web App (Next.js)
  |
  v
Gateway API (FastAPI)
  |\
  | \__ Postgres
  |      conversations and messages
  |
  v
Infera SDK
  |
  v
Ollama / OpenRouter provider


Infera SDK
  |
  v
Ingestion API
  |
  v
Redpanda
  |
  v
Worker
  |
  v
ClickHouse
  |
  v
Grafana + in-app metrics
```

The chat path is user-facing and synchronous. The logging path is asynchronous
and designed not to slow down chat responses.

See [docs/architecture.md](docs/architecture.md) for the detailed design.

## Tech Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind |
| Gateway | Python, FastAPI, SQLAlchemy async |
| SDK | Python package (`infera`) |
| LLM access | Ollama locally, OpenRouter for hosted providers |
| Transactional DB | PostgreSQL |
| Analytics DB | ClickHouse |
| Broker | Redpanda (Kafka API) |
| Redaction | Regex by default, optional Presidio |
| Dashboards | Grafana and in-app metrics |
| Local infra | Docker Compose |
| Deployment | Docker images + Kubernetes/k3s manifests |

## Prerequisites

- Docker and Docker Compose
- Ollama with `qwen3:14b` pulled for local model calls
- Optional for host development: `uv`, Node.js, and pnpm
- Optional: `kubectl` for Kubernetes manifest rendering/deployment

## Local Quickstart

Start the full stack:

```bash
cp .env.example .env
docker compose up --build
```

By default the app uses local Ollama when no OpenRouter key is configured. Pull
the local model before starting the stack:

```bash
ollama pull qwen3:14b
```

For faster local responses on smaller machines, also pull `qwen3:8b` and select
`Qwen3 8B - Local` in the model picker:

```bash
ollama pull qwen3:8b
```

OpenRouter models are also implemented in the model picker. They require a valid
`OPENROUTER_API_KEY`; without one, the local Ollama model is the default path.

Open:

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| Gateway API | http://localhost:8000 |
| Ingestion API | http://localhost:8001 |
| Grafana | http://localhost:3001 |
| Redpanda Console | http://localhost:8080 |

Grafana uses `admin / admin` locally.

Stop the stack:

```bash
docker compose down
```

Delete local data volumes:

```bash
docker compose down -v
```

## Environment

Copy `.env.example` to `.env`.

Important values:

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `auto`, `ollama`, `openrouter`, or `mock` |
| `OPENROUTER_API_KEY` | Optional; enables real model calls through OpenRouter |
| `OLLAMA_BASE_URL` | Local Ollama OpenAI-compatible endpoint |
| `OLLAMA_MODEL` | Local fallback/default model |
| `DEFAULT_MODEL` | Model used when the client does not send one |
| `INGESTION_URL` | Where the SDK sends inference logs |
| `POSTGRES_*` | Gateway conversation database |
| `CLICKHOUSE_*` | Metrics database |
| `KAFKA_BOOTSTRAP_SERVERS` | Redpanda/Kafka connection |
| `WEB_PORT` | Host port for the web app |

In `auto` mode, the gateway uses OpenRouter when `OPENROUTER_API_KEY` is set.
If the key is missing, it uses local Ollama. If OpenRouter fails before a stream
starts, the gateway can fall back to `OLLAMA_MODEL`.

## Data Model

Postgres stores chat state:

- `conversations`: title, status, selected/last model, timestamps
- `messages`: role, content, status, token counts, linked request ID

ClickHouse stores inference logs:

- request/session/conversation IDs
- provider and model
- status and error details
- latency and time to first token
- token usage and optional cost
- redacted input/output previews
- metadata JSON

The ClickHouse table definition lives in
`infra/clickhouse/init/01_inference_logs.sql`.

## Reliability

- The SDK queues logs in a bounded buffer and ships them in the background.
- Chat does not wait for log ingestion.
- The ingestion API returns `503` if the broker is unavailable, so SDK retries
  can keep trying.
- The worker commits Redpanda offsets only after ClickHouse insert succeeds.
- Bad events go to a dead-letter topic.
- ClickHouse uses a replacing table so duplicate deliveries can collapse.

## Redaction

The SDK can optionally redact previews before shipping. The worker also redacts
previews before ClickHouse storage. The default redactor handles common structured
PII such as emails, phone numbers, SSNs, cards, and IPs. Presidio can be enabled
for deeper detection.

## Metrics

Grafana dashboard:

- request volume
- error rate
- p50/p95/p99 latency
- streaming time to first token
- provider/model breakdown
- token and cost views

In-app metrics page:

```text
http://localhost:3000/metrics
```

## Docker Images

Build production images from the repository root:

```bash
docker build -f services/gateway/Dockerfile -t infera-gateway:local .
docker build -f services/ingestion/Dockerfile -t infera-ingestion:local .
docker build -f apps/web/Dockerfile -t infera-web:local .
```

The ingestion worker reuses the ingestion image with:

```bash
python -m app.consumer
```

## Kubernetes

Kubernetes manifests live in `infra/k8s`. They are included as deployment assets
and can be rendered/validated locally, but the demo path is Docker Compose.

The Kubernetes manifests assume hosted model access through OpenRouter. Local
Ollama is intentionally a local development path; to use Ollama on Kubernetes,
deploy Ollama in-cluster or point `OLLAMA_BASE_URL` at a reachable Ollama
service. A real deployment should set a valid `OPENROUTER_API_KEY` secret.

Render the reusable base:

```bash
kubectl kustomize infra/k8s/base
```

Render the production overlay:

```bash
kubectl kustomize infra/k8s/overlays/production
```

Before deploying production, replace placeholder values in
`infra/k8s/overlays/production`:

- `ghcr.io/your-github-user/...`
- `infera.your-domain.example`
- `api.infera.your-domain.example`

Then apply:

```bash
kubectl apply -k infra/k8s/overlays/production
```

For this demo, deployment to a live cluster is not required; the manifests are
kept readable so the deployment shape can be reviewed.

The manifests include:

- app deployments and services
- Postgres
- ClickHouse
- Redpanda
- Redpanda topic creation job
- web/API ingress
- production overlay for domains and image registry names

## Tests And Checks

Python SDK:

```bash
cd packages/infera-sdk
uv run pytest
uv run --extra dev ruff check .
```

Ingestion:

```bash
cd services/ingestion
uv run pytest
uv run --extra dev ruff check .
```

Gateway:

```bash
cd services/gateway
uv run --extra dev pytest
uv run --extra dev ruff check .
```

Web:

```bash
cd apps/web
pnpm lint
pnpm exec tsc --noEmit
pnpm build
pnpm audit --prod
```

Kubernetes schema validation:

```bash
kubectl kustomize infra/k8s/overlays/production > /tmp/infera-k8s.yaml
docker run --rm -v /tmp/infera-k8s.yaml:/rendered.yaml:ro \
  ghcr.io/yannh/kubeconform:latest -strict -summary /rendered.yaml
```

## Project Structure

```text
Infera/
├── apps/web/               # Next.js chat UI and metrics page
├── docs/                   # architecture notes
├── infra/                  # Docker Compose, ClickHouse, Grafana, Kubernetes
├── packages/infera-sdk/    # Python SDK
├── scripts/                # local dev runner
├── services/gateway/       # FastAPI chat and metrics API
└── services/ingestion/     # ingestion API and Redpanda worker
```

## Tradeoffs

- FastAPI keeps streaming and async service code simple.
- Redpanda gives the pipeline Kafka semantics with easier local operations.
- ClickHouse is more complex than Postgres, but much better for metrics queries.
- The SDK prioritizes chat latency over perfect log retention.
- The Kubernetes setup is plain Kustomize instead of Helm so it is easy to read.

## Future Improvements

- Add Alembic migrations for Postgres.
- Add OpenTelemetry tracing.
- Add auth for the app and APIs.
- Add CI for tests, image builds, manifest validation, and GHCR pushes.
- Add managed secret handling for production.
- Add cost lookup/enrichment for providers that do not return cost directly.
