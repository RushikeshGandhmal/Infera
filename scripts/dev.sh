#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Infera — one-command local dev runner
#
# Brings up the whole backend on the host with a single command:
#   - docker infra (postgres, clickhouse, redpanda, grafana)
#   - ingestion API   (port 8001)
#   - ingestion worker
#   - gateway API      (port 8000)
#
# All Python services run on the host with localhost overrides, so the
# docker-network names in .env (postgres/clickhouse/redpanda/ingestion)
# don't need to resolve.
#
# Usage:
#   scripts/dev.sh up       start everything
#   scripts/dev.sh down     stop the host services (leaves docker infra up)
#   scripts/dev.sh logs     tail all service logs
#   scripts/dev.sh status   show what's running
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/.run"
mkdir -p "$RUN_DIR"

GATEWAY_DIR="$ROOT/services/gateway"
INGESTION_DIR="$ROOT/services/ingestion"

# Host-side connection overrides (docker names -> localhost)
export POSTGRES_HOST=localhost
export CLICKHOUSE_HOST=localhost
export KAFKA_BOOTSTRAP_SERVERS=localhost:19092
export INGESTION_URL=http://localhost:8001/v1/logs

c_green() { printf "\033[32m%s\033[0m\n" "$1"; }
c_blue()  { printf "\033[36m%s\033[0m\n" "$1"; }
c_red()   { printf "\033[31m%s\033[0m\n" "$1"; }

wait_for() { # name, command
  local name="$1"; shift
  for _ in $(seq 1 30); do
    if "$@" >/dev/null 2>&1; then c_green "  $name ready"; return 0; fi
    sleep 2
  done
  c_red "  $name did not become ready in time"; return 1
}

start_infra() {
  c_blue "==> Starting docker infrastructure"
  test -f "$ROOT/.env" || cp "$ROOT/.env.example" "$ROOT/.env"
  (cd "$ROOT" && docker compose up -d >/dev/null 2>&1)

  wait_for "postgres"   docker compose -f "$ROOT/docker-compose.yml" exec -T postgres pg_isready -U infera
  wait_for "clickhouse" curl -sf http://localhost:8123/ping
  wait_for "redpanda"   docker compose -f "$ROOT/docker-compose.yml" exec -T redpanda rpk cluster health

  c_blue "==> Ensuring ClickHouse table + Redpanda topics"
  docker compose -f "$ROOT/docker-compose.yml" exec -T clickhouse \
    clickhouse-client --user infera --password infera --multiquery \
    < "$ROOT/infra/clickhouse/init/01_inference_logs.sql" >/dev/null 2>&1 || true
  docker compose -f "$ROOT/docker-compose.yml" exec -T redpanda \
    rpk topic create inference.logs.raw -p 3 >/dev/null 2>&1 || true
  docker compose -f "$ROOT/docker-compose.yml" exec -T redpanda \
    rpk topic create inference.logs.dlq -p 1 >/dev/null 2>&1 || true
}

ensure_deps() {
  c_blue "==> Ensuring Python deps (first run installs, then cached)"
  if [ ! -d "$INGESTION_DIR/.venv" ]; then
    (cd "$INGESTION_DIR" && uv venv --python 3.13 >/dev/null 2>&1 \
      && uv pip install -e "$ROOT/packages/infera-sdk" >/dev/null 2>&1 \
      && uv pip install -e ".[dev]" >/dev/null 2>&1)
    c_green "  ingestion deps installed"
  fi
  if [ ! -d "$GATEWAY_DIR/.venv" ]; then
    (cd "$GATEWAY_DIR" && uv venv --python 3.13 >/dev/null 2>&1 \
      && uv pip install -e "$ROOT/packages/infera-sdk" >/dev/null 2>&1 \
      && uv pip install -e . >/dev/null 2>&1)
    c_green "  gateway deps installed"
  fi
}

start_svc() { # name, dir, command...
  local name="$1"; local dir="$2"; shift 2
  local pidfile="$RUN_DIR/$name.pid"
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    c_green "  $name already running (pid $(cat "$pidfile"))"; return
  fi
  ( cd "$dir"
    set -a; [ -f "$ROOT/.env" ] && source "$ROOT/.env"; set +a
    # Re-apply host overrides AFTER sourcing .env, so the docker-network
    # names in .env (postgres/clickhouse/redpanda) don't win.
    export POSTGRES_HOST=localhost
    export CLICKHOUSE_HOST=localhost
    export KAFKA_BOOTSTRAP_SERVERS=localhost:19092
    export INGESTION_URL=http://localhost:8001/v1/logs
    nohup "$@" > "$RUN_DIR/$name.log" 2>&1 &
    echo $! > "$pidfile"
  )
  c_green "  $name started (pid $(cat "$pidfile")) → .run/$name.log"
}

cmd_up() {
  start_infra
  ensure_deps
  c_blue "==> Starting backend services"
  start_svc ingestion "$INGESTION_DIR" uv run uvicorn app.main:app --port 8001
  start_svc worker    "$INGESTION_DIR" uv run python -m app.consumer
  start_svc gateway   "$GATEWAY_DIR"   uv run uvicorn app.main:app --port 8000
  sleep 4
  echo
  c_green "Backend is up:"
  echo "  gateway     http://localhost:8000  (health: /health)"
  echo "  ingestion   http://localhost:8001"
  echo "  grafana     http://localhost:3001"
  echo
  echo "Now start the frontend:   cd apps/web && pnpm dev   → http://localhost:3000"
  echo "Tail logs:   make dev-logs     Stop:   make dev-down"
}

# Recursively kill a PID and all its descendants (uv run spawns child
# uvicorn/python processes with different PIDs, so killing the tracked
# parent alone leaves orphans behind).
kill_tree() {
  local pid="$1"
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    kill_tree "$child"
  done
  kill -9 "$pid" 2>/dev/null || true
}

cmd_down() {
  c_blue "==> Stopping backend services"
  for name in gateway worker ingestion; do
    local pidfile="$RUN_DIR/$name.pid"
    if [ -f "$pidfile" ]; then
      kill_tree "$(cat "$pidfile")" && c_green "  $name stopped" || true
      rm -f "$pidfile"
    fi
  done
  echo "Docker infra left running (stop with: make down)"
}

cmd_logs() {
  c_blue "==> Tailing service logs (Ctrl-C to stop)"
  tail -n 20 -f "$RUN_DIR"/*.log
}

cmd_status() {
  c_blue "==> Service status"
  for name in gateway ingestion worker; do
    local pidfile="$RUN_DIR/$name.pid"
    if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
      c_green "  $name running (pid $(cat "$pidfile"))"
    else
      c_red "  $name not running"
    fi
  done
}

case "${1:-up}" in
  up)     cmd_up ;;
  down)   cmd_down ;;
  logs)   cmd_logs ;;
  status) cmd_status ;;
  *) echo "usage: scripts/dev.sh {up|down|logs|status}"; exit 1 ;;
esac
