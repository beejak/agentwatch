"""
Runtime configuration (12-factor). All backing-service connection details come from
environment variables so the platform can point at any infrastructure without code
changes. Defaults match docker-compose.yml for zero-config local dev.

Env vars:
  CH_HOST CH_PORT CH_DB CH_USER CH_PASS   — ClickHouse (Chronicle)
  REDIS_URL                                — Redis (signal stream / bus)
  PG_DSN                                   — PostgreSQL (baseline / policy)
  NEO4J_URI NEO4J_USER NEO4J_PASS          — Neo4j (access graph)
  WT_HMAC_SECRET                           — signal HMAC key
"""
from __future__ import annotations

import os

# ── ClickHouse (Chronicle) ───────────────────────────────────────────────────
CH_HOST = os.getenv("CH_HOST", "localhost")
CH_PORT = int(os.getenv("CH_PORT", "8123"))
CH_DB = os.getenv("CH_DB", "watchtower")
CH_USER = os.getenv("CH_USER", "wt")
CH_PASS = os.getenv("CH_PASS", "wt")

# ── Redis (signal stream + interceptor bus + memory events) ──────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ── PostgreSQL (behavioral baseline + policy store) ──────────────────────────
PG_DSN = os.getenv("PG_DSN", "postgresql://wt:wt@localhost:5433/watchtower")

# ── Neo4j (access graph / blast radius) ──────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "watchtower")

# ── Integrity ────────────────────────────────────────────────────────────────
HMAC_SECRET = os.getenv("WT_HMAC_SECRET", "watchtower-hmac-secret-change-in-prod")


def clickhouse_client():
    """A ClickHouse client wired from env config."""
    import clickhouse_connect
    return clickhouse_connect.get_client(
        host=CH_HOST, port=CH_PORT, database=CH_DB, username=CH_USER, password=CH_PASS
    )
