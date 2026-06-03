# AgentWatch — Production Integration Guide

Complete instructions for deploying AgentWatch in a production environment
and wiring it to your existing AI agent infrastructure.

---

## Architecture Overview

```
Your AI Agents
     │
     │  Signal (OTel span + AgentWatch fields)
     ▼
┌─────────────────┐
│  Signal Receiver │  ← HMAC verification, schema validation
│  (port 8080)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Chronicle     │  ← ClickHouse, append-only, 90-day TTL
│  (ClickHouse)   │
└────────┬────────┘
         │
    ┌────┴─────────────────────────────┐
    │                                   │
    ▼                                   ▼
┌────────────┐                  ┌──────────────────┐
│  Real-time  │                  │  Analyst (async)  │
│  Detection  │                  │  SC1/SC2/SC3      │
│  (MIM,CI,  │                  │  Attribution      │
│  Policy)   │                  │  Verdict Engine   │
└────────────┘                  └──────────────────┘
         │                               │
         ▼                               ▼
┌─────────────────┐             ┌──────────────────┐
│   Interceptor   │             │    Dashboard /    │
│  Halt/Quarantine│             │    Alerts API     │
└─────────────────┘             └──────────────────┘
```

---

## Phase 1: Infrastructure Setup

### Option A: Docker Compose (staging / small prod)

```bash
# Clone and start infrastructure
git clone https://github.com/beejak/agentwatch
cd agentwatch
docker compose up -d

# Verify all services running
docker compose ps
# Expected: clickhouse, postgres, redis, neo4j, langfuse all Up
```

### Option B: Kubernetes (production)

Deploy each service independently. Use the Docker images from `docker-compose.yml` as reference.

Minimum resources per pod:
| Service | CPU | Memory |
|---------|-----|--------|
| ClickHouse | 2 cores | 8GB |
| Redis | 0.5 core | 2GB |
| Postgres | 1 core | 4GB |
| Neo4j | 1 core | 4GB |
| AgentWatch API | 1 core | 2GB |
| Signal Receiver | 0.5 core | 512MB |

---

## Phase 2: Database Initialization

```bash
# Run migrations (idempotent — safe to run multiple times)
python -m watchtower.chronicle.migrations

# Verify Chronicle tables created
python -c "
import clickhouse_connect
ch = clickhouse_connect.get_client(host='localhost', port=8123, 
    database='watchtower', username='wt', password='wt')
print(ch.query('SHOW TABLES').result_rows)
"
```

Expected tables:
```
traces, spans, silent_failures, policy_violations, 
mim_events, interceptor_actions, host_telemetry, verdict_results
```

---

## Phase 3: Configuration

### Required Environment Variables

```bash
# Core
export WATCHTOWER_ENV=production
export WT_HMAC_SECRET="<generate: openssl rand -hex 32>"

# Databases
export CLICKHOUSE_HOST=clickhouse.internal
export CLICKHOUSE_PORT=8123
export CLICKHOUSE_DB=watchtower
export CLICKHOUSE_USER=wt
export CLICKHOUSE_PASSWORD=<secret>

export REDIS_URL=redis://redis.internal:6379
export POSTGRES_DSN=postgresql://wt:<pass>@postgres.internal:5432/watchtower
export NEO4J_URI=bolt://neo4j.internal:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=<secret>

# Optional: LLM Judge (verdict engine stage 3)
export LLM_API_KEY=<your key>

# Optional: Observability for AgentWatch itself
export LANGFUSE_PUBLIC_KEY=<key>
export LANGFUSE_SECRET_KEY=<key>
export LANGFUSE_HOST=http://langfuse.internal:3000
```

### Detection Thresholds (tune per environment)

Edit `watchtower/analyst/silent.py`:
```python
# Adjust based on your agent's typical cost profile
EXPECTED_COST_PER_SPAN = 0.000045   # baseline cost per span
RETRY_REPEAT_THRESHOLD = 3          # identical summaries before loop detection
MIN_SPANS_FOR_LOOP = 10             # minimum spans to trigger loop check
```

Edit `watchtower/verdict/sources/deterministic.py`:
```python
COST_THRESHOLD = 0.10    # $0.10 per trace triggers deterministic verdict
MAX_SPANS = 50           # spans before flagging as excessive
```

---

## Phase 4: Signal Instrumentation

### Python SDK (recommended)

Install in your agent codebase:
```bash
pip install watchtower-sdk  # coming soon; for now copy watchtower/core/signal.py
```

Instrument each agent span:

```python
import hmac as hmac_mod
import hashlib
import json
import time
import uuid
from watchtower.core.signal import Signal

HMAC_SECRET = os.environ["WT_HMAC_SECRET"]
WATCHTOWER_ENDPOINT = "http://watchtower.internal:8000/api/v1/signals/ingest"

def emit_span(
    agent_id: str,
    action: str,
    status: str,
    tokens_in: int,
    tokens_out: int,
    cost: float,
    summary: str,
    trace_id: str,
    model: str = "gpt-4o",
    **kwargs,
) -> None:
    signal = Signal(
        trace_id=trace_id,
        span_id=str(uuid.uuid4()),
        agent_id=agent_id,
        action=action,
        status=status,
        timestamp=time.time(),
        duration_ms=kwargs.get("duration_ms", 0.0),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        model=model,
        cost=cost,
        summary=summary,
        policy_checked=kwargs.get("policy_checked", True),
        framework_fault=kwargs.get("framework_fault", False),
        **{k: v for k, v in kwargs.items() if k not in ("duration_ms", "policy_checked", "framework_fault")},
    )

    payload = json.dumps(signal.model_dump(), sort_keys=True, default=str)
    sig = hmac_mod.new(
        HMAC_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    requests.post(
        WATCHTOWER_ENDPOINT,
        json={"signal": payload, "hmac": sig},
        timeout=1.0,  # never block your agent on observability
    )
```

### LangChain / LangGraph Integration

```python
from langchain.callbacks.base import BaseCallbackHandler

class AgentWatchCallback(BaseCallbackHandler):
    def __init__(self, agent_id: str, trace_id: str):
        self.agent_id = agent_id
        self.trace_id = trace_id
        self._start = None

    def on_llm_start(self, serialized, prompts, **kwargs):
        self._start = time.time()

    def on_llm_end(self, response, **kwargs):
        usage = response.llm_output.get("token_usage", {})
        emit_span(
            agent_id=self.agent_id,
            action="llm_call",
            status="ok",
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            cost=usage.get("total_tokens", 0) * 0.000003,
            summary=response.generations[0][0].text[:200],
            trace_id=self.trace_id,
            duration_ms=(time.time() - self._start) * 1000,
        )

    def on_llm_error(self, error, **kwargs):
        emit_span(
            agent_id=self.agent_id,
            action="llm_call",
            status="error",
            tokens_in=0, tokens_out=0, cost=0.0,
            summary=str(error)[:200],
            trace_id=self.trace_id,
        )
```

---

## Phase 5: Policy Configuration

Define allowed actions per agent before deployment:

```python
import asyncio
from watchtower.policy_engine.engine import PolicyEngine
from watchtower.policy_engine.temporal import TemporalConstraint, ConstraintType
from watchtower.access_graph.graph import AccessGraph
from watchtower.access_graph.manifest import AgentManifest

async def configure_policies():
    # Policy engine
    policy = PolicyEngine()

    # Orchestrator: can delegate and call LLM
    await policy.allow("orchestrator-agent", ["llm_call", "delegate", "tool_use"])

    # Worker agents: restricted to LLM calls only
    await policy.allow("worker-agent-*", ["llm_call"])

    # Constrain: deploy must happen after test
    await policy.add_constraint("deploy-agent", TemporalConstraint(
        action_a="run_tests",
        action_b="deploy",
        type=ConstraintType.AFTER,
        reason="Deploy requires tests to pass first",
    ))

    # Access graph: who can call whom
    graph = AccessGraph()

    await graph.load_manifest(AgentManifest(
        agent_id="orchestrator-agent",
        allowed_actions=["delegate", "llm_call"],
        allowed_systems=["redis", "postgres"],
        allowed_callers=[],  # top level — no one calls orchestrator
        allowed_callees=["worker-agent-a", "worker-agent-b"],
        memory_scope="read_write",
        data_access=["logs", "tasks"],
        blast_radius=[],
    ))

    await graph.load_manifest(AgentManifest(
        agent_id="worker-agent-a",
        allowed_actions=["llm_call", "tool_use"],
        allowed_systems=["redis"],
        allowed_callers=["orchestrator-agent"],  # only orchestrator may call
        allowed_callees=[],
        memory_scope="read_only",
        data_access=["logs"],
        blast_radius=[],
    ))

asyncio.run(configure_policies())
```

---

## Phase 6: Start the API

```bash
# Development
uvicorn watchtower.api.main:app --host 0.0.0.0 --port 8000 --reload

# Production (with gunicorn for process management)
pip install gunicorn
gunicorn watchtower.api.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logfile - \
    --error-logfile -
```

### Health check
```bash
curl http://localhost:8000/api/v1/health
# {"status": "ok", "chronicle": "connected", "redis": "connected"}
```

---

## Phase 7: Alert Routing

AgentWatch detects but doesn't send alerts by default. Wire detections to your alert system:

### Webhook (generic)

```python
# watchtower/alerts/webhook.py
import httpx

WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL")

async def send_alert(detection_type: str, agent_id: str, severity: str, details: dict):
    if not WEBHOOK_URL:
        return
    await httpx.AsyncClient().post(WEBHOOK_URL, json={
        "text": f"[AgentWatch] {severity.upper()} — {detection_type} on {agent_id}",
        "detection_type": detection_type,
        "agent_id": agent_id,
        "severity": severity,
        **details,
    })
```

Wire into interceptor actions, MIM events, and verdict results.

### PagerDuty

```python
from pdpyras import EventsAPISession

pd = EventsAPISession(os.environ["PAGERDUTY_ROUTING_KEY"])

async def page_on_critical(detection: dict):
    if detection["severity"] == "critical":
        pd.trigger(
            summary=f"AgentWatch: {detection['type']} — {detection['agent_id']}",
            severity="critical",
            source="agentwatch",
            custom_details=detection,
        )
```

### Slack

```python
import httpx

SLACK_WEBHOOK = os.environ.get("SLACK_ALERT_WEBHOOK")

async def slack_alert(msg: str, severity: str):
    emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(severity, "⚪")
    await httpx.AsyncClient().post(SLACK_WEBHOOK, json={
        "text": f"{emoji} *AgentWatch* — {msg}"
    })
```

---

## Phase 8: Shadow Mode → Enforcement Mode

**Never go straight to enforcement mode in production.**

### Week 1-2: Shadow Mode
- Run AgentWatch alongside your agents
- Detections logged but no interceptor actions taken
- Review the dashboard daily: `GET /api/v1/analyst/topology-risks`
- Tune thresholds based on your actual traffic
- Target: FP rate < 2% before enabling enforcement

Enable shadow mode:
```bash
export WT_ENFORCEMENT_MODE=shadow
```

### Week 3-4: Soft Enforcement
- Interceptor logs actions but doesn't block
- Operators receive alerts for all `high` and `critical` detections
- Human reviews before any agent is halted

```bash
export WT_ENFORCEMENT_MODE=soft
```

### Week 5+: Full Enforcement
- Interceptor halts/quarantines automatically on critical detections
- Policy engine denies unauthorized actions in real time
- Alert on all high/critical severity events

```bash
export WT_ENFORCEMENT_MODE=enforce
```

---

## Phase 9: CI/CD Integration

### Run full test suite in CI

```yaml
# .github/workflows/agentwatch.yml
- name: Run AgentWatch test suite
  run: |
    pytest tests/adversarial/test_must_detect.py -x -q \
      --tb=short \
      || exit 1  # Tier 1 failures block everything

    pytest tests/adversarial/test_false_positives.py -x -q \
      --tb=short \
      || exit 1  # Tier 2 failures block everything

    pytest tests/scenarios/ tests/integration/ -q \
      --tb=short

    make gate-all
```

### Weekly agentic tester (requires API key in CI secrets)

```yaml
# .github/workflows/agentic-tester.yml
on:
  schedule:
    - cron: '0 2 * * 1'  # Monday 2am UTC
  workflow_dispatch:

jobs:
  agentic-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run agentic tester
        env:
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
        run: |
          python -m agents.agentic_tester \
            --save-report docs/TESTING_GAPS.md \
            --output gaps/$(date +%Y%m%d).json

      - name: Upload gap report
        uses: actions/upload-artifact@v4
        with:
          name: gap-report-${{ github.run_id }}
          path: docs/TESTING_GAPS.md
```

---

## Phase 10: Monitoring AgentWatch Itself

AgentWatch needs to be monitored too. Things to track:

| Metric | Alert Threshold | Meaning |
|--------|----------------|---------|
| Chronicle write lag | > 5s | ClickHouse backpressure |
| Signal receiver queue depth | > 1000 | Agent flood or receiver down |
| MIM event rate | 10x normal spike | Attack in progress OR FP storm |
| Verdict engine latency P99 | > 2s | LLM judge timeout |
| Interceptor action count | > 5/hour | Coordinated attack OR misconfiguration |
| False positive rate (rolling 1h) | > 5% | Threshold misconfiguration |

Expose `/api/v1/health` to your monitoring platform (Datadog, Prometheus, etc.).

```bash
# Prometheus scrape config
- job_name: 'agentwatch'
  static_configs:
    - targets: ['agentwatch.internal:8000']
  metrics_path: '/api/v1/metrics'
```

---

## Incident Response Playbook

### Agent Halted by Interceptor
1. Check: `GET /api/v1/analyst/report/{trace_id}` for the triggering trace
2. Review MIM events: `GET /api/v1/agents/{agent_id}/verdicts`
3. If false positive: manually lift halt via API, adjust threshold, add to FP test
4. If true positive: investigate full trace, identify root cause, patch agent

### Silent Failure Alert ($47K scenario)
1. `GET /api/v1/analyst/silent-failures` — identify the looping agent
2. Check current cost burn rate
3. Immediately quarantine: `POST /api/v1/interceptor/quarantine`
4. Trace the root cause (stuck tool, infinite retry, LLM loop)
5. Fix agent, test with `test_sc2_full_chain_to_quarantine`, redeploy

### MINJA Memory Injection Detected
1. Review MIM events for the agent — identify what was written
2. Check if the write influenced downstream agents (blast radius)
3. Quarantine affected agents
4. Scan all memory for the injected content hash
5. Rotate any credentials or session tokens the agent had access to
