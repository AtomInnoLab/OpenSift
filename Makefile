.PHONY: help install dev-setup test lint format typecheck clean docker-up docker-down run \
       test-integration test-adapter test-backends-up test-backends-down \
       test-es test-opensearch test-solr test-meili test-wikipedia

# Default target
help: ## Show this help message
	@echo "OpenSift — AI-Powered Search Augmentation Layer"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Setup ───────────────────────────────────────────────

install: ## Install production dependencies
	poetry install --without=dev,docs

dev-setup: ## Set up development environment (all dependencies + pre-commit)
	poetry install --with=dev,docs
	poetry run pre-commit install || true
	@echo ""
	@echo "Development environment ready!"
	@echo "  Run tests:  make test"
	@echo "  Run server: make run"

# ─── Development ─────────────────────────────────────────

run: ## Run the development server with auto-reload
	poetry run opensift --reload --log-level debug

run-prod: ## Run the production server
	poetry run opensift --workers 4 --log-level info

# ─── Quality ─────────────────────────────────────────────

test: ## Run all tests
	poetry run pytest tests/ -v

test-unit: ## Run unit tests only
	poetry run pytest tests/unit/ -v -m "not integration"

test-integration: ## Run all integration tests (requires Docker backends)
	poetry run pytest tests/integration/ -v -m integration

# ─── Per-adapter targets ─────────────────────────────────
# Usage:  make test-es         — start Elasticsearch + run its tests
#         make test-opensearch  — start OpenSearch    + run its tests
#         make test-solr        — start Solr          + run its tests
#         make test-meili       — start MeiliSearch   + run its tests
#         make test-wikipedia   — run Wikipedia tests (no Docker needed)
#
# Generic:  make test-adapter ADAPTER=elasticsearch

COMPOSE_FILE := deployments/docker/docker-compose.test.yml

test-adapter: ## Run one adapter's tests: make test-adapter ADAPTER=elasticsearch
ifndef ADAPTER
	$(error ADAPTER is required. Use: elasticsearch, opensearch, solr, meilisearch, wikipedia)
endif
ifeq ($(ADAPTER),wikipedia)
	poetry run pytest tests/integration/test_wikipedia.py -v -m wikipedia
else
	@echo "Starting $(ADAPTER)..."
	docker compose -f $(COMPOSE_FILE) up -d $(ADAPTER)
	@echo "Waiting for $(ADAPTER) to become healthy..."
	@until docker compose -f $(COMPOSE_FILE) ps $(ADAPTER) --format '{{.Status}}' | grep -q healthy; do sleep 2; done
	@echo "$(ADAPTER) is ready. Running tests..."
	poetry run pytest tests/integration/test_$(ADAPTER).py -v -m $(ADAPTER)
endif

test-es: ## Start Elasticsearch + run its tests
	@$(MAKE) test-adapter ADAPTER=elasticsearch

test-opensearch: ## Start OpenSearch + run its tests
	@$(MAKE) test-adapter ADAPTER=opensearch

test-solr: ## Start Solr + run its tests
	@$(MAKE) test-adapter ADAPTER=solr

test-meili: ## Start MeiliSearch + run its tests
	@$(MAKE) test-adapter ADAPTER=meilisearch

test-wikipedia: ## Run Wikipedia tests (no Docker needed)
	poetry run pytest tests/integration/test_wikipedia.py -v -m wikipedia

test-backends-up: ## Start all search backends for integration tests
	docker compose -f $(COMPOSE_FILE) up -d
	@echo "Waiting for all backends to be ready..."
	@until docker compose -f $(COMPOSE_FILE) ps --format '{{.Status}}' | grep -v healthy | grep -qv STATUS || true; do sleep 2; done
	@echo "  Elasticsearch: http://localhost:9200"
	@echo "  OpenSearch:    http://localhost:9201"
	@echo "  Solr:          http://localhost:8983"
	@echo "  MeiliSearch:   http://localhost:7700"

test-backends-down: ## Stop search backends and remove volumes
	docker compose -f $(COMPOSE_FILE) down -v

test-cov: ## Run tests with coverage report
	poetry run pytest tests/ --cov=opensift --cov-report=html --cov-report=term-missing

lint: ## Run linter (ruff)
	poetry run ruff check src/ tests/

lint-fix: ## Run linter with auto-fix
	poetry run ruff check --fix src/ tests/

format: ## Format code (ruff)
	poetry run ruff format src/ tests/

format-check: ## Check code formatting without changes
	poetry run ruff format --check src/ tests/

typecheck: ## Run type checker (mypy)
	poetry run mypy src/opensift/

check: lint format-check typecheck test ## Run all checks (CI pipeline)

# ─── Docker ──────────────────────────────────────────────

docker-build: ## Build Docker image
	docker build -f deployments/docker/Dockerfile -t opensift/core:latest .

docker-up: ## Start development stack (Docker Compose)
	docker-compose -f deployments/docker/docker-compose.dev.yml up -d

docker-down: ## Stop development stack
	docker-compose -f deployments/docker/docker-compose.dev.yml down

docker-logs: ## Tail Docker Compose logs
	docker-compose -f deployments/docker/docker-compose.dev.yml logs -f

# ─── Documentation ───────────────────────────────────────

docs-serve: ## Serve documentation locally
	poetry run mkdocs serve

docs-build: ## Build documentation
	poetry run mkdocs build

# ─── SDK ─────────────────────────────────────────────

openapi-export: ## Export OpenAPI spec to sdks/openapi.json
	poetry run python -c "\
		from opensift.api.app import create_app; \
		import json; \
		app = create_app(); \
		spec = app.openapi(); \
		print(json.dumps(spec, indent=2))" > sdks/openapi.json
	@echo "Exported OpenAPI spec to sdks/openapi.json"

# ─── Build & Publish ─────────────────────────────────

build: clean ## Build sdist and wheel
	poetry build
	@echo "Built packages:"
	@ls -lh dist/

publish-check: build ## Build and verify package metadata
	poetry run twine check dist/*

publish-test: publish-check ## Publish to TestPyPI
	poetry run twine upload --repository testpypi dist/*

publish: publish-check ## Publish to PyPI (use with caution)
	@echo "Publishing opensift $$(poetry version -s) to PyPI..."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	poetry run twine upload dist/*

# ─── Cleanup ─────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	rm -rf dist/ build/ *.egg-info/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf htmlcov/ .coverage
	rm -rf site/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned up build artifacts and caches."
