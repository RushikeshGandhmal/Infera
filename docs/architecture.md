# Infera Architecture

Infera is split into two paths: the chat path, which must feel fast to the user,
and the logging path, which records observability data without slowing chat down.

## System Flow

```text
Browser
  |
  v
Next.js web app
  |
  v
Gateway API
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
Grafana and in-app metrics
```

## Chat Path

The chat path is the user-facing path.

1. The browser sends a message to the Next.js app.
2. The web app calls the Gateway API.
3. The gateway stores the user message in Postgres.
4. The gateway sends the conversation context to the Infera SDK.
5. The SDK calls the selected model through Ollama or OpenRouter.
6. The response streams back to the browser.
7. The final assistant message is saved in Postgres.

Postgres is used here because conversations need consistent reads and writes.
When a user opens a previous conversation, Postgres is the source of truth.

## Logging Path

The logging path is separate from the chat path.

1. The SDK captures metadata for every model call.
2. It queues the log event in a bounded local buffer.
3. A background shipper sends logs to the ingestion API.
4. The ingestion API validates the event and writes it to Redpanda.
5. The worker consumes events from Redpanda.
6. The worker redacts preview text and writes the event to ClickHouse.
7. Grafana and the in-app metrics page query ClickHouse.

This path is intentionally asynchronous. If ingestion or ClickHouse is slow, the
chat response should still continue.

## Model Providers

The gateway runs in `auto` provider mode by default:

- if `OPENROUTER_API_KEY` is configured, OpenRouter is used for hosted models
- if no OpenRouter key is configured, local Ollama is used
- if OpenRouter fails before a streamed response starts, the gateway can fall
  back to the configured Ollama model

This keeps local demos independent of hosted API keys while preserving
multi-provider support through OpenRouter.

## Storage Choices

Postgres stores transactional chat data:

- conversations
- messages
- conversation status
- message status
- request IDs that link messages to inference logs

ClickHouse stores analytics data:

- latency
- time to first token
- token counts
- cost
- provider and model
- status and errors
- short redacted previews

This split keeps chat simple and consistent while making metrics queries fast.

## Reliability Model

The SDK uses a bounded buffer and retrying background shipper. Logging is best
effort from the chat process's point of view: losing a log is better than making
the user wait for a reply.

The ingestion worker is at-least-once:

- it reads from Redpanda
- writes to ClickHouse
- commits offsets only after storage succeeds

ClickHouse uses a replacing table keyed by request identity and timestamp, so
duplicate deliveries can collapse during merges.

Malformed events are sent to a dead-letter topic so one bad message does not
block the whole pipeline.

## Redaction

Only short input and output previews are stored in ClickHouse. The worker redacts
common PII before storage. Presidio can be enabled for deeper detection, while a
regex redactor remains available by default.

The raw full prompt and full model response are not stored in ClickHouse by this
pipeline.

## Local Deployment

Local setup uses Docker Compose for the full stack:

- web app
- gateway API
- ingestion API
- ingestion worker
- Postgres
- ClickHouse
- Redpanda
- Redpanda Console
- Grafana

The stack starts with:

```bash
docker compose up --build
```

## Kubernetes Deployment

The Kubernetes manifests live under `infra/k8s`.

- `base` contains reusable manifests for the app, databases, broker, services,
  and ingress.
- `overlays/production` changes image names and public domains for a real
  deployment.

The app images are built from the Dockerfiles in:

- `apps/web/Dockerfile`
- `services/gateway/Dockerfile`
- `services/ingestion/Dockerfile`

The ingestion worker reuses the ingestion image and starts with a different
command: `python -m app.consumer`.

## Tradeoffs

- FastAPI was chosen for async streaming and simple Python service code.
- Redpanda keeps the log pipeline event-based without requiring a large Kafka
  setup.
- ClickHouse is more operationally complex than Postgres, but it is a better fit
  for high-volume metrics.
- The local SDK buffer protects chat latency, but it can drop logs under sustained
  ingestion outages.
- The Kubernetes manifests are simple and self-contained instead of a Helm chart;
  this keeps the assignment easier to review.

## Future Improvements

- Add Alembic migrations for Postgres schema changes.
- Add OpenTelemetry traces across gateway, ingestion, worker, and ClickHouse.
- Add authentication for the web UI and API.
- Add retention settings per environment.
- Add CI to build images, run tests, validate manifests, and push to GHCR.
- Add production secret management instead of placeholder Kubernetes secrets.
