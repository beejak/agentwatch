.PHONY: all infra-up infra-down infra-status infra-wait \
        gate-all poc test progress clean install \
        ruflo-build langfuse-setup

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

## Ruflo parallel build (after components 01-03 done)
ruflo-parallel:
	@echo "Requires Ruflo installed: npx claude-flow@latest init --sparc"
	npx claude-flow@latest swarm \
		"Read SPEC.md. Build layers 04-06 in parallel. Each uses its SKILL.md. Gate must pass before marking done." \
		--agents 4 --parallel --memory-namespace watchtower

## Help
help:
	@echo "WatchTower build commands:"
	@echo "  make infra-up        Start all Docker services"
	@echo "  make install         Install Python deps"
	@echo "  make gate-NN         Run gate for layer NN (e.g. make gate-01)"
	@echo "  make gate-all        Run all gates sequentially"
	@echo "  make poc             Run SC1 + SC2 + SC3 proof scenarios"
	@echo "  make benchmark       Run LangSmith gap comparison"
	@echo "  make test            Full test suite with coverage"
	@echo "  make api             Start FastAPI server"
	@echo "  make progress        Show build progress"
