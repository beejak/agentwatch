# Quickstart

Get AgentWatch running and detecting your first failure in under 10 minutes.

## Prerequisites

- Docker + Docker Compose
- Python 3.12+
- `gh` CLI (for GitHub operations, optional)

---

## 1. Clone and configure

```bash
git clone https://github.com/agentwatch/agentwatch.git
cd agentwatch
cp .env.example .env
```

Default `.env` works for local development. Edit if you need different ports.

---

## 2. Start infrastructure

```bash
docker compose up -d redis clickhouse postgres neo4j
```

Wait ~10 seconds for ClickHouse to initialize, then verify:

```bash
make infra-status
```

Expected output:
```
NAME          STATUS    PORTS
clickhouse    running   0.0.0.0:8123->8123/tcp
neo4j         running   0.0.0.0:7687->7687/tcp
postgres      running   0.0.0.0:5433->5432/tcp
redis         running   0.0.0.0:6379->6379/tcp
```

---

## 3. Install AgentWatch

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

---

## 4. Run gate tests

Each layer has a gate test. All must pass:

```bash
make gate-all
```

Expected: `125 passed` across all 16 layers.

Run a specific layer:

```bash
make gate-07   # Memory Integrity Monitor
make gate-12   # Analyst (SC1/SC2/SC3)
```

---

## 5. Run proof scenarios

```bash
make poc
```

This runs all three proof scenarios:

**SC1** — Coordination failure: orchestrator + two workers, one errors, MAST C2 matched.

**SC2** — Silent failure: 150 identical ok-status spans, `cost_anomaly_ratio=10.0`, detected.

**SC3** — Cross-layer discrepancy: 1 agent-reported call, 3 Sysmon network events, delta=2.

---

## 6. Start the API

```bash
make api
```

API at `http://localhost:8000`. Swagger UI at `http://localhost:8000/docs`.

---

## 7. Try it

```bash
# Health check
curl http://localhost:8000/api/v1/health | jq

# All topology signatures (MAST + infra)
curl http://localhost:8000/api/v1/analyst/topology-risks | jq '.[].name'

# Silent failures in last 24h
curl "http://localhost:8000/api/v1/analyst/silent-failures?hours=24" | jq
```

---

## Connecting your agents

Agents emit signals to Redis stream `wt:signals`. Each signal must be HMAC-signed.

**Python example:**

```python
import hmac, hashlib, json, time, uuid
import redis.asyncio as aioredis

HMAC_SECRET = "watchtower-hmac-secret-change-in-prod"
SIGNAL_STREAM = "wt:signals"

async def emit_signal(agent_id: str, action: str, status: str, summary: str):
    signal = {
        "trace_id": str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "agent_id": agent_id,
        "action": action,
        "status": status,
        "summary": summary,
        "timestamp": time.time(),
        "duration_ms": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost": 0.0,
        "retrieval_flag": False,
        "framework_fault": False,
        "policy_checked": False,
    }
    payload = json.dumps(signal, sort_keys=True)
    sig = hmac.new(HMAC_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    signal["hmac"] = sig

    r = await aioredis.from_url("redis://localhost:6379")
    await r.xadd(SIGNAL_STREAM, {"data": json.dumps(signal)})
    await r.aclose()
```

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `CH_HOST` | `localhost` | ClickHouse host |
| `CH_PORT` | `8123` | ClickHouse HTTP port |
| `PG_DSN` | `postgresql://wt:wt@localhost:5433/watchtower` | PostgreSQL DSN |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j bolt URI |
| `WT_HMAC_SECRET` | (change in prod) | HMAC signing secret |
| `WT_BASELINE_MIN_TRACES` | `50` | Traces before agent exits restricted mode |

---

## Makefile reference

```bash
make gate-NN      # Run gate test for layer NN (01–16)
make gate-all     # Run all gates in order, stop on first failure
make poc          # Run SC1 + SC2 + SC3 proof scenarios
make test         # Full test suite
make api          # Start FastAPI server (port 8000)
make infra-status # docker compose ps
make progress     # Show PROGRESS.md
```
