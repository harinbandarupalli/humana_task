# Strict uv-only execution
VENV := .venv
UV := /opt/homebrew/bin/uv

.PHONY: help venv install up down migrate run orchestrate test clean

help:
	@echo "Available commands (powered by uv & .venv):"
	@echo "  make venv         - Create isolated virtual environment using uv"
	@echo "  make install      - Install dependencies into .venv with uv pip"
	@echo "  make orchestrate  - Run end-to-end orchestration placeholder pipeline"
	@echo "  make run          - Run FastAPI orchestrator server via uv run"
	@echo "  make test         - Run test suite via uv run"
	@echo "  make up           - Start PostgreSQL & Flyway via Docker"
	@echo "  make down         - Stop Docker containers"
	@echo "  make migrate      - Apply Flyway migrations"
	@echo "  make clean        - Remove caches and virtual environment"

venv:
	$(UV) venv $(VENV) --python /opt/homebrew/bin/python3.14

install:
	$(UV) pip install --python $(VENV) -r requirements.txt

orchestrate:
	$(UV) run --no-sync python -m src.orchestrator.graph.runner

run:
	$(UV) run --no-sync uvicorn src.orchestrator.api.app:app --host 0.0.0.0 --port 8000 --reload

test:
	$(UV) run --no-sync pytest tests/

up:
	docker compose up --build -d

down:
	docker compose down

migrate:
	./scripts/migrate.sh

clean:
	rm -rf $(VENV) .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
