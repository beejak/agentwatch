# API Reference

- **Base URL:** `http://localhost:8000`
- **Interactive docs:** `http://localhost:8000/docs` (Swagger UI)
- **All responses:** JSON

---

## Endpoints at a glance

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Infra connectivity check |
| `GET` | `/api/v1/traces/{trace_id}` | Reconstruct trace from Chronicle |
| `GET` | `/api/v1/agents/{agent_id}/verdicts` | Agent verdict history |
| `GET` | `/api/v1/analyst/report/{trace_id}` | SC1 + SC2 + SC3 analysis |
| `GET` | `/api/v1/analyst/silent-failures` | Recent silent failure traces |
| `GET` | `/api/v1/analyst/topology-risks` | MAST + infra signatures |
| `POST` | `/api/v1/interceptor/quarantine` | Quarantine an agent |

---

## Health

### `GET /api/v1/health`

Check connectivity to all infrastructure components.

```bash
curl http://localhost:8000/api/v1/health
```

```json
{
  "status": "ok",
  "clickhouse": "ok",
  "redis": "ok",
  "neo4j": "ok",
  "postgres": "ok"
}
```

`status` is `"ok"` only when **all** components respond. Otherwise `"degraded"`.

---

## Traces

### `GET /api/v1/traces/{trace_id}`

Reconstruct a full trace from Chronicle (ClickHouse).

```bash
curl http://localhost:8000/api/v1/traces/b7aedc09-ae5f-4fd8-a5db-61f74f1902d8
```

```json
{
  "trace_id": "b7aedc09-ae5f-4fd8-a5db-61f74f1902d8",
  "span_count": 150,
  "spans": [
    {
      "trace_id": "b7aedc09...",
      "span_id": "3f2a...",
      "agent_id": "looping-agent",
      "action": "llm_call",
      "status": "ok",
      "summary": "retry attempt: same output repeated",
      "cost": 0.00045,
      "timestamp": 1780025755.818
    }
  ]
}
```

---

### `GET /api/v1/agents/{agent_id}/verdicts`

Get verdict history for an agent.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max records to return |

```bash
curl "http://localhost:8000/api/v1/agents/looping-agent/verdicts?limit=10"
```

```json
[
  {
    "trace_id": "b7aedc09-...",
    "agent_id": "looping-agent",
    "verdict": "bad",
    "timestamp": 1780025925.125,
    "details": "{'confidence': 0.95, 'source': 'deterministic'}"
  }
]
```

---

## Analyst

### `GET /api/v1/analyst/report/{trace_id}`

Run full **SC1 + SC2 + SC3** analysis on a trace.

```bash
curl http://localhost:8000/api/v1/analyst/report/b7aedc09-ae5f-4fd8-a5db-61f74f1902d8
```

```json
{
  "trace_id": "b7aedc09-...",
  "markdown_report": "# AgentWatch Analyst Report\n...",
  "sc1_result": {
    "failing_agent": "worker-b",
    "failing_action": "llm_call",
    "call_tree_depth": 2,
    "mast_category": 2,
    "signature_name": "Conflicting Parallel Outputs",
    "fix_direction": "Add consensus/merge step; define conflict resolution strategy",
    "confidence": 0.85
  },
  "sc2_result": {
    "pattern": "infinite_retry_loop",
    "evidence": "150 spans, summary repeated 150 times, no errors (silent)",
    "cost_anomaly_ratio": 10.0,
    "detected": true
  },
  "sc3_result": {
    "agent_reported_calls": 1,
    "host_observed_calls": 3,
    "delta": 2,
    "severity": "high",
    "evidence": "Agent reported 1 network call; Sysmon shows 3 for process_guid abc123"
  }
}
```

**SC1 fields:**

| Field | Type | Description |
|-------|------|-------------|
| `failing_agent` | string | Agent ID with the error span |
| `failing_action` | string | Action type that failed |
| `call_tree_depth` | int | Depth in call tree where failure occurred |
| `mast_category` | int | `1`=Specification · `2`=Inter-agent · `3`=Verification |
| `signature_name` | string | Matched MAST signature |
| `fix_direction` | string | Prescriptive remediation |
| `confidence` | float | 0.0–1.0 match confidence |

**SC2 fields:**

| Field | Type | Description |
|-------|------|-------------|
| `pattern` | string | `infinite_retry_loop` · `token_burn` · `entropy_collapse` · `none` |
| `evidence` | string | Human-readable evidence summary |
| `cost_anomaly_ratio` | float | `actual_cost / expected_cost` — >10.0 is critical |
| `detected` | bool | Whether a silent failure pattern was found |

**SC3 fields:**

| Field | Type | Description |
|-------|------|-------------|
| `agent_reported_calls` | int | Network calls in agent's span |
| `host_observed_calls` | int | Connections from Sysmon for same `process_guid` |
| `delta` | int | `host_observed − agent_reported` |
| `severity` | string | `none` · `low` · `medium` · `high` · `critical` |

---

### `GET /api/v1/analyst/silent-failures`

Find traces where all spans are `status=ok` but span count indicates an infinite retry loop.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `hours` | int | 24 | Lookback window |

```bash
curl "http://localhost:8000/api/v1/analyst/silent-failures?hours=1"
```

```json
[
  {
    "trace_id": "b7aedc09-ae5f-4fd8-a5db-61f74f1902d8",
    "agent_id": "looping-agent",
    "status": "ok x150 (silent loop)",
    "summary": "retry attempt: same output repeated",
    "timestamp": 1780025755.818
  }
]
```

---

### `GET /api/v1/analyst/topology-risks`

Return all loaded coordination signatures — 14 MAST failure modes plus 5 infrastructure patterns.

```bash
# All signatures
curl http://localhost:8000/api/v1/analyst/topology-risks | jq

# Filter to critical only
curl http://localhost:8000/api/v1/analyst/topology-risks \
  | jq '[.[] | select(.risk_level == "critical")]'
```

```json
[
  {
    "signature_id": "mast_c1_missing_termination",
    "name": "Missing Termination Condition",
    "risk_level": "critical",
    "description": "No clear stopping condition; agent loops indefinitely"
  },
  {
    "signature_id": "mast_c2_conflicting_parallel_outputs",
    "name": "Conflicting Parallel Outputs",
    "risk_level": "critical",
    "description": "Parallel worker agents produce mutually exclusive outputs"
  },
  {
    "signature_id": "infra_infinite_retry_loop",
    "name": "Infinite Retry Loop",
    "risk_level": "critical",
    "description": "Agent in retry loop — HTTP 200, no errors, expensive"
  }
]
```

---

## Interceptor

### `POST /api/v1/interceptor/quarantine`

Quarantine an agent. Queries Access Graph for blast radius, quarantines all downstream agents, and logs the action to Chronicle — **permanently**.

```bash
curl -X POST http://localhost:8000/api/v1/interceptor/quarantine \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "worker-b",
    "reason": "MAST C2: conflicting parallel outputs detected",
    "trigger": "analyst"
  }'
```

```json
{
  "action_id": "f4ef6505-0e4d-4fef-abbb-0d911afefe08",
  "target_agent": "worker-b",
  "blast_radius": ["downstream-agent-1", "downstream-agent-2"],
  "reason": "MAST C2: conflicting parallel outputs detected",
  "logged": true
}
```

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | string | **yes** | Agent to quarantine |
| `reason` | string | **yes** | Human-readable reason — logged to Chronicle |
| `trigger` | string | no | Source: `analyst` · `mim` · `policy_engine` · `api` (default: `api`) |

> **`logged: true` is guaranteed.** The Chronicle write completes before the response returns.  
> If Chronicle is unavailable, the action is still applied in-memory and the error is reported separately.

---

## Error responses

Standard FastAPI validation errors on bad input:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "agent_id"],
      "msg": "Field required"
    }
  ]
}
```

---

## Signals ingestion

Agents emit signals directly to Redis stream `wt:signals`. See [QUICKSTART.md](QUICKSTART.md) for the HMAC-signed signal format and [PRODUCTION_INTEGRATION.md](PRODUCTION_INTEGRATION.md) for the full instrumentation guide.
