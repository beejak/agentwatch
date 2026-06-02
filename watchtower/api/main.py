"""WatchTower FastAPI application."""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from watchtower.api.routers import traces, analyst, interceptor

logger = logging.getLogger(__name__)

_CH_HOST = os.getenv("CH_HOST", "localhost")
_CH_PORT = int(os.getenv("CH_PORT", "8123"))
_CH_DB   = os.getenv("CH_DB", "watchtower")
_CH_USER = os.getenv("CH_USER", "wt")
_CH_PASS = os.getenv("CH_PASS", "wt")

_PG_DSN  = os.getenv("PG_DSN", "postgresql://wt:wt@localhost:5432/watchtower")
_REDIS   = os.getenv("REDIS_URL", "redis://localhost:6379")
_NEO4J   = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
_NEO4J_PASS = os.getenv("NEO4J_PASS", "watchtower")

# Global singletons (injected at startup or test time)
_reader = None
_analyst_manager = None


def get_reader():
    return _reader


def get_analyst():
    return _analyst_manager


def set_reader(reader):
    global _reader
    _reader = reader


def set_analyst(analyst_manager):
    global _analyst_manager
    _analyst_manager = analyst_manager


app = FastAPI(
    title="WatchTower Agent Observability",
    version="0.1.0",
    description="Multi-layer agent observability and security platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "").split(",") or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(traces.router)
app.include_router(analyst.router)
app.include_router(interceptor.router)


@app.on_event("startup")
async def startup():
    global _reader, _analyst_manager
    try:
        import clickhouse_connect
        from watchtower.chronicle.reader import ChronicleReader
        from watchtower.chronicle.writer import ChronicleWriter
        from watchtower.analyst.manager import AnalystManager
        from watchtower.api.routers.interceptor import _interceptor
        ch = clickhouse_connect.get_client(
            host=_CH_HOST, port=_CH_PORT,
            database=_CH_DB, username=_CH_USER, password=_CH_PASS,
        )
        _reader = ChronicleReader(client=ch)
        _analyst_manager = AnalystManager()
        writer = ChronicleWriter(client=ch)
        await writer.start()
        _interceptor._chronicle = writer
    except Exception as e:
        logger.warning("Startup: ClickHouse unavailable — running in degraded mode: %s", e)
        from watchtower.analyst.manager import AnalystManager
        _analyst_manager = AnalystManager()


@app.get("/api/v1/health")
async def health():
    """Check health of all infrastructure components."""
    statuses: dict[str, str] = {}

    # ClickHouse — reuse shared client config
    try:
        import clickhouse_connect
        client = clickhouse_connect.get_client(
            host=_CH_HOST, port=_CH_PORT,
            database=_CH_DB, username=_CH_USER, password=_CH_PASS,
        )
        client.query("SELECT 1")
        statuses["clickhouse"] = "ok"
        client.close()
    except Exception as e:
        statuses["clickhouse"] = f"error: {e}"

    # Redis
    try:
        import redis.asyncio as aioredis
        r = await aioredis.from_url(_REDIS, decode_responses=True)
        await r.ping()
        statuses["redis"] = "ok"
        await r.aclose()
    except Exception as e:
        statuses["redis"] = f"error: {e}"

    # Neo4j
    try:
        from neo4j import AsyncGraphDatabase
        driver = AsyncGraphDatabase.driver(_NEO4J, auth=(_NEO4J_USER, _NEO4J_PASS))
        async with driver.session() as session:
            await session.run("RETURN 1")
        statuses["neo4j"] = "ok"
        await driver.close()
    except Exception as e:
        statuses["neo4j"] = f"error: {e}"

    # Postgres
    try:
        import asyncpg
        conn = await asyncpg.connect(_PG_DSN)
        await conn.execute("SELECT 1")
        statuses["postgres"] = "ok"
        await conn.close()
    except Exception as e:
        statuses["postgres"] = f"error: {e}"

    overall = "ok" if all(v == "ok" for v in statuses.values()) else "degraded"
    return {"status": overall, **statuses}
