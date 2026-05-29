"""WatchTower FastAPI application."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI

from watchtower.api.routers import traces, analyst, interceptor

logger = logging.getLogger(__name__)

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

# Include routers
app.include_router(traces.router)
app.include_router(analyst.router)
app.include_router(interceptor.router)


@app.on_event("startup")
async def startup():
    global _reader, _analyst_manager
    import clickhouse_connect
    from watchtower.chronicle.reader import ChronicleReader
    from watchtower.chronicle.writer import ChronicleWriter
    from watchtower.analyst.manager import AnalystManager
    from watchtower.api.routers.interceptor import _interceptor
    ch = clickhouse_connect.get_client(
        host="localhost", port=8123,
        database="watchtower", username="wt", password="wt"
    )
    _reader = ChronicleReader(client=ch)
    _analyst_manager = AnalystManager()
    writer = ChronicleWriter(client=ch)
    await writer.start()
    _interceptor._chronicle = writer


@app.get("/api/v1/health")
async def health():
    """Check health of all infrastructure components."""
    statuses = {}

    # ClickHouse
    try:
        import clickhouse_connect
        client = clickhouse_connect.get_client(
            host="localhost", port=8123,
            database="watchtower", username="wt", password="wt"
        )
        client.query("SELECT 1")
        statuses["clickhouse"] = "ok"
        client.close()
    except Exception as e:
        statuses["clickhouse"] = f"error: {e}"

    # Redis
    try:
        import redis.asyncio as aioredis
        r = await aioredis.from_url("redis://localhost:6379", decode_responses=True)
        await r.ping()
        statuses["redis"] = "ok"
        await r.aclose()
    except Exception as e:
        statuses["redis"] = f"error: {e}"

    # Neo4j
    try:
        from neo4j import AsyncGraphDatabase
        driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "watchtower"))
        async with driver.session() as session:
            await session.run("RETURN 1")
        statuses["neo4j"] = "ok"
        await driver.close()
    except Exception as e:
        statuses["neo4j"] = f"error: {e}"

    # Postgres
    try:
        import asyncpg
        conn = await asyncpg.connect("postgresql://wt:wt@localhost:5433/watchtower")
        await conn.execute("SELECT 1")
        statuses["postgres"] = "ok"
        await conn.close()
    except Exception as e:
        statuses["postgres"] = f"error: {e}"

    overall = "ok" if all(v == "ok" for v in statuses.values()) else "degraded"

    return {
        "status": overall,
        **statuses,
    }
