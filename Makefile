# Common dev commands. Run `make help` to list.

SHELL := /bin/sh
.DEFAULT_GOAL := help

.PHONY: help install dev stop agent ngrok agent-card check lint format typecheck test test-fast integration clean

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install: ## Install all dependencies via uv (including workspace members)
	uv sync --all-packages --all-extras --dev

dev: ## Run both services locally via docker-compose
	docker-compose up --build

stop: ## Stop local dev stack
	docker-compose down

agent: ## Run the A2A agent locally on :8001 (reads .env)
	uv run --package a2a_agent uvicorn a2a_agent.app:a2a_app --host 0.0.0.0 --port 8001 --log-level info --reload --env-file .env

ngrok: ## Expose local :8001 via ngrok (requires NGROK_AUTHTOKEN in .env on first run)
	ngrok http 8001

agent-card: ## Fetch the local agent card (agent must be running via `make agent`)
	curl -s http://localhost:8001/.well-known/agent-card.json | python -m json.tool

check: lint typecheck test-fast ## Lint + typecheck + fast tests

lint: ## Run ruff lint
	uv run ruff check .

format: ## Run ruff format
	uv run ruff format .

typecheck: ## Run mypy
	uv run mypy shared mcp_server a2a_agent

test-fast: ## Run tests excluding slow LLM tests
	uv run pytest -m "not llm and not integration" -v

test: ## Run all tests (including LLM calls — may be slow)
	uv run pytest -v

integration: ## Run end-to-end integration tests against all 3 demo patients
	uv run pytest -m integration -v

clean: ## Remove build artifacts + caches
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
