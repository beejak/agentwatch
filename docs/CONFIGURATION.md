# Configuration

Copy `.env.example` to `.env` and edit as needed:

```bash
cp .env.example .env
```

---

## Environment variables

### Infrastructure

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `CH_HOST` | `localhost` | ClickHouse HTTP host |
| `CH_PORT` | `8123` | ClickHouse HTTP port |
| `CH_DB` | `watchtower` | ClickHouse database name |
| `CH_USER` | `wt` | ClickHouse username |
| `CH_PASS` | `wt` | ClickHouse password |
| `PG_DSN` | `postgresql://wt:wt@localhost:5432/watchtower` | PostgreSQL DSN |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j bolt URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASS` | `watchtower` | Neo4j password |

### AgentWatch

| Variable | Default | Description |
|----------|---------|-------------|
| `WT_SIGNAL_QUEUE` | `wt:signals` | Redis stream key for incoming signals |
| `WT_INTERCEPTOR_BUS` | `wt:interceptor` | Redis stream for interceptor events |
| `WT_MEMORY_CHANNEL` | `wt:memory_events` | Redis pub/sub channel for MIM events |
| `WT_HMAC_SECRET` | `watchtower-hmac-secret-change-in-prod` | HMAC secret — **change in production** |
| `WT_BASELINE_MIN_TRACES` | `50` | Traces before agent exits restricted mode |

### LLM Judge (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_KEY` | — | Required only for Verdict Engine Stage 3 (LLM Judge) |

> Without `LLM_API_KEY`, the Verdict Engine still works — it exits at Stage 1 (deterministic) or Stage 2 (baseline) for most traces. Stage 3 is sampled at only 20%.

### Langfuse (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-local` | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | `sk-lf-local` | Langfuse project secret key |
| `LANGFUSE_HOST` | `http://localhost:3010` | Langfuse self-hosted URL |

---

## Docker Compose ports

| Service | Host port | Notes |
|---------|-----------|-------|
| Redis | `6379` | — |
| ClickHouse | `8123` (HTTP) · `9000` (native) | — |
| PostgreSQL | `5432` | — |
| Neo4j | `7687` (bolt) · `7474` (browser) | — |
| Langfuse | `3010` | Maps to container port 3000 |

---

## Detection thresholds

All thresholds are tunable constants in source. Change them to match your agent's cost profile and traffic patterns.

### Silent failure — `watchtower/analyst/silent.py`

```python
EXPECTED_COST_PER_SPAN = 0.000045   # ~150 tokens at $0.000003/token
RETRY_REPEAT_THRESHOLD = 3          # repeated identical summaries before flagging
MIN_SPANS_FOR_LOOP = 10             # minimum spans before loop detection activates
```

> Calibrate `EXPECTED_COST_PER_SPAN` to your actual per-call cost. LLM model at default usage = ~$0.000045. GPT-4o = higher. Haiku = lower.

### Behavioral baseline — `watchtower/baseline/engine.py`

```python
SIGMA_THRESHOLD = 3.0               # standard deviations for anomaly detection
BASELINE_MIN_TRACES = 50            # from WT_BASELINE_MIN_TRACES env var
```

- Reduce to `2.0` for tighter detection (more FPs in noisy environments)
- Increase to `4.0` for high-variance agents

### Verdict engine — `watchtower/verdict/engine.py`

```python
llm_sample_rate = 0.2               # 20% of traces reach LLM Judge (Stage 3)
```

- Increase to `1.0` for maximum coverage (higher API cost)
- Set to `0.0` to disable LLM Judge entirely

### Verdict deterministic thresholds — `watchtower/verdict/sources/deterministic.py`

```python
COST_THRESHOLD = 0.10    # $0.10 per trace triggers deterministic verdict
MAX_SPANS = 50           # spans before flagging as excessive
```

### Content inspection

15 patterns compiled at startup from `watchtower/content_inspection/patterns/injection_patterns.yaml`. Add or modify patterns there — no code changes needed.

---

## Chronicle retention

ClickHouse TTL is set to 90 days:

```sql
TTL toDate(timestamp) + INTERVAL 90 DAY
```

To change: modify the TTL in `watchtower/chronicle/schema.sql` and recreate tables. Existing data is unaffected — TTL only applies during ClickHouse merge operations.

---

## Production checklist

```
[ ] Change WT_HMAC_SECRET to a random 32+ byte secret
    openssl rand -hex 32

[ ] Change all database passwords from defaults

[ ] Set LLM_API_KEY if you want LLM Judge (Stage 3)

[ ] Tune EXPECTED_COST_PER_SPAN to your actual per-call cost

[ ] Tune WT_BASELINE_MIN_TRACES to your agent traffic volume
    (higher traffic = lower value needed to establish baseline faster)

[ ] Set up Sysmon (Windows) or Falco (Linux) on agent hosts for SC3

[ ] Point WT_SIGNAL_QUEUE to a production Redis with AOF persistence

[ ] Configure ClickHouse with replication if running multi-node

[ ] Set WT_ENFORCEMENT_MODE (shadow → soft → enforce)
    See PRODUCTION_INTEGRATION.md Phase 8
```
