.PHONY: help up down logs migrate migrate-status dev dev-workers test test-unit test-integration lint format install clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Environment setup
# ---------------------------------------------------------------------------
install: ## Install Python dependencies (editable, with dev extras)
	python -m pip install -e ".[dev]"

# ---------------------------------------------------------------------------
# Docker (PostgreSQL + TimescaleDB + API)
# ---------------------------------------------------------------------------
up: ## Start PostgreSQL + API via docker compose (detached)
	docker compose up -d

down: ## Stop and remove containers
	docker compose down

down-volumes: ## Stop containers AND delete data volumes (DESTRUCTIVE)
	docker compose down -v

logs: ## Tail container logs
	docker compose logs -f

# ---------------------------------------------------------------------------
# Database migrations
# ---------------------------------------------------------------------------
migrate: ## Apply all SQL migrations in canonical order
	@echo "Applying migrations..."
	python scripts/migrate.py apply

migrate-status: ## Show migration status
	python scripts/migrate.py status

# ---------------------------------------------------------------------------
# Local development (without docker for the API; db still via docker)
# ---------------------------------------------------------------------------
dev: ## Run the FastAPI API locally with hot reload
	uvicorn app.main:app --host $$(API_HOST) --port $$(API_PORT) --reload

dev-workers: ## Run all independent workers locally
	python -m app.workers.run_all

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------
test: test-unit test-integration ## Run all tests

test-unit: ## Run existing unit tests (PYTHONPATH=src, unittest per-wave)
	@for w in wave1 wave2 wave3 wave4 assurance project_memory; do \
		echo "=== $$w ===" ; \
		PYTHONPATH=src python -m unittest discover -s tests/$$w -p 'test_*.py' || exit 1 ; \
	done

test-integration: ## Run integration tests (requires docker compose up + migrate)
	pytest tests/integration -v

# ---------------------------------------------------------------------------
# Linting / formatting
# ---------------------------------------------------------------------------
lint: ## Run ruff linter
	ruff check app scripts tests

format: ## Run ruff formatter
	ruff format app scripts tests

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
clean: ## Remove Python caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	rm -rf build dist *.egg-info .eggs
