-- WatchTower Chronicle Schema
-- Append-only ClickHouse tables. NO UPDATE. NO DELETE.
-- All tables use MergeTree engine with 90-day TTL.

CREATE DATABASE IF NOT EXISTS watchtower;

-- ── agent_spans ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchtower.agent_spans
(
    trace_id        String,
    span_id         String,
    parent_span_id  Nullable(String),
    agent_id        String,
    action          String,
    status          String,
    timestamp       DateTime64(3, 'UTC'),
    duration_ms     Float64,
    tokens_in       Int32,
    tokens_out      Int32,
    model           Nullable(String),
    cost            Float64,
    instruction_hash Nullable(String),
    caller_agent_id Nullable(String),
    process_guid    Nullable(String),
    retrieval_flag  UInt8,
    memory_op       Nullable(String),
    framework_fault UInt8,
    policy_checked  UInt8,
    summary         String
)
ENGINE = MergeTree()
PARTITION BY toDate(timestamp)
ORDER BY (timestamp, trace_id, span_id)
TTL toDate(timestamp) + INTERVAL 90 DAY;

-- ── host_telemetry ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchtower.host_telemetry
(
    trace_id    String,
    agent_id    String,
    timestamp   DateTime64(3, 'UTC'),
    event_type  String,
    process_guid Nullable(String),
    details     String
)
ENGINE = MergeTree()
PARTITION BY toDate(timestamp)
ORDER BY (timestamp, trace_id)
TTL toDate(timestamp) + INTERVAL 90 DAY;

-- ── memory_events ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchtower.memory_events
(
    trace_id        String,
    agent_id        String,
    timestamp       DateTime64(3, 'UTC'),
    operation       String,
    content_hash    String,
    flagged         UInt8,
    pattern         Nullable(String),
    severity        String,
    session_id      String,
    details         String
)
ENGINE = MergeTree()
PARTITION BY toDate(timestamp)
ORDER BY (timestamp, agent_id)
TTL toDate(timestamp) + INTERVAL 90 DAY;

-- ── content_results ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchtower.content_results
(
    trace_id        String,
    agent_id        String,
    timestamp       DateTime64(3, 'UTC'),
    content_hash    String,
    flagged         UInt8,
    confidence      Float64,
    pattern_matched Nullable(String),
    severity        String,
    action          String,
    details         String
)
ENGINE = MergeTree()
PARTITION BY toDate(timestamp)
ORDER BY (timestamp, agent_id)
TTL toDate(timestamp) + INTERVAL 90 DAY;

-- ── policy_decisions ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchtower.policy_decisions
(
    trace_id    String,
    agent_id    String,
    timestamp   DateTime64(3, 'UTC'),
    action      String,
    permitted   UInt8,
    reason      String,
    details     String
)
ENGINE = MergeTree()
PARTITION BY toDate(timestamp)
ORDER BY (timestamp, agent_id)
TTL toDate(timestamp) + INTERVAL 90 DAY;

-- ── verdicts ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchtower.verdicts
(
    trace_id    String,
    agent_id    String,
    timestamp   DateTime64(3, 'UTC'),
    verdict     String,
    confidence  Float64,
    sources     String,
    reason      String,
    details     String
)
ENGINE = MergeTree()
PARTITION BY toDate(timestamp)
ORDER BY (timestamp, agent_id, trace_id)
TTL toDate(timestamp) + INTERVAL 90 DAY;

-- ── interceptor_acts ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchtower.interceptor_acts
(
    trace_id    String,
    agent_id    String,
    timestamp   DateTime64(3, 'UTC'),
    action      String,
    reason      String,
    details     String
)
ENGINE = MergeTree()
PARTITION BY toDate(timestamp)
ORDER BY (timestamp, agent_id)
TTL toDate(timestamp) + INTERVAL 90 DAY;

-- ── discovery_events ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchtower.discovery_events
(
    trace_id    String,
    agent_id    String,
    timestamp   DateTime64(3, 'UTC'),
    flagged     UInt8,
    namespace   Nullable(String),
    details     String
)
ENGINE = MergeTree()
PARTITION BY toDate(timestamp)
ORDER BY (timestamp, agent_id)
TTL toDate(timestamp) + INTERVAL 90 DAY;
