.PHONY: all infra-up infra-down infra-status infra-wait \
        gate-all poc test benchmark eval progress clean install \
        api seed-sysmon langfuse-setup help

PYTHON     = .venv/bin/python -m pytest
PYTEST_FLAGS = -v --tb=short --asyncio-mode=auto

## Infra
infra-up:
	docker compose up -d

infra-down:
	docker compose down

infra-status:
	docker compose ps

infra-wait:
	@echo "Waiting for infra to be healthy..."
	@docker compose up -d
	@sleep 5
	@docker compose ps

## Install
install:
	pip install -e ".[dev]"

## Layer implementation (read SKILL.md then implement)
layer-%:
	@echo "==> Layer $* — read skills/layer-$*.md before implementing"

## Gate tests — single layer
gate-%:
	$(PYTHON) tests/gates/gate_$*_*.py $(PYTEST_FLAGS)

## Run all gates in order, stop on first failure
gate-all:
	@for gate in $$(ls tests/gates/gate_*.py | sort); do \
		echo "==> Running $$gate"; \
		$(PYTHON) $$gate $(PYTEST_FLAGS) || exit 1; \
	done
	@echo "All gates passed."

## POC proof scenarios
poc:
	$(PYTHON) tests/poc/ $(PYTEST_FLAGS) -s

## Benchmark comparison vs LangSmith
benchmark:
	$(PYTHON) tests/benchmark/ $(PYTEST_FLAGS) -s

## Full suite
test:
	$(PYTHON) tests/ $(PYTEST_FLAGS) --cov=watchtower --cov-report=term-missing

## Progress
progress:
	@cat PROGRESS.md

## Langfuse setup (run once after infra-up)
langfuse-setup:
	@echo "Langfuse running at http://localhost:3000"
	@echo "Create project 'watchtower' and copy keys to .env"

## Seed synthetic data
seed-sysmon:
	@mkdir -p data/sysmon data/telemetry data/falco
	@python agents/adversarial/sysmon_sim.py --seed

## Start API
api:
	uvicorn watchtower.api.main:app --reload --port 8000

## Clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean."

## Observability evaluation (SC2/SC3 vs baselines, held-out metrics)
eval:
	.venv/bin/python -m eval.harness --split test

## Help
help:
	@echo "WatchTower — command reference"
	@echo ""
	@echo "Setup:"
	@echo "  make install         Install package + dev deps into .venv"
	@echo "  make infra-up        Start backing services (redis, clickhouse, postgres, neo4j)"
	@echo "  make infra-down      Stop backing services"
	@echo "  make infra-status    docker compose ps"
	@echo ""
	@echo "Test:"
	@echo "  make gate-NN         Run the gate for layer NN (e.g. make gate-08)"
	@echo "  make gate-all        Run all layer gates in order (stop on first failure)"
	@echo "  make poc             Run proof scenarios SC1 + SC2 + SC3"
	@echo "  make test            Full suite (203 tests) with coverage"
	@echo "  make benchmark       WatchTower vs LangSmith capability-gap"
	@echo "  make eval            SC2/SC3 detection vs baselines on the held-out corpus"
	@echo ""
	@echo "Run / data:"
	@echo "  make api             Start the FastAPI server (http://localhost:8000/docs)"
	@echo "  make seed-sysmon     Generate synthetic host-telemetry seed data"
	@echo "  make progress        Show PROGRESS.md"
	@echo "  make clean           Remove __pycache__ / *.pyc / .pytest_cache"
