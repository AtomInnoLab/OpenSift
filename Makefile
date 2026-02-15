.PHONY: help install dev-setup test lint format typecheck clean docker-up docker-down run

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

test-integration: ## Run integration tests only
	poetry run pytest tests/integration/ -v -m integration

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

# ─── Cleanup ─────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	rm -rf dist/ build/ *.egg-info/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf htmlcov/ .coverage
	rm -rf site/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned up build artifacts and caches."
