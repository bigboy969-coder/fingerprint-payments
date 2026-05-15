# FingerPay — common development commands
# Run `make help` to see available targets.

.DEFAULT_GOAL := help
SHELL := /bin/bash

VENV := .venv

# Cross-platform: detect Windows (Scripts/) vs Unix (bin/)
ifeq ($(OS),Windows_NT)
    BIN := $(VENV)/Scripts
else
    BIN := $(VENV)/bin
endif

PYTHON := $(BIN)/python
PIP := $(BIN)/pip

# ── Setup ────────────────────────────────────────────────────────────────────

.PHONY: setup
setup: venv deps hooks ## Full local setup (venv + deps + pre-commit hooks)
	@echo "Done. Run 'make dev' to start the server."

.PHONY: venv
venv: ## Create Python virtual environment
	python -m venv $(VENV)

.PHONY: deps
deps: ## Install all dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install ruff black mypy pytest pytest-cov httpx pre-commit pip-audit

.PHONY: hooks
hooks: ## Install pre-commit hooks
	$(BIN)/pre-commit install

# ── Development ──────────────────────────────────────────────────────────────

.PHONY: dev
dev: ## Run the dev server with hot reload
	$(PYTHON) -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

.PHONY: run
run: ## Run the server (no reload)
	$(PYTHON) -m uvicorn main:app --host 0.0.0.0 --port 8000

# ── Quality ──────────────────────────────────────────────────────────────────

.PHONY: lint
lint: ## Run ruff linter
	$(BIN)/ruff check .

.PHONY: format
format: ## Auto-format with black + ruff --fix
	$(BIN)/black .
	$(BIN)/ruff check --fix .

.PHONY: format-check
format-check: ## Check formatting without modifying files
	$(BIN)/black --check .
	$(BIN)/ruff check .

.PHONY: typecheck
typecheck: ## Run mypy
	$(BIN)/mypy --install-types --non-interactive .

.PHONY: audit
audit: ## Check dependencies for known CVEs
	$(BIN)/pip-audit -r requirements.txt

# ── Testing ──────────────────────────────────────────────────────────────────

.PHONY: test
test: ## Run test suite
	@if [ -d tests ]; then \
		$(PYTHON) -m pytest -x -q; \
	else \
		echo "No tests/ directory yet — see docs/TESTING.md"; \
	fi

.PHONY: test-cov
test-cov: ## Run tests with coverage report
	@if [ -d tests ]; then \
		$(PYTHON) -m pytest --cov=. --cov-report=term-missing; \
	else \
		echo "No tests/ directory yet — see docs/TESTING.md"; \
	fi

# ── Docker ───────────────────────────────────────────────────────────────────

.PHONY: docker-build
docker-build: ## Build Docker image locally
	docker build -t fingerpay:local .

.PHONY: docker-run
docker-run: ## Run Docker image locally (requires .env)
	docker run --rm -p 8000:8000 --env-file .env fingerpay:local

# ── Housekeeping ─────────────────────────────────────────────────────────────

.PHONY: clean
clean: ## Remove caches and temp files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf temp_uploads/* 2>/dev/null || true
	rm -f fingerpay.db 2>/dev/null || true
	@echo "Cleaned."

# ── Help ─────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
