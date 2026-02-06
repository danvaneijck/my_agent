COMPOSE = docker compose -f agent/docker-compose.yml
CLI = $(COMPOSE) exec core python /app/cli.py

# ──────────────────────────────────────────────
# Lifecycle
# ──────────────────────────────────────────────

.PHONY: up down restart status

up: ## Start all services
	$(COMPOSE) up -d

down: ## Stop all services
	$(COMPOSE) down

restart: ## Restart all services
	$(COMPOSE) restart

status: ## Show running services
	$(COMPOSE) ps

# ──────────────────────────────────────────────
# First-time setup
# ──────────────────────────────────────────────

.PHONY: setup migrate

setup: ## Full first-time setup: build, start infra, migrate, create bucket + default persona
	$(COMPOSE) build
	$(COMPOSE) up -d postgres redis minio
	@echo "Waiting for infrastructure..."
	@sleep 5
	$(COMPOSE) up -d core
	@sleep 3
	$(CLI) setup
	$(COMPOSE) up -d
	@echo "Setup complete. All services running."

migrate: ## Run database migrations
	$(CLI) setup

# ──────────────────────────────────────────────
# Infrastructure only
# ──────────────────────────────────────────────

.PHONY: infra infra-down

infra: ## Start only Postgres, Redis, MinIO
	$(COMPOSE) up -d postgres redis minio

infra-down: ## Stop infrastructure services
	$(COMPOSE) stop postgres redis minio

# ──────────────────────────────────────────────
# Build
# ──────────────────────────────────────────────

.PHONY: build build-core build-module

build: ## Rebuild all Docker images
	$(COMPOSE) build

build-core: ## Rebuild the core service image
	$(COMPOSE) build core

build-module: ## Rebuild a module image (usage: make build-module M=research)
ifndef M
	@echo "Usage: make build-module M=<module-name>"
	@echo "  e.g. make build-module M=research"
	@exit 1
endif
	$(COMPOSE) build $(M)

# ──────────────────────────────────────────────
# Restart with rebuild
# ──────────────────────────────────────────────

.PHONY: restart-core restart-module restart-bots

restart-core: build-core ## Rebuild and restart the core service
	$(COMPOSE) up -d --no-deps core

restart-module: build-module ## Rebuild and restart a module (usage: make restart-module M=research)
	$(COMPOSE) up -d --no-deps $(M)

restart-bots: ## Restart all communication bots
	$(COMPOSE) restart discord-bot telegram-bot slack-bot

# ──────────────────────────────────────────────
# Logs
# ──────────────────────────────────────────────

.PHONY: logs logs-core logs-module logs-bots

logs: ## Tail logs from all services
	$(COMPOSE) logs -f --tail=100

logs-core: ## Tail logs from the core service
	$(COMPOSE) logs -f --tail=100 core

logs-module: ## Tail logs from a module (usage: make logs-module M=research)
ifndef M
	@echo "Usage: make logs-module M=<module-name>"
	@exit 1
endif
	$(COMPOSE) logs -f --tail=100 $(M)

logs-bots: ## Tail logs from all communication bots
	$(COMPOSE) logs -f --tail=100 discord-bot telegram-bot slack-bot

# ──────────────────────────────────────────────
# User management
# ──────────────────────────────────────────────

.PHONY: create-owner list-users

create-owner: ## Create owner user (usage: make create-owner DISCORD_ID=123 [TELEGRAM_ID=456] [SLACK_ID=789])
	@CMD="$(CLI) user create-owner"; \
	if [ -n "$(DISCORD_ID)" ]; then CMD="$$CMD --discord-id $(DISCORD_ID)"; fi; \
	if [ -n "$(TELEGRAM_ID)" ]; then CMD="$$CMD --telegram-id $(TELEGRAM_ID)"; fi; \
	if [ -n "$(SLACK_ID)" ]; then CMD="$$CMD --slack-id $(SLACK_ID)"; fi; \
	eval $$CMD

list-users: ## List all users
	$(CLI) user list

# ──────────────────────────────────────────────
# Persona management
# ──────────────────────────────────────────────

.PHONY: list-personas

list-personas: ## List all personas
	$(CLI) persona list

# ──────────────────────────────────────────────
# Module management
# ──────────────────────────────────────────────

.PHONY: list-modules refresh-tools

list-modules: ## Show all modules and health status
	$(CLI) modules list

refresh-tools: ## Re-discover all module manifests
	$(CLI) modules refresh

# ──────────────────────────────────────────────
# Debug / shell access
# ──────────────────────────────────────────────

.PHONY: shell psql redis-cli

shell: ## Open a bash shell in the core container
	$(COMPOSE) exec core bash

psql: ## Open a PostgreSQL shell
	$(COMPOSE) exec postgres psql -U agent agent

redis-cli: ## Open a Redis CLI
	$(COMPOSE) exec redis redis-cli

# ──────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────

.PHONY: clean clean-volumes

clean: down ## Stop services and remove built images
	$(COMPOSE) down --rmi local

clean-volumes: ## Stop services and delete all data volumes (DESTRUCTIVE)
	@echo "This will DELETE all database data, Redis cache, and stored files."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	$(COMPOSE) down -v

# ──────────────────────────────────────────────
# Help
# ──────────────────────────────────────────────

.PHONY: help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
