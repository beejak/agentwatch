# Quickstart

> Get AgentWatch running and detecting your first failure in under 10 minutes.

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Docker + Docker Compose | any recent |
| Python | 3.12+ |

---

## Step 1 — Clone and configure

```bash
git clone https://github.com/beejak/agentwatch.git
cd agentwatch
cp .env.example .env
```

Default `.env` works for local dev. Edit only if you need non-default ports.

---

## Step 2 — Start infrastructure

```bash
docker compose up -d redis clickhouse postgres neo4j
```

Wait ~10s for ClickHouse to initialize, then verify:

```bash
make infra-status
```

```
NAME          STATUS    PORTS
clickhouse    running   0.0.0.0:8123->8123/tcp
neo4j         running   0.0.0.0:7687->7687/tcp
postgres      running   0.0.0.0:5432->5432/tcp
redis         running   0.0.0.0:6379->6379/tcp
```

---

## Step 3 — Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

---

## Step 4 — Run gate tests

All 16 layers, sequential:

```bash
make gate-all
```

```
==> Running tests/gates/gate_01_discovery.py  ....  passed
==> Running tests/gates/gate_02_access_graph.py  ...  passed
...
==> Running tests/gates/gate_16_telemetry.py  ........  passed
All gates passed.
```

Run a specific layer:

```bash
make gate-07   # Memory Integrity Monitor
make gate-09   # Verdict Engine
make gate-12   # Analyst (SC1/SC2/SC3)
```

---

## Step 5 — Run proof scenarios

```bash
make poc
```

Three scenarios that demonstrate what no existing tool can detect:

```
SC1  orchestrator + two workers → worker-b errors → MAST C2 attributed
SC2  150 identical ok spans → infinite_retry_loop → cost_anomaly_ratio=10.0
SC3  agent reports 1 network call → Sysmon shows 3 → delta=2 severity=high
```

---

## Step 6 — Start the API

```bash
make api
```

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`

---

## Step 7 — Try it

```bash
# Verify all infra is connected
curl http://localhost:8000/api/v1/health | jq

# All 19 MAST + infra topology signatures
curl http://localhost:8000/api/v1/analyst/topology-risks | jq '.[].name'

# Silent failures in last 24h
curl "http://localhost:8000/api/v1/analyst/silent-failures?hours=24" | jq
```

---

## Connecting your agents

Agents emit signals to Redis stream `wt:signals`. Each signal must be HMAC-signed.

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

For LangChain / LangGraph integration and production SDK usage, see [PRODUCTION_INTEGRATION.md](PRODUCTION_INTEGRATION.md).

---

## Makefile reference

```
make gate-NN        Run gate test for layer NN (01–16)
make gate-all       Run all gates in order, stop on first failure
make poc            Run SC1 + SC2 + SC3 proof scenarios
make test           Full test suite (207 tests)
make api            Start FastAPI server (port 8000)
make infra-status   docker compose ps
make progress       Show PROGRESS.md
```

---

## Next steps

| Goal | Doc |
|------|-----|
| Deploy to production | [PRODUCTION_INTEGRATION.md](PRODUCTION_INTEGRATION.md) |
| Tune detection thresholds | [CONFIGURATION.md](CONFIGURATION.md) |
| Understand attack scenarios | [SCENARIOS.md](SCENARIOS.md) |
| Full API reference | [API.md](API.md) |
| Threat model | [THREAT_MODEL.md](THREAT_MODEL.md) |
