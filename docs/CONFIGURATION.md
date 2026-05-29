# Configuration

## Environment variables

Copy `.env.example` to `.env` and edit as needed.

```bash
cp .env.example .env
```

### Infrastructure

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `CH_HOST` | `localhost` | ClickHouse HTTP host |
| `CH_PORT` | `8123` | ClickHouse HTTP port |
| `CH_DB` | `watchtower` | ClickHouse database name |
| `CH_USER` | `wt` | ClickHouse username |
| `CH_PASS` | `wt` | ClickHouse password |
| `PG_DSN` | `postgresql://wt:wt@localhost:5433/watchtower` | PostgreSQL DSN |
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

### Langfuse (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-local` | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | `sk-lf-local` | Langfuse project secret key |
| `LANGFUSE_HOST` | `http://localhost:3010` | Langfuse self-hosted URL |

### Anthropic (LLM Judge — optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required only for LLM Judge in Verdict Engine |

Without `ANTHROPIC_API_KEY`, the Verdict Engine still works — it exits at Stage 1 (deterministic) or Stage 2 (baseline) for most traces. Stage 3 (LLM Judge) is only sampled at 20%.

---

## Docker Compose ports

| Service | Host port | Container port |
|---------|-----------|----------------|
| Redis | 6379 | 6379 |
| ClickHouse | 8123 (HTTP), 9000 (native) | 8123, 9000 |
| PostgreSQL | 5433 | 5432 |
| Neo4j | 7687 (bolt), 7474 (browser) | 7687, 7474 |
| Langfuse | 3010 | 3000 |

PostgreSQL uses host port **5433** (not 5432) to avoid conflicts with local Postgres installations.

---

## Detection thresholds

These constants are in source and can be tuned for your environment:

### Silent failure (`watchtower/analyst/silent.py`)

```python
EXPECTED_COST_PER_SPAN = 0.000045   # $0.000045/span (~150 tokens @ $0.000003/token)
RETRY_REPEAT_THRESHOLD = 3          # min repeated summaries before flagging
MIN_SPANS_FOR_LOOP = 10             # min spans before loop detection activates
```

Token pricing varies by model. Calibrate `EXPECTED_COST_PER_SPAN` to your actual cost per LLM call.

### Behavioral baseline (`watchtower/baseline/engine.py`)

```python
SIGMA_THRESHOLD = 3.0               # Standard deviations for anomaly detection
BASELINE_MIN_TRACES = 50            # From WT_BASELINE_MIN_TRACES env var
```

Reduce `SIGMA_THRESHOLD` to 2.0 for tighter detection (more false positives). Increase to 4.0 for noisier environments.

### Verdict engine (`watchtower/verdict/engine.py`)

```python
llm_sample_rate = 0.2               # 20% of traces reach LLM Judge
```

Increase for more coverage at higher API cost. Set to `0.0` to disable LLM Judge entirely.

### Content inspection (`watchtower/content_inspection/inspector.py`)

12 patterns are compiled at startup from `patterns/injection_patterns.yaml`. Add patterns there without code changes.

---

## Chronicle retention

ClickHouse TTL is set to 90 days in `schema.sql`:

```sql
TTL toDate(timestamp) + INTERVAL 90 DAY
```

To change retention, modify the TTL in `schema.sql` and recreate the tables. **Note**: existing data is unaffected (TTL only applies to new partitions during merges).

---

## Production checklist

- [ ] Change `WT_HMAC_SECRET` to a random 32+ byte secret
- [ ] Change all database passwords from defaults
- [ ] Set `ANTHROPIC_API_KEY` if you want LLM Judge
- [ ] Configure `WT_BASELINE_MIN_TRACES` based on your agent traffic volume
- [ ] Tune `EXPECTED_COST_PER_SPAN` to your actual per-call cost
- [ ] Set up Sysmon (Windows) or Falco (Linux) on agent hosts for SC3 detection
- [ ] Point `WT_SIGNAL_QUEUE` to a production Redis with persistence enabled
- [ ] Configure ClickHouse with replication if running multi-node
