# ─────────────────────────────────────────────────────────────
# Infera — developer commands
# ─────────────────────────────────────────────────────────────
.DEFAULT_GOAL := help

.PHONY: help env infra up down stop logs ps health clean dev dev-down dev-logs dev-status

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo "Created .env — set OPENROUTER_API_KEY")

infra: env ## Start backing infrastructure only
	docker compose up -d postgres clickhouse redpanda redpanda-init redpanda-console grafana

up: env ## Start the full app stack
	docker compose up -d --build

down: ## Stop and remove containers (keeps data volumes)
	docker compose down

stop: ## Stop containers without removing them
	docker compose stop

logs: ## Tail logs from all services
	docker compose logs -f

ps: ## Show container status
	docker compose ps

health: ## Show health/status of each service
	docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'

clean: ## Stop everything and DELETE all data volumes
	docker compose down -v

# ─────────────────────────────────────────────────────────────
# Local dev (run backend services on the host, one command)
# ─────────────────────────────────────────────────────────────
dev: ## Start full local backend (infra + gateway + ingestion + worker)
	@./scripts/dev.sh up

dev-down: ## Stop the local backend services started by `make dev`
	@./scripts/dev.sh down

dev-logs: ## Tail logs from the local backend services
	@./scripts/dev.sh logs

dev-status: ## Show status of the local backend services
	@./scripts/dev.sh status
